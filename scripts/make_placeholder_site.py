"""Generate the PLACEHOLDER site GeoJSON (local metres). Replace with digitised data in Phase 2.

Only two published numbers are reproduced: 1,500 m quay and ~80 ha. Everything else is schematic.
Run: python scripts/make_placeholder_site.py > data/site/best_terminal.geojson
"""
import json

QUAY = 1500.0
DEPTH = 540.0           # 1500 x 540 m = 81 ha, matches published ~80 ha
N_BLOCKS = 34           # automated blocks after the 2024–25 expansion (seatrade-maritime 2024-08)
BLOCK_W, BLOCK_L = 30.0, 360.0
Y0_BLOCKS = 80.0

features = []
def poly(name, kind, coords, **props):
    features.append({"type": "Feature", "properties": {"name": name, "kind": kind, **props},
                     "geometry": {"type": "Polygon", "coordinates": [coords + [coords[0]]]}})
def point(name, kind, x, y, **props):
    features.append({"type": "Feature", "properties": {"name": name, "kind": kind, **props},
                     "geometry": {"type": "Point", "coordinates": [x, y]}})

poly("terminal", "terminal", [[0, 0], [QUAY, 0], [QUAY, DEPTH], [0, DEPTH]])
features.append({"type": "Feature", "properties": {"name": "quay", "kind": "quay_line"},
                 "geometry": {"type": "LineString", "coordinates": [[0, 0], [QUAY, 0]]}})
poly("quay_apron", "zone", [[0, 0], [QUAY, 0], [QUAY, 60], [0, 60]], zone="quay_apron")
poly("asc_blocks", "zone", [[0, 60], [QUAY, 60], [QUAY, 460], [0, 460]], zone="asc_blocks")
poly("gate_rail", "zone", [[0, 460], [QUAY, 460], [QUAY, DEPTH], [0, DEPTH]], zone="gate_rail")

pitch = QUAY / N_BLOCKS
for i in range(N_BLOCKS):
    x0 = i * pitch + (pitch - BLOCK_W) / 2
    poly(f"block_{i+1:02d}", "container_block",
         [[x0, Y0_BLOCKS], [x0 + BLOCK_W, Y0_BLOCKS], [x0 + BLOCK_W, Y0_BLOCKS + BLOCK_L], [x0, Y0_BLOCKS + BLOCK_L]])

for k in range(15):                                   # 15 STS cranes (container-news 2026-09)
    point(f"sts_{k+1:02d}", "mount", 50 + k * 100, 15, mount_type="sts_crane")
for k in range(8):                                    # lighting masts, waterside + landside block ends
    x = 95 + k * 190
    point(f"mast_w_{k+1}", "mount", x, 70, mount_type="lighting_mast")
    point(f"mast_l_{k+1}", "mount", x, 455, mount_type="lighting_mast")
for k in range(4):
    point(f"mast_gate_{k+1}", "mount", 190 + k * 380, 520, mount_type="lighting_mast")

gj = {"type": "FeatureCollection",
      "crs_note": "PLACEHOLDER local metric frame: x east along quay, y inland. Not georeferenced.",
      "features": features}
print(json.dumps(gj, indent=1))
