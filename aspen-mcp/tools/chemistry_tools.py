"""Create electrolyte Chemistry objects by patching the .bkp text.

The COM node tree rejects incremental writes to a Chemistry object's reaction
table: rows inserted via insert_row/set_value are silently rolled back unless
the whole reaction arrives atomically (see
docs/properties/properties-chemistry.md). This module bypasses COM entirely --
save the session to .bkp (plain Aspen input language), splice a CHEMISTRY
paragraph into the text, and reopen. Atomicity is delegated to Aspen's own
input parser: the paragraph either loads whole or fails loudly at open.

Grammar: the CHEMISTRY paragraph as a saved .bkp carries it in clear text (the numbers
below are illustrative):

    ? CHEMISTRY "NAME" ? ; "SET1_MOLE" ; \\
    STOIC REACNO = 1 STOIC-CID = H2O COEF = -2.0 <0> <0> / ... \\ \\
    STOIC1 REACNO1 = 1 STOIC-CID1 = "H3O+" COEF1 = 1.0 <0> <0> / ... \\ \\
    K-STOIC K-S-REACNO = 1 A = 100.0 <0> <0> B = -10000.0 <0> <0> ... \\ \\
    STOIC-DATA S-D-REACNO = 1 / ... \\ \\
    ALLREACT RXNID = "1" RXNTYPE = "Equilibrium" / ... \\

The file is spliced as bytes: only the paragraph (and the GCHEMISTRY binding) is added, in
the file's own line endings; every other byte, non-ASCII text included, stays as it was.
"""

import logging
import re

from tools import checkpoints
from tools.checkpoints import SaveError

logger = logging.getLogger(__name__)

# What may be written into the .bkp text: Aspen IDs (at most 8 characters; ions carry + or -)
# and the chemistry reaction types. Anything else is refused before the file is touched.
_ID = re.compile(r"^[A-Za-z0-9_+-]{1,8}$")
_RXN_TYPES = {"equilibrium": "Equilibrium", "salt": "Salt", "dissociation": "Dissociation",
              "kinetic": "Kinetic"}


def _eol(data: bytes, pos: int) -> bytes:
    """The line ending the file uses at ``pos`` (CRLF when it has no line break at all)."""
    nl = data.find(b"\n", pos)
    if nl < 0:
        nl = data.find(b"\n")
    if nl < 0:
        return b"\r\n"
    return b"\r\n" if data[nl - 1:nl] == b"\r" else b"\n"


def _cid(component_id: str) -> str:
    """Quote a component id unless it is purely alphanumeric (ions need quotes)."""
    return component_id if component_id.isalnum() else f'"{component_id}"'


def _wrap(text: str, width: int = 70) -> str:
    """Wrap at spaces -- the bkp reader treats all whitespace alike, but the
    format is Fortran-descended and ships hard-wrapped ~76 chars."""
    words = text.split(" ")
    lines, line = [], ""
    for w in words:
        if line and len(line) + 1 + len(w) > width:
            lines.append(line)
            line = w
        else:
            line = f"{line} {w}" if line else w
    if line:
        lines.append(line)
    return "\n".join(lines)


# The model's own input unit set, which a paragraph's tag names ("METCBAR_MOLE"): a set the file
# does not define (the examples' "SET1") loads as ENG, so the object's fields read in English
# units (live V15: Chemistry Unit Set ENG in a METCBAR model).
_INSET = re.compile(rb'"IN-UNITS"\s+INSET\s*=\s*"?([A-Za-z0-9_+-]+)"?')


def _unit_set(data: bytes) -> str:
    """The model's input unit set, from its global setup; ENG (Aspen's default) when unnamed."""
    m = _INSET.search(data)
    return m.group(1).decode("ascii") if m else "ENG"


def _build_paragraph(chemistry_name: str, reactions: list[dict], unit_set: str = "ENG") -> str:
    stoic, stoic1, kstoic, sdata, allreact = [], [], [], [], []
    for i, rxn in enumerate(reactions, start=1):
        for comp, coef in rxn["reactants"].items():
            stoic.append(
                f"REACNO = {i} STOIC-CID = {_cid(comp)} "
                f"COEF = {-abs(float(coef))} <0> <0>")
        for comp, coef in rxn["products"].items():
            stoic1.append(
                f"REACNO1 = {i} STOIC-CID1 = {_cid(comp)} "
                f"COEF1 = {abs(float(coef))} <0> <0>")
        keq = rxn.get("keq")
        entry = f"K-STOIC K-S-REACNO = {i}"
        if keq:
            for key in ("A", "B", "C", "D"):
                entry += f" {key} = {float(keq.get(key, 0.0))} <0> <0>"
        kstoic.append(entry)
        sdata.append(f"S-D-REACNO = {i}")
        rxntype = _RXN_TYPES[str(rxn.get("type", "Equilibrium")).lower()]
        allreact.append(f'RXNID = "{i}" RXNTYPE = "{rxntype}"')

    parts = [
        f'? CHEMISTRY "{chemistry_name}" ? ; "{unit_set}_MOLE" ;',
        "\\ STOIC " + " /  ".join(stoic),
        "\\ \\ STOIC1 " + " /  ".join(stoic1),
    ]
    for entry in kstoic:
        parts.append("\\ \\ " + entry)
    parts.append("\\ \\ STOIC-DATA " + " /  ".join(sdata))
    parts.append("\\ \\ ALLREACT " + " /  ".join(allreact))
    parts.append("\\")
    return _wrap(" ".join(parts))


