# Conventions

Rules for identifiers, coordinate systems and recorded output. Phase
0.5 builds the code that enforces them. Every later phase depends on
them.

## Coordinate systems

Three coordinate systems, each with one job.

| Purpose | CRS | Reason |
| --- | --- | --- |
| Read | The native UTM of the MGRS tile | No reprojection on the read path |
| Write | EPSG:4326 | The GeoParquet specification expects it |
| **Area** | **EPSG:5070, CONUS Albers** | **Equal area. UTM area is not comparable across tiles** |

**Compute every area figure in EPSG:5070.** Scar area against time
is the headline result. A UTM area is correct inside one zone and
wrong across the three tiles. This error is silent, so the code must
prevent it.

Record the CRS in the column name when a column holds a geometry.

## Identifiers

**Derive an identifier. Do not assign one.** A restart must produce
the same identifier for the same input. Phase 10 depends on this.

| Identifier | Derived from |
| --- | --- |
| chip ID | The MGRS tile, the date, the chip row, the chip column |
| run ID | The hash of the frozen configuration |
| scar ID | The connected component of the scar over time. See below |

A chip ID is stable across runs, across machines and across code
versions. A scar ID is not. A scar ID depends on the segmentation
output, so it changes when the model or the threshold changes.
Record the run ID beside every scar ID.

## The scar ID

The scar ID solves a second connected-components problem, over time
instead of space.

1. Phase 5 unions chip polygons into one scar for one date.
2. A scar at date `t` links to a scar at date `t+1` when the two
   overlap by more than a threshold.
3. The connected components of that link graph are the scar IDs.

Record the threshold in `decisions.md` when you choose it.

The reburn split in phase 9 is a deliberate cut in this same graph.
A scar that recovers and then darkens again is two scars, not one.
Design the link and the cut together.

## Configuration

One immutable configuration object controls one run. The hash of
that object is the run ID.

- Do not read a constant from module scope. Put it in the
  configuration.
- A sweep is a list of configuration objects. A sweep is not a set
  of edited constants.
- Record the configuration beside the result. A number without its
  configuration is not a measurement.

## Run records

Every run appends one row to `results/`. Commit the file.

| Field | Content |
| --- | --- |
| `run_id` | The configuration hash |
| `git_sha` | The commit that produced the run |
| `config` | The full configuration |
| `machine` | The host that ran it |
| `extent` | The tiles, the dates, the band count |
| `bytes_read` | The bytes that arrived over the network |
| `bytes_needed` | The bytes that the pipeline used |
| `wall_seconds` | The elapsed time |
| `chips_per_second` | The inference rate |
| `gpu_utilization` | The mean GPU use, when a GPU ran |

`bytes_read` divided by `bytes_needed` is the read amplification.
Both fields are necessary. One field alone hides the waste.

## The byte counter

**Use one byte counter for every measurement.** Two counters make
the rows of the result table incomparable, and the table is the
output of the project.

`rasterio` does not report bytes over the network. The method:

1. Set `CPL_DEBUG=ON`.
2. Capture the GDAL VSICURL log through a Python error handler.
3. Sum the byte ranges of the requests.

Validate the counter once against process-level network counters, on
a read of known size. Then trust it.

Keep a second, analytic count: the number of windows multiplied by
the block size. It does not replace the primary counter. It catches
a read that the pipeline drops without an error.

## Result tables

The tables in `README.md` are generated. `just report` rebuilds them
from `results/`.

**Do not edit a number in `README.md` by hand.** A hand-edited table
stops matching the code that produced it, and no reader can tell.

## Versions across the cluster

The two nodes use different processor architectures. That is
acceptable. Different Python versions or different Ray versions are
not. Pin both. Phase 6 fails in a confusing way when they differ.
