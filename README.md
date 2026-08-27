# burn-scar-recovery

**How fast does a burn scar recover?**

A query plan over raster. Segmentation inference across eight years
of Harmonized Landsat Sentinel-2 imagery, read from object storage
and measured as a sequence of pushdowns.

> **Status: in progress.** The pipeline is being built. Result
> tables below are stubs until the production run lands. See
> [ROADMAP.md](ROADMAP.md).

---

## Results

*Pending. Two numbers come out of this project.*

**Recovery.** California chaparral reaches half-recovery in `N`
years on north-facing slopes and `M` years on south-facing, across
`K` fires and `P` hectares.

**Throughput.** This workload runs roughly `9:1` IO to compute.
Saturating one RTX 5070 on this model needs `X` MB/s sustained,
which no domestic link delivers and an in-region instance does.

The second number is the interesting one. Below that read rate,
adding GPUs buys nothing and the correct move is to put the compute
next to the data.

---

## The question

Fire perimeters are well mapped. Recovery is not. Published burn
products record where a fire burned and when, then stop. This
project measures what happens afterwards, on every clear
observation, for eight years.

Chaparral recovers over roughly five to ten years, which fits inside
the HLS archive. Conifer takes decades and would show only the start
of the curve.

**The polygon is the measurement.** The pipeline does not segment
each scar once and then compute statistics inside a fixed shape. It
segments on every date and lets the polygon shrink from its edges as
vegetation returns. Area against time is the result.

**The seasonal trap.** NBR and NDVI swing through the year. Compare
March against August and you have measured the season, not the
recovery. Every scar therefore carries a control ring: a buffer of
unburned pixels of the same land cover class just outside it.
Measuring the scar relative to its ring cancels weather, phenology
and sensor drift.

**Two independent measurements.** The model produces a shrinking
polygon. The control ring produces a dNBR curve. Same quantity, two
routes. Where they disagree is reported, not hidden.

---

## The method

Eight years of dense observation over three MGRS tiles is about
580 GB and 1.3 million inferences if you read it naively. That does
not run on a workstation behind a domestic connection.

It becomes tractable by never reading what the query does not need.
Each step below is measured independently.

```
CMR-STAC search
  |- predicate pushdown: bbox + date range + scene cloud cover  [0 bytes]
     |- manifest: IDs, hrefs, footprints, CRS
        |- band projection: 6 of the available assets
           |- chip plan: 224 chip, 192 stride, COG-tile aligned
              |- PROBE READ: Fmask only, 1 band          [~17% of bytes]
                 |- chip-level cloud predicate
                    |- LATE MATERIALIZE: 6 bands, survivors only
                       |- decode, reproject, normalise  [CPU actors, node A]
                          |- batched segmentation       [GPU actors, node B]
                             |- vectorise, crop to the 192 interior
                                |- UNION: connected components
                                   |- Hilbert sort, GeoParquet + bbox
                                      |- spatial joins
```

Two details carry most of the work.

**The pipeline never pre-downloads the corpus.** Pulling the archive
to disk and then measuring what the pushdowns saved pays the exact
cost the pushdowns exist to avoid. Pixels stream in, polygons come
out, pixels are discarded. The output is a few hundred MB against
several hundred GB read.

**Scars cross chip boundaries.** At 30m a 224-pixel chip covers
6.72 km, about 4,500 ha. A 45,000 ha fire spans 15 to 25 chips, and
fires are elongated, so they cross more boundaries than a compact
shape of equal area. Reassembling them is a spatial self-join on
edge-touching polygons, then connected components over the touch
graph, then a dissolve. One fire must come out as one row.

---

## Results tables

### Read path

Bytes are the primary metric. Bytes saved by a pushdown is a
property of the pipeline and holds at any link speed. Wall-clock is
a property of the machine it ran on.

<!-- BEGIN GENERATED: read-path -->
| Configuration | Bytes read | Wall time | GPU util | $/M chips |
| --- | --- | --- | --- | --- |
| Naive: all tile-dates, all bands, fp32, no stride overlap | | | | |
| + STAC predicate pushdown | | | | |
| + band projection, 6 assets | | | | |
| + COG-tile-aligned windowed reads | | | | |
| + Fmask probe, two-phase read | | | | |
| + Ray CPU/GPU pool split with backpressure | | | | |
| + second node | | | | |
| + fp16, channels_last, compile | | | | |
| (measured, not applied) spatial pushdown to known perimeters | | | | |
<!-- END GENERATED: read-path -->

### Bottleneck crossover

| Environment | Read MB/s | Chips/s | GPU util | Bound by |
| --- | --- | --- | --- | --- |
| S3 over domestic link | | | | |
| Local NVMe cache | | | | |
| **Required to saturate the GPU** | | | | |
| In-region equivalent, estimated | | | | |

### Write path

| Write order | Row groups touched | Wall time |
| --- | --- | --- |
| Chip order | | |
| Hilbert order | | |

---

## Data

| Source | Use |
| --- | --- |
| HLS (HLSL30 + HLSS30), 30m | imagery, 2 to 3 day median revisit |
| Prithvi burn scar head | segmentation, zero-shot |
| MTBS perimeters | validation, and the fires it misses |
| Copernicus DEM, 30m | slope, aspect, elevation |
| ESA WorldCover, 10m | pre-fire vegetation class |

HLS is used rather than raw Sentinel-2 because the segmentation head
was fine-tuned on it. That removes the domain gap and lets the
normalisation statistics apply unchanged, so no training is needed.
Combining Landsat with Sentinel-2 also cuts median revisit from 5
days to 2 or 3, which matters for a recovery time series.

---

## Stack

Ray Data, PyTorch, rasterio and GDAL, pystac-client, GeoParquet,
SedonaDB.

---

## Reproduce

*Pending.* The reproduce path will run against a 24 GB single-tile,
single-year subset rather than the full corpus, so it completes in
minutes.

---

## Limitations

*To be completed as results land. Known in advance:*

- The segmentation head was trained on fresh burn scars. Partly
  recovered ground is out of distribution, which is the reason the
  independent dNBR control-ring measurement exists.
- MTBS perimeters are approximate and carry a minimum size
  threshold, so agreement figures are reported as a range.
- Reburns break a recovery curve and must be split at the
  discontinuity.
- Wall-clock figures come from a domestic connection and do not
  represent an in-region deployment. Bytes do.

---

## Licence

MIT.
