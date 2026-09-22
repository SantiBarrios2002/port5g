# 3 Technical requirements and required capabilities

> **DRAFT for the team (2026-09-22).** Same markers as Chapter 2: **[VERIFY: …]**, **[TODO: …]**. Every
> number is either cited, or derived by the project model from `config/*.yaml` (and then carries that
> input's status from `docs/assumptions.md`). 3GPP values quoted via a white paper come from an older release
> and must be checked against the current one.

## 3.1 Approach and sources

Requirements are derived per service. Sources are used in this order of precedence:

1. **3GPP service requirements:** TS 22.261 (5G system), TS 22.104 (cyber-physical control in vertical domains),
   TS 22.186 (V2X). These are normative; TR 22.804 (communication for automation) contains the underlying use
   cases, but its values are suggestions only [6, p. 36].
2. **Industry white papers from the course reading list** [1]–[10], where they quantify comparable use cases.
3. **Design values chosen by the team**, stated as such and swept in the sensitivity analysis.

Following the course material, requirements are grouped into **performance** (Section 3.3–3.4), **functional**
(3.5) and **operational** (3.6) requirements [6, p. 21].

## 3.2 KPI definitions

| KPI | Definition used here |
|---|---|
| User-experienced data rate | Data rate that must be available to one device across its service area |
| End-to-end latency | One-way time from the application at one end to the application at the other |
| Reliability | Fraction of packets delivered within the latency bound |
| Communication service availability | Fraction of time the service meets its agreed quality; distinct from reliability [6, p. 18, note 3] |
| Survival time | How long the application tolerates missing messages before it fails safe |
| Mobility | Maximum device speed with seamless service |
| Connection density | Devices per km² |
| Area traffic capacity | Total traffic per unit area (Mbit/s/km²) |
| Positioning accuracy | Horizontal accuracy required for the application |

## 3.3 Performance requirements per service

| Flow | Direction / traffic | Data rate | Latency (one-way) | Reliability | Mobility | Basis |
|---|---|---|---|---|---|---|
| **S1 control** | DL (+UL feedback), periodic small packets, 50–100 Hz, ≤255 B | ~0.2 Mbit/s per crane (model) | **10 ms** (see 3.3.1) | 99.999 % | Crane-mounted (slow) | 5QI 82 PDB/MDBV (TS 23.501); TS 22.104 [VERIFY row] |
| **S1 video** | UL, 6–8 cameras per crane | 20–60 Mbit/s per crane (baseline 40) | 30 ms (design) | PER 10⁻⁴ (design) | Crane-mounted | Non-standardised 5QI 130 defined by the team (`qos.yaml`); rate range from the project brief [VERIFY vendor ref]; cf. "video-operated remote control" 10–100 ms [4, p. 5] |
| **S2 video** | UL, 4–6 perception cameras | 4 Mbit/s per camera [UNVERIFIED] → ~20 Mbit/s per vehicle | 30 ms | 99.99 % [UNVERIFIED row] | **30 km/h** | 5QI 84 PDB (TS 23.501); TS 22.186 [VERIFY row]; remote driving needs up to 25 Mbit/s UL [8, p. 26] |
| **S2 remote assistance** | UL video + DL commands when a vehicle is stuck | up to 25 Mbit/s UL, 1 Mbit/s DL | 5 ms (application server ↔ vehicle) | 99.999 % | 30 km/h | Remote driving [8, p. 26] — **stricter than S2 autonomous mode; see 3.3.2** |
| **S2 positioning** | — | — | — | — | — | Sub-metre (TS 22.261 positioning service levels [VERIFY level]) |
| **S3 reefer** | UL, ~200 B every 5–15 min | negligible | 300 ms (best effort) | 99 % | Static | 5QI 9 default (TS 23.501); payload [UNVERIFIED] |
| **S3 gate OCR** | UL bursts per truck | ~2 Mbit/s average (model) | seconds | 99 % | Static | Truck rate and image size [UNVERIFIED] |
| **S3 handhelds** | UL/DL, PTT + apps | ~0.1 Mbit/s each [UNVERIFIED] | 300 ms (PTT voice may need a tighter 5QI [TODO]) | 99 % | Pedestrian | — |

### 3.3.1 Open point: how strict is the crane-control latency?

The model uses **10 ms** because the brief maps crane control to 5QI 82 (PDB 10 ms). The closest TS 22.261 row
reproduced in the course material, **"process automation – remote control"**, specifies **60 ms** end-to-end
latency, 100 ms survival time, 99.9999 % availability, 99.999 % reliability and 1–100 Mbit/s [6, p. 18].
Heavy Reading's table (3GPP/ZVEI) gives **12 ms** at >99.9999 % for *mobile control panels with safety
functions — mobile cranes*, which is the emergency-stop path, not the video [4, p. 5].

This matters for the design. With 10 ms, the on-site user plane is mandatory and HARQ retransmissions barely
fit. With 60 ms, much of that pressure disappears. **The team must pick the governing requirement, cite the
current TS 22.104 / TS 22.261 row, and possibly split S1 control into a safety function (E-stop, ~12 ms) and
operator control (tens of ms).** This is worth raising with the professor.

### 3.3.2 Open point: autonomous vs remotely assisted shuttles

In autonomous mode, perception runs on the vehicle and the network carries video for supervision (30 ms class).
When a vehicle stops at an obstacle and a human takes over, the requirement tightens to the remote-driving
figures: 5 ms and 99.999 % [8, p. 26]. This happens for one or a few vehicles at a time, so it is a *QoS change on
demand* (Section 3.5), not a fleet-wide requirement.

## 3.4 Aggregate and area requirements

Derived by the model from the baseline device counts (values inherit the status of their inputs):

| Quantity | Value | Comment |
|---|---|---|
| Offered UL load, S1 video | 440 Mbit/s | 11 cranes × 40 Mbit/s, all in remote mode (worst case) |
| Offered UL load, S2 video + telemetry | ~430 Mbit/s | 30 vehicles × 70 % active × 5 cameras × 4 Mbit/s [UNVERIFIED] |
| Offered UL load, S1 control + S3 | ~25 Mbit/s | Control, reefer, gate and handhelds together |
| **Total offered UL load** | **~895 Mbit/s** | Almost entirely video; downlink is small in comparison → **uplink-dominated** |
| Area traffic capacity needed | ~0.9–1.1 Gbit/s/km² | Over the ~80–100 ha site; within TS 22.261 targets (e.g. 100 Gbit/s/km² for process-automation remote control [6, p. 18]). The challenge is *uplink* capacity per cell, not area capacity. |
| Devices | ~3,600 | 11 + 30 + 1,350 + 2,000 + 200 |
| Connection density | ~3,600–4,500 /km² | Far below the 10,000 /km² process-monitoring target [6, p. 18] and the 1,000,000 /km² mMTC connection density of TS 22.261 [VERIFY table]; massive IoT is a standard 5G category [1, p. 22]. **Device count is not the problem; keeping S3 from interfering with S1/S2 is.** |
| Service area | ~1.5 km × ~0.6 km, outdoor, with container stacks up to ~13 m and crane structures ~50 m | [VERIFY dimensions with the digitised plan] |

For a first sense of scale: one 100 MHz NR carrier gives 469 Mbit/s peak uplink with one layer (TS 38.306
formula, reproduced in the model's tests). The offered load is about **twice one carrier's peak uplink** before any
TDD split. This is why the uplink sets the network size (Chapter 4).

## 3.5 Functional requirements

| Requirement | Why | Applies to |
|---|---|---|
| **Service isolation** | Crane control must never be degraded by video or IoT load; a fault in one service must not spread [6, p. 35] | S1 ≫ S2 > S3 |
| **Security and data sovereignty** | Cargo and operational data are commercially sensitive; the network must use its own subscriber credentials and authentication [6, pp. 24–25, 37] | All |
| **Functional safety** | Remote crane operation needs a certified fail-safe path (emergency stop, survival-time behaviour) [6, p. 21] | S1, S2 |
| **Positioning** | Driverless vehicles need sub-metre positioning; 5G positioning can complement GNSS near steel structures [VERIFY] | S2 |
| **QoS on demand** | QoS must change quickly when a crane switches to remote mode or a shuttle requests remote assistance, triggered by the terminal's own systems through network exposure | S1, S2 |
| **Service continuity at the gate** | Handhelds (and visitors) need to fall back to, or roam onto, public networks at the terminal boundary | S3 |
| **Mobility** | Seamless handover for vehicles at 30 km/h between cells in the yard, with interruption time compatible with S2 | S2 |

## 3.6 Operational requirements

Following [6, p. 21]:

- **Simple configuration and operation** by the terminal's own staff or a managed-service partner.
- **Monitoring, fault management and assurance** — per-slice KPIs visible to the operations team; QoS monitoring
  and reporting is one of 3GPP's vertical requirement categories [6, p. 36].
- **Availability during public-network outages** — the terminal must keep working if an MNO network fails. This
  feeds the SNPN vs PNI-NPN decision in Chapter 4.
- **Maintainability** — equipment on cranes and masts must be serviceable without stopping operations.
- **Phased introduction** — pilot on one crane and a few shuttles before full roll-out.

## 3.7 Required 5G capabilities (bridge to Chapter 4)

| Requirement driver | 5G capability | Standard basis |
|---|---|---|
| S1 control latency and reliability | URLLC features: mini-slots, configured grant, on-site UPF, HARQ/duplication; delay-critical GBR 5QI | TS 38 series; TS 23.501 |
| S1/S2 uplink video volume | Uplink-heavy TDD pattern, UL MIMO, more sites — constrained by coexistence with MNO spectrum | TS 38.213; TS 38.306 |
| S3 device count and battery life | mMTC / RedCap devices | TS 38.306 |
| Isolation of three services | Network slicing: three S-NSSAIs (URLLC, eMBB, MIoT) with ARP-based pre-emption | TS 23.501 §5.15, §5.7 |
| Data sovereignty, availability during MNO outage | Standalone non-public network (SNPN) with an on-site core | TS 23.501 §5.30 |
| QoS on demand from terminal systems | Network exposure (NEF) | TS 23.502 |
| Low-latency application hosting | Edge computing (MEC) next to the on-site UPF | ETSI MEC; [6] |
| Vehicle positioning | NR positioning (complementing GNSS) | TS 22.261 / TS 38.305 [VERIFY] |

## 3.8 Open points for the team

1. Choose and cite the governing latency requirement for S1 control (3.3.1). Consider splitting S1 into a safety
   path and an operator-control path.
2. Source the S2 camera rate, activity factor and reliability row (all currently [UNVERIFIED]).
3. Verify every 3GPP value against the current release (the white papers quote Rel-15 era versions, e.g.
   TS 22.261 v15.5.0 [6, p. 18]).
4. Confirm BEST's current connectivity (Wi-Fi, PTT, crane fibre) — it changes the "why 5G" argument in 2.4.1.
