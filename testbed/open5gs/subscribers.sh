#!/bin/sh
# Provision subscriber records so each UE class receives a DIFFERENT Allowed NSSAI (brief §5.1).
# Uses open5gs-dbctl from the image. K/OPc are the UERANSIM defaults (test values).
set -e
K=465B5CE8B199B49FAA5F0A2EE238A6BC
OPC=E8ED289DEBA952E4283B54E88E6183CA
DB=${DB_URI:-mongodb://mongo/open5gs}
add() { open5gs-dbctl --db_uri="$DB" add_ue_with_slice "$1" "$K" "$OPC" "$4" "$2" "$3" || true; }   # imsi sst sd dnn
# Crane CPEs: control + vision slices
for i in 01 02 03; do
  add 9997000000000$i 2 000001 control.port5g
  open5gs-dbctl --db_uri="$DB" update_slice 9997000000000$i vision.port5g 1 000002 || true
done
# Shuttle CPEs: vision only
for i in 11 12 13 14 15; do add 9997000000000$i 1 000002 vision.port5g; done
# Reefer/IoT devices: telemetry only (many — used to saturate in the pre-emption step)
for i in $(seq -w 21 60); do add 9997000000000$i 3 000003 iot.port5g; done
echo "subscribers provisioned"
