# Component list and global method

The component list and the global property method of a simulation; both are set before a run.

## Components

`add_component` takes an Aspen ID, a databank name or a CAS number (`64-17-5` resolves to ethanol).

A name longer than 8 characters gets an 8-character ID and is written to `ANAME` (`ACETIC-ACID` becomes `ACETICAC`).

Read `DBNAME` back: a short ID can be another compound (`TEA` is triethyl aluminium; write `TRIETHANOLAMINE`).

A component already listed, by ID, alias or databank name in any case, is not added twice.

`remove_component` takes the ID.

| Path | Type | Purpose |
|---|---|---|
| `\Data\Components\Specifications\Input\TYPE\{comp}` | `CONV`, `SOLID` | Component class: conventional, or solid (the solid run uses stream class `MIXCISLD`) |
| `\Data\Components\Specifications\Input\ANAME\{comp}` | name | Name or alias to look the ID up by; once found it reads the alias (`PROPYLENE` gives `C3H6-2`) |
| `\Data\Components\Specifications\Input\DBNAME\{comp}` | name (read) | Databank compound the ID resolved to; empty when none matched |
| `\Data\Components\Specifications\Input\CASN\{comp}` | text (read) | CAS number of the resolved compound |

## Property method

| Path | Type | Purpose |
|---|---|---|
| `\Data\Properties\Specifications\Input\GOPSETNAME` | `IDEAL`, `NRTL`, `NRTL-RK`, `WILSON`, `UNIQUAC`, `UNIFAC`, `PENG-ROB`, `RK-SOAVE`, `SRK`, `ENRTL-RK` | Global method, one of about 100 names (`set_property_method`) |

Binary parameters come with the method: after `set_property_method` the run's input carries the databank NRTL pairs of benzene and toluene, with none written.

It can change at any time: each run above set it after the blocks, and the streams report the new one.

A block can use its own method: `Input\OPSETNAME` on the block ([common.md](../blocks/common.md)).

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `\Data\Streams\{stream}\Output\PPOPSET` | method name | Method the stream was computed with |

More: [method options](properties-methods.md), [Henry components](properties-henry.md), [chemistry and electrolytes](properties-chemistry.md), [property sets](properties-prop-sets.md), [component groups](properties-comp-groups.md).

Not covered: Component selection grid (GUI grid fields with no tree node); Nonconventional components, Assays, blends, pseudocomponents, Component group empty-substream flag (COMP) (not checked); Molecular structure (its keywords are not in the tree); Flowsheet-section methods, Flowsheet-section method list (no tree field moves a block into a section, and a method on section GLOBAL left its streams on the global method); Referenced methods (a list of extra methods; its effect was not checked); Dissociation reactions, Salt reactions (create_chemistry writes equilibrium reactions only); New-reaction dialog (a reaction-entry dialog); Prop-set visibility flag (ISPLUS) (a GUI visibility flag).
