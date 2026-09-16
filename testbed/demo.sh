#!/usr/bin/env bash
# port5g testbed demo — scripted, unattended, target < 3 minutes (brief §5).
# Steps: (1) capture on; (2) three UE classes register -> different Allowed NSSAI; (3) PDU sessions on distinct
# UPFs; (4) PCF QoS flows visible in NGAP; (5) saturation: many IoT UEs -> rejections while URLLC still admitted;
# (6) capture off + summary. Output in captures/.
set -euo pipefail
cd "$(dirname "$0")"
T0=$(date +%s); log(){ printf '[%3ds] %s\n' $(( $(date +%s) - T0 )) "$*"; }
LOG=captures/demo_$(date +%Y%m%d_%H%M%S).log; exec > >(tee "$LOG") 2>&1

log "1/6 start capture (NGAP/PFCP/GTP-U)"
docker compose --profile demo up -d capture; sleep 2

log "2/6 register crane, shuttle, reefer UEs"
docker compose --profile demo up -d ue-crane ue-shuttle ue-reefer; sleep 12
for u in ue-crane ue-shuttle ue-reefer; do
  log "   $u Allowed NSSAI:"; docker compose logs $u 2>/dev/null | grep -iE "allowed|nssai|registration" | tail -3 || true
done

log "3/6 PDU sessions and UE IPs (subnet tells you the UPF: 10.45.1=control 10.45.2=vision 10.45.3=iot)"
for u in ue-crane ue-shuttle ue-reefer; do
  docker compose exec -T $u sh -c 'ip -4 -o addr show | grep uesimtun || true'
done

log "4/6 QoS flows signalled by PCF/SMF (from SMF log)"
docker compose logs smf 2>/dev/null | grep -iE "5QI|QFI|ARP|qos" | tail -6 || true

log "5/6 saturation: start 40 IoT UEs (max ue per slice is limited in amf.yaml/global.max) then one more crane"
docker compose --profile demo run -d --name ue-flood ue-reefer ue -c /etc/ueransim/ue-reefer.yaml -n 40 -i imsi-999700000000021 >/dev/null 2>&1 || true
sleep 15
docker compose logs amf 2>/dev/null | grep -iE "reject|cause|overload" | tail -5 || true
log "   crane (URLLC) still admitted?"; docker compose --profile demo run --rm ue-crane ue -c /etc/ueransim/ue-crane.yaml -i imsi-999700000000002 & sleep 10; kill %1 2>/dev/null || true

log "6/6 stop capture, summarise"
docker compose --profile demo stop capture ue-flood >/dev/null 2>&1 || true; docker rm -f ue-flood >/dev/null 2>&1 || true
PCAP=$(ls -t captures/*.pcap | head -1)
command -v tshark >/dev/null && tshark -r "$PCAP" -Y "ngap.procedureCode == 14 || pfcp.msg_type == 50" -T fields -e frame.number -e _ws.col.Protocol -e _ws.col.Info | head -20 || echo "tshark not installed — open $PCAP in Wireshark: filter 'ngap.procedureCode==14 || pfcp.msg_type==50'"
log "done — capture: $PCAP  log: $LOG"
