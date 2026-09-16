# Network architecture (brief §3) — working notes

## 3.1 SNPN vs PNI-NPN — recommendation skeleton

| Criterion | SNPN (own PLMN ID + NID) | PNI-NPN (CAG + S-NSSAI from MNO) | Weight |
|---|---|---|---|
| Data sovereignty / isolation | Full: UDM/UDR, UPF, N6 all on site | Control plane in MNO core; N6 breakout negotiable | High (cargo data) |
| SLA control | Terminal controls scheduler, QoS, TDD | Contractual; MNO TDD pattern fixed (DDDSU) | High — **UL-heavy TDD needs SNPN** |
| Handheld roaming at gate | Needs Credentials Holder / dual-SIM / PNI-NPN fallback (Rel-17 §5.30.2.9) | Native | Medium |
| Availability during MNO outage | Unaffected | Depends on MNO | High (24/7 terminal) |
| Spectrum | Self-provision 3.8–3.92 GHz [UNVERIFIED] | MNO n78 licensed | — |
| Cost | Core + radio capex; no recurring MNO fee | Opex; lower capex | Medium |

Recommendation (to be argued with the numbers): **SNPN**, with a public-network fallback for the ~200 handhelds
via dual-registration or a PNI-NPN slice at the gate. The decisive technical argument is the TDD pattern: the
UL-heavy configuration in fig. 7 is only available if we own the carrier.

## 3.2 Functions and placement (draw as `figures/architecture.svg`)

On-site (terminal server room, ≤ 2 km fibre from every DU): gNB-CU + DUs on masts/cranes, UPF (local
breakout, N6 → MEC), AMF, SMF, PCF, UDM/UDR, AUSF, NRF, NSSF; MEC platform hosting the crane-control
application and the shuttle fleet manager. Optional: NEF (QoS-on-demand to the TOS), NWDAF (load analytics).
External via N6: TOS (nGen-equivalent), corporate IT, internet breakout with firewall.

Why the UPF is on site: `results.json → latency.local_upf_proof` — with the placeholder 8 ms remote transport
term, one-way latency is 12.5 ms > PDB 10 ms; local = 4.5 ms.

## 3.3 Slices — see `config/qos.yaml`; 3.4 QoS flow table — generated from `qos.yaml` by the report build.

## 3.5 Procedures — `docs/msc/*.mmd` (Mermaid). Render with `npx -y @mermaid-js/mermaid-cli -i docs/msc/01_registration_slice_selection.mmd -o figures/msc01.svg`.
