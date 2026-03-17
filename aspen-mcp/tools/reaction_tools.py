"""Implementations for reaction-related tools.

Handles creating reaction sets, adding stoichiometry, and setting kinetic
parameters via direct COM tree manipulation.

Key COM patterns for 2D tables (COEF, COEF1, EXPONENT, EXPONENT1):
  - Dimension 0 = component ID, Dimension 1 = substream (usually MIXED)
  - First InsertRow + SetLabel(d0) + SetLabel(d1=MIXED) creates the entry
  - Second InsertRow auto-expands to N entries (N = number of components)
  - Subsequent entries: SetLabel(d0=comp) on the empty slot (GetLabel(0,i)=='')
  - FindNode works with path: TABLE\\rxn_no\\comp\\substream
"""

from __future__ import annotations

_REACTIONS_BASE = r"\Data\Reactions\Reactions"


def _create_2d_table_labels(app, table_path: str,
                            components: list[str],
                            substream: str = "MIXED") -> str | None:
    """Create component labels in a 2D (component x substream) table.

    Only creates labels — does NOT set values. Call _set_2d_table_values
    after ALL tables have their labels set.

    Returns:
        Error message string, or None on success.
    """
    node = app.Tree.FindNode(table_path)
    if node is None:
        return f"Node not found: {table_path}"

    els = node.Elements
    # Clear existing entries
    while els.Count > 0:
        els.RemoveRow(0, 0)

    for idx, comp in enumerate(components):
        if idx == 0:
            els.InsertRow(0, 0)
        else:
            if els.Count <= idx:
                els.InsertRow(0, els.Count)

        if idx == 0:
            target_idx = 0
        else:
            target_idx = None
            for i in range(els.Count):
                try:
                    l0 = els.GetLabel(0, i)
                    if l0 == '':
                        target_idx = i
                        break
                except Exception:
                    continue
            if target_idx is None:
                continue

        els.SetLabel(0, target_idx, False, comp)
        try:
            els.SetLabel(1, target_idx, False, substream)
        except Exception:
            pass  # dim1 may already be set from auto-expansion

    return None


def _set_2d_table_values(manager, session_name: str,
                         table_path: str,
                         entries: list[tuple[str, float]],
                         substream: str = "MIXED") -> list[str]:
    """Set values in a 2D table that already has labels created.

    Call this AFTER all tables have their labels set via
    _create_2d_table_labels to avoid cross-table invalidation.

    Returns:
        List of status messages.
    """
    messages = []
    for comp, val in entries:
        value_path = f"{table_path}\\{comp}\\{substream}"
        result = manager.set_node_value(session_name, value_path, value=val)
        messages.append(f"{comp}: {result}")
    return messages


def add_reaction_set(
    manager, session_name: str, reaction_set_name: str,
    reaction_type: str = "POWERLAW"
) -> str:
    """Create a new reaction set.

    Args:
        reaction_set_name: Name for the reaction set (e.g. 'R-1').
        reaction_type: Reaction model type. Options: POWERLAW, LHHW,
                       GENERAL, EQUILIBRIUM.
    """
    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."
    try:
        rxns = app.Tree.FindNode(_REACTIONS_BASE)
        if rxns is None:
            return "Reactions node not found in data tree."

        # Check for duplicates
        els = rxns.Elements
        for i in range(els.Count):
            el = els.Item(i)
            if el and el.Name.upper() == reaction_set_name.upper():
                return f"Reaction set '{reaction_set_name}' already exists."

        # Create: Elements.Add("name!type")
        rtype = reaction_type.upper()
        els.Add(f"{reaction_set_name}!{rtype}")

        # Verify creation
        new_node = app.Tree.FindNode(f"{_REACTIONS_BASE}\\{reaction_set_name}")
        if new_node is None:
            return f"Failed to create reaction set '{reaction_set_name}'."

        return (
            f"Reaction set '{reaction_set_name}' created (type={rtype}). "
            f"Use add_reaction to add reactions to this set."
        )
    except Exception as exc:
        return f"Failed to create reaction set '{reaction_set_name}': {exc}"


