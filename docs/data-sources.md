# Data sources

Five datasets. One supplies the pixels. Four supply the answers that
the pipeline joins against.

| Source | Resolution | Use |
| --- | --- | --- |
| HLS (HLSL30 and HLSS30) | 30 m | The imagery |
| Prithvi burn scar head | 224 px input | The segmentation |
| MTBS perimeters | vector | Validation, and the fires that MTBS misses |
| Copernicus DEM | 30 m | Slope, aspect, elevation |
| ESA WorldCover | 10 m | Pre-fire vegetation class |

## HLS

NASA harmonizes Landsat 8, Landsat 9 and Sentinel-2 onto one grid.
Both products are atmospherically corrected, BRDF normalized and
bandpass adjusted.

**Why HLS and not raw Sentinel-2.** The segmentation head was
fine-tuned on HLS. HLS removes the domain gap, so the published
normalization statistics apply without a change. That is the reason
a zero-shot run has a chance. The combination of two satellite
families also cuts the median revisit from 5 days to 2 or 3.

**What it costs.** The resolution drops from 20 m to 30 m, which
does not matter for a scar of several thousand hectares. Access
needs an Earthdata Login. The data sits in AWS `us-west-2`.

The six model bands carry different names in the two products.
**Verified against the live CMR-STAC responses for both collections.**

Landsat does not merely spell them differently. It carries no `B8A`
and no `B12` at all. One tuple of asset keys therefore cannot serve
both products, and a configuration must hold the semantic band list
and resolve it per collection. `burn_scar_recovery.bands` does that,
and an integration test re-checks it against the archive.

| Band | HLSS30 | HLSL30 |
| --- | --- | --- |
| Blue | B02 | B02 |
| Green | B03 | B03 |
| Red | B04 | B04 |
| Narrow NIR | B8A | B05 |
| SWIR 1 | B11 | B06 |
| SWIR 2 | B12 | B07 |
| Quality | Fmask | Fmask |

Every asset also has an `s3_` twin, for example `s3_B04`. Those
resolve to `s3://` URLs and only work from `us-west-2`. That is the
in-region path the README bottleneck table estimates, so the figure
is measurable rather than hypothetical.

`eo:cloud_cover` is in the STAC properties, so the scene-level cloud
predicate costs no credentials and no bytes.

**STAC carries no file size.** An asset entry holds only the href,
a title, a description and roles. Asset sizes therefore need HEAD
requests against `lp-prod-protected`, which need an Earthdata login.
The byte figures wait on that. The manifest does not.

Fmask is 1 band of 6, so the probe read costs approximately 17% of
the bytes. Raw Sentinel-2 has 15 bands, where the same probe would
cost approximately 7%.

**Confirm the egress terms in phase 0.** NASA does not usually
charge for egress. Verify it before you read 377 GB.

## The extent

| Quantity | Value |
| --- | --- |
| MGRS tiles | 3, UTM zone 11 |
| Window | 2017-07 to 2025-06 |
| Tile-dates | approximately 3,600 |
| Naive bytes | approximately 580 GB |
| Bytes after the Fmask probe | approximately 377 GB |

The window opens in July 2017, when Sentinel-2B reached operations.
Before that date the 2 to 3 day revisit claim is not true.

Phase 1 resolves the three MGRS tile identifiers from the STAC
search. Do not guess them. `decisions.md` holds the selection
criteria.

## Fmask

Fmask marks cloud, cloud shadow, snow, ice and water. The chip
predicate reads it.

**Treat cloud shadow as unusable.** Shadow over chaparral is dark
and looks like a burn scar. A chip that keeps shadow produces a
false positive, and phase 9 then measures that false positive as
recovery.

The bit assignments and the clear-fraction threshold are open. Phase
2 decides them. Record the chip drop rate for each choice.

## The model

The Prithvi burn scar head runs zero-shot. The project does not
train it.

**Pin the exact checkpoint.** More than one Prithvi generation
exists, and the generations differ in their input expectations and
in their normalization statistics. Those are the two things that
phase 0 varies when the gate fails. Record the checkpoint in
`decisions.md`. Without it, a gate failure is ambiguous.

Verify the input size. It is probably 224.

## MTBS

MTBS supplies the published fire perimeters. Phase 0 scores the
model against them. Phase 9 joins against them.

**An MTBS perimeter is an operational boundary.** It encloses
unburned islands inside the fire. It is not a per-pixel burn map. A
correct model therefore has a ceiling of approximately 0.6 to 0.7
IoU against MTBS. Set a pass mark below that ceiling.

MTBS also carries a minimum fire size. Fires below the threshold are
absent. The pipeline finds some of them, which is a result and not
an error. Report agreement as a range.

## Copernicus DEM and ESA WorldCover

The DEM gives slope, aspect and elevation at 30 m, which matches the
HLS grid.

WorldCover gives the land cover class at 10 m. It has two jobs. It
selects the control ring, which must hold the same class as the
scar. It also groups the recovery curves by pre-fire vegetation.

Download both in phase 0.
