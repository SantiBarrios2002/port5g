# port5g testbed — Open5GS + UERANSIM

`make testbed-up` → `make testbed-demo` → `make testbed-down` (from the repo root).

## What it demonstrates (brief §5)
1. Three S-NSSAIs in NSSF/AMF/SMF (`open5gs/nssf.yaml`, `amf.yaml`, `smf.yaml`) and subscriber records with
   different subscribed slices (`open5gs/subscribers.sh`) → crane / shuttle / reefer UEs get different Allowed NSSAI.
2. PDU sessions on **distinct UPFs** per DNN (`upf-control|vision|iot.yaml`, UE subnets 10.45.1/2/3.0/24) — visible
   in the PFCP Session Establishment on N4 and in the NGAP PDU Session Resource Setup on N2 (capture container).
3. PCF policy with different 5QI/ARP per DNN plus a GBR PCC rule for shuttle video (`pcf.yaml`).
4. Saturation step in `demo.sh`.
5. Figure 10: open the pcap, filter `ngap.procedureCode == 14` (InitialContextSetup) and `pfcp.msg_type == 50`
   (Session Establishment Request), annotate the IEs (Allowed NSSAI, QoS Flow Setup List / 5QI / ARP; PDR/FAR/QER/F-TEID).

## Known limitation — report it, do not hide it
Open5GS + UERANSIM has **no radio scheduler**, so ARP-based *pre-emption of radio resources* cannot happen here.
What the core can show is: (a) ARP values carried in NGAP/PFCP per flow, (b) admission limits at the core
(`global.max.ue`, per-slice session counts) producing rejections under saturation. The radio pre-emption event
itself is produced by the Python simulator (`admission.py`, figure 8). Say exactly this on the slide.

## Before the first run
- `cd testbed/open5gs && ./gen_defaults.sh` to produce nrf/scp/ausf/udm/udr/bsf.yaml from the pinned image.
- Pin `OPEN5GS_TAG` / `UERANSIM_TAG` in `.env` once a run succeeds; record them here.
- Open5GS YAML keys differ between 2.6 and 2.7 — validate each file against the version's sample configs.
- Rehearse: the demo must finish in < 3 min on the presentation laptop; pre-pull images.
