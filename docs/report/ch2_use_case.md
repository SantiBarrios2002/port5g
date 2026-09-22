# 2 Needs and innovation opportunity: private 5G for an automated container terminal

> **DRAFT for the team (2026-09-22).** Markers:
> **[VERIFY: …]** = a fact that must be checked against a primary source before submission (most come from the
> project brief, which was compiled from press coverage). **[TODO: …]** = content the team still has to produce.
> Reference numbers point to `docs/report/references.md`. Numbers attributed to "the model" come from
> `results/results.json` and inherit the confidence of their config inputs (`docs/assumptions.md`).

## 2.1 Sector: maritime container terminals

Container terminals are the interface between sea and land transport. Their performance is measured in how
fast they turn a vessel around and how reliably they move boxes between quay, yard, gate and rail. They already
use heavy automation, but the automation grew up in separate pieces: automated yard cranes on fixed rails and
fibre, manned quay cranes and vehicles, and a patchwork of Wi-Fi and proprietary radio for telemetry and
handhelds.

Within the course's sector list this use case belongs to **Logistics / Transportation**. Technically it is an
instance of what 5G Americas calls *communication for automation in vertical domains* [6] and of the
*remote object manipulation* use case in the GSMA mmWave study, which explicitly names the remote control of
"complex equipment (e.g., cranes …)" as a way to make work sites safer [10, p. 55].

## 2.2 Reference site: BEST terminal, Port of Barcelona

We use Hutchison Ports BEST (Barcelona Europe South Terminal) on the Moll Prat as a real reference site, so that
geometry, fleet sizes and constraints are concrete rather than generic. Baseline figures used in this study:

| Parameter | Value used | Status |
|---|---|---|
| Yard area | ~80 ha (some sources ~100 ha) | [VERIFY: sources conflict; phase-dependent] |
| Quay length | 1,500 m, five deep-sea berths | [VERIFY] |
| Ship-to-shore (STS) quay cranes | 11, super post-Panamax, cabin-operated | [VERIFY] |
| Automated stacking cranes (ASC) | ~48–54, rail-mounted, automated | [VERIFY] |
| Shuttle / straddle carriers | ~30, manned | [VERIFY] |
| Reefer plugs | ~1,350 | [VERIFY] |
| Rail terminal | 8 tracks | [VERIFY] |

