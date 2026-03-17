# DSTWU (Shortcut Distillation)

Winn-Underwood-Gilliland shortcut distillation method. Good for quick estimates before RadFrac.

## Ports

| Port | Direction | Type |
|------|-----------|------|
| F | IN | Feed |
| CHS | IN | Condenser heat stream |
| RHS | IN | Reboiler heat stream |
| D | OUT | Distillate |
| B | OUT | Bottoms |
| CWD | OUT | Condenser work duty |
| CHS | OUT | Condenser heat stream out |
| RHS | OUT | Reboiler heat stream out |

## Key Input Paths

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\LIGHTKEY` | string | Light key component |
| `\Data\Blocks\{name}\Input\HEAVYKEY` | string | Heavy key component |
| `\Data\Blocks\{name}\Input\RECOVL` | float | Light key recovery in distillate (0-1) |
| `\Data\Blocks\{name}\Input\RECOVH` | float | Heavy key recovery in bottoms (0-1) |
| `\Data\Blocks\{name}\Input\PTOP` | float | Condenser pressure |
| `\Data\Blocks\{name}\Input\PBOT` | float | Reboiler pressure |
| `\Data\Blocks\{name}\Input\CONDENSER` | string | `TOTAL` or `PARTIAL-V` |
| `\Data\Blocks\{name}\Input\RR` | float | Reflux ratio (optional, calculated if not given) |
