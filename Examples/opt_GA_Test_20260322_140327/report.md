# Optimization Report — GA_Test

**Date:** 2026-03-22 14:03:27

## Settings

| Parameter | Value |
|-----------|-------|
| Population | 10 |
| Generations | 8 |
| Crossover | 0.8 |
| Mutation | 0.2 |

### Decision Variables

| Name | Path | Lower | Upper | Type |
|------|------|-------|-------|------|
| BASIS_RR | `\Data\Blocks\COL\Input\BASIS_RR` | 1 | 5 | float |
| FEED | `\Data\Blocks\COL\Input\FEED_STAGE\FEED` | 5 | 15 | int |
| VOL | `\Data\Blocks\R1\Input\VOL` | 0.1 | 5 | float |

### Objectives

| Name | Direction | Path |
|------|-----------|------|
| DIMETHYL | maximize | `\Data\Streams\PROD\Output\MOLEFLOW\MIXED\DIMETHYL` |
| REB_DUTY | minimize | `\Data\Blocks\COL\Output\REB_DUTY` |

### Constraints

| Path | Lower | Upper |
|------|-------|-------|
| `\Data\Streams\PROD\Output\MOLEFRAC\MIXED\METHANOL` | - | 0.1 |

## Pareto Front (8 solutions)

| # | BASIS_RR | FEED | VOL | DIMETHYL (maximize) | REB_DUTY (minimize) | Best |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 1.027 | 14 | 3.109 | 24.5 | 2.712e+05 |  |
| 2 | 1.039 | 14 | 3.571 | 24.53 | 2.726e+05 |  |
| 3 | 1.361 | 12 | 3.404 | 24.58 | 3.103e+05 |  |
| 4 | 1.382 | 13 | 3.416 | 24.6 | 3.128e+05 |  |
| 5 | 1.392 | 14 | 3.644 | 24.63 | 3.14e+05 | **>>>** |
| 6 | 1.891 | 13 | 3.415 | 24.63 | 3.724e+05 |  |
| 7 | 1.893 | 12 | 3.567 | 24.64 | 3.726e+05 |  |
| 8 | 1.91 | 12 | 3.567 | 24.64 | 3.746e+05 |  |

## Generation Log

- Gen 0: evaluated 10 individuals
- Gen 1/8: evaluated 9 new
- Gen 2/8: evaluated 9 new
- Gen 3/8: evaluated 8 new
- Gen 4/8: evaluated 8 new
- Gen 5/8: evaluated 10 new
- Gen 6/8: evaluated 9 new
- Gen 7/8: evaluated 3 new
- Gen 8/8: evaluated 9 new
