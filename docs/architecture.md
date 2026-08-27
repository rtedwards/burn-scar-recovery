# Architecture

How the phases in `ROADMAP.md` map onto modules, and the rules that
keep the map true.

## Layers

Each layer may import the layers above it. It must not import the
layers below it.

| Layer | Modules | Job |
| --- | --- | --- |
| Foundation | `config`, `log` | What the machine provides |
| Primitives | `bands`, `crs`, `ids` | Domain facts. No IO |
| Instrument | `runs`, `sizes`, `byte_counter`, `report` | What a run did, and what it cost |
| Stages | `stac`, `read`, `chip`, `infer`, `vectorize`, `union`, `write` | One step of the pipeline |
| Driver | `cli`, `pipeline` | Composition, distribution, recording |

**Two rules, and a test enforces both.**

1. A stage must not import the instrument.
2. A stage must not import `ray`.

Rule 1 exists because a stage that can write a run record eventually
will, and then the measurements are scattered across eleven phases
with no single place to read them.

Rule 2 exists because a stage that imports `ray` cannot be tested
without a Ray runtime, and the commit hook runs the unit tests.

`tests/unit/test_architecture.py` walks the import graph and fails
if either rule breaks. The rule is enforced, not described.

## Ray owns the plumbing. Our functions own the batch

Ray Data does the work it is good at:

- the object store, and zero-copy transport between stages
- batching, streaming execution and backpressure
- actor pools, including GPU actors that load the model once
- its own readers where they fit: `read_parquet` for the manifest,
  `write_parquet` for the output

Our code supplies only the function that transforms one batch:

```python
# In a stage module. No ray import.
def decode(batch: dict[str, np.ndarray]) -> dict[str, np.ndarray]: ...


# In the driver. This is where ray lives.
dataset.map_batches(decode, batch_size=64)
```

**This is not a compromise against Ray.** It is the idiomatic Ray
Data pattern. The stage keeps the object store, the backpressure and
the actor pool, and it stays callable directly with a dictionary of
arrays, which is what keeps the unit tests hermetic and fast.

The GPU stage is a class rather than a function, because the model
must load once for each actor. Ray Data takes a class the same way,
and `__call__` is still directly testable.

**One reader has to be ours.** Ray Data has no reader for HLS COGs
over `/vsicurl/`, so phase 2 writes that as `map_batches` over
manifest rows. It distributes identically to a built-in reader.

The interesting parts of Ray sit in the driver, which is where
phases 3 and 6 do their work: backpressure, the actor ratio, object
store spilling, and cross-node transfer.

## A stage is a function over a partition

```python
stage(config: RunConfig, partition: Partition, data: T) -> tuple[U, StageStats]
```

No classes with a `run` method. No module-level state. No globals.

A **partition** is the unit of restartable work, probably
`(tile, date)`. It appears now rather than at phase 10, because
adding it to a stage signature later means changing every stage.

A stage returns its data and its statistics together. Statistics are
counts the stage alone can know: chips planned, chips dropped by the
probe, polygons produced. They are not measurements of the machine.

## The instrument is ambient

The driver wraps each stage. It times the call, counts bytes around
it, collects the returned statistics, builds one `RunRecord` and
appends it to `results/`.

So exactly one place writes a measurement.

A stage never opens `results/`. It never imports `runs`. It reports
what it did by returning it.

## What persists, and what does not

| Boundary | Form | Why |
| --- | --- | --- |
| Phase 1 output | GeoParquet manifest on disk | Small. Restart reads it |
| Phase 2 to 5 | In-memory batches | 377 GB. See below |
| Phase 8 output | GeoParquet on disk | The product |
| Completion record | A manifest of finished partitions | Phase 10 restart |

**Chips never persist.** That is the "never pre-download the corpus"
rule, expressed as an architectural constraint rather than a policy
somebody has to remember. Pixels stream in, polygons come out,
pixels are discarded.

The 10 GB chip cache is the one exception, and it is an instrument.
It exists to answer how fast the card goes when nothing starves it.
It is not a stage boundary and no stage reads it by default.

## No orchestrator

Airflow, Dagster and Prefect are schedulers. They own when a job
runs, retries across runs, backfills, and a DAG of coarse tasks.
They do not move data.

Ray is an execution engine. It owns how one job spreads across cores
and nodes.

They compose, and this project needs only the second one. There is
one pass over an archive, run a few times: the benchmark subset
repeatedly, the production run once. No schedule. No backfill. No
DAG across teams.

An orchestrator would add a scheduler, a metadata database and a web
server, and would put a layer between the reader and the thing the
project measures, which is a producer and consumer rate mismatch.

Phase 10 needs idempotent tasks, per-partition output and a restart
that skips finished work. The partition and the completion manifest
give that, and both are inspectable in a way a task-state database
is not.

**Ray Workflows is not an option either.** It was the obvious
in-cluster answer for durable execution, but it was removed in Ray
2.44 and this project pins 2.58, where the import raises. See
`decisions.md`.

## The productionization seam

This project is a research result and a throughput measurement, not
a service. But the layering above leaves one clean seam, and it
costs nothing to keep open.

An orchestrator sits **above** Ray and submits a job. It never learns
what a chip is.

| Changes | Does not change |
| --- | --- |
| A scheduler above Ray | Any stage |
| A STAC sensor, for new granules | Any primitive |
| Job submission instead of a local driver | The manifest format |
| Alerting and cost control | The output format |

**The production shape is incremental, not periodic.** HLS grows: new
granules land every 2 to 3 days. A production version does not rerun
the batch on a schedule. It asks CMR-STAC for tile-dates newer than
a watermark, makes those the partitions, and appends to the
year-partitioned GeoParquet from phase 8.

That needs idempotent tasks, per-partition output, a completion
manifest and retry with backoff. **That is phase 10 exactly.** So
phase 10 is not reliability decoration. It is the prerequisite, and
it is already in the plan.

Keep the seam clean. Say in the writeup that it exists. Do not build
the orchestrator on speculation.

## The package root stays light

`burn_scar_recovery/__init__.py` re-exports the foundation, the
primitives and the instrument. It does **not** re-export a stage.

`infer` imports torch, which costs seconds. The commit hook runs the
unit tests, so `import burn_scar_recovery` must stay cheap.

**This is not a lazy import.** Every module imports what it needs at
its own top level. The package root simply does not name the heavy
ones, so a caller that wants a stage imports it by path:

```python
from burn_scar_recovery.infer import BurnScarModel
```

## Configuration comes from a file

A sweep is a list of configurations. It is never a set of edited
constants, and it is never a shell loop over command-line flags.

```
bsr run --config sweeps/stride-176.toml
```

`RunConfig` validates the file through `pydantic-settings` with a
TOML source.

**The environment source is disabled for `RunConfig`.** Its hash is
the run identifier, so an environment variable that could feed into
it would let a machine silently change a run's identity. `Settings`
keeps the environment source, because credentials and paths are
exactly what it is for.

That split is the same one recorded in `conventions.md`: `Settings`
holds what a machine provides, `RunConfig` holds what an experiment
decides.
