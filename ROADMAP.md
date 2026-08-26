# Roadmap

Build order, measurements, and the decisions already made.

## Three rules

**The analysis makes the engineering necessary.** One scene on one
date needs no predicate pushdown. Eight dense years needs all of it.
Never measure pushdowns on a workload too small to want them.

**The polygon is the measurement.** Segment on every date and let
the polygon shrink from its edges as vegetation returns. Do not
segment once and compute statistics inside a fixed shape.

**Do not train anything.** The model is a load generator. Phase 0 is
a gate. Failing it changes the source or the area of interest, never
the weights.

## The workload

One pass. Dense in time, full spatial extent, three tiles.

| Quantity | Value |
| --- | --- |
| MGRS tiles | 3, southern California chaparral belt, UTM zone 11 |
| Window | 2017-07 to 2025-06 |
| Years | 8 |
| HLS revisit, median | 2 to 3 days |
| Tile-dates | ~3,600 |
| Tile-date, 6 bands, int16, uncompressed | ~161 MB |
| Naive bytes | ~580 GB |
| Chips per tile-date, 224 chip / 192 stride | ~363 |
| Naive inferences | ~1.31 M |
| After the Fmask probe (~35% dropped) | ~377 GB, ~850 K chips |

**The ratio that is the whole project.** At 25 MB/s, 377 GB takes
about 4.2 hours to read. At a few hundred chips per second, 850 K
inferences take under half an hour. Roughly nine parts IO to one
part compute. Measure the real figures and quote them.

**Why dense in time and narrow in space.** Temporal density gives
per-date recovery curves, ignition dates to within the revisit
interval, and fires below the MTBS size threshold. Pruning to known
perimeters would buy speed by using the answer, which is fine for a
recovery study and circular for a discovery claim. Cutting from six
tiles to three buys the same speed and costs only statistical power.

**Why this window.** Sentinel-2B reached operations in July 2017,
which is the first date the 2 to 3 day revisit claim is actually
true. Starting there also opens the window weeks before the Thomas
Fire, roughly 114,000 ha of Ventura and Santa Barbara chaparral,
which gives one large well-mapped scar followed for seven and a
half years. Closing in mid-2025 catches the January 2025 Palisades
and Eaton fires while their scars are still fresh.

That last point matters more than it looks. Fresh scars are what
the model was fine-tuned on, so they are the in-distribution end of
the corpus. Old scars carry the recovery curve; fresh scars are the
standing check that a disappointing curve is the ground recovering
and not the model degrading.

**The three tiles are resolved in phase 1, not guessed here.** The
belt runs Ventura and Santa Barbara, then the Santa Monica and San
Gabriel front, then the San Diego backcountry. Take the exact MGRS
IDs from the STAC search. Selection criteria, in order: chaparral
fraction per WorldCover, count of MTBS fires igniting in the first
two years of the window, low ocean and urban fraction, and tiles
that share edges so the phase 5 union is exercised across tiles and
not only within one.

**Spatial pushdown is measured, not applied.** Report what pruning
to MTBS perimeters would have saved on the read path. Then
demonstrate it at query time against the written GeoParquet, in
phase 8, which is where a query engine does it.

## Never pre-download the corpus

The pipeline reads from S3 and stays IO bound. That is the subject,
not an accident.

Pulling 580 GB to disk first and then measuring "what the pushdowns
saved" pays the exact cost the pushdowns exist to avoid. Against
local NVMe the savings shrink to nothing and the table becomes a
simulation. Range requests, the concurrency knee, HTTP multiplexing
and latency-bound small reads all disappear too.

**The cache is an instrument, not a data store.** About 10 GB, some
twenty thousand chips, on NVMe. It answers one question: how fast
does the card go when nothing starves it? Without that ceiling the
bandwidth gap cannot be computed, because it is never observed.

**Split the benchmark runs from the production run.**

| Run | Extent | Bytes | At 25 MB/s | Purpose |
| --- | --- | --- | --- | --- |
| Benchmark subset | 1 tile, 1 year | ~24 GB | ~16 min | every table row, every sweep |
| Production | 3 tiles, 8 years | ~377 GB | ~4.2 h | once, at the winning config |

