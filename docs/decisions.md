# Decision log

Each entry gives the decision and the reason. A decision without a
reason is a decision that somebody undoes by accident.

Add an entry when you make a choice that a later reader could
reverse. Do not delete an entry. Mark it superseded and add the new
one.

---

## 2026-08-26. The observation window is 2017-07 to 2025-06

Sentinel-2B reached operations in July 2017. Before that date the 2
to 3 day median revisit is not true, and temporal density is the
analysis.

The window opens weeks before the Thomas Fire, which burned
approximately 114,000 hectares of Ventura and Santa Barbara
chaparral in December 2017. That fire gives one large, well-mapped
scar with seven and a half years of observation after it.

The window closes after the January 2025 Palisades and Eaton fires,
while those scars are still fresh.

**Why the fresh scars matter.** The model was fine-tuned on fresh
scars, so the 2025 fires are the in-distribution end of the corpus.
Old scars carry the recovery curve. Fresh scars are the standing
check that a disappointing curve shows the ground recovers, and does
not show the model degrades.

---

## 2026-08-26. Phase 1 resolves the MGRS tiles, not the plan

The three tiles cover a belt in UTM zone 11: Ventura and Santa
Barbara, then the Santa Monica and San Gabriel front, then the San
Diego backcountry.

Take the exact tile identifiers from the STAC search. Do not guess
them.

Selection criteria, in order:

1. Chaparral fraction, from WorldCover. Chaparral recovers in 5 to
   10 years, which fits inside the archive. Conifer takes decades
   and shows only the start of the curve.
2. The count of MTBS fires that ignite in the first two years of the
   window. A fire late in the window has no recovery to measure.
3. A low ocean fraction and a low urban fraction. Both waste read
   bandwidth.
4. Tiles that share an edge. The phase 5 union must run across two
   tiles, not only inside one.

---

## 2026-08-26. The phase 0 gate is a median per-chip IoU of 0.50

Score the model against rasterized MTBS perimeters, over
approximately 20 chips.

**Median, not mean.** One perimeter with a large unburned interior
must not fail the gate alone.

**Fresh scars only, less than one year after ignition.** A recovered
scar that scores badly is ambiguous. It can mean the model is
broken, or it can mean the scar recovered. The second is the signal
that the project measures. Fresh chips separate the two.

**Why 0.50 and not a higher number.** An MTBS perimeter encloses
unburned islands, so a correct model has a ceiling of approximately
0.6 to 0.7. A pass mark of 0.50 is approximately three quarters of
the achievable score. A higher bar fails a model that works.

**Why the number is written down first.** Twenty chips look
approximately correct. Approximately correct always passes when
somebody sets the bar afterwards. The failure branch is expensive,
so the pressure to pass is real.

**What the gate does not test.** It does not test partly recovered
scars. Those are out of distribution, and no change fixes that
without training. The dNBR control ring is the independent
measurement that covers them. Do not extend the gate.

---

## 2026-08-26. Phase 0.5 builds the instrument before phase 1

The project produces nine table rows, approximately a dozen
measurements for each phase, two machines and several sweeps. No
code records any of it.

Phase 0.5 builds the byte counter, the run record, the `results/`
convention, the table generator, the frozen configuration, the
configuration hash and the chip identifiers.

**Why before phase 1 and not inside it.** An instrument built inside
phase 1 takes the shape of phase 1 alone. Phase 2 then reworks it,
and the two phases produce numbers that nobody can compare.

See `conventions.md` for the detail.

---

## 2026-08-26. Every area figure uses EPSG:5070

Scar area against time is the headline result.

HLS tiles arrive in the native UTM of the MGRS tile. A UTM area is
correct inside one zone. Across the three tiles it is not
comparable, and the error is silent.

GeoParquet output stays in EPSG:4326, which the specification
expects. Only the area computation moves to EPSG:5070.

---

## 2026-08-26. The justfile is the single source of truth for tools

The pre-commit hooks and the CI workflow both call `just` recipes.
Neither one names `ruff`, `mypy` or `pytest` directly.

**Why.** A pre-commit configuration that pins its own tool versions
drifts from the justfile. A CI workflow that spells out its own
arguments drifts from both. Then a commit passes the hook and fails
CI, and nobody can see the reason.

The standard hygiene hooks still come from `pre-commit-hooks`
upstream. There is no duplication risk in a whitespace check.

---

