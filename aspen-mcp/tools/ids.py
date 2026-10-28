"""Block and stream IDs as Aspen's input file keeps them (docs/setup/setup.md, IDs).

An ID takes at most 8 characters: letters, digits and - (Aspen also takes + # $). Aspen refuses
a block ID that breaks this, with a hint that blames the block type; a stream ID it takes and
cuts later: at a _ the run does not start, past 8 characters the stream gets no results, and
two IDs that cut to the same text break the flowsheet. So a new block or stream is checked
before Aspen is asked, and the refusal names an ID that fits.

    problem(name)                    why ``name`` is no such ID ("11 characters and '_'"), else None
    suggest(name, taken, fallback)   an ID that fits, made from ``name``'s words, not in ``taken``
    refusal(what, name, taken, ...)  the tools' "Not applied: ..." answer, else None

Stdlib only; no I/O.
"""
from __future__ import annotations

import re

MAX = 8
OK = re.compile(r"[A-Za-z0-9#$+-]+")         # _ . @ % ~ rejected (NXTITM.1, BLDITM.9)
_WORD = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|[0-9]+")    # REACTOR_OUT, reactorOut, Feed2
_SHOWN = 4                                    # bad characters named at most


def problem(name) -> str | None:
    """Why ``name`` is no ID Aspen keeps as it is: its length past 8 and the characters it does
    not take, as a phrase. None when it fits, and for an empty name (the callers' own check)."""
    s = str(name or "").strip()
    if not s:
        return None
    why = [f"{len(s)} characters"] if len(s) > MAX else []
    bad = list(dict.fromkeys(c for c in s if not OK.fullmatch(c)))
    if bad:
        why.append(", ".join("a space" if c == " " else f"'{c}'" for c in bad[:_SHOWN])
                   + (" ..." if len(bad) > _SHOWN else ""))
    return " and ".join(why) or None


def suggest(name, taken=(), fallback: str = "S") -> str:
    """An ID that fits, from ``name``: its words (split at other characters and at a lower-to-
    upper case change) shortened in turn to fill 8 characters, a trailing number kept
    (REACTOR_OUT -> REACTOUT, reactor_out_2 -> REACOUT2, Distillate -> DISTILLA); ``fallback``
    and a number when no letter or digit is left. Not one of ``taken`` (ignoring case): a number
    replaces its end."""
    taken = {str(t).upper() for t in taken or ()}
    words = [w.upper() for w in _WORD.findall(str(name or ""))]
    tail = words.pop()[-3:] if len(words) > 1 and words[-1].isdigit() else ""
    room, take = MAX - len(tail), [0] * len(words)
    while room > 0 and any(t < len(w) for t, w in zip(take, words)):
        for i, w in enumerate(words):
            if room and take[i] < len(w):
                take[i] += 1
                room -= 1
    base = "".join(w[:t] for w, t in zip(words, take)) + tail
    if base and base not in taken:
        return base
    stem = base or fallback
    for i in range(1 if base == "" else 2, 10 ** (MAX - 1)):
        cand = stem[:MAX - len(str(i))] + str(i)
        if cand not in taken:
            return cand
    return stem[:MAX]


def refusal(what: str, name, taken=(), fallback: str = "S") -> str | None:
    """The answer a tool gives instead of placing ``name``: ``what`` 'Block' / 'Stream'. None
    when ``name`` fits. Starts "Not applied", which the server instructions say changed nothing."""
    why = problem(name)
    if why is None:
        return None
    name = str(name).strip()
    return (f"Not applied: {what.lower()} '{name}' not placed -- it has {why}, and an ID takes at most "
            f"{MAX} characters: letters, digits and -. Aspen refuses a longer or other one, or cuts it and "
            f"loses its results. Use '{suggest(name, taken, fallback)}' or another ID that fits, and the "
            f"same ID wherever later steps name it.")
