# Model-structure assumptions and "impact if wrong"

`assumptions.md` is generated from the config provenance records and covers every *numeric* value. This file
covers assumptions that are **structural** (choices of model/formula) and the impact column for the big-ticket
numeric ones. Keep it short and honest — brief §9 demands at least one negative result.

## Structural assumptions

| # | Assumption | Where | Source / justification | Impact if wrong |
|---|---|---|---|---|
| M1 | Per-zone channel model: quay = UMi-SC, ASC blocks = InF-DH, gate/rail = InF-SH; InF LOS-probability parameters mapped from container geometry (r, h_c, d_clutter) | `channel.py`, `scenario_best.yaml` | TR 38.901 §7.4.1/7.4.2; mapping is this project's argument (brief §4.1) | **Large.** InF-DH NLOS exponent 2.19 gives weak inter-cell isolation → the UL SINR map is interference-limited (median ≈ 3 dB with 4 sites). If the yard behaves like a street canyon (UMi NLOS, exponent 3.53), cells are smaller but better isolated. Sensitivity knob `channel_model` in fig. 9. **Candidate negative result: the standard models disagree by >10 dB at 300 m in the ASC rows; a drive test is needed.** |
| M2 | Mean (LOS-probability-weighted, linear-domain) path loss for planning; shadowing/blockage only in Monte-Carlo mode | `channel.mean_path_loss` | Deterministic planning pass (rule §10.4) | Under-estimates tail loss; the area-availability margin (Jakes) is meant to cover it. Verify with the shadowing-on run. |
| M3 | Blockage = Bernoulli(p) × fixed loss; link-budget uses the *mean* p × L | `channel.stochastic_blockage_db` | Brief §4.1 allows a simple justified term | Mean is not a tail: for 99.9 % area availability the blockage should enter as a full loss with probability p. Phase 2 task: switch to TR 38.901 Blockage Model B in the ASC zone. |
| M4 | Required SINR from the normal approximation (PPV 2010) + implementation loss; α-Shannon (TR 36.942 A.2, α = 0.6) for SINR → throughput | `linkbudget.required_snr_db`, `capacity.spectral_efficiency_from_sinr` | Cited formulas; α and the implementation loss are calibration constants | The 1e-5 vs 1e-1 BLER penalty comes out at ~0.8–0.9 dB at n = 500, which is optimistic versus LDPC link-level results (typically 2–4 dB). The `implementation_loss_db` placeholder carries this gap and is [UNVERIFIED]. |
| M5 | Rx diversity gain = 10·log10(N_rx) (ideal MRC, noise-limited) | `linkbudget._diversity_gain_db` | Upper bound | Over-estimates by 1–3 dB in interference-limited cells. |
| M6 | HARQ retransmissions have independent errors; no soft-combining gain | `reliability.residual_error_harq` | Conservative | Real Chase/IR combining makes HARQ *better* than shown; the CA-duplication comparison is therefore conservative for HARQ. |
| M7 | UL interference = one full-power (post-power-control) co-scheduled UE per neighbour cell per PRB, uniformly distributed; full load | `sinr.uplink_sinr_map` | Worst-case busy hour | Real load < 100 % → SINR higher; add a `ul_load_factor` knob if needed. |
| M8 | Open-loop fractional power control P0 = −80 dBm, α = 0.8 (TS 38.213 §7.1.1) | `band.yaml` | Design | P0 was tuned from fig. 2; treat it as a design variable and sweep. |
| M9 | Admission simulator: Poisson arrivals, exponential holding, GFBR reservation, ARP exactly per TS 23.501 §5.7.2.2; slice minimum shares are inviolable | `admission.py` | Brief §6 contract | Real gNB schedulers pre-empt at PRB level, not session level; the qualitative result (control never pre-empted, MIoT squeezed first) is robust, the numbers are not. |
| M10 | Site placement = set cover on UL coverage radius only | `planning.py` | Phase 2 baseline | **This is the headline negative result: coverage needs 4 sites, capacity needs 17 (DSUUU, 1 layer) or 9 (2-layer UL MIMO).** The design is capacity-limited in the uplink; the report must present the capacity-driven count and the fixes (UL MIMO, mmWave on quay, video bit-rate reduction, more sites). |

## TDD coexistence (`coexistence.py`) — structural assumptions