def remove_reaction_set(manager, session_name: str, reaction_set_name: str) -> str:
    """Remove a reaction set."""
    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."
    try:
        rxns = app.Tree.FindNode(_REACTIONS_BASE)
        if rxns is None:
            return "Reactions node not found."
        els = rxns.Elements
        for i in range(els.Count):
            el = els.Item(i)
            if el and el.Name.upper() == reaction_set_name.upper():
                els.RemoveRow(0, i)
                return f"Reaction set '{reaction_set_name}' removed."
        return f"Reaction set '{reaction_set_name}' not found."
    except Exception as exc:
        return f"Failed to remove reaction set '{reaction_set_name}': {exc}"


def add_reaction(
    manager, session_name: str, reaction_set_name: str,
    reaction_no: int,
    reactants: dict[str, float],
    products: dict[str, float],
    phase: str = "L",
    exponents: dict[str, float] | None = None,
    substream: str = "MIXED",
) -> str:
    """Add a reaction with stoichiometry to an existing reaction set.

    This creates reaction number `reaction_no` in the set and populates:
      - REACTYPE (set to KINETIC)
      - COEF (reactant stoichiometric coefficients, negative values)
      - COEF1 (product stoichiometric coefficients, positive values)
      - PHASE
      - EXPONENT (concentration exponents for rate law)

    Args:
        reaction_set_name: Name of the reaction set (e.g. 'R-1').
        reaction_no: Reaction number within the set (usually 1).
        reactants: Dict of {component_id: stoichiometric_coefficient}.
                   Use positive values — Aspen auto-negates for reactants.
                   (e.g. {'ACETICAC': 1, 'METHANOL': 1}).
        products: Dict of {component_id: stoichiometric_coefficient}.
                  Use positive values (e.g. {'WATER': 1}).
        phase: Reaction phase ('L' for liquid, 'V' for vapor).
        exponents: Dict of {component_id: concentration_exponent}.
                   If None, uses absolute values of reactant coefficients.
        substream: Substream name (default 'MIXED').
    """
    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."

    base = f"{_REACTIONS_BASE}\\{reaction_set_name}\\Input"
    rxn = str(reaction_no)

    try:
        # Verify reaction set exists
        inp_node = app.Tree.FindNode(base)
        if inp_node is None:
            return f"Reaction set '{reaction_set_name}' not found."

        # Step 1: Set REACTYPE (this auto-creates reaction entries in all tables)
        rt_node = app.Tree.FindNode(f"{base}\\REACTYPE")
        if rt_node is None:
            return "REACTYPE node not found."
        rt_els = rt_node.Elements

        # Check if reaction number already exists
        existing = False
        for i in range(rt_els.Count):
            el = rt_els.Item(i)
            if el and el.Name == rxn:
                existing = True
                break

        if not existing:
            rt_els.InsertRow(0, rt_els.Count)
            rt_els.SetLabel(0, rt_els.Count - 1, False, rxn)

        rt_val = app.Tree.FindNode(f"{base}\\REACTYPE\\{rxn}")
        if rt_val:
            rt_val.Value = "KINETIC"

        # Step 2: Set PHASE
        ph_node = app.Tree.FindNode(f"{base}\\PHASE\\{rxn}")
        if ph_node:
            ph_node.Value = phase

        # Prepare entries
        coef_entries = [(comp, abs(coef)) for comp, coef in reactants.items()]
        coef1_entries = [(comp, abs(coef)) for comp, coef in products.items()]
        if exponents is None:
            exponents = {comp: abs(coef) for comp, coef in reactants.items()}
        exp_entries = list(exponents.items())

        # Phase A: Create ALL labels first (InsertRow + SetLabel)
        # This avoids cross-table invalidation
        for table, comps in [
            (f"{base}\\COEF\\{rxn}", [c for c, _ in coef_entries]),
            (f"{base}\\COEF1\\{rxn}", [c for c, _ in coef1_entries]),
            (f"{base}\\EXPONENT\\{rxn}", [c for c, _ in exp_entries]),
        ]:
            err = _create_2d_table_labels(app, table, comps, substream)
            if err:
                return f"Failed creating labels: {err}"

        # Phase B: Set ALL values (labels are stable across all tables)
        coef_msgs = _set_2d_table_values(
            manager, session_name,
            f"{base}\\COEF\\{rxn}", coef_entries, substream
        )
        coef1_msgs = _set_2d_table_values(
            manager, session_name,
            f"{base}\\COEF1\\{rxn}", coef1_entries, substream
        )
        exp_msgs = _set_2d_table_values(
            manager, session_name,
            f"{base}\\EXPONENT\\{rxn}", exp_entries, substream
        )

        # Build result message
        lines = [f"Reaction {rxn} added to '{reaction_set_name}':"]
        lines.append(f"  Phase: {phase}")
        lines.append(f"  Reactants (COEF): {', '.join(coef_msgs)}")
        lines.append(f"  Products (COEF1): {', '.join(coef1_msgs)}")
        lines.append(f"  Exponents: {', '.join(exp_msgs)}")
        return "\n".join(lines)

    except Exception as exc:
        return f"Failed to add reaction {rxn} to '{reaction_set_name}': {exc}"