**Report bytes first, seconds second.** Bytes saved by each pushdown
is a property of the pipeline. Seconds are a property of the machine
it ran on.

## Hardware

| Machine | Role |
| --- | --- |
| MacBook M1 Max | dev; CPU preprocessing node in the cluster |
| Ryzen 5900X + RTX 5070 | GPU node; both benchmark environments |

Together they form a two-node heterogeneous Ray cluster with a
network between producer and consumer, which is the subject of the
project.

**Check in phase 0, not phase 7.** The 5070 is Blackwell, compute
capability sm_120. It needs a PyTorch built against CUDA 12.8 or
later (verify). An older wheel carries no kernels for it and fails
in a confusing way.

## Two benchmark environments, deliberately

| Environment | Bound by | What it measures |
| --- | --- | --- |
| Remote, HLS over S3 | read bandwidth | every pushdown, in wall-clock |
| Local NVMe cache | GPU throughput | actor ratio, batch size, fp16 ladder |

Expect GPU tuning to buy nothing in the remote environment. Say so
plainly.

An IO-bound conclusion can read as an alibi for a starved card. It
stops being one when the GPU is saturated in the cached environment,
the full tuning ladder runs there, and a number is attached to the
bandwidth requirement. A conclusion with a figure is a finding.
Without one it is an excuse.

## Source and bands

**HLS, 30m, one grid.** HLSL30 from Landsat 8/9 and HLSS30 from
Sentinel-2, both atmospherically corrected, BRDF-normalised,
bandpass-adjusted, resampled onto the Sentinel-2 MGRS grid.

Six bands, matching the model: blue, green, red, narrow NIR, SWIR1,
SWIR2. Fmask ships as the QA band for the cloud probe.

**Why not raw Sentinel-2.** The burn scar head was trained on HLS,
so HLS removes the domain gap and the normalisation statistics apply
as-is. That is why zero-shot has a chance. Combining Landsat with
Sentinel-2 also cuts median revisit from 5 days to 2 or 3.

**What it costs.** Resolution drops from 20m to 30m, which barely
matters for scars measured in thousands of hectares. The Fmask probe
is 1 band of 6 rather than 1 of 15, so the two-phase read saves
about 17% rather than about 7%. Access needs an Earthdata Login and
the data sits in AWS us-west-2. NASA does not usually charge egress,
but verify before assuming zero.

## Phases

### Phase 0. Gates (1 day)

Three gates. Fail any and the plan changes, not the model.

- **Toolchain.** PyTorch with CUDA 12.8+ on the 5070. One forward
  pass. Do this before anything else.
- **Access.** Earthdata Login, CMR-STAC search returning HLS hrefs,
  one windowed read over `/vsicurl/`. Confirm egress terms.
- **Model.** Run the Prithvi burn scar head zero-shot on ~20 chips
  over known MTBS fires. Score against rasterised MTBS.
  - **Pass mark: median per-chip IoU at or above 0.50.** Median, not
    mean, so one perimeter with a large unburned interior cannot
    sink the gate on its own.
  - **Fresh scars only, under a year post-ignition.** A recovered
    scar scoring badly is ambiguous. It could mean the model is
    broken or it could mean the scar recovered, which is the thing
    being measured. Fresh chips separate those.
  - Passes: stop, move on.
  - Fails: vary chip size and normalisation, then the area of
    interest. Do not train.

**Why 0.50 and not higher.** MTBS perimeters are operational fire
boundaries. They enclose unburned islands and are not per-pixel
burn maps, so a correct model has a ceiling against them somewhere
around 0.6 to 0.7. A bar of 0.50 is roughly three quarters of what
is achievable. Set it higher and a working model fails.

**Why the number is written down first.** Twenty chips will look
roughly right. Roughly right always passes when the bar is set
afterwards, and the failure branch here is expensive, so there is
real pressure to call it a pass. Decide before looking.

**What this gate does not test.** Behaviour on partly recovered
scars. That is known to be out of distribution, it is unfixable
without training, and it is exactly why the dNBR control ring
exists as a second independent measurement. Do not extend the gate
to cover it.
- Confirm the model's input size (verify; likely 224). Pick the
  stride. Stride is the halo knob, see phase 4.
