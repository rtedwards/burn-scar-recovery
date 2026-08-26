# Glossary

The approved term for each concept. Use these words in code, in
column names and in documentation. Do not use a synonym.

## The imagery

| Term | Definition |
| --- | --- |
| **HLS** | Harmonized Landsat Sentinel-2. The imagery source. 30 m resolution, on the Sentinel-2 MGRS grid |
| **HLSL30** | The HLS product from Landsat 8 and Landsat 9 |
| **HLSS30** | The HLS product from Sentinel-2 |
| **MGRS tile** | A 109.8 km square of the Sentinel-2 grid. The project uses three tiles |
| **tile-date** | One MGRS tile on one date. The unit of the archive. The project covers approximately 3,600 |
| **band** | One spectral channel of a tile-date. The model uses six |
| **Fmask** | The quality band. It marks cloud, cloud shadow, snow and water |
| **COG** | Cloud Optimized GeoTIFF. The file format of a band |
| **revisit** | The interval between two observations of one tile. The median is 2 to 3 days |

## The pipeline

| Term | Definition |
| --- | --- |
| **chip** | A 224 x 224 pixel square. The input to the model |
| **stride** | The distance between the origin of one chip and the next. Less than 224, so chips overlap |
| **halo** | The overlap between two chips. `(224 - stride) / 2` on each side |
| **interior** | The centre of a chip, of size `stride` x `stride`. Masks are cropped to it |
| **read amplification** | Bytes read divided by bytes needed. The overlap causes it |
| **probe read** | The first read of the two-phase read. Fmask only, one band |
| **late materialize** | The second read of the two-phase read. Six bands, clear chips only |
| **predicate pushdown** | A filter applied before the read. It costs zero bytes |
| **band projection** | The choice of six bands out of the available assets |
| **backpressure** | The limit that stops the producer from outrunning the consumer |
| **actor ratio** | The number of CPU actors for each GPU actor |

## The analysis

| Term | Definition |
| --- | --- |
| **scar** | One burn scar, as one polygon, on one date |
| **scar ID** | The identifier that links one scar across dates |
| **union** | The join of chip polygons into one scar polygon |
| **touch graph** | The graph of chip polygons that touch at a chip edge |
| **control ring** | A buffer of unburned pixels outside a scar, of the same land cover class |
| **shrink** | The reduction of scar area between two dates. The recovery signal |
| **half recovery** | The time for a scar to lose half of its original area |
| **reburn** | A second fire on a scar that has not fully recovered |
| **NBR** | Normalized Burn Ratio. An index computed from NIR and SWIR |
| **dNBR** | The difference in NBR between a scar and its control ring |
| **MTBS** | Monitoring Trends in Burn Severity. The published fire perimeters |
| **perimeter** | An MTBS fire boundary. It is operational, so it encloses unburned islands |

## Words to avoid

| Do not use | Use |
| --- | --- |
| scene, granule, image, acquisition | tile-date |
| patch, tile (for the model input), window | chip |
| burn, burned area, fire (for the polygon) | scar |
| overlap, margin, buffer (for the chip) | halo |
| filter, prune (for the STAC step) | predicate pushdown |
| mask (for the output polygon) | scar |

The word **tile** is ambiguous. It means an MGRS tile, or a COG
internal tile. Always qualify it. Write `MGRS tile` or `COG tile`.

The word **fire** means the event. The word **scar** means the
polygon that the event leaves. Do not exchange them.
