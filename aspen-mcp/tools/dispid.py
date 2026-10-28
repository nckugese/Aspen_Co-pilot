"""Members of Aspen's tree nodes by cached DISPID: one IDispatch::Invoke per access.

    dispid.get(node, "Value")                   node.Value
    dispid.get(node, "AttributeValue", 7)       node.AttributeValue(7)
    dispid.put(node, "Value", v)                node.Value = v
    dispid.put(node, "AttributeValue", n, False, v)   AttributeValue(n, force) = v
    dispid.call(node, "SetValueAndUnit", v, col, False)

win32com's attribute access on a node FindNode just returned binds the name through the
node's type info first -- several cross-process round trips per name per node, plus a
compiled Python method for a member with arguments (measured on Aspen V15: AttributeValue(7) 0.44 ms
late vs 0.06 by DISPID, a Value write 0.47 vs 0.16). IHNode is a dual interface, so a
member's DISPID is the same on every node: resolved once, then the same Invoke win32com
itself makes (Value / UnitString / AttributeValue get, Value put, the Set... methods).

When the call does not go through -- no raw Invoke (an object that is not a real COM node), a DISPID or arguments
IDispatch refuses (DISP_E_* other than DISP_E_EXCEPTION), a value Python cannot pass -- it is
made again through win32com's own access, so the result is what that access gives. An error
from the member itself (DISP_E_EXCEPTION, any other HRESULT) is raised as is: win32com's call
is the same Invoke and would raise it too, and repeating a write Aspen ran could run it twice.
Stdlib only.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

GET, GET_ARGS, PUT, METHOD = 2, 3, 4, 1   # DISPATCH_: PROPERTYGET, | METHOD, PROPERTYPUT, METHOD
_RAISED = -2147352567                   # DISP_E_EXCEPTION: the member ran and raised
_REFUSED = range(-2147352575, -2147352556)   # DISP_E_*: IDispatch refused the call itself
_BAD_MEMBER = (-2147352573, -2147352570)     # DISP_E_MEMBERNOTFOUND, DISP_E_UNKNOWNNAME
_PLAIN = frozenset((str, float, int, bool, type(None)))
_IDS: dict = {}                         # member name -> DISPID
_LATE = object()                        # "make the call through win32com instead"


def _hr(exc):
    hr = getattr(exc, "hresult", None)
    return hr if hr is not None else (exc.args[0] if getattr(exc, "args", None) else None)


def _fast(node, name, flags, args):
    """The Invoke's result, or _LATE when it did not go through."""
    try:
        ole = node._oleobj_
        d = _IDS.get(name)
        if d is None:
            d = ole.GetIDsOfNames(name)
            d = _IDS[name] = d[0] if isinstance(d, (tuple, list)) else d
        return ole.Invoke(d, 0, flags, flags != PUT, *args)
    except (AttributeError, TypeError) as exc:
        logger.debug("dispid: %s on %s not by DISPID (%r)", name, type(node).__name__, exc)
    except Exception as exc:
        hr = _hr(exc)
        if not isinstance(hr, int) or hr not in _REFUSED or hr == _RAISED:
            raise
        if hr in _BAD_MEMBER:
            _IDS.pop(name, None)
        logger.debug("dispid: %s refused by DISPID (%r)", name, exc)
    return _LATE


LATE = _LATE


def raw(node, name, *args):
    """The Invoke's result as it comes back -- a COM object as a bare PyIDispatch, without
    win32com's wrapper -- or LATE when the call did not go through by DISPID (make it through
    win32com then). tools/nodes.py's FindNode."""
    return _fast(node, name, GET_ARGS if args else GET, args)


def get(node, name, *args):
    """``node.<name>``, or ``node.<name>(*args)`` for a member with arguments. A result that
    is not a plain value (a COM object, an array) is read again through win32com, which
    wraps it."""
    r = _fast(node, name, GET_ARGS if args else GET, args)
    if r is _LATE or type(r) not in _PLAIN:
        r = getattr(node, name)
        r = r(*args) if args else r
    return r


def put(node, name, *args) -> None:
    """``node.<name> = args[-1]``; ``args[:-1]`` are the member's own arguments
    (``AttributeValue(n, force) = v``), which win32com has no attribute syntax for: that
    one's fallback is the same Invoke with the DISPID looked up afresh."""
    if _fast(node, name, PUT, args) is _LATE:
        if len(args) == 1:
            setattr(node, name, args[0])
        else:
            ole = node._oleobj_
            d = ole.GetIDsOfNames(name)
            ole.Invoke(d[0] if isinstance(d, (tuple, list)) else d, 0, PUT, False, *args)


def call(node, name, *args) -> None:
    """``node.<name>(*args)``, a method called for its effect (its result is dropped)."""
    if _fast(node, name, METHOD, args) is _LATE:
        getattr(node, name)(*args)
