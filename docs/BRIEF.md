# Agent Brief — `port5g`

**Project:** Private 5G network design for an automated container terminal (Port of Barcelona)
**Course:** 230709 5GMCS — 5G Mobile Communications Systems, UPC ETSETB (Jordi Pérez-Romero)
**Deliverable weight:** 30% of final grade — "Team work on the development of a use case"
**Language of all outputs:** English

> **Scope decisions after import (these override the body of this brief)**
> - 2026-09-22 — The graded deliverable is the report template + two talks in `docs/course_material/`
>   (needs, requirements, design, techno-economics/regulation/SWOT). This brief was written for the agent that built
>   the repo and is kept as history; where it conflicts with the course material, the course material wins.
> - 2026-09-22 — **§5 testbed dropped** (never run, not required by the course; live demos are a risk). Figure 10,
>   Phase 5 and the testbed acceptance criterion no longer apply. The slice/QoS/procedure design stays on paper.

---

## 0. How to read this brief

You are building an engineering study, not a demo. Every number that appears in the final report must be either (a) computed by code in this repository from a config file, or (b) cited to a 3GPP specification, a regulator document, or a named industry source. Numbers that are neither are a defect.

Read Sections 1–3 before writing any code. Section 8 is the build order. Section 10 contains rules that override anything else in this document.

---

## 1. The scenario

### 1.1 Site

Hutchison Ports **BEST** (Barcelona Europe South Terminal), Moll Prat, Port of Barcelona. A real semi-automated deep-water container terminal. Public figures to use as the baseline (verify and cite each one; where sources disagree, state the range in `docs/assumptions.md` and pick one):

| Parameter | Value | Note |
|---|---|---|
| Yard area | ~80 ha (some sources ~100 ha) | Phase-dependent; sources conflict — flag it |
| Quay length | 1,500 m | Five deep-sea berths |
| STS quay cranes | 11 super post-Panamax | Manual cabin operation today |
| Automated stacking cranes (ASC) | ~48–54, rail-mounted | Already automated |
| Shuttle / straddle carriers | ~30 | Manned today |
| Reefer plugs | ~1,350 | Each a monitoring point |
| Rail terminal | 8 mixed-gauge tracks | Additional coverage area |
| Operating model | Manual vessel operation, automated yard | This is the gap the project closes |

The framing of the project is therefore **not** "5G enables automation" — the yard is already automated over fibre and Wi-Fi. The framing is: *what does the terminal need from a private 5G network in order to (i) move STS crane operators out of the cabin into a remote control room, (ii) remove the drivers from the shuttle carriers, and (iii) replace a fragile Wi-Fi/proprietary-telemetry patchwork with one managed network?* That is a more defensible engineering question and it is the one the report should answer.

Get the yard geometry from the Port of Barcelona open data portal (`opendata.portdebarcelona.cat`) — the port plan is published as a PDF/GIS layer. Digitise the terminal polygon, the quay line, the ASC block layout, and the gate/rail area into a GeoJSON in `data/site/`. Do not hand-draw a rectangle.

### 1.2 The three services

| # | Service | Traffic character | Devices | Governing requirement source |
|---|---|---|---|---|
| **S1** | Remote STS crane control | UL-heavy: 6–8 camera feeds per crane (mix of 1080p60 and 4K), 20–60 Mbit/s aggregate UL per crane. DL: control commands, small packets, high rate (50–100 Hz control loop) | 11 cranes | TS 22.104 (cyber-physical control), 5G-ACIA port white papers |
| **S2** | Autonomous shuttle carriers | UL video (obstacle detection, 4–6 cameras) + telemetry; DL mission commands. Mobility ~25–30 km/h, sub-metre positioning | ~30 vehicles | TS 22.104, TS 22.261 (positioning), TS 22.186 for analogous V2X figures |
| **S3** | Reefer + asset monitoring, gate, handhelds | Tiny periodic reports (reefer temp/humidity/power every 5–15 min), gate OCR bursts, workforce handhelds/PTT | ~1,350 reefer plugs + ~2,000 asset tags + ~200 handhelds | TS 22.261 connection density, NB-IoT/RedCap capability specs |

**The engineering tension that makes this project interesting:** S1 and S2 are *uplink-dominated*, which inverts the standard TDD design. S1 needs low latency and extreme reliability but modest volume; S2 needs volume and mobility; S3 needs neither but is enormous in device count and must not be allowed to starve the others. One radio carrier, three incompatible optimisation targets. Resolving that is the project.

