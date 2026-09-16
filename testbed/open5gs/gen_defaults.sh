#!/bin/sh
# Extract the upstream default configs from the pinned image and patch the SBI/NRF addresses.
set -e
IMG=gradiant/open5gs:${OPEN5GS_TAG:-2.7.2}
for nf in nrf scp ausf udm udr bsf; do
  docker run --rm --entrypoint cat $IMG /etc/open5gs/$nf.yaml > $nf.yaml
done
sed -i 's/127.0.0.10/10.33.0.10/g; s/127.0.0.200/10.33.0.11/g; s/127.0.0.11/10.33.0.12/g; s/127.0.0.12/10.33.0.13/g; s/127.0.0.20/10.33.0.14/g; s/127.0.0.15/10.33.0.16/g' *.yaml
echo "defaults generated — review sbi addresses before make up"