def create_chemistry(
    manager,
    session_name: str,
    reactions: list[dict],
    chemistry_name: str = "GLOBAL",
    bind_global: bool = True,
) -> str:
    if not reactions:
        return "No reactions given."
    for i, rxn in enumerate(reactions, start=1):
        if not rxn.get("reactants") or not rxn.get("products"):
            return f"Reaction {i} needs both 'reactants' and 'products'."
        bad = [str(c) for c in (*rxn["reactants"], *rxn["products"]) if not _ID.match(str(c))]
        if bad:
            return (f"Reaction {i}: component id(s) {', '.join(map(repr, bad))} are not Aspen IDs "
                    "(1-8 letters, digits, _, + or -); nothing patched.")
        rtype = str(rxn.get("type", "Equilibrium"))
        if rtype.lower() not in _RXN_TYPES:
            return (f"Reaction {i}: type {rtype!r} is not one of "
                    f"{', '.join(_RXN_TYPES.values())}; nothing patched.")
    if not _ID.match(str(chemistry_name or "")):
        return (f"Chemistry name {chemistry_name!r} is not an Aspen ID "
                "(1-8 letters, digits, _, + or -); nothing patched.")

    if manager.get_app(session_name) is None:
        return f"No active session named '{session_name}'."
    try:
        paragraph = _build_paragraph(chemistry_name, reactions).encode("ascii")
        name = chemistry_name.encode("ascii")
    except UnicodeEncodeError:
        return "The chemistry name and the component ids must be plain ASCII; nothing patched."

    # 1. save the session to its file; 2. splice the paragraph into the bytes (every other
    # byte stays); 3. reopen -- Aspen's input parser validates the paragraph atomically.
    found = {}

    def edit(data: bytes):
        if re.search(rb'\?\s+CHEMISTRY\s+"' + re.escape(name) + rb'"', data):
            found["exists"] = True
            return None
        anchor = re.search(rb'\?\s+"BIO-COMPS"\s+\?', data)
        if anchor is None:
            return None
        eol = _eol(data, anchor.end())
        para = _build_paragraph(chemistry_name, reactions, _unit_set(data)).encode("ascii")
        text = (data[:anchor.end()] + eol + para.replace(b"\n", eol) + eol
                + data[anchor.end():])
        if bind_global and b"GCHEMISTRY" not in text:
            text, n = re.subn(rb"(?<![\w-])GPROPERTIES(?=\s)",
                              b"GPROPERTIES GCHEMISTRY = " + _cid(chemistry_name).encode("ascii"),
                              text, count=1)
            found["bound"] = n == 1
        return text

    try:
        res = manager.patch_file(session_name, edit, tool="create_chemistry", keep=True)   # a restore point first
    except SaveError as exc:
        return f"Nothing patched: {exc}"
    except Exception as exc:
        logger.error("create_chemistry on '%s' failed: %s", session_name, exc, exc_info=True)
        return f"create_chemistry failed: {exc}"
    note = "\n".join(filter(None, (checkpoints.note(res["backup"]),              # (none made: the AI is told)
                                   (res.get("restore_point") or {}).get("note"))))
    file_path = res["path"]
    if not res["changed"]:
        msg = (f"Chemistry '{chemistry_name}' already exists in {file_path}; nothing patched. "
               "Remove it first to rebuild." if found.get("exists") else
               'Anchor \'? "BIO-COMPS" ?\' not found in the .bkp -- file layout is unexpected, '
               "nothing patched.")
        return "\n".join(filter(None, (msg, note)))
    if not res["reopened"]:
        return "\n".join(filter(None, (
            f"Patched {file_path} but reopen failed: {res['opened']}\n"
            "Inspect the CHEMISTRY paragraph in the file.", note)))

    # 4. verify the object materialized in the node tree
    listing = manager.list_elements(
        session_name,
        f"\\Data\\Reactions\\Chemistry\\{chemistry_name}\\Input\\RXNSTRING")
    return "\n".join(filter(None, (
        f"Chemistry '{chemistry_name}' written ({len(reactions)} reactions"
        + (", GCHEMISTRY bound" if found.get("bound") else "")
        + f") and file reopened as session '{session_name}'.", note,
        f"Parsed reactions:\n{listing}")))