---

## 2. Spectrum and regulatory frame

Spain has reorganised the 3.8–4.2 GHz range for local/private networks. As of the latest CNAF revision (Cuadro Nacional de Atribución de Frecuencias, Secretaría de Estado de Telecomunicaciones), the relevant sub-ranges are approximately:

- **3800–3920 MHz** — local broadband, low/medium power, available under concession *and* self-provision (*autoprestación*)
- **3920–4020 MHz** — reserved for Ministry of Defence
- **3920–4120 MHz** — electronic newsgathering, self-provision
- **4020–4120 MHz** — local broadband, low/medium power, self-provision

Separately, a portion of the **26 GHz** band is available for industrial private networks on a self-provision basis without auction.

**Agent task:** verify the current CNAF text yourself, cite the specific *nota UN* reference numbers, and state the effective EIRP/power limits and any coordination obligations. Do not take the figures above as final — they come from press coverage, not the primary document. If you cannot confirm a figure from the primary source, mark it `[UNVERIFIED]` in the report and say so in the presentation. *(This is deliberate: competence CT4 is assessed on critical evaluation of information sources. A slide that says "we could not confirm X from the CNAF and here is why that matters" scores better than a confident wrong number.)*

Design decisions to justify with numbers, not assertions:

1. **Band choice.** Baseline: 100 MHz TDD at ~3.9 GHz (n77 range) under self-provision. Compare against: (a) a PNI-NPN slice from a Spanish MNO on n78, (b) a 26 GHz mmWave overlay for the quay crane zone only. Decide on coverage/capacity/cost grounds.
2. **TDD pattern and the coexistence trap.** The default `DDDSU` (2.5 ms period) gives roughly 60–70% downlink. Your traffic is 80%+ uplink. Switching to an uplink-heavy pattern (e.g. `DSUUU`, or `DDSUU`) is the obvious move — but if your carrier is adjacent to MNO n78 spectrum, an unsynchronised pattern creates gNB-to-gNB and UE-to-UE cross-link interference. Quantify the guard band or geographic separation required, or justify accepting a synchronised pattern and paying for it in uplink capacity. **This trade-off should be one of your headline slides.** Most teams will not notice it exists.
3. **Numerology.** µ=1 (30 kHz SCS, 0.5 ms slot, 273 PRB at 100 MHz) as baseline. Show what µ=2 (60 kHz, 0.25 ms slot) would buy on the S1 latency budget and what it costs in cyclic prefix overhead and coverage.

---

## 3. Network architecture to design

### 3.1 SNPN vs PNI-NPN

Produce a reasoned recommendation. SNPN (own PLMN ID + NID, independent credentials, no MNO dependency, Rel-17 onboarding and Credentials Holder) versus PNI-NPN (CAG cells + a dedicated S-NSSAI from the MNO). Evaluate on: isolation and data sovereignty (terminal operators are paranoid about cargo data), SLA control, handheld roaming to public network at the gate, availability during MNO outage, and cost. **Recommend SNPN with a PNI-NPN or public-network fallback for handhelds**, unless your analysis says otherwise — but the analysis has to be real.

### 3.2 Network functions and placement

Deliver a diagram (SVG, generated or drawn, in `figures/`) showing:

- **On-site at the terminal:** gNB-DU/CU, local UPF, AMF, SMF, PCF, UDM/UDR, AUSF, NRF, NSSF, and a MEC platform on the N6 side hosting the crane-control application and the vehicle fleet manager.
- **N6 / external:** terminal operating system (nGen-equivalent), corporate IT, internet breakout.
- Justify why the UPF must be on-site (the S1 latency budget will not close otherwise — prove it with the number).
- Optional depth: NEF exposure of QoS-on-demand to the terminal operating system, and NWDAF for load analytics.

### 3.3 Slices

Define three S-NSSAIs. SST values per TS 23.501: 1=eMBB, 2=URLLC, 3=MIoT, 4=V2X, 5=HMTC.

| Slice | SST | SD | Serves | Isolation rationale |
|---|---|---|---|---|
| Control | 2 (URLLC) | `000001` | S1 crane control loop | Safety-critical; must never be pre-empted |
| Vision | 1 (eMBB) or 2 | `000002` | S1 video + S2 vehicles | High UL volume, tolerant of ~30 ms |
| Telemetry | 3 (MIoT) | `000003` | S3 sensors, gate, handhelds | Massive count, best-effort, first to be squeezed |

