"""Aspen Plus MCP Server — entry point.

All tools are registered directly via @mcp.tool().
No dynamic activation/deactivation — every tool is always available.
"""

from __future__ import annotations

import logging
import os

from mcp.server.fastmcp import FastMCP, Context

# ---------------------------------------------------------------------------
# Logging setup — writes to aspen_mcp.log next to server.py
# Only logs from our own modules (aspen_manager, tools) go to file.
# MCP framework noise is suppressed.
# ---------------------------------------------------------------------------
_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aspen_mcp.log")

_file_handler = logging.FileHandler(_LOG_FILE, encoding="utf-8")
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))

for _logger_name in ("aspen_manager", "tools"):
    _logger = logging.getLogger(_logger_name)
    _logger.setLevel(logging.DEBUG)
    _logger.addHandler(_file_handler)

from aspen_manager import AspenPlusManager
from tools import main_tools, flowsheet_tools, value_tools
from tools.properties_tools import (
    get_property_method as _get_prop, set_property_method as _set_prop,
    add_component as _add_comp, remove_component as _rm_comp,
    add_side_duty as _add_side_duty, remove_side_duty as _rm_side_duty,
)
from tools.reaction_tools import (
    add_reaction_set as _add_rxn_set,
    remove_reaction_set as _rm_rxn_set,
    add_reaction as _add_rxn,
    remove_reaction as _rm_rxn,
)
from tools.optimization_tools import run_optimization as _run_optimization
from searcher.discover_ports import discover_ports as _discover_ports

# ------------------------------------------------------------------
# Core objects
# ------------------------------------------------------------------

mcp = FastMCP(name="aspen-plus")
manager = AspenPlusManager()

# ==================================================================
# Main tools (6)
# ==================================================================

@mcp.tool()
def open_aspen_plus(file_path: str) -> str:
    """Open Aspen Plus and load a .bkp simulation file"""
    return main_tools.open_aspen_plus(manager, file_path)


@mcp.tool()
def create_new_simulation(project_name: str, destination_folder: str = None) -> str:
    """Create a new Aspen Plus simulation from the blank template.

    Copies Blank_Simulation.bkp to <destination_folder>/<project_name>.bkp and opens it.
    Use this when starting a brand new project instead of opening an existing file.
    If destination_folder is omitted, the file is created next to the blank template.
    """
    return main_tools.create_new_simulation(manager, project_name, destination_folder)


@mcp.tool()
def close_aspen_plus(session_name: str = None) -> str:
    """Close an Aspen Plus session"""
    return main_tools.close_aspen_plus(manager, session_name)


@mcp.tool()
def list_aspen_sessions() -> str:
    """List all active Aspen Plus sessions"""
    return main_tools.list_aspen_sessions(manager)


@mcp.tool()
def reinit_simulation(session_name: str) -> str:
    """Reinitialize the block solver in a given session"""
    return main_tools.reinit_simulation(manager, session_name)


@mcp.tool()
def run_simulation(session_name: str) -> str:
    """Run the simulation in a given session"""
    return main_tools.run_simulation(manager, session_name)


@mcp.tool()
def save_simulation(session_name: str, file_path: str = None) -> str:
    """Save the current simulation to disk"""
    return main_tools.save_simulation(manager, session_name, file_path)


@mcp.tool()
def check_inputs(session_name: str) -> str:
    """Check if all required inputs are complete before running.
    
    Walks the data tree to find all incomplete input nodes.
    Call this before run_simulation to ensure nothing is missing.
    """
    return main_tools.check_inputs(manager, session_name)


@mcp.tool()
def get_value(
    session_name: str,
    aspen_path: str = None,
    paths: list[str] = None,
) -> str:
    """Read a value from Aspen Plus.

    Single:  get_value(session, aspen_path='\\Data\\Blocks\\B1\\Input\\TEMP')
    Batch:   get_value(session, paths=['\\Data\\Blocks\\B1\\Output\\B_TEMP', '\\Data\\Blocks\\B1\\Output\\QCALC'])
    """
    if paths:
        results = []
        for p in paths:
            results.append(f"{p}: {manager.get_node_value(session_name, p)}")
        return "\n".join(results)
    return value_tools.get_value(manager, session_name, aspen_path)


