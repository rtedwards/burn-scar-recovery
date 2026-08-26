# Documentation

Reference material for the project. `README.md` gives the pitch.
`ROADMAP.md` gives the plan. These files give the durable detail
that both of those documents assume.

| File | Content | Read it when |
| --- | --- | --- |
| [glossary.md](glossary.md) | The approved term for each concept | You name a function, a column or a file |
| [conventions.md](conventions.md) | Identifiers, coordinate systems, run records | You write data to disk |
| [data-sources.md](data-sources.md) | The datasets, the bands, the access rules | You read a new dataset |
| [decisions.md](decisions.md) | The decision log, with the reason for each | A decision looks arbitrary |
| [visualization.md](visualization.md) | The three views, and which one needs a map | You build or change a viewer |

## How to use these files

Add a decision to `decisions.md` when you make a choice that a later
reader could reverse by accident. Give the reason. A decision
without a reason is a decision that somebody undoes.

Add a term to `glossary.md` when you introduce a concept. The
project uses Simplified Technical English, which requires one word
for one thing. The glossary is the record of which word won.

These files use Simplified Technical English. `README.md` and
`ROADMAP.md` do not. See `CLAUDE.md` for the rules.