def remove_reaction(
    manager, session_name: str, reaction_set_name: str, reaction_no: int
) -> str:
    """Remove a single reaction from a reaction set.

    Removes the reaction number from REACTYPE and all related tables
    (COEF, COEF1, EXPONENT, EXPONENT1, PRE_EXP, ACT_ENERGY, etc.).

    Args:
        reaction_set_name: Name of the reaction set (e.g. 'R-1').
        reaction_no: Reaction number to remove.
    """
    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."

    base = f"{_REACTIONS_BASE}\\{reaction_set_name}\\Input"
    rxn = str(reaction_no)

    try:
        # Remove from REACTYPE (this should cascade to other tables)
        rt_node = app.Tree.FindNode(f"{base}\\REACTYPE")
        if rt_node is None:
            return f"Reaction set '{reaction_set_name}' not found."

        rt_els = rt_node.Elements
        target_idx = None
        for i in range(rt_els.Count):
            el = rt_els.Item(i)
            if el and el.Name == rxn:
                target_idx = i
                break

        if target_idx is None:
            return f"Reaction {rxn} not found in '{reaction_set_name}'."

        rt_els.RemoveRow(0, target_idx)

        # Also clean up 2D tables and scalar tables explicitly
        for table in ["COEF", "COEF1", "EXPONENT", "EXPONENT1",
                       "PRE_EXP", "ACT_ENERGY", "T_EXP", "PHASE",
                       "OPT_KEQ", "R_D_CBASIS", "R_D_RBASIS",
                       "R_D_KBASIS", "R_D_SBASIS", "R_D_PBASL",
                       "R_D_PBASS", "A", "B", "C", "D"]:
            tbl_node = app.Tree.FindNode(f"{base}\\{table}")
            if tbl_node is None:
                continue
            els = tbl_node.Elements
            for i in range(els.Count):
                el = els.Item(i)
                if el and el.Name == rxn:
                    try:
                        els.RemoveRow(0, i)
                    except Exception:
                        pass
                    break

        return f"Reaction {rxn} removed from '{reaction_set_name}'."

    except Exception as exc:
        return f"Failed to remove reaction {rxn} from '{reaction_set_name}': {exc}"