- Pull MTBS perimeters, Copernicus DEM, ESA WorldCover.

### Phase 0.5. The instrument (½ day)

Every later phase writes into this. Nine table rows, a dozen
measurements per phase, two machines and several sweeps. Build the
recording layer once, before phase 1 produces the first number.

- **The byte counter.** Bytes are the primary metric and nothing
  reports them yet. `rasterio` does not expose bytes over the wire.
  Capture GDAL's VSICURL range-request log through a Python error
  handler under `CPL_DEBUG=ON` and sum the ranges. Validate it once
  against process-level network counters on a known read, then
  trust it. Also keep the analytic count, windows times block size,
  as a cross-check that catches silently dropped reads.
- **One instrument, every row.** The same counter has to produce
  every figure in the read-path table or the rows are not
  comparable and the table means nothing.
- **The run record.** One row per run: config hash, git SHA,
  machine, extent, bytes read, bytes needed, wall time, chips per
  second, GPU utilisation. Append to `results/`. Commit it.
- **Tables are generated, not typed.** A `just report` recipe
  rebuilds the README tables from `results/`. Hand-edited markdown
  across four weekends is how numbers stop matching the code that
  produced them.
- **Frozen config, hashed.** One immutable config object per run.
  Its hash is the run ID. A sweep is a list of configs, not a set
  of edited constants.
- **Deterministic chip IDs.** `(tile, date, row, col)`, derived not
  assigned. Phase 9 joins on them across dates and phase 10 needs
  them stable so a restart can skip finished work.
- **CRS conventions, fixed now.** Read in the tile's native UTM.
  Write GeoParquet in EPSG:4326. **Compute every area figure in
  EPSG:5070, CONUS Albers.** Area against time is the headline
  result and per-tile UTM areas are not comparable across the belt.

### Phase 1. Predicate pushdown (½ day)

- `pystac-client` against CMR-STAC to a GeoParquet manifest: ID,
  band hrefs, footprint, CRS, scene cloud cover.
- **Measure:** tile-dates matched against tile-dates in the archive.
  Bytes read: zero.
- Also compute, without applying it, what a spatial pushdown to
  buffered MTBS perimeters would have pruned.
- Cheapest and largest win in the pipeline.

### Phase 2. Windowed reads, the cloud probe, the cache (2 days)

- `rasterio` windowed reads over `/vsicurl/`, band subset only.
- Align windows to COG internal tile boundaries. Measure read
  amplification with and without alignment. This is the raster
  version of reading a whole row group to get three columns.
- **The two-phase read.** Scene-level cloud cover is the obvious
  pushdown. Go one level further. Read Fmask first, one band, decide
  per chip, then fetch the six model bands only for clear chips.
  Cheap column first, expensive column second.
- **Define "clear" explicitly, and write it down.** Which Fmask bits
  disqualify a pixel, and what fraction of clear pixels a chip needs
  to survive. Cloud shadow deserves its own decision: shadow over
  chaparral is dark and reads like a burn scar, so treating it as
  clear manufactures false positives that phase 9 then measures as
  recovery. Record the chip drop rate for each choice.
- Set and measure the GDAL variables one at a time:
  `GDAL_DISABLE_READDIR_ON_OPEN`, `GDAL_HTTP_MULTIPLEX`, `VSI_CACHE`,
  `CPL_VSIL_CURL_ALLOWED_EXTENSIONS`.
- **Measure:** bytes fetched against bytes needed, requests per
  second, chips dropped by the probe. Small reads are latency bound,
  so scale concurrency and find the knee.
- **Build the instrument cache.** About twenty thousand chips to
  NVMe, roughly 10 GB. Not the corpus.

### Phase 3. Ray Data, one node, CPU only (2 days)

Chipping comes from phase 4, so build the chip planner first or
stub it. The ordering here is by risk, not by dependency.

- `ray.init()` on the M1 Max. Real actors, real backpressure, no
  cluster yet.
- `map_batches` with a CPU preprocessing pool and an inference pool.
  Run the model on CPU for now.
