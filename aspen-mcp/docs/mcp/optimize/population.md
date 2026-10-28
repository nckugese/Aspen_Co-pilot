# Population methods: NSGA-II, NSGA-III, DE / GDE3, PSO / MOPSO

Shared arguments, budget split and files: [common.md](common.md). Each generation evaluates the whole population, the initial one included, so evaluations = size × generations. `sampling` picks the initial population: `random` (default) or `lhs` (Latin hypercube); any other text is refused.

## NSGA-II (`nsga2`)

SBX crossover and polynomial mutation; 1 or more objectives.

| Option | Type | Default | Purpose |
|---|---|---|---|
| `pop_size` | int | 50 | Points per generation |
| `n_gen` | int | 30 | Generations, the first included |
| `crossover_prob` | 0–1 | 0.8 | Chance that a pair of parents is crossed |
| `mutation_prob` | 0–1 | 0.2 | Chance that a child is mutated; each of its variables then mutates with chance 1/variables, at most 0.5 |
| `eta_crossover` | float | 20 | Crossover spread: higher keeps children near their parents |
| `eta_mutation` | float | 20 | Mutation spread: higher makes smaller steps |
| `sampling` | `random`, `lhs` | `random` | Initial population |
| `stall_generations` | int | 0 | Stop after this many generations in which no objective's best improved; 0 = off |

## NSGA-III (`nsga3`)

Keeps the front spread along reference directions; needs 2+ objectives and is meant for 3+.

| Option | Type | Default | Purpose |
|---|---|---|---|
| `pop_size` | int | 92 | Points per generation |
| `n_gen` | int | 30 | Generations, the first included |
| `n_partitions` | int | None | Divisions per objective axis. None: the largest p whose direction count C(M+p−1, p) does not exceed `pop_size` (3 objectives, 92 → p = 12, 91 directions) |
| `sampling` | `random`, `lhs` | `random` | Initial population |

## DE / GDE3 (`de`, `gde3`)

`de` runs differential evolution for one objective and GDE3 for 2+; `gde3` refuses one objective.

| Option | Type | Default | Purpose |
|---|---|---|---|
| `pop_size` | int | 50 | Points per generation |
| `n_gen` | int | 30 | Generations, the first included |
| `variant` | str | `DE/rand/1/bin` | Mutation scheme in pymoo's notation, e.g. `DE/best/1/bin`; one objective only (GDE3 always uses rand/1/bin) |
| `CR` | 0–1 | 0.7 | Crossover rate |
| `F` | float | 0.5 | Weight of the difference vector |
| `dither` | `vector`, `scalar`, `no` | `vector` | `vector`: a random weight between `F` and 1 for each new point; `scalar`: one per generation; `no`: `F` as given. One objective only |
| `sampling` | `random`, `lhs` | `random` | Initial population |

## PSO / MOPSO (`pso`, `mopso`)

`pso` runs pymoo's particle swarm for one objective and the server's MOPSO for 2+; `mopso` refuses one objective.

| Option | Type | Default | Purpose |
|---|---|---|---|
| `swarm_size` | int | 40 | Particles per iteration |
| `n_iterations` | int | 30 | Iterations, the first included |
| `w` | float | 0.9 | Inertia. PSO adapts `w`, `c1` and `c2` from these start values; MOPSO lowers `w` linearly toward 0.4 |
| `c1` | float | 2.0 | Pull toward each particle's own best |
| `c2` | float | 2.0 | Pull toward the swarm's best (MOPSO: a leader drawn from its archive) |
| `sampling` | `random`, `lhs` | `random` | Initial swarm |

MOPSO keeps the non-dominated feasible points in an archive of at most 3 × `swarm_size`, thinned by crowding; that archive is the reported front. A point that violates a constraint is penalized and never enters it.

Not yet verified against a live Aspen run; the quality of the fronts each method reaches is not benchmarked.