## 2026-08-26. The commit hook runs unit tests only

`tests/unit/` holds fast tests that need no network. The commit hook
runs them.

`tests/integration/` holds the tests that read live S3 or that need
a GPU. They skip when the credentials are absent. They must skip and
must not fail, so that a fork can run CI.

**Why separate trees and not only markers.** The hook must not
import a network-dependent module to then deselect it. Path
separation keeps collection fast.

**Why the hook must stay fast.** A slow hook causes a developer to
use `--no-verify` as a habit. Then the hook protects nothing.

---

## 2026-08-26. Three views. Python for the gates, TypeScript for the artifact

Full detail in `visualization.md`. The reasoning, in short:

**Views A and B need no map, because both use a fixed extent.** A
chip is already pixel space. The scar recovery view fixes its extent
from the first date and never moves it, so Python projects the
polygon to pixel coordinates once, at export. The browser then draws
an image and an SVG path in one coordinate frame.

**View C needs deck.gl.** Every scar over three tiles and eight
years, over a basemap, with pan and zoom, is runtime reprojection
plus tiles plus a large feature count. That is the workload a map
library exists for.

**Python for phases 0, 4 and 5. TypeScript for phases 9 and 11.**
The gates are a dev loop where the picture must arrive in 30
seconds, and the code is throwaway. The phase 11 output is a
published artifact that a reader sees. A web application to inspect
20 chips during a gate is the tail that wags the dog. A notebook
screenshot as the headline artifact is the same error reversed.

**A superseded draft proposed FiftyOne, lonboard and Panel for
everything.** That was wrong. It applied a "do not rebuild dataset
tooling" heuristic without checking it against this project's scale.
The phase 0 gate looks at approximately 20 chips, where per-chip IoU
is three lines of NumPy, and FiftyOne carries a MongoDB that would
sit between a reader and the phase 11 reproduce path. The correction
is not "never use a library". It is match the tool to the scale,
which is why View C still uses deck.gl.

**A structural benefit of the browser.** A web application cannot
import a pipeline stage and cannot read S3. The rule that the viewer
stays outside the measured path stops being something a developer
must remember, and becomes a property of the architecture.

---

## 2026-08-26. The GDAL debug log does not measure bytes

`conventions.md` prescribed a byte counter that reads GDAL's VSICURL
debug log and sums the `Downloading a-b` ranges. Phase 0.5 built it
and validated it against a public Copernicus DEM COG, which needs no
Earthdata login. **The validation failed.**

GDAL emits that line only for a chunk it pulls into its cache. Bulk
data transfer produces no line at all. A 256 pixel window and a 1024
pixel window both report 16384 bytes, the header fetch alone, while
the larger read returns a full float32 block with a million distinct
values.

The counter is kept, because the request count and the header fetch
are real and useful. It carries a warning, and the gap is pinned by
a strict `xfail` test, so a GDAL upgrade that fixes it fails loudly
rather than passing unnoticed.

**Why this matters more than one broken module.** Every row of the
read-path table is a byte count. An instrument that under-reports
would have made every pushdown look better than it is, and the
project's headline conclusion is a ratio of bytes to compute. This is
the argument for phase 0.5 existing at all, and it paid for itself
before phase 1 read anything.

**Superseded in scope by the entry below.** The question was
"how do we observe bytes?". The better question was "which rows need
observation?", and the answer turned out to be one of them. A local
counting proxy remains the candidate for that row, in phase 2.

---

## 2026-08-26. Compute the pushdown rows. Observe only the alignment row

Supersedes the search for a single replacement byte counter. The
failure above asked "how do we observe bytes?". The better question
was "which rows actually need observation?", and the answer is one
of them.

Four of the five read-path rows are set arithmetic. Which tile-dates
survived the predicate, which six assets were projected, which chips
the probe kept. The cost of a subset is the sum of the sizes of the
files in it, and a HEAD request gives each size exactly.

**Computed is the better instrument here, not a fallback.** The
project claims that bytes saved by a pushdown holds at any link
speed while seconds belong to one machine. A figure derived from
file sizes has exactly that property. A figure observed on one
domestic connection has it less.

Read amplification is the exception. The gap between blocks needed
and bytes fetched comes from GDAL's fetch granularity, and a model
of that is a hypothesis rather than a measurement. That row is
observed, and it is the only one that needs a wire counter.