@mcp.tool()
def set_value(
    session_name: str,
    aspen_path: str = None,
    value: str = None,
    unit: str = None,
    basis: str = None,
    items: list[dict] = None,
) -> str:
    """Set a value in Aspen Plus.

    Single:  set_value(session, aspen_path='\\Data\\Blocks\\B1\\Input\\TEMP', value='100', unit='C')
    Batch:   set_value(session, items=[{"path": "\\...\\TEMP", "value": "80", "unit": "C"}, ...])

    Smart dispatch — provide only what you want to change:
      - value only:  changes the numeric value (keeps current unit & basis)
      - unit only:   changes the unit (keeps current value & basis)
      - basis only:  changes the basis, e.g. 'MASS' or 'MOLE'
      - any combination: changes all specified fields at once
    """
    if items:
        return value_tools.batch_set_values(manager, session_name, items)
    return value_tools.set_value(
        manager, session_name, aspen_path,
        value=value, unit=unit, basis=basis,
    )


@mcp.tool()
def get_node_attribute(session_name: str, aspen_path: str, attribute: str) -> str:
    """Read an attribute from a node by attribute name or number.

    Known attributes: VALUE(0), UNITROW(2), UNITCOL(3), OPTIONLIST(5),
    RECORDTYPE(6), ENTERABLE(7), UPPERLIMIT(8), LOWERLIMIT(9),
    VALUEDEFAULT(10), USERENTERED(11), COMPSTATUS(12), BASIS(13),
    INOUT(14), PROMPT(19).

    Example: get_node_attribute(session, '\\Data\\Streams\\FEED\\Input\\FLOW', 'BASIS')
    """
    return main_tools.get_node_attribute(manager, session_name, aspen_path, attribute)


@mcp.tool()
def set_node_attribute(session_name: str, aspen_path: str, attribute: str, value: str) -> str:
    """Write an attribute on a node by attribute name or number.

    Use this to change basis, unit settings, or other node attributes
    without changing the node's value. Works on container nodes too.

    Example: set_node_attribute(session, '\\Data\\Streams\\FEED\\Input\\FLOW', 'BASIS', 'Mass-Flow')
    """
    return main_tools.set_node_attribute(manager, session_name, aspen_path, attribute, value)


@mcp.tool()
def get_node_unit_info(session_name: str, aspen_path: str) -> str:
    """Get unit information for a node: current unit, dimension, and all available units.

    Example: get_node_unit_info(session, '\\Data\\Blocks\\COMP\\Input\\PRES')
    """
    return main_tools.get_node_unit_info(manager, session_name, aspen_path)


@mcp.tool()
def list_node_children(session_name: str, aspen_path: str) -> str:
    """List all child elements of a node in the Aspen Plus data tree.

    Use this to explore the tree structure.
    Example paths: '\\Data\\Properties\\Parameters', '\\Data\\Blocks'
    """
    return main_tools.list_node_children(manager, session_name, aspen_path)



# ==================================================================
# Flowsheet tools (5)
# ==================================================================

@mcp.tool()
def place_block(
    session_name: str,
    block_name: str = None, block_type: str = None,
    blocks: list[dict] = None,
) -> str:
    """Place block(s) on the flowsheet.

    Single: place_block(session, block_name='R1', block_type='RCSTR')
    Batch:  place_block(session, blocks=[{"name": "R1", "type": "RCSTR"}, {"name": "COL1", "type": "RadFrac"}])
    """
    if blocks:
        results = []
        for b in blocks:
            results.append(flowsheet_tools.place_block(manager, session_name, b["name"], b["type"]))
        return "\n".join(results)
    return flowsheet_tools.place_block(manager, session_name, block_name, block_type)


@mcp.tool()
def remove_block(session_name: str, block_name: str) -> str:
    """Remove a block from the flowsheet"""
    return flowsheet_tools.remove_block(manager, session_name, block_name)


@mcp.tool()
def place_stream(
    session_name: str,
    stream_name: str = None, stream_type: str = "MATERIAL",
    streams: list[dict] = None,
) -> str:
    """Place stream(s) on the flowsheet.

    Single: place_stream(session, stream_name='FEED', stream_type='MATERIAL')
    Batch:  place_stream(session, streams=[{"name": "FEED"}, {"name": "PROD", "type": "MATERIAL"}])
    """
    if streams:
        results = []
        for s in streams:
            results.append(flowsheet_tools.place_stream(manager, session_name, s["name"], s.get("type", "MATERIAL")))
        return "\n".join(results)
    return flowsheet_tools.place_stream(manager, session_name, stream_name, stream_type)


