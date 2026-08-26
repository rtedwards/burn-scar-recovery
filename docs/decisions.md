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