- **Induce the OOM deliberately.** Remove backpressure, let the
  producer outrun the consumer, watch the object store grow, then
  fix it with bounded queues. Write down what the failure looked
  like. It is a producer/consumer rate mismatch, and it is not the
  shuffle OOM a groupby produces.
- **Measure:** throughput, and the actor ratio that saturates the
  consumer.

### Phase 4. Chips, stride, masks (1 day)

A fixed-input ViT cannot take a halo for free. The input stays at
224, so the halo comes out of the stride, and every pixel of it
costs read amplification.

| Stride | Halo each side | Read amplification |
| --- | --- | --- |
| 208 | 8 | 1.16x |
| 192 | 16 | 1.36x |
| 176 | 24 | 1.62x |
| 160 | 32 | 1.96x |

- **Measure:** the smallest halo that kills the edge artifacts.
- **This one needs eyes.** No number tells you the seam is gone, so
  a minimal chip grid gets built here rather than at phase 9. See
  `docs/visualization.md` for the plan, and for the rule that keeps
  a viewer from reading S3 and polluting the byte counter.
- Vectorise masks per chip, cropped to the stride interior. Do not
  merge yet.

### Phase 5. The union (2 days)

The hard part, and the part worth the most.

At 30m a 224 chip covers 6.72 km, about 4,500 ha. A 45,000 ha fire
spans roughly 15 to 25 chips once shape is accounted for. Wind and
terrain make fires elongated, which crosses more boundaries than a
compact shape of equal area.

- Filter to candidates: only polygons whose bbox touches a chip
  edge. A small fraction of the total, and it is what makes this
  tractable.
- Spatial join candidates against candidates on the adjacent edge.
- An object can span more than two chips, so this is not a pairwise
  merge. Build a touch graph, run connected components, dissolve
  each component.
- Assign a stable scar ID so one scar is trackable across dates.
  This is a second connected-components problem, over time rather
  than space: a scar at `t` links to a scar at `t+1` when they
  overlap above a threshold. Pick and record that threshold. The
  reburn split in phase 9 is a deliberate cut in this same graph,
  so design the two together even though they are built apart.
- **Measure:** candidate fraction, component size distribution,
  union wall time against total polygon count.
- **Prove it:** take the largest fire in the area of interest and
  confirm it comes out as one row, not as N chip fragments.

### Phase 6. Two nodes (1 day)

- **Pin the versions before starting.** Mixed arm64 and x86_64 is
  fine, mismatched Python or Ray versions across the two nodes is
  not. Lock both in phase 0.5 rather than discovering it here.
- Start a head node on the 5900X box. Join the M1 Max as a worker.
- Schedule the CPU preprocessing pool on the M1 Max and the GPU
  actors on the 5900X box. Use resource labels, not luck.
- **Measure:** cross-node object transfer, object store spilling,
  and the CPU-to-GPU actor ratio over a link rather than a memory
  bus. Compare against the single-node ratio from phase 3.
- **Optional.** Rent a multi-GPU box for two hours at the very end,
  purely to fill one scaling row.

### Phase 7. GPU (1 day)

Everything above is validated on CPU, so GPU time buys numbers and
not debugging.

