"""Tree lookups for the value hot paths, the Tree kept per session.

    node = nodes.find(session, app, path)    # the node at `path` now, or None
    nodes.forget(session)                    # the session's Aspen was opened, reopened or closed

``app.Tree.FindNode(p)`` costs ~1.3 ms on V15, and most of it is win32com, not Aspen: each
``app.Tree`` is a fresh wrapper, and ``FindNode`` is bound on it through its type info. ``find``
keeps each session's Tree and calls FindNode on it by DISPID (tools/dispid.py), handing back
the node without win32com's wrapper: ~0.27 ms, and still a lookup by path. Live V15, 300 calls
each: a value read (FindNode, Value, UnitString) 1.50 -> 0.40 ms, a value write 1.93 -> 0.78 ms.

Only the Tree is kept, never a node. Measurement found a kept node wrong with
no error to notice it by:
- a node's value is refreshed when FindNode hands the node out (it hands out the same object
  for a path each time): a block result read through a kept node after a run is the result of
  the run before, and stays so -- polled for 500 ms -- until FindNode is called for that path;
- a node in an indexed table follows the row's position, not its name: after a component was
  added or removed, the node of FLOW\\MIXED\\ACETONE read -- and a write through it changed --
  METHANOL's flow;
- the nodes of a removed block or stream raise RPC_E_DISCONNECTED, as everything does after
  Close.
A lookup by path is right in all three. The Tree itself stayed the same COM object through runs,
Reinit, blocks and components added and removed, and FindNode through it agreed with a fresh
``app.Tree.FindNode`` every time.

A kept Tree belongs to one app and is dropped when the manager opens, reopens or closes the
session, when the session's app is another object than the one it came from, and after any
error through it -- the lookup is then made once more on a fresh ``app.Tree``, whose error, if
any, is the caller's. The app itself is never held. ``ASPEN_MCP_NODE_CACHE=0``:
``app.Tree.FindNode`` on every call, as before. Stdlib only; no I/O or COM at import.
"""
from __future__ import annotations

import logging
import os
import sys
import weakref

from tools import dispid

logger = logging.getLogger(__name__)

_KEPT: dict = {}           # session -> [weak reference to the app (or its id), its Tree, FindNode late]
STATS = {"kept": 0, "fetched": 0, "retried": 0, "forgot": 0}


def enabled() -> bool:
    """The switch, read on every call (ASPEN_MCP_NODE_CACHE=0 turns the kept Tree off)."""
    return os.environ.get("ASPEN_MCP_NODE_CACHE", "1") != "0"


class Node:
    """A node FindNode returned by DISPID: a bare PyIDispatch that tools/dispid.py calls directly
    (``_oleobj_``); any other member goes through win32com's wrapper, made on first use."""
    __slots__ = ("_oleobj_", "_wrapped")

    def __init__(self, ole):
        self._oleobj_ = ole
        self._wrapped = None

    def __getattr__(self, name):
        w = self._wrapped
        if w is None:
            w = self._wrapped = sys.modules["win32com.client.dynamic"].Dispatch(self._oleobj_)
        return getattr(w, name)


def _ref(app):
    try:
        return weakref.ref(app)
    except TypeError:
        return id(app)


def _owns(ref, app) -> bool:
    return (ref() is app) if isinstance(ref, weakref.ref) else ref == id(app)


def _tree(session, app):
    """(the kept entry [app reference, Tree, FindNode not by DISPID], whether it was kept from
    an earlier call)."""
    hit = _KEPT.get(session)
    if hit is not None and _owns(hit[0], app):
        STATS["kept"] += 1
        return hit, True
    hit = _KEPT[session] = [_ref(app), app.Tree, False]
    STATS["fetched"] += 1
    return hit, False


def _lookup(hit, path):
    tree = hit[1]
    r = dispid.LATE if hit[2] else dispid.raw(tree, "FindNode", path)
    if r is dispid.LATE:                      # not by DISPID (not a real COM node): win32com's own call
        hit[2] = True
        return tree.FindNode(path)
    if r is None or hasattr(r, "_oleobj_"):   # nothing at that path; or a wrapper already
        return r
    return Node(r)


def find(session, app, path):
    """``app.Tree.FindNode(path)`` through the session's kept Tree: the node at ``path`` now,
    or None. An error through a kept Tree drops it and the lookup is made once more on a fresh
    ``app.Tree``; that one's error is raised."""
    if not enabled() or session is None:
        return app.Tree.FindNode(path)
    hit, kept = _tree(session, app)
    try:
        return _lookup(hit, path)
    except Exception as exc:
        forget(session)
        if not kept:
            raise
        STATS["retried"] += 1
        logger.info("nodes: the kept Tree of %s failed (%r); looking up %s again", session, exc, path)
        hit, _ = _tree(session, app)
        try:
            return _lookup(hit, path)
        except Exception:
            forget(session)
            raise


def forget(session=None) -> None:
    """Drop the kept Tree of ``session`` (None: of every session) -- its Aspen was opened,
    reopened or closed, or a call through it failed."""
    if session is None:
        n = len(_KEPT)
        _KEPT.clear()
    else:
        n = 0 if _KEPT.pop(session, None) is None else 1
    STATS["forgot"] += n