@mcp.tool()
def remove_stream(session_name: str, stream_name: str) -> str:
    """Remove a stream from the flowsheet"""
    return flowsheet_tools.remove_stream(manager, session_name, stream_name)


@mcp.tool()
def connect_stream(
    session_name: str,
    block_name: str = None, stream_name: str = None,
    port_name: str = None, block_type: str = None,
    connections: list[dict] = None,
) -> str:
    """Connect stream(s) to block port(s).

    Single: connect_stream(session, block_name='R1', stream_name='FEED', port_name='F(IN)', block_type='RCSTR')
    Batch:  connect_stream(session, connections=[
                {"stream": "FEED", "block": "R1", "port": "F(IN)", "block_type": "RCSTR"},
                {"stream": "PROD", "block": "R1", "port": "P(OUT)", "block_type": "RCSTR"}])
    """
    if connections:
        results = []
        for c in connections:
            results.append(flowsheet_tools.connect_stream(
                manager, session_name,
                c["block"], c["stream"], c["port"], c.get("block_type"),
            ))
        return "\n".join(results)
    return flowsheet_tools.connect_stream(manager, session_name, block_name, stream_name, port_name, block_type)


# ==================================================================
# Property method tools (2)
# ==================================================================

@mcp.tool()
def get_property_method(session_name: str) -> str:
    """Get the current global property method"""
    return _get_prop(manager, session_name)


@mcp.tool()
def set_property_method(session_name: str, method: str) -> str:
    """Set the global property method (e.g. NRTL, UNIQUAC, PENG-ROB, IDEAL)"""
    return _set_prop(manager, session_name, method)


@mcp.tool()
def add_component(
    session_name: str,
    component_id: str = None,
    components: list[str] = None,
) -> str:
    """Add a component to the simulation component list (e.g. WATER, ETHANOL, METHANOL).

    Accepts any component name, synonym, CAS number, or short ID.
    Long names are auto-resolved via the Aspen databank.

    Single: add_component(session, component_id='WATER')
    Batch:  add_component(session, components=['WATER', 'ETHANOL', 'METHANOL'])
    """
    if components:
        results = []
        for comp in components:
            results.append(_add_comp(manager, session_name, comp))
        return "\n".join(results)
    return _add_comp(manager, session_name, component_id)


@mcp.tool()
def remove_component(session_name: str, component_id: str) -> str:
    """Remove a component from the simulation component list by its label ID"""
    return _rm_comp(manager, session_name, component_id)


@mcp.tool()
def add_side_duty(session_name: str, block_name: str, stage: int, duty: float) -> str:
    """Add or update a side duty (heater/cooler) on a RadFrac stage.

    Creates a new HEATER_DUTY entry if the stage doesn't have one,
    or updates the existing value. Use positive values for heating,
    negative for cooling.

    Args:
        block_name: RadFrac block name (e.g. 'STRIP', 'RECT').
        stage: Stage number (integer).
        duty: Heat duty value in current display unit (e.g. cal/sec).
    """
    return _add_side_duty(manager, session_name, block_name, stage, duty)


@mcp.tool()
def remove_side_duty(session_name: str, block_name: str, stage: int) -> str:
    """Remove a side duty entry from a RadFrac stage.

    Args:
        block_name: RadFrac block name.
        stage: Stage number to remove the duty from.
    """
    return _rm_side_duty(manager, session_name, block_name, stage)



# ==================================================================
# Reaction tools (4)
# ==================================================================

@mcp.tool()
def add_reaction_set(
    session_name: str, reaction_set_name: str,
    reaction_type: str = "POWERLAW"
) -> str:
    """Create a new reaction set (e.g. POWERLAW, LHHW, EQUILIBRIUM).

    This creates the reaction set container. Use add_reaction next to
    define individual reactions with stoichiometry inside the set.

    Args:
        reaction_set_name: Name for the set (e.g. 'R-1').
        reaction_type: Model type — POWERLAW, LHHW, GENERAL, EQUILIBRIUM.
    """
    return _add_rxn_set(manager, session_name, reaction_set_name, reaction_type)