- Probe the maximum batch size against activation memory on 12 GB
  (verify the card's VRAM), then back off about 20%.
- Layer the wins and measure each on its own: fp16 or bf16 autocast,
  then `channels_last`, then `torch.compile`.
- `torch.inference_mode()`, pinned memory, async host-to-device
  copies on a separate CUDA stream.
- **Measure:** chips per second, GPU utilisation, and a
  `torch.profiler` trace showing gaps between kernels closing.
- **Run it twice.** Once against S3, once against the local cache.
  The gap between them is the point of the phase.
- **Derive the headline:** sustained MB/s needed to saturate the
  card. Compare against the actual link, and against what an
  in-region instance would deliver.

### Phase 8. Write for the reader (1 day)

The output is a dataset someone queries, not a dump.

- Sort by a space-filling curve before writing, so row group bboxes
  come out tight and mostly disjoint.
- Write the GeoParquet 1.1 `bbox` covering column. That is what the
  reader prunes on.
- Tune the row group size against the query. Smaller groups prune
  better and cost more metadata.
- Partition by year and spatial cell, so "this area, these dates"
  touches few files.
- **Benchmark it in SedonaDB.** Same query, two writes, chip order
  against Hilbert order. Report row groups touched and wall time.
- This is also where spatial pruning gets demonstrated, at query
  time, which is where it belongs.

### Phase 9. The analysis (2 days)

- Build the control ring per scar: buffer, difference, filter to the
  same WorldCover class, sample.
- Compute the season-corrected recovery curve per scar.
- Run the five joins.
- Fit a half-recovery time per scar. Group by aspect, slope and
  pre-fire vegetation.
- Date each ignition from the first detection, and report the
  uncertainty as the revisit gap.
- **Handle reburns.** California reburns often. A scar that recovers
  and then re-darkens must be split at the discontinuity.
- Compare the model's polygon shrink against the dNBR curve. Report
  where they disagree and why.

**The joins.**

| # | Join | Yields |
| --- | --- | --- |
| 1 | scars x MTBS perimeters | agreement, plus fires MTBS missed |
| 2 | scar(t) x scar(t+1) | shrink rate, and ignition date |
| 3 | scar x its control ring | season-corrected recovery |
| 4 | scar x Copernicus DEM 30m | recovery by slope, aspect, elevation |
| 5 | scar x ESA WorldCover 10m | recovery by pre-fire vegetation |

### Phase 10. Reliability (1 day)

- Idempotent tasks, per-partition output, a completion manifest so a
  restart skips finished work.
- Retry with backoff on S3 5xx. A quarantine path for bad inputs.
- Kill the job halfway and restart it. Prove it resumes.
- Kill the worker node and prove the head recovers.

### Phase 11. Writeup (1 day)

Result first. Figures above the fold, because tables alone do not
survive a skim. A reproduce path that runs on the 24 GB subset. A
limitations section that names the model's out-of-distribution
problem before a reader finds it.

## Effort

About four weekends. Phases 0 to 5 run on the M1 Max. Phases 6 to 11
need both machines.

If time runs short, **cut tiles, not phases, and never cut dates.**
Temporal density is the analysis. One tile followed densely across
eight years still exercises every phase and every join.

## Out of scope

**Zarr and Xarray.** The COG path carries the project. A second
reader adds nothing to the analysis.

**Training, of any kind.** Phase 0 is a gate, not a fine-tune.

**Multi-resolution cascade.** One grid at 30m.

**Model accuracy work past the gate.** If a prediction looks wrong,
that is fine, as long as the MTBS agreement number is honest.

## Risks

| Risk | Mitigation |
| --- | --- |
| Prithvi fails the phase 0 gate | Vary chip size and normalisation, then the area of interest. Never the weights |
| Model is out of distribution on partly recovered scars | The dNBR control ring is the independent check. This is why both measurements exist |
| Seasonality swamps the recovery signal | Control ring. Never compare raw index values across dates |
| MTBS labels are approximate and size-thresholded | Report agreement as a range. Do not claim precision the labels cannot support |
| Reburns corrupt recovery curves | Detect the discontinuity and split the series |
| Blackwell needs a CUDA 12.8+ PyTorch | Gate it in phase 0 |
| IO-bound conclusion reads as an alibi | Saturate the GPU in the cached environment, run the full tuning ladder there, and quote the bandwidth figure |
| Egress charges appear | Verify Earthdata terms in phase 0. The cache limits repeat reads |
| Re-reading 377 GB for every benchmark row | Sweep against the 24 GB subset. One production run at the end |
| Slow link makes wall-clock unrepresentative | Report bytes as the primary metric |
| Areas computed in per-tile UTM are not comparable across the belt | Every area figure in EPSG:5070. Fixed in phase 0.5 |
| Cloud shadow reads as burn scar and inflates recovery | Shadow disqualifies a pixel. Record the drop rate for each Fmask choice |
| The byte counter itself is wrong, so every row is wrong | Validate against process-level network counters once, and keep the analytic count as a cross-check |
| Mismatched Python or Ray versions across the two nodes | Pin both in phase 0.5, not at phase 6 |
