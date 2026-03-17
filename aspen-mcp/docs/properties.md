# Properties & Components

## Property Methods

| Method | Best For |
|--------|----------|
| `PENG-ROB` | Hydrocarbons, gases, high pressure |
| `SRK` | Gas processing, similar to Peng-Robinson |
| `NRTL` | Polar/non-ideal liquid mixtures |
| `UNIQUAC` | Liquid-liquid equilibrium |
| `IDEAL` | Ideal gas + ideal liquid mixtures |
| `WILSON` | Non-ideal liquid, no LLE |
| `UNIFAC` | Predictive (no binary data needed) |

### Setting Property Method
```
set_property_method(session, 'PENG-ROB')
```
Path: `\Data\Properties\Specifications\Input\GOPSETNAME`

## Components

### Adding Components
```
add_component(session, 'ETHANOL')
add_component(session, 'WATER')
add_component(session, '64-17-5')   # by CAS number
```

### Removing Components
```
remove_component(session, 'ETHANOL')
```

### Component List Path
Components are stored at: `\Data\Components\Specifications\Input\TYPE`

Use `list_elements` to see all components:
```
list_elements(session, '\Data\Components\Specifications\Input\TYPE')
```

## Gotchas

- Set property method BEFORE adding blocks — it affects all calculations.
- Binary interaction parameters are auto-retrieved from Aspen databanks when available.
- Some component names need resolution (e.g. 'PROPYLENE' → 'PROPYLEN' in Aspen ID).