@mcp.tool()
def remove_reaction_set(session_name: str, reaction_set_name: str) -> str:
    """Remove a reaction set and all its reactions."""
    return _rm_rxn_set(manager, session_name, reaction_set_name)


@mcp.tool()
def remove_reaction(
    session_name: str, reaction_set_name: str, reaction_no: int
) -> str:
    """Remove a single reaction from a reaction set.

    Removes the specified reaction number and all its associated data
    (stoichiometry, exponents, kinetics) while keeping other reactions.

    Args:
        reaction_set_name: Reaction set name (e.g. 'R-1').
        reaction_no: Reaction number to remove (e.g. 2).
    """
    return _rm_rxn(manager, session_name, reaction_set_name, reaction_no)


@mcp.tool()
def add_reaction(
    session_name: str, reaction_set_name: str,
    reaction_no: int,
    reactants: dict[str, float],
    products: dict[str, float],
    phase: str = "L",
    exponents: dict[str, float] = None,
) -> str:
    """Add a reaction with stoichiometry to an existing reaction set.

    Creates the reaction and sets stoichiometric coefficients and
    concentration exponents for the rate law.

    Args:
        reaction_set_name: Reaction set name (e.g. 'R-1').
        reaction_no: Reaction number within the set (usually 1).
        reactants: {component_id: coefficient} — use positive values,
                   Aspen auto-negates (e.g. {'ACETICAC': 1, 'METHANOL': 1}).
        products: {component_id: coefficient} — use positive values
                  (e.g. {'METHYLAC': 1, 'WATER': 1}).
        phase: 'L' (liquid) or 'V' (vapor).
        exponents: {component_id: exponent} for rate law. If omitted,
                   defaults to abs(reactant coefficients).
    """
    return _add_rxn(
        manager, session_name, reaction_set_name, reaction_no,
        reactants, products, phase, exponents,
    )


# ==================================================================
# Generic Elements tools (5)
# ==================================================================

@mcp.tool()
def list_elements(session_name: str, aspen_path: str) -> str:
    """List all elements under a node in the data tree.

    Shows index, name, and value for each element.
    Use this to explore table/collection nodes.

    Example: list_elements(session, '\\Data\\Blocks')
    """
    return manager.list_elements(session_name, aspen_path)


@mcp.tool()
def add_element(session_name: str, aspen_path: str, name: str) -> str:
    """Add an element to a node via Elements.Add(name).

    Use 'NAME!TYPE' syntax for typed elements (e.g. 'B1!Heater', 'R1!POWERLAW').
    This is the generic version of place_block, place_stream, etc.

    Examples:
      - add_element(session, '\\Data\\Blocks', 'PUMP1!Pump')
      - add_element(session, '\\Data\\Reactions\\Reactions', 'RXN1!POWERLAW')
    """
    return manager.add_element(session_name, aspen_path, name)


@mcp.tool()
def remove_element(session_name: str, aspen_path: str, name: str) -> str:
    """Remove an element from a node by name via Elements.Remove(name).

    Examples:
      - remove_element(session, '\\Data\\Blocks', 'PUMP1')
      - remove_element(session, '\\Data\\Streams', 'S1')
    """
    return manager.remove_element(session_name, aspen_path, name)


@mcp.tool()
def insert_row(session_name: str, aspen_path: str, dimension: int = 0) -> str:
    """Insert a new row in a table node.

    Use this for table-type nodes that require adding rows
    (e.g. component lists, reaction stoichiometry, sensitivity variables).
    Returns the index of the newly inserted row.
    Use set_label separately if the row needs a label.

    Args:
        aspen_path: Path to the table node.
        dimension: Table dimension (default 0).

    Example: insert_row(session, '\\Data\\Blocks\\R1\\Input\\RXN_ID')
    """
    return manager.insert_row(session_name, aspen_path, dimension)


@mcp.tool()
def set_label(session_name: str, aspen_path: str, index: int, label: str, dimension: int = 0) -> str:
    """Set the label of a row in a table node.

    Use this after insert_row to assign a label to the new row.
    Some table dimensions do not support labels — in that case, skip this step.

    Args:
        aspen_path: Path to the table node.
        index: Row index to label.
        label: Label string.
        dimension: Table dimension (default 0).

    Example: set_label(session, '\\Data\\Blocks\\R1\\Input\\RXN_ID', 0, 'CRACKING')
    """
    return manager.set_label(session_name, aspen_path, index, label, dimension)


