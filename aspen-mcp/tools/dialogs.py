"""Aspen's own dialogs, kept from blocking the server's COM calls.

A COM call that makes Aspen ask something waits for the answer. On a visible session Aspen
shows a modal WPF dialog and the call -- the tool with it -- hangs until someone clicks it
(seen on V15): "Update Parameters" (Yes / No) when add_component changes a model whose
binary parameters are on a form, "Design-Spec(s) ... have been hidden or deleted" when a
Design-Spec is removed, Reinitialize's confirmation. With the document's ``SuppressDialogs``
on, Aspen takes the dialog's default answer and the call returns; add_component then leaves
the same model a click on Yes does.

``suppressed(app)`` turns it on around a block and puts back what was there, so a person
working in Aspen's own window still gets their questions between calls (a hidden session
reads 1 anyway: V15 has dialogs off until a document is shown). ``quiet`` does the
same around a whole tool whose first two arguments are (manager, session_name) -- a manager
method included (self is the manager). Value writes are left alone: none raised a dialog
live, and they are the hot path. A scope is one property read and two writes (0.3-1 ms live);
``quiet`` adds the session's liveness check (``manager.get_app``).

Stdlib only; no COM of its own beyond that property.
"""
from __future__ import annotations

import contextlib
import functools
import logging

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def suppressed(app):
    """Aspen's dialogs off (``app.SuppressDialogs = 1``) inside the block, the value it had
    put back after it, exception or not. ``app`` None: nothing is done. Never raises for the
    property itself -- a dead document is the tool's to report."""
    if app is None:
        yield
        return
    try:
        old = app.SuppressDialogs
    except Exception:
        old = 0
    try:
        app.SuppressDialogs = 1
    except Exception:
        logger.debug("SuppressDialogs could not be set", exc_info=True)
    try:
        yield
    finally:
        try:
            app.SuppressDialogs = old
        except Exception:
            logger.debug("SuppressDialogs could not be put back", exc_info=True)


def quiet(fn):
    """Decorator: ``fn(manager, session_name, ...)`` runs with that session's dialogs
    suppressed. An unknown or dead session suppresses nothing; ``fn`` answers as it did."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        manager = args[0] if args else kwargs.get("manager")
        session = args[1] if len(args) > 1 else kwargs.get("session_name")
        try:
            app = manager.get_app(session) if session is not None else None
        except Exception:
            app = None
        with suppressed(app):
            return fn(*args, **kwargs)
    return wrapper