Argue the split. A defensible alternative is putting crane video in the URLLC slice because the operator cannot act without it — if you go that way, say why.

### 3.4 QoS flow table

For every service, specify: 5QI, resource type (GBR / delay-critical GBR / non-GBR), ARP priority level (1–15) with pre-emption capability and vulnerability flags, GFBR/MFBR, PDB, PER, MDBV, and the averaging window.

Starting candidates from TS 23.501 Table 5.7.4-1 — **verify every row against the current release of the spec before using it**, including whether Rel-17/18 added better-fitting 5QIs:

- 5QI 82 — delay-critical GBR, PDB 10 ms, PER 10⁻⁴, MDBV 255 B (discrete automation)
- 5QI 83 — delay-critical GBR, PDB 10 ms, PER 10⁻⁴, MDBV 1354 B (discrete automation)
- 5QI 85 — delay-critical GBR, PDB 5 ms, PER 10⁻⁵, MDBV 255 B
- 5QI 84 — delay-critical GBR, PDB 30 ms, PER 10⁻⁵ (intelligent transport systems)
- 5QI 80 — non-GBR, PDB 10 ms, PER 10⁻⁶ (low-latency eMBB)
- 5QI 9 — non-GBR default

If no standardised 5QI fits (likely for the crane video), define a **non-standardised 5QI** and specify the full parameter set the PCF would signal. Say explicitly that you are doing this and why.

### 3.5 Procedures

Draw three message sequence charts (use Mermaid or PlantUML, checked into the repo so they regenerate):

1. **Registration + slice selection** for a shuttle carrier: UE → gNB → AMF → AUSF/UDM, Requested NSSAI → NSSF → Allowed NSSAI. Show where the NID appears in the SNPN case.
2. **PDU Session Establishment** on the URLLC slice, showing SMF selecting the local UPF and the PCF installing the QoS rules.
3. **Xn handover** of a shuttle carrier between two gNBs mid-yard, with the sequence numbers / data-forwarding path shown, and the interruption time annotated against the S2 requirement.

Optional fourth if you have time: PDU Session Modification triggered via NEF when a crane enters remote-control mode (QoS-on-demand). This is a genuinely good slide.

---

## 4. Radio dimensioning — the physics you must implement

### 4.1 Channel model — a real modelling decision, not a default

A container yard is outdoor, but it is outdoor *filled with stacked metal boxes up to ~13 m high* (containers ~2.59 m each, stacked 4–5 high) plus ASC gantries and 47 m crane structures. Neither TR 38.901 UMi-Street Canyon nor the Indoor Factory (InF) models were built for it.

**Required approach:** implement both and justify a hybrid.

- **TR 38.901 UMi-SC** for the open-geometry LOS/NLOS path loss.
- **TR 38.901 InF** sub-scenarios for the clutter-dominated regions — InF-SL, InF-DL, InF-SH, InF-DH. The InF LOS probability formula is parameterised by clutter density `r`, clutter height `h_c`, and antenna heights, which maps *directly* onto container stack density and stacking height. This is the model's key advantage here and it should be stated explicitly in the report.
- Model the yard as zones: quay apron (open, LOS-dominant), ASC block rows (dense clutter, canyon-like between stacks), gate/rail area (moderate clutter), and derive a per-zone model assignment.
- Add a **blockage margin** for a shuttle carrier passing behind a stack. Consider TR 38.901 Blockage Model A/B, or a simpler stochastic blockage term — either is acceptable if justified.

Reference values to anchor your implementation (compute at 3.7 GHz, d₃D = 100 m, and check your code reproduces these to within 0.1 dB):

| Model | Expected PL |
|---|---|
| UMi-SC LOS: `32.4 + 21·log10(d₃D) + 20·log10(f_GHz)` | **85.76 dB** |
| InF LOS: `31.84 + 21.50·log10(d₃D) + 19.00·log10(f_GHz)` | **85.64 dB** |
| InF-DH NLOS: `33.63 + 21.9·log10(d₃D) + 20·log10(f_GHz)` | **88.79 dB** |