@mcp.tool()
def remove_row(session_name: str, aspen_path: str, index: int, dimension: int = 0) -> str:
    """Remove a row from a table node by index.

    Args:
        aspen_path: Path to the table node.
        index: Row index to remove (0-based).
        dimension: Table dimension (default 0).

    Use list_elements to see current indices before removing.
    """
    return manager.remove_row(session_name, aspen_path, index, dimension)


# ==================================================================
# Discovery tool (1)
# ==================================================================

@mcp.tool()
def discover_ports(session_name: str, block_types: list[str] = None) -> str:
    """Auto-discover block ports via COM API.

    Places a temporary block of each type, reads its ports, removes it,
    and saves results to block_ports.json. Requires an active Aspen session
    (preferably a blank simulation).

    Args:
        block_types: Optional list of block type names to discover.
                     If omitted, re-discovers all types in block_ports.json.
    """
    try:
        results, errors = _discover_ports(manager, session_name, block_types)
        summary_lines = [f"Discovered ports for {len(results)} block types:"]
        for bt, ports in sorted(results.items()):
            summary_lines.append(f"  {bt}: {', '.join(ports) if ports else '(none)'}")
        if errors:
            summary_lines.append(f"\nFailed for {len(errors)} block types:")
            for err in errors:
                summary_lines.append(f"  {err}")
        return "\n".join(summary_lines)
    except Exception as exc:
        return f"Port discovery failed: {exc}"


# ==================================================================
# Optimization tool (1)
# ==================================================================

@mcp.tool()
async def optimize(
    session_name: str,
    variables: list[dict],
    objectives: list[dict],
    constraints: list[dict] = None,
    pop_size: int = 50,
    n_gen: int = 30,
    crossover_prob: float = 0.8,
    mutation_prob: float = 0.2,
    output_dir: str = None,
    ctx: Context = None,
) -> str:
    """Run NSGA-II multi-objective genetic algorithm optimization.

    Iteratively adjusts decision variables, runs the Aspen simulation,
    and evolves towards the Pareto-optimal front.

    Progress is reported in real-time via MCP notifications after each
    generation, showing feasible count and current best objective values.

    Args:
        session_name: Active Aspen Plus session.
        variables: Decision variables, each a dict with keys:
            - aspen_path: Aspen tree path (e.g. '\\Data\\Blocks\\B1\\Input\\REFLUX_RATIO')
            - lower: Lower bound (float)
            - upper: Upper bound (float)
            - type: Optional, 'int' for integer variables
        objectives: Objectives, each a dict with keys:
            - aspen_path: Single Aspen path to read the objective value
            - aspen_paths: List of Aspen paths (use instead of aspen_path for multi-path objectives)
            - expression: Optional math formula using v0, v1, v2... referencing aspen_paths values.
                Supports: sqrt, log, log10, exp, sin, cos, abs, pow, max, min, pi, e.
                If omitted with aspen_paths, defaults to sum.
                Example: {"aspen_paths": [pathA, pathB], "expression": "v0 / v1", "direction": "maximize"}
            - direction: 'minimize' or 'maximize'
        constraints: Optional constraint list, each a dict with keys:
            - aspen_path: Aspen tree path to read
            - lower: Optional lower bound
            - upper: Optional upper bound
        pop_size: Population size per generation (default 50).
        n_gen: Number of generations (default 30).
        crossover_prob: Crossover probability (default 0.8).
        mutation_prob: Mutation probability (default 0.2).
        output_dir: Directory to save results JSON. Each run creates a
            timestamped file (e.g. opt_session_20260318_143022.json).
            If omitted, results are not saved to disk.
    """
    return await _run_optimization(
        manager, session_name, variables, objectives,
        constraints=constraints, pop_size=pop_size, n_gen=n_gen,
        crossover_prob=crossover_prob, mutation_prob=mutation_prob,
        output_dir=output_dir, ctx=ctx,
    )


# ------------------------------------------------------------------
# Run
# ------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