**What this changes.** The wire-observation problem shrinks from
"the whole table" to "one row", and it moves to phase 2 alongside
the COG alignment work it serves. Sub-file accounting needs
`TileByteCounts` from the TIFF header, since a COG is compressed and
a block's size on the wire is not its size in memory. `rasterio`
does not expose that tag, so it needs a header parse. Also phase 2.

**Provenance is recorded, not implied.** `RunRecord.accounting` is
one of `analytic`, `wire` or `both`, and the generated table has a
Source column. A computed number presented as a measurement would be
the same drift the generated tables exist to prevent.

Credit where due: this came from the question "don't we know how
large the file is?". We do, and the first draft had reached for a
proxy without asking it.

---

## 2026-08-26. GDAL's VSICURL cache is process-global

Found during the same validation. A second read of the same byte
ranges inside one process costs zero.

A benchmark that re-reads a tile in one process therefore records a
saving that is entirely cache and not a pushdown. Every measured run
must use a fresh process, or must set `CPL_VSIL_CURL_NON_CACHED`.

Phase 2 already lists `VSI_CACHE` as a knob to measure. This
promotes it from a tuning knob to a correctness concern.

**A second, related finding: GDAL's read-ahead adapts.** The same
logical read costs 16384 bytes in a fresh process and 32768 bytes in
a process that has already read something, and in both cases it is
**one** request rather than two. GDAL widens the range it asks for
once it has seen prior activity.

So a byte figure carries a dependence on process history from two
directions: the cache makes a repeat read free, and the read-ahead
makes a first read wider. Both point the same way. **Measure in a
fresh process**, and treat any benchmark that reuses one as
reporting the process, not the pipeline.

---

## 2026-08-27. Ray Workflows is removed. Use the completion manifest

Evaluated as a durable-execution layer, so that a killed run could
resume from the last finished step. **It cannot be used.**

`ray.workflow` was deprecated in Ray 2.44 and removed. The last
release that contains it is `ray==2.47`. This project pins ray
2.58.0, where the import raises:

```
RuntimeError: The experimental Ray Workflows library was deprecated
in Ray 2.44 and has been removed.
```

It never left `stability="alpha"` in its lifetime. Documentation
pages for it still exist and are stale, so check the installed
package rather than the docs.

**Why it went, from the Ray team.** It was dropped rather than
superseded: "We do not plan to replace this functionality. The Ray
team is already at more than full capacity maintaining Ray and the
other GA libraries." It shipped in Ray 1.7 in October 2021 and was
still alpha when it was removed, so adoption never justified the
maintenance cost beside Core, Data, Train, Tune and Serve.

The team names Airflow and Temporal as the closest analogs, and says
plainly that the Anyscale platform does not replace it either.

**The distinction that matters here.** Ray Core still has fault
tolerance through lineage reconstruction: a dead worker's task is
re-executed and the job continues. What Ray never had, and now will
not have, is durability across a *driver* crash. Killing the whole
job and resuming it tomorrow is phase 10's requirement, and no Ray
feature covers it.

So the completion manifest is not a workaround for a missing
library. Ray has drawn its boundary at "execution engine" and
pushed durable execution out to orchestrators. For a 4.2 hour run,
a file listing finished partitions is the proportionate tool.
Temporal is built for long-running business workflows, and Airflow
would be a scheduler with nothing to schedule.

**Nothing changes.** Phase 10 already specifies idempotent tasks,
per-partition output and a completion manifest, which gives the same
resume property with no dependency, and a text file is inspectable
in a way a checkpoint store is not.

Do not reopen this without checking `import ray.workflow` against
the pinned version first.

---

## Open decisions

These need data. Do not decide them in advance.

| Decision | Phase | Note |
| --- | --- | --- |
| The three MGRS tile identifiers | 1 | Criteria above |
| The Fmask bits that disqualify a pixel | 2 | Cloud shadow looks like a scar |
| The clear-fraction threshold for a chip | 2 | Record the drop rate for each choice |
| The stride | 4 | The smallest halo that removes the edge artifacts |
| The scar link overlap threshold | 5 | See `conventions.md` |
| The exact Prithvi checkpoint | 0 | Pin it, or a gate failure is ambiguous |
| Wire byte observation | 2 | Needed only for the alignment row. A local counting proxy is the candidate |
| TIFF `TileByteCounts` parse | 2 | Sub-file accounting. `rasterio` does not expose the tag |