Shadow fading σ per TR 38.901: InF LOS 4.3 dB, InF-SL 5.7, InF-DL 7.2, InF-SH 5.9, InF-DH 4.0. Verify all coefficients against the current TR before shipping.

### 4.2 Link budget — uplink-limited

Build a full uplink and downlink budget. The uplink governs site count; say so and show it.

Uplink terms to include, each with a sourced value in the config:
- UE Tx power by class: 23 dBm (handheld, PC3), 26 dBm (PC2), and a roof-mounted CPE on crane/vehicle with external antenna gain — justify the gain figure from a real product datasheet and cite it.
- UE and gNB antenna gains, cable/feeder loss, vehicle penetration or mounting loss, body loss for handhelds.
- gNB noise figure (2–3 dB typical for a macro; cite), thermal noise density −174 dBm/Hz.
- Required SINR per service, derived from the target spectral efficiency and target BLER — **not** guessed. For the URLLC service the operating BLER is 10⁻⁵ or lower at first transmission, which costs several dB versus the usual 10⁻¹; quantify that penalty.
- Interference margin, shadow-fading margin sized for the target **area availability** (99.9% for the control slice is a different margin from 95% — show the Q-function / Jakes area-coverage calculation).
- Receive diversity / MIMO gain, and any repetition or PUSCH slot-aggregation gain.

Thermal noise anchors for your unit tests: 100 MHz → **−94.0 dBm**; one PRB at 30 kHz SCS (360 kHz) → **−118.4 dBm**.

Output: MAPL per service per zone → cell radius by inverting the zone's path loss model → required site count over the digitised terminal polygon → site positions. Note that crane and lighting-mast structures are the realistic mounting points; constrain site placement to them.

### 4.3 Capacity

Implement the TS 38.306 approximate data rate formula exactly:

```
R = 10⁻⁶ · Σⱼ ( v_layers⁽ʲ⁾ · Qm⁽ʲ⁾ · f⁽ʲ⁾ · R_max · (N_PRB^{BW(j),µ} · 12) / T_s^µ · (1 − OH⁽ʲ⁾) )   [Mbit/s]
```
with `R_max = 948/1024`, `T_s^µ = 10⁻³ / (14 · 2^µ)`, and FR1 overhead `OH = 0.14` (DL) / `0.08` (UL).

**Acceptance anchors** (n78/n77, 100 MHz, µ=1, 273 PRB):
- DL, 4 layers, 256QAM (Qm=8), f=1 → **2337 Mbit/s** (±1)
- UL, 1 layer, 64QAM (Qm=6), f=1 → **469 Mbit/s** (±1)

Then apply the TDD duty cycle, the per-zone MCS distribution from your SINR map, and the slice allocations to get *achievable* per-slice throughput. Compare against offered load computed from the service table in §1.2. If the uplink does not close, that is a finding — report it and propose the fix (more sites, higher-order UL MIMO, a mmWave overlay on the quay, video codec/bitrate reduction).

### 4.4 Latency budget for S1

Decompose end-to-end one-way latency into explicit, individually-sourced terms:

```
UE app + UE processing
+ scheduling request / grant  (≈0 if configured grant — show both cases)
+ slot alignment              (uniform 0…slot duration; 0.5 ms at µ=1)
+ transmission duration       (mini-slot: 2/4/7 symbols vs full slot)
+ gNB processing (N1/N2 capability-dependent)
+ n × HARQ RTT                (n from the residual-BLER target)
+ fronthaul/midhaul/backhaul  (≈5 µs per km of fibre + switch hops)
+ UPF forwarding
+ MEC application processing
```

Present it as a stacked bar chart per configuration, with the TS 22.104 / 5QI PDB target drawn as a horizontal line. Then show the **reliability–latency trade**: each HARQ retransmission buys reliability and costs ~RTT. Compute the residual error probability for 1, 2, 3 transmissions at a given BLER and find the configuration that meets 99.999% within the PDB. Compare against PDCP duplication over carrier aggregation (parallel, not serial — no latency cost, spectral efficiency cost instead). **The CA-duplication vs HARQ-repetition comparison is the strongest single analysis in this project. Do it properly.**

---

## 5. The testbed (real, running software)

A live core network demo is the thing that will be remembered in the presentation room. Build it.

**Stack:** Open5GS (5GC) + UERANSIM (gNB and UE simulator), Docker Compose, in `testbed/`.

