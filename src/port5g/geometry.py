"""Terminal geometry: GeoJSON -> local metric frame, zones, container blocks, demand grid, candidate mounts."""
from __future__ import annotations

import json
import math
import warnings
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from shapely.geometry import LineString, Point, Polygon, shape


class PlaceholderGeometryWarning(UserWarning):
    pass


@dataclass
class Site:
    terminal: Polygon
    quay: LineString
    zones: dict[str, Polygon]
    asc_blocks: list[Polygon] = field(default_factory=list)
    placeholder: bool = True
    origin: tuple[float, float] = (0.0, 0.0)

    @property
    def area_ha(self) -> float:
        return self.terminal.area / 1e4

    def bounds(self):
        return self.terminal.bounds

    def clutter_density(self, zone: str) -> float:
        """Ground fraction of a zone covered by ASC blocks — feeds InF `r` once real polygons exist."""
        z = self.zones[zone]
        cov = sum(b.intersection(z).area for b in self.asc_blocks)
        return cov / z.area if z.area else 0.0


def _projector(lat0: float, lon0: float):
    kx = 111_320.0 * math.cos(math.radians(lat0))
    ky = 111_320.0
    def to_local(coords):
        return [((lon - lon0) * kx, (lat - lat0) * ky) for lon, lat in coords]
    return to_local


def load_site(cfg) -> Site:
    path = Path(cfg.root) / cfg.scenario_best.site.geojson
    gj = json.loads(path.read_text(encoding="utf-8"))
    props = gj.get("properties", {})
    placeholder = bool(props.get("PLACEHOLDER", False)) or bool(cfg.scenario_best.site.geojson_is_placeholder)
    if placeholder:
        warnings.warn("Site geometry is a SCHEMATIC PLACEHOLDER — see scripts/DIGITISE_SITE.md. "
                      "Figures 1/2 and the site count are NOT reportable until replaced.",
                      PlaceholderGeometryWarning, stacklevel=2)
    origin = props.get("local_origin", {})
    feats = gj["features"]
    lat0 = origin.get("lat") or feats[0]["geometry"]["coordinates"][0][0][1]
    lon0 = origin.get("lon") or feats[0]["geometry"]["coordinates"][0][0][0]
    proj = _projector(lat0, lon0)

    def local(geom):
        g = shape(geom)
        if g.geom_type == "Polygon":
            return Polygon(proj(g.exterior.coords))
        if g.geom_type == "LineString":
            return LineString(proj(g.coords))
        if g.geom_type == "Point":
            return Point(proj([g.coords[0]])[0])
        raise ValueError(g.geom_type)

    terminal = quay = None
    zones, blocks = {}, []
    for f in feats:
        k = f["properties"].get("kind")
        if k == "terminal":
            terminal = local(f["geometry"])
        elif k == "quay_line":
            quay = local(f["geometry"])
        elif k == "zone":
            zones[f["properties"]["zone"]] = local(f["geometry"])
        elif k == "asc_block":
            blocks.append(local(f["geometry"]))
    if terminal is None or quay is None or not zones:
        raise ValueError("GeoJSON must contain kind=terminal, quay_line and zone features")
    return Site(terminal, quay, zones, blocks, placeholder, (lat0, lon0))


@dataclass
class Mount:
    id: str
    type: str
    x: float
    y: float
    h: float


def candidate_mounts(cfg) -> list[Mount]:
    heights = cfg.ues.gnb.height_m_by_mount
    return [Mount(p["id"], p["type"], float(p["x"]), float(p["y"]), float(heights[p["type"]]))
            for p in cfg.scenario_best.candidate_mounts.points]


@dataclass
class Grid:
    x: np.ndarray          # (N,)
    y: np.ndarray          # (N,)
    zone: np.ndarray       # (N,) str
    res_m: float

    def __len__(self):
        return len(self.x)


def demand_grid(site: Site, res_m: float) -> Grid:
    minx, miny, maxx, maxy = site.bounds()
    xs = np.arange(minx + res_m / 2, maxx, res_m)
    ys = np.arange(miny + res_m / 2, maxy, res_m)
    X, Y = np.meshgrid(xs, ys)
    X, Y = X.ravel(), Y.ravel()
    zone = np.full(len(X), "", dtype=object)
    from shapely import contains_xy
    for name, poly in site.zones.items():
        m = contains_xy(poly, X, Y)
        zone[m & (zone == "")] = name
    keep = zone != ""
    return Grid(X[keep], Y[keep], zone[keep].astype(str), res_m)
