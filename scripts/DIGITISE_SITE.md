# Digitising the BEST terminal polygon (replaces the placeholder GeoJSON)

The shipped `data/site/best_terminal.geojson` is a schematic built from the brief's numbers. Brief §1.1 forbids
hand-drawn rectangles in the final study. Do this before Phase 2:

1. Go to `https://opendata.portdebarcelona.cat` and locate the port plan layer (search "plànol del port", "terminals",
   "Moll Prat"). Download the GIS layer (SHP/GeoJSON/KML) or the PDF plan.
2. If only a PDF is available: georeference it in QGIS (Raster ▸ Georeferencer) using 3–4 control points from
   OpenStreetMap / PNOA orthophoto (`https://pnoa.ign.es`), then digitise.
3. Digitise, in WGS84 (EPSG:4326), these features with the exact `properties.kind` values the loader expects:
   - `terminal`  — outer polygon of the BEST concession
   - `quay_line` — LineString along the berth face (1,500 m)
   - `zone`      — three polygons with `zone ∈ {quay_apron, asc_blocks, gate_rail}` covering the terminal
   - `asc_block` — one polygon per ASC block (used to compute clutter density `r` per zone)
   - `mount`     — points for cranes / lighting masts (optional; otherwise use `candidate_mounts` in config)
4. Set `properties.PLACEHOLDER` to `false` at the FeatureCollection root and
   `site.geojson_is_placeholder.value: false` in `config/scenario_best.yaml`.
5. Run `python -m port5g.cli geometry-check` — it prints area, quay length, per-zone clutter density and warns if
   the area is outside 70–110 ha (brief range).

Record the data source, licence and download date in `docs/assumptions.md`.
