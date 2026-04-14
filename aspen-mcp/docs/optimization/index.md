# Optimization Index

Aspen Plus provides two optimization approaches: the built-in SQP optimizer and an external NSGA-II genetic algorithm.

| Method | Type | Objectives | Doc |
|--------|------|------------|-----|
| Built-in SQP | Single-objective, gradient-based | 1 | [built-in.md](built-in.md) |
| GA (NSGA-II) | Multi-objective, population-based | 1+ (Pareto front) | [ga.md](ga.md) |

## When to use which

- **Built-in SQP** — fast convergence for single-objective problems with smooth, continuous variables. Runs inside Aspen Plus.
- **GA (NSGA-II)** — multi-objective problems, integer variables, non-smooth objectives, or when you need the full Pareto front. Runs externally via MCP.