| # | Assumption | Impact if wrong |
|---|---|---|
| C1 | Minimum-coupling-loss, single interferer, free-space path loss | Worst case: real clutter, antenna down-tilt and terrain reduce the required separation, possibly by tens of dB; a site-specific study (terrain + real antenna patterns) is needed before ruling unsynchronised operation in or out |
| C2 | Frames aligned (same numerology, period, GNSS timing); only the slot pattern differs | Misaligned frames add conflicts; this is the best case for an unsynchronised pattern |
| C3 | 3GPP minimum RF specs (BS ACLR 45 dB flat over first and second adjacent channel) → a guard band alone buys nothing | Real equipment usually beats the minimum spec and extra filtering is possible; the datasheet value then sets the achievable isolation |
| C4 | Beamforming gain excluded on both sides | MNO massive-MIMO beams pointed at the port area would make the MNO → us link worse |

**Negative result (current inputs):** an uplink-heavy pattern next to an MNO DDDSU carrier is not viable at any
realistic separation (MNO gNB → our gNB needs ~24 km in free space). The team must either synchronise (DDDSU → 23
sites 2-layer vs 9 for DSUUU) or show site-specific isolation. The coexistence trade-off is therefore also a cost
trade-off (`economics.tco_by_tdd_pattern`).

## Techno-economic model (`economics.py`) — structural assumptions

| # | Assumption | Impact if wrong |
|---|---|---|
| E1 | Savings come from automation; the business case charges them against network **and** automation retrofit CAPEX. The network alone is reported as a pure cost (TCO), never as having its own ROI | Crediting labour savings to the network alone would inflate ROI by the retrofit cost, which is much larger than the network cost in the placeholder numbers |
| E2 | Labour saving = posts removed × FTE per 24/7 post × loaded cost; remote supervision ratios (cranes/operator, vehicles/supervisor) are the key inputs | A 1:1 remote ratio gives zero crane labour saving (test-covered); the case then rests on safety/ergonomics, not cost. Workforce impact is also a SWOT threat (dock labour relations) |
| E3 | PNI-NPN option still buys RAN, CPE and MEC on site (local UPF is mandatory, R5.2); only the core, its staff and the spectrum fee are swapped for an MNO fee | If the MNO would fund the on-site RAN, PNI-NPN looks cheaper than shown |
| E4 | All CAPEX in year 0, flat OPEX, benefits phased by `benefit_ramp`; real terms, no tax, no residual value, no equipment refresh within the 10-year horizon | Refreshing RAN mid-horizon or phasing CAPEX with the roll-out changes NPV/payback; keep the ramp consistent with the deployment phases in Ch. 4 |
| E5 | Site counts are taken from the capacity model, which assumes per-cell spectral efficiency from the coverage-driven layout | Densifying to 9-23 sites changes inter-cell interference, so the per-cell capacity (and site count) is approximate |

## Numeric assumptions with dominant impact (from fig. 9, the code decides)

1. `services.S1_crane_control.area_availability_target` (0.99 ↔ 0.9999): 3 ↔ 6 sites. The 99.9 % target costs a ~21 dB shadow margin with σ = 7.82 dB. Whether 99.9 % *area* availability is the right reading of TS 22.104 "communication service availability" is a definitional question — raise it with the course staff.
2. `latency.link_level.interference_margin_db` (0 ↔ 6 dB): 3 ↔ 6 sites. Must be replaced by the per-zone value from `sinr.py`.
3. `ues.gnb.beamforming_gain_db` (0 ↔ 9 dB): 6 ↔ 3 sites. [UNVERIFIED] placeholder → needs a product datasheet.

## Negative results to report (current state of the code)

- **Uplink capacity does not close** with the coverage-driven site count for any TDD pattern (fig. 7). Even DSUUU with 2-layer UL MIMO needs ≈9 sites vs 4 for coverage.
- **HARQ cannot reach 1e-5 within the 10 ms PDB from a 10 % first-transmission MCS** (fig. 6): 5 transmissions ≈ 10 ms. The only configurations that meet 99.999 % inside the PDB are (a) conservative MCS at 1e-5 first-tx (+0.8 dB SINR in this model, more in reality) or (b) PDCP duplication (2× spectral cost on an uplink that is already the bottleneck). There is no free option — say so.
- **A remote (MNO) UPF breaks the S1 budget** (12.5 ms vs 10 ms PDB with the placeholder 8 ms transport term) → on-site UPF is mandatory (brief §3.2).
- **CNAF spectrum figures are unverified** and the 2023 CNMC report contradicts the brief's sub-ranges (see `band.yaml`).