[TODO: cite the Hutchison Ports BEST facts page and a Port de Barcelona source for each row; digitise the
terminal outline from the port's open-data plan (the model currently runs on a schematic placeholder).]

## 2.3 Current situation and the gap

The yard at BEST is already automated, so the use case is **not** "5G enables automation". The remaining manual,
fragmented parts are:

1. **STS cranes are operated from a cabin** about 40–50 m above the quay [VERIFY height]. Operators work alone,
   at height, looking straight down for long shifts.
2. **Horizontal transport between quay and yard is manned** (shuttle carriers with drivers).
3. **Telemetry and workforce communications run over several separate systems** (Wi-Fi, proprietary telemetry,
   PTT radio) that are hard to manage end to end and give no guaranteed quality of service. [VERIFY: confirm
   what BEST actually uses today — interview/visit or published case study.]

The innovation opportunity is to close that gap with **one managed private 5G network** that supports three
services with very different needs.

## 2.4 Use case description

| # | Service | What changes | Devices (baseline) |
|---|---|---|---|
| **S1** | **Remote STS crane operation** | Operators move from the cabin to a remote operations centre. Each crane streams several camera feeds up to the operator; control commands come down at a high, regular rate. | 11 cranes |
| **S2** | **Driverless shuttle carriers** | Shuttle carriers drive autonomously between quay and yard. They send perception video and telemetry up and receive mission commands; a remote operator takes over when a vehicle is stuck (remote assistance, cf. [8, p. 26]). | ~30 vehicles |
| **S3** | **Unified monitoring and workforce connectivity** | Reefer containers, asset tags, gate cameras and handhelds move onto the same managed network. | ~1,350 reefer plugs, ~2,000 asset tags, ~200 handhelds |

[TODO: Figure 2.1 — illustration of the use case (quay with cranes, remote operations centre, shuttle lanes,
yard, gate, private 5G sites), in the style of the course example. Cite the source of any borrowed artwork.]

**The engineering tension.** S1 and S2 are dominated by *uplink* video, which inverts the usual downlink-heavy
design of mobile networks. S1 control needs low latency and very high reliability but little volume; S2 needs
volume and mobility; S3 needs neither but has by far the most devices and must not be allowed to take capacity
from the other two. One radio network has to serve three incompatible optimisation targets. Resolving that is the
core of the design (Chapter 4).

### 2.4.1 Why 5G, and why not the alternatives

| Alternative | Why it falls short for this use case |
|---|---|
| **Wi-Fi** | Unlicensed spectrum means no control over interference, and contention-based access gives no guaranteed latency. Handover is weak for vehicles at yard speed across a site of ~1 km². |
| **Private LTE** | Mature and licensed, but no URLLC features (mini-slots, configured grant) and no standard network slicing. That limits how well S1 control can be protected from S2/S3 load. |
| **Fibre / cable** | The right answer for fixed equipment, and the ASCs already use it. STS cranes may already carry fibre in their power-cable reel [VERIFY at BEST]. If so, S1 could partly use it, and the case for 5G on the cranes rests on retrofit cost, redundancy and a single managed network rather than on "no alternative". **The team should state this honestly.** Fibre cannot serve S2 vehicles or S3 devices. |
| **Private 5G (chosen)** | Licensed or locally licensed spectrum, a standard QoS framework (5QI/ARP), network slicing to isolate the three services, URLLC features for S1 control, mobility for S2 and massive-IoT support for S3, all on one managed system [1], [6]. |

Replacing wires with radio also has generic benefits in automation: lower installation and maintenance cost,
no wear and tear on moving cables, and deployment flexibility [5, p. 9].

## 2.5 Actors and roles

| Actor | Role in the use case | Main interest / concern |
|---|---|---|
| **Terminal operator** (Hutchison Ports BEST) | Owns the use case; in the recommended model, also owns and operates the private network | Productivity, safety, dependability, control over its own operational data |
| **Port authority** (Autoritat Portuària de Barcelona) | Landlord and concession grantor; drives port-wide digital strategy; could host shared infrastructure | Port competitiveness, safety, coordination between terminals |
| **Spectrum regulator** (Ministry — Secretaría de Estado de Telecomunicaciones; CNMC as market regulator) | Allocates local/private spectrum through the CNAF, grants the licence, sets power limits and fees | Efficient spectrum use, coexistence with public networks |
| **Mobile network operators (MNOs)** | (a) Alternative provider of the network as a PNI-NPN slice; (b) neighbours in adjacent spectrum (coexistence); (c) public coverage for visitors, truck drivers and handheld fallback | Revenue from enterprise services; protection of their own networks |
| **Network vendor / systems integrator** | Supplies RAN, core and edge computing; integrates them with terminal systems | Reference deployment, service contract |
| **Equipment OEMs** (crane, shuttle-carrier and automation vendors) | Retrofit cranes for remote operation, supply autonomy kits; integrate the 5G modems | Certification, safety, interoperability |
| **Terminal operating system (TOS) provider** | Orchestrates moves; consumes telemetry; can request QoS on demand through network exposure | Data access, APIs |
| **Workforce** (crane operators, drivers, stevedores and their organisations) | Operators move to the remote centre; drivers' roles change with automation | Safety and ergonomics (a clear benefit), jobs and working conditions (a real concern, see Ch. 5 SWOT) |
| **Shipping lines and cargo owners** | Indirect customers of the improved service | Vessel turnaround time, reliability, confidentiality of cargo data |
| **Hauliers / truck drivers** | Use the gate (OCR, check-in) | Gate throughput; their phones are MNO devices near our network (coexistence) |

[VERIFY: official names and competences of the Spanish authorities before submission.]

## 2.6 Expected improvements and benefits

Qualitative benefits, each tied to a mechanism. Quantified costs and savings belong to Chapter 5 (techno-economic
model, `economics.py`), where every input is sourced or marked unverified.

- **Safety and ergonomics.** Crane operators leave a cabin at height for a ground-level control room; drivers are
  removed from mixed traffic with heavy machinery. Remote control of cranes as a safety measure is cited in [10, p. 20, p. 55].
- **Productivity and flexibility.** A remote operator is no longer tied to one physical crane. Whether one operator
  can serve more than one crane is a key input to the business case [VERIFY with vendor case studies].
- **Dependability.** One managed network with monitoring and fault management replaces several unmanaged systems.
  Dependability — reliability, availability, maintainability, safety and integrity — is the property automation
  users care about most [6, p. 21].
- **Service isolation.** Slicing lets the terminal guarantee crane control even when thousands of IoT devices and
  30 video-streaming vehicles share the network.
- **Data sovereignty.** A non-public network is deployed in the enterprise's own environment and can use its own
  identities, credentials and authentication [6, pp. 24–25]. With an on-site core and user plane (Ch. 4),
  operational data stays on site under the terminal's control.
- **Foundation for further automation.** The same network can later carry more cameras, drones for inspection or
  additional automated vehicles without a new infrastructure project.

## 2.7 Structure of the rest of the document

Chapter 3 turns the three services into technical requirements. Chapter 4 designs the solution (spectrum, TDD
pattern, architecture, slicing and QoS, radio dimensioning). Chapter 5 assesses costs, business model, regulation
and a SWOT analysis. Chapter 6 concludes.
