# Error History

Resolved Aspen Plus simulation errors. One H2 section per error keyword, H3 entries underneath.

## COLUMN NOT IN MASS BALANCE

### RadFrac — BASIS_D exceeds total feed flow (2026-03-26)

- **Block type**: RadFrac
- **Property method**: NRTL
- **Cause**: BASIS_D was set higher than the total feed mole flow, making mass balance impossible.
- **Fix**: Reduced `Data.Blocks.{name}.Input.BASIS_D` to a value less than the total feed flow.