def set_reaction_kinetics(
    manager, session_name: str, reaction_set_name: str,
    reaction_no: int,
    pre_exponential: float | None = None,
    activation_energy: float | None = None,
    temperature_exponent: float | None = None,
    concentration_basis: str | None = None,
    rate_basis: str | None = None,
) -> str:
    """Set kinetic parameters for a reaction in a POWERLAW reaction set.

    The rate expression is: r = k0 * T^n * exp(-E/RT) * product(Ci^ai)

    Args:
        reaction_set_name: Name of the reaction set (e.g. 'R-1').
        reaction_no: Reaction number within the set.
        pre_exponential: Pre-exponential factor k0.
        activation_energy: Activation energy E (in current display units).
        temperature_exponent: Temperature exponent n (default 0).
        concentration_basis: Concentration basis (e.g. 'MOLARITY', 'MOLEFRAC').
        rate_basis: Rate basis (e.g. 'REAC-VOL', 'CAT-WT').
    """
    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."

    base = f"{_REACTIONS_BASE}\\{reaction_set_name}\\Input"
    rxn = str(reaction_no)

    try:
        results = []

        param_map = {
            "PRE_EXP": pre_exponential,
            "ACT_ENERGY": activation_energy,
            "T_EXP": temperature_exponent,
            "R_D_CBASIS": concentration_basis,
            "R_D_RBASIS": rate_basis,
        }

        for field, value in param_map.items():
            if value is None:
                continue
            node = app.Tree.FindNode(f"{base}\\{field}\\{rxn}")
            if node is None:
                results.append(f"{field}: node not found")
                continue
            node.Value = value
            results.append(f"{field} = {value}")

        if not results:
            return "No parameters specified."

        return f"Kinetics for reaction {rxn} in '{reaction_set_name}':\n  " + \
               "\n  ".join(results)

    except Exception as exc:
        return f"Failed to set kinetics for reaction {rxn}: {exc}"


def assign_reaction_set_to_block(
    manager, session_name: str, block_name: str, reaction_set_name: str
) -> str:
    """Assign (select) a reaction set to a reactor block (RCSTR, RPlug, etc.).

    Moves the reaction set from 'Available' to 'Selected' in the block's
    Kinetics tab.

    Args:
        block_name: Name of the reactor block (e.g. 'FURNACE').
        reaction_set_name: Name of the reaction set (e.g. 'CRACKING').
    """
    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."

    errors = []

    # Strategy 1: Direct Value assignment on RXN_ID node
    try:
        rxn_id_path = f"\\Data\\Blocks\\{block_name}\\Input\\RXN_ID"
        rxn_node = app.Tree.FindNode(rxn_id_path)
        if rxn_node is not None:
            rxn_node.Value = reaction_set_name
            return f"Reaction set '{reaction_set_name}' assigned to block '{block_name}' (via Value)."
    except Exception as exc:
        errors.append(f"Value: {exc}")

    # Strategy 2: Elements.Item(0).Value
    try:
        rxn_id_path = f"\\Data\\Blocks\\{block_name}\\Input\\RXN_ID"
        rxn_node = app.Tree.FindNode(rxn_id_path)
        if rxn_node is not None:
            els = rxn_node.Elements
            if els.Count == 0:
                els.InsertRow(0, 0)
            els.Item(0).Value = reaction_set_name
            return f"Reaction set '{reaction_set_name}' assigned to block '{block_name}' (via Element)."
    except Exception as exc:
        errors.append(f"Element: {exc}")

    # Strategy 3: FindNode on sub-path
    try:
        sub_path = f"\\Data\\Blocks\\{block_name}\\Input\\RXN_ID\\{reaction_set_name}"
        sub_node = app.Tree.FindNode(sub_path)
        if sub_node is None:
            # Try creating via KINETICS + reinit
            kin_path = f"\\Data\\Blocks\\{block_name}\\Input\\KINETICS"
            kin_node = app.Tree.FindNode(kin_path)
            if kin_node is not None:
                kin_node.Value = reaction_set_name
                app.Reinit()
                return f"Reaction set '{reaction_set_name}' assigned via KINETICS + Reinit."
        else:
            sub_node.Value = reaction_set_name
            return f"Reaction set '{reaction_set_name}' assigned to block '{block_name}' (via sub-path)."
    except Exception as exc:
        errors.append(f"SubPath: {exc}")

    return f"All strategies failed for '{reaction_set_name}' -> '{block_name}': " + " | ".join(errors)
