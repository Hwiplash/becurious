"""공개 SGIS 경계를 웹용 WGS84 단순화 GeoJSON으로 변환한다."""
from __future__ import annotations

import json
from pathlib import Path

from pyproj import Transformer


ROOT = Path(__file__).resolve().parents[1]
GEO = ROOT / "data" / "geo"
TRANSFORM = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)
SPECIAL_NAMES = {"강원도": "강원특별자치도", "전라북도": "전북특별자치도"}


def perpendicular(point, start, end):
    if start == end:
        return ((point[0] - start[0]) ** 2 + (point[1] - start[1]) ** 2) ** .5
    dx, dy = end[0] - start[0], end[1] - start[1]
    return abs(dy * point[0] - dx * point[1] + end[0] * start[1] - end[1] * start[0]) / (dx * dx + dy * dy) ** .5


def rdp(points, epsilon=.002):
    if len(points) < 4:
        return points
    distances = [perpendicular(point, points[0], points[-1]) for point in points[1:-1]]
    distance = max(distances, default=0)
    index = distances.index(distance) + 1 if distances else 0
    if distance > epsilon:
        return rdp(points[: index + 1], epsilon)[:-1] + rdp(points[index:], epsilon)
    return [points[0], points[-1]]


def transform_ring(ring):
    points = [list(TRANSFORM.transform(x, y)) for x, y, *_ in ring]
    closed = points[0] == points[-1]
    simplified = rdp(points)
    if closed and simplified[0] != simplified[-1]:
        simplified.append(simplified[0])
    return simplified if len(simplified) >= 4 else points


def transform_geometry(geometry):
    coordinates = geometry["coordinates"]
    if geometry["type"] == "Polygon":
        result = [transform_ring(ring) for ring in coordinates]
    elif geometry["type"] == "MultiPolygon":
        result = [[transform_ring(ring) for ring in polygon] for polygon in coordinates]
    else:
        raise ValueError(geometry["type"])
    return {"type": geometry["type"], "coordinates": result}


def convert(source: Path, sido: str | None = None):
    collection = json.loads(source.read_text(encoding="utf-8"))
    features = []
    for feature in collection["features"]:
        name = feature["properties"]["title"]
        features.append({
            "type": "Feature",
            "properties": {"name": SPECIAL_NAMES.get(name, name), "sido": sido},
            "geometry": transform_geometry(feature["geometry"]),
        })
    return features


def main():
    sido_features = convert(GEO / "전국_시도_경계.json")
    sigungu_features = []
    for path in sorted(GEO.glob("*_시군구_경계.json")):
        sido = SPECIAL_NAMES.get(path.name.split("_시군구_경계.json")[0], path.name.split("_시군구_경계.json")[0])
        sigungu_features.extend(convert(path, sido=sido))
    for name, features in [("sido.geojson", sido_features), ("sigungu.geojson", sigungu_features)]:
        output = {"type": "FeatureCollection", "features": features}
        (GEO / name).write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()
