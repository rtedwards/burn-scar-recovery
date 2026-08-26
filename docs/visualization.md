# Visualization

A plan. No code yet.

## Two needs, not one

Do not build one tool for both. They read different data and they
answer different questions.

| | Need A. Chip review | Need B. Recovery review |
| --- | --- | --- |
| Question | Did the model get this chip right? | How did this scar change over 8 years? |
| Unit | One chip, 224 x 224 px | One scar, approximately 200 dates |
| Reads | Cached chips, predicted masks, MTBS | GeoParquet, cached imagery |
| Interaction | Sort and filter by a score | Pick a scar, then move a date slider |
| Needed by | Phase 0, phase 4 | Phase 9 |

## Do not build a renderer

Rendering, tile service and dataset query are solved. Only the
composition of a scar picker, a date slider and two curves is
specific to this project, and no general tool supplies it.

Buy the layers. Write the glue.

| Layer | Tool | Reason |
| --- | --- | --- |
| Chip review | FiftyOne | It sorts samples by a computed score. "Show the 20 worst chips by IoU" is the phase 0 gate workflow |
| Polygon render | lonboard | It reads GeoParquet through GeoArrow. It draws large polygon sets fast |
| Raster backdrop | TiTiler or leafmap | Both serve a COG without a download. leafmap also gives a split view for a before and after comparison |
| Curves | matplotlib or hvplot | Area against time, and dNBR against time |
| Glue | Panel or Streamlit | The scar picker, the date slider and the curves in one page |
| Writeup figures | matplotlib | Static output for phase 11 |

**Rerun is the alternative.** It holds a timeline as a first-class
concept, so it suits one chip across many dates. It is weak on
geospatial data and it cannot sort by a score. Consider it only if
the two tools above prove awkward.

**QGIS covers ad-hoc inspection.** It needs no build. It does not
produce a shareable artifact, so it does not replace the plan above.

## Constraints

**The viewer must never read S3.** This is the important one. The
project measures the bytes that the pipeline reads from object
storage. A viewer that fetches a COG to draw it adds bytes to that
measurement and corrupts every row of the headline table.

The viewer reads two things: the local chip cache, and the written
GeoParquet. Nothing else.

**The viewer is a consumer of the output.** It sits outside the
measured path. It must not import pipeline stages, and it must not
appear in a run record.

**A third coordinate system enters here.** Web tiles use EPSG:3857.
GeoParquet holds EPSG:4326. Areas use EPSG:5070. Convert for
display only. Never compute an area from a display coordinate.

**Need B depends on the scar ID.** A view across dates needs the
stable scar identifier, which phase 5 still has to decide. Need A
has no such dependency, which is a second reason to build it first.

## Build order

1. **Phase 4. A chip grid.** Approximately 50 lines of matplotlib.
   It shows the chip, the predicted mask, the MTBS reference and the
   seam between two chips. Phase 4 asks for the smallest halo that
   removes the edge artifacts. No number answers that question. Only
   a picture does.
2. **Phase 0 and after. FiftyOne for chip review.** Load the cached
   chips with the predicted mask and the MTBS mask. Sort by IoU. This
   runs the phase 0 gate and then serves as the standing check.
3. **Phase 5. A union proof.** Draw the largest fire and its chip
   boundaries. Show one polygon, not N fragments.
4. **Phase 9. The recovery view.** A Panel page: pick a scar, move a
   date slider, see the polygon over the imagery, and see the area
   curve beside the dNBR curve. This is where the two independent
   measurements get compared by eye.
5. **Phase 11. Static figures.** The writeup needs figures above the
   fold. Generate them from the same data as the recovery view.

## Open questions

| Question | Note |
| --- | --- |
| Does FiftyOne handle a 6-band chip? | It expects RGB. A false-colour composite is probably necessary |
| Panel or Streamlit? | Panel composes better with hvplot. Streamlit is simpler |
| Does the viewer need its own cache? | The 10 GB instrument cache may not hold the dates a user wants |