Must demonstrate:
1. Three S-NSSAIs configured in NSSF/AMF/SMF, with subscriber records in the UDM/UDR provisioned so different UE classes get different Allowed NSSAI.
2. UEs registering and establishing PDU sessions on their correct slice, with distinct UPFs (or distinct DNNs) per slice — captured in a `tcpdump`/Wireshark trace of N2/NGAP and N4/PFCP.
3. PCF rules producing different QoS flows (different 5QI/ARP) per service.
4. A demonstrable pre-emption event: saturate the network, show the MIoT slice sessions being rejected or pre-empted while URLLC sessions are admitted, because of ARP.
5. A capture-and-annotate exercise: take one NGAP Initial Context Setup and one PFCP Session Establishment from your own trace and annotate the IEs on a slide. This proves you understand chapter 2 rather than having read about it.

Provide `make testbed-up`, `make testbed-demo`, `make testbed-down`. Script the demo so it runs unattended in under 3 minutes — presentations are time-boxed and live demos fail.

---

## 6. Simulator — repository structure

```
port5g/
├── README.md
├── Makefile                    # make test | figures | report | testbed-up | testbed-demo
├── pyproject.toml
├── config/
│   ├── scenario_best.yaml      # site geometry refs, zones, sites, UE populations
│   ├── band.yaml               # carrier, BW, µ, N_PRB, TDD pattern, power limits
│   ├── ues.yaml                # UE classes: Tx power, antenna, NF, mobility
│   ├── services.yaml           # S1/S2/S3 traffic models, offered load
│   └── qos.yaml                # slices, 5QIs, ARP, GFBR/MFBR, PDB, PER, MDBV
├── data/site/best_terminal.geojson
├── src/port5g/
│   ├── geometry.py             # polygon, zones, container stacks, site candidates
│   ├── channel.py              # TR 38.901 UMi + InF, LOS prob, shadowing, blockage
│   ├── linkbudget.py           # MAPL, margins, cell radius inversion
│   ├── sinr.py                 # SINR map over the yard grid, interference from neighbours
│   ├── capacity.py             # TS 38.306 formula, MCS mapping, TDD duty cycle
│   ├── latency.py              # S1 budget decomposition, HARQ, duplication
│   ├── reliability.py          # residual error, availability, area coverage
│   ├── slicing.py              # slice model, GFBR guarantees, ARP semantics
│   ├── admission.py            # session arrival process + admission/pre-emption logic
│   ├── planning.py             # site placement optimiser over candidate mounts
│   ├── scenario.py             # orchestration: config -> results
│   ├── plots.py                # every figure in the report
│   └── cli.py                  # typer/argparse entry points
├── tests/                      # pytest, including the anchors in §4
├── figures/                    # generated, git-ignored except a manifest
├── docs/
│   ├── assumptions.md          # EVERY assumption, with source or [UNVERIFIED]
│   ├── references.bib
│   └── requirements_traceability.csv
└── testbed/                    # docker-compose, open5gs configs, ueransim configs, demo script
```

### Module contracts

- **`channel.py`** — pure functions, no globals. `path_loss(model, d3d, fc, h_bs, h_ut, los) -> dB`. LOS probability separate. Shadowing applied by the caller with a seeded RNG so results are reproducible.
- **`capacity.py`** — implement `data_rate_38306(...)` exactly as specified, with the parameters named as in the spec so a reader can check it line by line against TS 38.306 §4.1.2.
- **`admission.py`** — a discrete-event or time-stepped simulator. Sessions arrive per slice with configurable rates; the controller enforces per-slice guaranteed and maximum bandwidth quotas, GFBR reservation, and ARP-based pre-emption (priority level, pre-emption capability, pre-emption vulnerability, exactly as TS 23.501 defines them). Report blocking probability and pre-emption rate per slice.
- **`planning.py`** — given candidate mounting points (crane structures, lighting masts) and a coverage requirement per zone per service, select a minimal set. Greedy set-cover is fine; ILP via PuLP is better; state which and why.

---

## 7. Required figures (this is the visual argument of the presentation)

