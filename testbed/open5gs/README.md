Open5GS configs. Only the files that carry project-specific content (slices, DNNs, UPF selection, QoS policy)
are written out in full: amf.yaml, smf.yaml, nssf.yaml, pcf.yaml, upf-*.yaml. nrf/scp/ausf/udm/udr/bsf.yaml are
copies of the upstream defaults with `sbi.server.address` set to the compose IPs — generate them with
`bash gen_defaults.sh` after pulling the image (they depend on the pinned Open5GS version).
PLMN 999/70 + NID 000007 is used as the SNPN identity (test range). Verify every key against the Open5GS
version pinned in docker-compose.yml — the YAML schema changed between 2.6 and 2.7.
