# port5g — Private 5G network design for the BEST container terminal (Port of Barcelona)

Engineering study for 230709 5GMCS (UPC ETSETB). Everything numeric in the report is either **computed by this
repo from `config/*.yaml`** or **cited** — see `docs/assumptions.md` (generated) and `docs/BRIEF.md` §10.

```
make install      # pip install -e ".[dev]"   (Python ≥ 3.10; includes PuLP -> ILP site placement)
make test         # 45 tests incl. every §4 numeric anchor
make run          # config -> results/results.json  (deterministic, seed in scenario_best.yaml)
make figures      # figures 1-12 as PNG, byte-identical across runs
make assumptions  # regenerate docs/assumptions.md from the config provenance records
make check-assumptions   # fails while any value is still [UNVERIFIED]  (use before the final report)
python -m port5g.cli anchors          # prints the §4 anchors next to the expected values
python -m port5g.cli geometry-check   # area / quay / clutter density of the GeoJSON
```

## How the config schema enforces the brief's rules
Every value in `config/*.yaml` is a record `{value, unit, source, confidence}`. The loader (`config.py`) exposes plain
values to the code and keeps a registry; `make assumptions` turns that registry into the assumptions table and
`--strict` fails while any `confidence: unverified` remains. **Nothing in the code carries a numeric constant that is
not either a spec table in `tables.py` (with its clause) or a formula.** To change the band, TDD pattern, or any
assumption you edit one YAML file (rule §10.5).

| confidence | meaning |
|---|---|
| `verified` | read from the primary spec/regulator text by a team member |
| `secondary` | from memory / secondary source — **must be re-checked** against the current release (rule §10.3) |
| `unverified` | placeholder so the pipeline runs; reported as **[UNVERIFIED]** until sourced |
| `design` | a choice this project makes and argues |

Current count: run `make assumptions` (≈230 values, ≈50 unverified at hand-over).

## Repository map
```
config/            band · ues · services · qos · scenario_best · latency · economics   (annotated YAML)
data/site/         best_terminal.geojson  — SCHEMATIC PLACEHOLDER, see scripts/DIGITISE_SITE.md
src/port5g/        channel · linkbudget · capacity · latency · reliability · sinr · geometry · planning
                   slicing · admission · economics · scenario · plots · cli · config · tables
tests/             anchors (§4), channel properties, budget/reliability, system/determinism, config provenance, economics
docs/              assumptions.md (generated) · impact_notes.md · requirements_traceability.csv · references.bib
                   architecture.md · msc/*.mmd (4 Mermaid MSCs) · BRIEF.md
figures/           generated PNGs + MANIFEST.md
results/           results.json (every number the report may quote)
```

## Phase status (brief §8)
| Phase | Status | Notes |
|---|---|---|
| 0 scaffolding | ✅ | repo, config schema, CI (pytest + determinism check), assumptions generator |
| 1 channel + link budget | ✅ code, ⚠️ values | all anchors pass; figs 3, 4; ~50 [UNVERIFIED] placeholders to source; reviewer sign-off needed before Phase 2 |
| 2 geometry + planning | ⚠️ pipeline runs on placeholder geometry | digitise the real polygon; implement cross-link (TDD coexistence) analysis in `sinr.py`; figs 1, 2 regenerate automatically |
| 3 capacity + latency + reliability | ✅ | figs 5, 6, 7; **negative result: UL does not close** with coverage-driven sites |
| 4 slicing + admission | ✅ | fig 8; ARP semantics unit-tested |
| 5 testbed | ❌ dropped | removed 2026-09-22 (never run; not required by the course). Slice/QoS design stays on paper: `qos.yaml`, `architecture.md`, MSCs. Recoverable from commit 81ae7ce |
| 6 synthesis | ⚠️ | fig 9 tornado done; traceability CSV drafted; assumption sweep pending |
| 7 techno-economics (report Ch. 5) | ⚠️ structure only | `economics.py`: site count → CAPEX/OPEX → NPV/payback, SNPN vs PNI-NPN, cost per TDD pattern; figs 10–12. **All 25 cost/saving inputs are [UNVERIFIED] placeholders** (figures carry a red stamp) |

## Headline results at hand-over (placeholder inputs — do not quote)
- Coverage needs **4 sites** (ILP); uplink **capacity needs 17** (DSUUU, 1 layer) or **9** (2-layer UL MIMO). The design is
  uplink-capacity-limited → the brief's "if the uplink does not close, that is a finding" applies.
- S1 one-way latency 4.5 ms worst-case (CG, mini-slot, 1 HARQ retx) vs 10 ms PDB; **remote UPF: 12.5 ms → fails**.
- HARQ from a 10 % first-tx MCS cannot reach 1e-5 inside the PDB (5 tx ≈ 10 ms). Options: MCS back-off (+0.8 dB here,
  more in reality) or PDCP duplication (2× spectral cost). See `docs/impact_notes.md`.
- 99.9 % *area* availability costs a ~21 dB shadow margin — the single most sensitive assumption (fig 9).
- CNAF sub-ranges in the brief conflict with the CNMC 2023 report → `[UNVERIFIED]`, headline CT4 slide.
- The configured TDD pattern is the MNO-synchronised `DDDSU`, which needs **23** sites (2-layer UL) vs **9** for `DSUUU`.
  `economics.tco_by_tdd_pattern` turns that into money: the TDD coexistence trade-off is also a cost trade-off.
- In the business case the network is a small share of total cost next to the automation retrofit, and NPV is
  driven by labour assumptions (fig 12). Structure only: every cost input is a placeholder.

## Next actions (in order)
1. Source the [UNVERIFIED] list (`make assumptions`); start with beamforming gain, interference margin, CNAF,
   then the economic inputs in `config/economics.yaml` (each source field says where to look).
2. Digitise the terminal polygon; set `geojson_is_placeholder: false`.
3. Implement the TDD cross-link interference analysis (`sinr.cross_link_interference_note()` is the plan).
4. Replace the Bernoulli blockage term with TR 38.901 Blockage Model B in the ASC zone (impact note M3).