1. Terminal map with zones, container blocks, candidate mounts, chosen sites, cell outlines.
2. Uplink SINR heatmap over the yard, one panel per TDD pattern candidate.
3. Link budget waterfall chart, UL and DL side by side, showing which is limiting.
4. Cell radius vs required uplink throughput, one curve per UE power class.
5. S1 latency stacked-bar budget vs PDB line, for ≥4 configurations (grant-free vs SR-based, µ=1 vs µ=2, mini-slot vs slot, 0/1/2 HARQ retx).
6. Reliability vs latency Pareto: HARQ repetition vs PDCP duplication.
7. Offered vs achievable throughput per slice, with the deficit highlighted.
8. Admission control time series: load ramp, showing MIoT pre-emption and URLLC protection.
9. Sensitivity tornado: which single assumption most changes the site count. (Usually the UL/DL split or the shadow-fading margin — but let the code tell you.)
10. Annotated Wireshark screenshot from the testbed.

---

## 8. Build order

**Phase 0 — scaffolding.** Repo, config schema, CI running pytest, `docs/assumptions.md` created empty. Nothing else until the config schema is settled.

**Phase 1 — channel + link budget.** Implement models, pass the §4 anchors, produce figures 3 and 4. *Stop and report to the team before continuing.*

**Phase 2 — geometry + planning.** Digitise the site, build the SINR map, place sites. Figures 1, 2.

**Phase 3 — capacity + latency + reliability.** Figures 5, 6, 7.

**Phase 4 — slicing + admission.** Figure 8.

**Phase 5 — testbed.** Open5GS/UERANSIM, the demo script, figure 10.

**Phase 6 — synthesis.** Sensitivity (figure 9), traceability CSV, README, final assumption sweep.

Do not start Phase N+1 while Phase N has failing tests.

---

## 9. Acceptance criteria

The project is complete when:

- [ ] `make test` passes, including every numeric anchor in §4
- [ ] `make figures` regenerates all 10 figures from config with fixed seeds, byte-identical across runs
- [ ] `docs/assumptions.md` has one row per assumption: value, source, confidence, impact if wrong
- [ ] `docs/requirements_traceability.csv` maps each requirement in §1.2 to its spec clause, the design mechanism that satisfies it, and the figure that proves it
- [ ] The testbed demo runs unattended in <3 minutes
- [ ] No number appears in the report that is not produced by code or cited
- [ ] At least one **negative result** is reported honestly (a requirement that does not close, an assumption that dominates, a trade-off with no good answer)

That last one matters. A study where everything works perfectly is a study that did not test anything.

---

## 10. Rules that override everything above

1. **Never invent a constant.** If a value is needed and not in a config file, stop and ask. Do not substitute a plausible-looking number for a 5QI, a PDB, an antenna gain, a noise figure, or a spec coefficient. A fabricated constant that propagates into the report is the single worst failure mode of this project.
2. **Cite or flag.** Every external value goes in `docs/assumptions.md` with a source. If you cannot find a source, write `[UNVERIFIED]` and continue — do not silently guess.
3. **Verify spec tables against the current release.** The 5QI values, TR 38.901 coefficients, and CNAF sub-ranges quoted in this brief are working values from secondary sources. Check them. Where this brief is wrong, the spec wins and you say so in a note.
4. **Deterministic by construction.** Every stochastic component takes an explicit seed from config. No `random` without a seed, no wall-clock dependence, no unordered-set iteration affecting output.
5. **Config-driven.** Changing the band from 3.9 GHz to 26 GHz, or the TDD pattern, must require editing one YAML file and rerunning — no code changes.
6. **Ask rather than assume** when: a requirement in §1.2 is ambiguous, two spec clauses conflict, a model is being applied outside its stated validity range (e.g. TR 38.901 distance bounds), or a design choice has no clearly better option.
7. **Report validity violations.** If you evaluate a path loss model outside its specified distance or frequency range, the code must emit a warning and the report must acknowledge it.

---

## 11. Team split suggestion

| Role | Owns |
|---|---|
| Core architect | §3 entirely, the testbed, MSCs, slice/QoS design |
| Radio engineer | §4, `channel.py` / `linkbudget.py` / `capacity.py`, figures 2–5 |
| Simulation lead | `admission.py`, `planning.py`, `latency.py`, reproducibility, CI |
| Requirements & narrative | §1–2 sourcing, CNAF verification, traceability CSV, presentation structure, the negative result |

Everyone presents. The course assesses oral presentation in English (CT5) — rehearse against a timer, and make sure the person presenting the link budget can answer "why is uplink limiting?" without looking at notes.
