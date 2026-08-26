# CLAUDE.md

Guidance for Claude Code when it works in this repository.

## The project

`burn-scar-recovery` measures how fast California chaparral recovers
after a fire.

The pipeline reads Harmonized Landsat Sentinel-2 (HLS) imagery from
S3. It runs a segmentation model over 224-pixel chips. It converts
the masks to polygons. It joins the polygons across chip boundaries
into one polygon for each scar. It writes the result to GeoParquet.
It then joins the scars against fire perimeters, elevation data and
land cover data.

The project has two results:

1. **Recovery.** The time for a burn scar to reach half recovery,
   grouped by slope aspect and by pre-fire vegetation.
2. **Throughput.** The read bandwidth that one GPU needs before the
   GPU becomes the bottleneck.

The second result is the more important one. The workload is
approximately nine parts IO to one part compute. Below the necessary
read rate, more GPUs give no benefit.

## Three rules that override other guidance

**Do not train the model.** The model is a load generator. Phase 0
is a gate. If the gate fails, change the source or the area of
interest. Do not change the weights.

**Do not pre-download the corpus.** The pipeline must read from S3
and must stay IO bound. That behaviour is the subject of the
project. A local copy makes the measurements meaningless. The 10 GB
chip cache is an instrument. It is not a data store.

**Report bytes before seconds.** Bytes saved is a property of the
pipeline. Seconds is a property of the machine.

## Where to find information

| File | Content |
| --- | --- |
| `README.md` | The question, the method, the result tables |
| `ROADMAP.md` | The build order, the phases, the measurements |
| `docs/glossary.md` | The approved term for each concept |
| `docs/conventions.md` | Identifiers, coordinate systems, run records |
| `docs/data-sources.md` | The datasets, the bands, the access rules |
| `docs/decisions.md` | The decision log, with the reason for each |
| `docs/visualization.md` | The three views, and which one needs a map |

Read `ROADMAP.md` before you start work on a phase. It gives the
measurement that each phase must produce. A phase is not complete
until it produces that measurement.

Read `docs/glossary.md` before you name a new function or a new
column. Use the term that the glossary gives.

## Language

Write in ASD-STE100 Simplified Technical English. This applies to
documentation, code comments, docstrings, commit messages and
replies to the user.

The primary rules:

- Write short sentences. Use a maximum of 20 words for an
  instruction. Use a maximum of 25 words for a description.
- Give one instruction in one sentence.
- Use the active voice.
- Use the simple present, past or future tense.
- Do not use the `-ing` form of a verb, unless it is a technical
  name.
- Keep the articles `a`, `an` and `the`. Do not remove them to make
  a sentence shorter.
- Use the same word for the same thing every time.
  `docs/glossary.md` holds the approved terms.
- Do not put more than three nouns together.
- Keep a paragraph to a maximum of six sentences.
- Use a vertical list for complex information.
- Start a warning with the command that prevents the problem.

**Exception.** `README.md` and `ROADMAP.md` use a different style on
purpose. Keep that style when you edit them. Do not rewrite them
into Simplified Technical English.

## Commands

The `justfile` is the authority. It defines how each tool runs. The
pre-commit hooks and the CI workflow both call these recipes, so the
three paths cannot diverge.

| Command | Action |
| --- | --- |
| `just` | Show the available recipes |
| `just setup` | Sync the environment and install the hooks |
| `just fmt` | Format the code |
| `just lint` | Run the linter |
| `just typecheck` | Run the type checker |
| `just test` | Run the unit tests only |
| `just test-integration` | Run the tests that read live S3 |
| `just test-all` | Run every test |
| `just check` | Run lint, typecheck and unit tests. CI runs this |

Call the recipes. Do not call `ruff`, `mypy` or `pytest` directly.
A direct call can use different arguments from CI and can give a
different result.

## Git workflow

All work happens on a branch. `main` is protected.

1. Create a branch from `main`. Name it `<type>/<short-description>`.
2. Make small commits. One commit does one thing.
3. Push the branch and open a pull request.
4. CI must pass. Then squash and merge.

**Do not commit to `main` directly.**

### Commit messages

Write every commit message in the Conventional Commits format:

```
<type>(<optional scope>): <description>

<optional body: the reason for the change>
```

The types are `feat`, `fix`, `docs`, `chore`, `refactor`, `test`,
`perf`, `build`, `ci` and `revert`.

A `commit-msg` hook rejects a message that does not match. Run
`just setup` to install it. `pre-commit install` alone does not
install a `commit-msg` hook, so a manual install misses it.

Rules for the message:

- Write the description in the imperative mood. Write `add the byte
  counter`, not `added the byte counter`.
- Do not put a full stop at the end of the description.
- Give the reason in the body. The diff shows what changed. Only the
  body can show why.
- Reference the phase when a commit belongs to one. Write
  `feat(phase2): ...`.

## Code rules

- `uv` manages the environment. Add a dependency with `uv add`. Do
  not edit `pyproject.toml` dependency lists by hand.
- The type checker runs in strict mode. Add type annotations to
  every function.
- Put fast tests that need no network in `tests/unit/`. The commit
  hook runs them.
- Put tests that read live S3 or that need a GPU in
  `tests/integration/`. These tests must skip when the credentials
  are absent. They must not fail.
- Keep the commit hook fast. A slow hook causes a developer to use
  `--no-verify`, and then the hook protects nothing.
- Do not commit imagery, chips or Parquet output. `.gitignore`
  excludes them. Commit the run records in `results/`.

## Constraints to respect

- Compute every area figure in EPSG:5070. A per-tile UTM area is not
  comparable across the three tiles.
- Derive a chip identifier. Do not assign one. A restart must produce
  the same identifier for the same chip.
- Use one byte counter for every measurement. Two counters make the
  result tables incomparable.
- Generate the result tables in `README.md` from `results/`. Do not
  edit the numbers by hand.
