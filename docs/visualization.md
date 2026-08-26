# Visualization

A plan. No code yet.

Three views. One needs a map. Two do not.

| View | Question | Where | Tool |
| --- | --- | --- | --- |
| A. Chip review | Did the model get this chip right? | Phases 0, 4, 5 | Python, matplotlib |
| B. Scar recovery | How did this scar change over 8 years? | Phases 9, 11 | TypeScript, no map |
| C. Scar atlas | Where are all the scars we found? | Phases 9, 11 | TypeScript, deck.gl |

## Which views need a map, and why

A map library solves three problems: it reprojects at runtime, it
fetches tiles, and it lets a user pan anywhere over a basemap.

**Views A and B have none of those problems, because both use a
fixed extent.**

- A chip is already pixel space. A 224 x 224 chip holds no
  geography. There is nothing to project.
- View B fixes its extent from the scar bounding box on the first
  date, and never moves it. Python therefore projects the polygon to
  pixel coordinates once, at export time.

The browser then receives an image and a path in one coordinate
frame. That is an `<img>` with an SVG `<path>` over it. The SVG form
also gives free styling and hit detection.

**View C is different, and it is what deck.gl exists for.** It draws
every scar across three MGRS tiles and eight years, over a basemap,
with pan and zoom. That is runtime reprojection, tiles and a large
feature count, all at once. Do not hand-roll it.

Use deck.gl over MapLibre GL for the basemap. deck.gl accepts
EPSG:4326 coordinates and reprojects internally, so the GeoParquet
needs no change.

## Build it, do not buy it, except where scale says otherwise

An earlier draft proposed FiftyOne, lonboard and Panel for
everything. That was wrong. The correction is not "never use a
library". It is **match the tool to the scale**.

FiftyOne queries datasets of tens of thousands of samples and
carries a MongoDB to do it. The phase 0 gate looks at approximately
20 chips. At that size the expensive capability is not expensive:

| Capability | Cost to write |
| --- | --- |
| IoU for one chip pair | 3 lines of NumPy |
| Sort chips by score | 1 line |
| A grid of the worst 20 | approximately 40 lines of matplotlib |
| A date slider over frames | one `<input type=range>` |

The roadmap also puts model accuracy work past the gate out of
scope, so nobody browses 850,000 chips. That query capability has no
user here.

View C is the opposite case. Thousands of polygons, pan, zoom and a
basemap is real scale, and deck.gl is the right answer.

**A heavy viewer also costs the reproduce path.** Phase 11 promises
a reproduce path that runs on the 24 GB subset in minutes. A
database server between a reader and that promise is a poor trade.

## The split between Python and TypeScript

**Phases 0, 4 and 5 are a dev loop.** You run a gate, hunt an edge
artifact, check a union. The picture must arrive in the next 30
seconds. That is matplotlib, and the code is throwaway.

**Phases 9 and 11 are a published artifact.** A reader sees this.
A static site with a scrubbing timeline and a scar atlas beats a
notebook screenshot decisively, and it needs no server.

A web application to inspect 20 chips during a gate is the tail that
wags the dog. A notebook screenshot as the headline artifact of the
writeup is equally wrong in the other direction.

**A structural benefit.** A browser application cannot import a
pipeline stage and cannot read S3. The rule below stops being
something a developer must remember. It becomes a property of the
architecture.

## View A. Chip review (Python)

**Data.** Cached chips, the predicted mask, the rasterised MTBS
mask.

**Form.** One figure. One row for each chip. Three columns: a
false-colour composite, the predicted mask, and the reference mask.
Put the IoU in the row title. Sort the rows by IoU, worst first.

**Needed by.** Phase 0, to run the gate. Phase 4, to see the seam
between two chips. Phase 5, to prove the largest fire comes out as
one polygon and not as N fragments.

## View B. Scar recovery (TypeScript, no map)

**Form.** An image element for the composite. An SVG overlay for the
scar polygon. A range input over the observation dates. Below them,
the area curve and the dNBR curve on a shared time axis, with a
vertical line at the current date.

**Needed by.** Phase 9, where a reader compares the two independent
measurements by eye.

## View C. Scar atlas (TypeScript, deck.gl)

**Form.** Every scar over a basemap. Pan and zoom across the three
tiles. Colour by year of ignition, or by half-recovery time. Click a
scar to open View B for that scar.

**Needed by.** Phase 11. It is the figure above the fold. It answers
"what did this project actually find?" in one screen.

It also does a job no table does: it shows the fires that MTBS
missed, beside the ones it recorded.

## The export step

Python writes what the browser reads. The browser does no
projection and no aggregation.

| Artifact | Format | Note |
| --- | --- | --- |
| Composite for each date (View B) | 8-bit WebP | The bands are 6 x int16. Reduce to a false-colour composite first |
| Scar polygon for each date (View B) | GeoJSON, pixel coordinates | Projected at export |
| Area and dNBR curves (View B) | JSON | One file for each scar |
| All scars (View C) | GeoJSON in EPSG:4326, or PMTiles | deck.gl reprojects. Use PMTiles if GeoJSON gets too large |

**Export a few showcase scars for View B, not all of them.** One
scar across approximately 200 dates is approximately 200 images. The
full set does not belong in a static site. View C carries the
breadth. View B carries the depth.

## Constraints

**The viewer must never read S3.** This is the important one. The
project measures the bytes that the pipeline reads from object
storage. A viewer that fetches a COG to draw it adds bytes to that
measurement and corrupts every row of the headline table.

The viewer reads the local chip cache and the written GeoParquet,
both through the export step.

**The viewer is a consumer of the output.** It sits outside the
measured path. It must not import a pipeline stage, and it must not
write a run record.

**Simplify geometry for display only.** View C will want simplified
polygons to stay fast. A simplified polygon has a different area.
Never compute an area, a recovery curve or a table row from display
geometry. Read `conventions.md`: every area figure uses EPSG:5070.

**A basemap is a third-party request.** View C fetches basemap tiles
from outside the project. That is acceptable, because it carries no
project data, but record the provider and its terms.

**View B and View C depend on the scar ID.** A view across dates
needs the stable scar identifier, which phase 5 still has to decide.
View A has no such dependency, which is a second reason it comes
first.

## The second toolchain

TypeScript arrives at phase 9. It does not arrive before.

When it does, it must meet the same bar as the Python side: one
entry point in the justfile, the same hook discipline, its own CI
job. A second toolchain held to a lower standard weakens the
repository more than it helps.

Phase 11 also needs a deploy workflow for GitHub Pages.

## When to reconsider

Revisit if somebody wants to browse and tag chips at the 850,000
scale. That is the workload a dataset tool exists for, and it is out
of scope today. Nothing in the result needs it.
