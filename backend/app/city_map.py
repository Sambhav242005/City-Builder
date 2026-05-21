from __future__ import annotations

from dataclasses import dataclass

from .models import (
    CityMapLayout,
    MapBuilding,
    MapTile,
    MapTileKind,
    RoadDirection,
    RoadType,
    WorldState,
)


MAP_WIDTH = 14
MAP_HEIGHT = 9

GridPoint = tuple[int, int]

WATER_TILES: set[GridPoint] = {(0, 7), (0, 8), (1, 8), (2, 8)}
DIRECTION_OFFSETS: dict[RoadDirection, GridPoint] = {
    "n": (0, -1),
    "e": (1, 0),
    "s": (0, 1),
    "w": (-1, 0),
}

BASE_ROAD_ROWS = {2, 5}
BASE_ROAD_COLUMNS = {4, 9}
ROAD_EXPANSION_ROUTES: list[list[GridPoint]] = [
    [(x, 8) for x in range(4, 10)],
    [(x, 7) for x in range(1, 5)],
    [(13, y) for y in range(2, 6)],
]


@dataclass(frozen=True)
class DistrictSpec:
    kind: MapTileKind
    base_label: str
    anchor: GridPoint
    width: int
    height: int
    units: int
    capacity: int
    workers_per_unit: int = 0
    output_per_unit: float = 0.0
    income_per_unit: float = 0.0
    pollution_per_unit: float = 0.0
    status: str = "Operating"


def build_city_map(state: WorldState) -> CityMapLayout:
    roads = build_road_network(state)
    road_metadata = build_road_metadata(roads)
    blocked = set(roads) | set(WATER_TILES)
    tile_buildings: dict[GridPoint, MapBuilding] = {}
    buildings: list[MapBuilding] = []

    for index, spec in enumerate(district_pipeline(state), start=1):
        if spec.units <= 0:
            continue

        cells = rectangle(spec.anchor, spec.width, spec.height)
        if not can_reserve_district(cells, blocked, set(tile_buildings)):
            continue

        building = make_district_building(spec, index)
        buildings.append(building)
        for cell in cells:
            tile_buildings[cell] = building

    tiles: list[MapTile] = []
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            position = (x, y)
            building = tile_buildings.get(position)
            road_connections = road_metadata.get(position, [])
            road_type = road_type_for(road_connections) if position in roads else None

            if position in WATER_TILES:
                kind: MapTileKind = "water"
                label = "Waterfront"
                active = True
            elif position in roads:
                kind = "road"
                label = road_label(road_type)
                active = True
            elif building is not None:
                kind = building.kind
                label = building.label
                active = True
            else:
                kind = "empty"
                label = "Available Land"
                active = False

            tiles.append(
                MapTile(
                    x=x,
                    y=y,
                    kind=kind,
                    label=label,
                    active=active,
                    zone=kind if kind != "empty" else None,
                    roadType=road_type,
                    roadConnections=road_connections,
                    buildingId=building.id if building else None,
                    lotId=lot_id(position, roads),
                    isAnchor=bool(building and building.x == x and building.y == y),
                )
            )

    return CityMapLayout(width=MAP_WIDTH, height=MAP_HEIGHT, tiles=tiles, buildings=buildings)


def build_road_network(state: WorldState) -> set[GridPoint]:
    roads: set[GridPoint] = set()

    for row in BASE_ROAD_ROWS:
        roads.update((x, row) for x in range(MAP_WIDTH))

    for column in BASE_ROAD_COLUMNS:
        roads.update((column, y) for y in range(MAP_HEIGHT))

    for route in ROAD_EXPANSION_ROUTES[: max(0, state.roads - 4)]:
        roads.update(route)

    return {point for point in roads if in_bounds(point) and point not in WATER_TILES}


def build_road_metadata(roads: set[GridPoint]) -> dict[GridPoint, list[RoadDirection]]:
    metadata: dict[GridPoint, list[RoadDirection]] = {}
    for point in roads:
        connections: list[RoadDirection] = []
        x, y = point
        for direction, (dx, dy) in DIRECTION_OFFSETS.items():
            if (x + dx, y + dy) in roads:
                connections.append(direction)
        metadata[point] = connections
    return metadata


def district_pipeline(state: WorldState) -> list[DistrictSpec]:
    government_workers = max(6, round(state.population * 0.05))

    return [
        DistrictSpec(
            kind="residential",
            base_label="Residential District",
            anchor=(0, 0),
            width=4,
            height=2,
            units=state.housing,
            capacity=12,
            workers_per_unit=12,
            income_per_unit=14,
            status="Occupied",
        ),
        DistrictSpec(
            kind="market",
            base_label="Market Quarter",
            anchor=(5, 0),
            width=4,
            height=2,
            units=state.markets,
            capacity=6,
            workers_per_unit=5,
            output_per_unit=20,
            income_per_unit=26,
            status="Trading",
        ),
        DistrictSpec(
            kind="factory",
            base_label="Industrial Yard",
            anchor=(10, 0),
            width=4,
            height=2,
            units=state.factories,
            capacity=8,
            workers_per_unit=8,
            output_per_unit=15,
            income_per_unit=22,
            pollution_per_unit=8,
        ),
        DistrictSpec(
            kind="park",
            base_label="Parkland",
            anchor=(0, 3),
            width=4,
            height=2,
            units=max(1, state.parks),
            capacity=4,
            workers_per_unit=2,
            income_per_unit=3,
            status="Maintained",
        ),
        DistrictSpec(
            kind="government",
            base_label="Civic Campus",
            anchor=(5, 3),
            width=4,
            height=2,
            units=4,
            capacity=4,
            workers_per_unit=max(1, government_workers // 4),
            income_per_unit=8,
            status="Active",
        ),
        DistrictSpec(
            kind="farm",
            base_label="Farm Belt",
            anchor=(5, 6),
            width=4,
            height=2,
            units=state.farms,
            capacity=16,
            workers_per_unit=4,
            output_per_unit=10,
            income_per_unit=10,
        ),
        DistrictSpec(
            kind="power_plant",
            base_label="Energy Yard",
            anchor=(10, 6),
            width=4,
            height=2,
            units=state.power_plants,
            capacity=4,
            workers_per_unit=3,
            output_per_unit=28,
            income_per_unit=12,
            pollution_per_unit=7,
            status="Supplying",
        ),
    ]


def can_reserve_district(cells: list[GridPoint], blocked: set[GridPoint], occupied: set[GridPoint]) -> bool:
    if not cells:
        return False
    if not all(in_bounds(cell) for cell in cells):
        return False
    if any(cell in blocked or cell in occupied for cell in cells):
        return False
    return any(touches_road(cell, blocked) for cell in cells)


def touches_road(point: GridPoint, blocked: set[GridPoint]) -> bool:
    x, y = point
    for dx, dy in DIRECTION_OFFSETS.values():
        neighbor = (x + dx, y + dy)
        if neighbor in blocked and neighbor not in WATER_TILES:
            return True
    return False


def rectangle(anchor: GridPoint, width: int, height: int) -> list[GridPoint]:
    x, y = anchor
    return [(x + dx, y + dy) for dy in range(height) for dx in range(width)]


def make_district_building(spec: DistrictSpec, index: int) -> MapBuilding:
    max_units = max(spec.capacity, spec.units)
    level = district_level(spec.units, spec.capacity)
    scale = district_scale(spec.kind, spec.units, level)
    return MapBuilding(
        id=f"{spec.kind}-{index}",
        kind=spec.kind,
        label=district_label(spec, level),
        x=spec.anchor[0],
        y=spec.anchor[1],
        width=spec.width,
        height=spec.height,
        units=spec.units,
        maxUnits=max_units,
        level=level,
        scale=scale,
        workers=spec.workers_per_unit * spec.units,
        output=round(spec.output_per_unit * spec.units, 2),
        income=round(spec.income_per_unit * spec.units, 2),
        pollution=round(spec.pollution_per_unit * spec.units, 2),
        status=spec.status,
        assetKey=asset_key_for(spec.kind, scale),
    )


def district_level(units: int, capacity: int) -> int:
    if units <= 1 or capacity <= 1:
        return 1
    ratio = units / capacity
    if ratio >= 0.7:
        return 3
    if ratio >= 0.35:
        return 2
    return 1


def district_scale(kind: MapTileKind, units: int, level: int):
    if kind == "government":
        return "landmark"
    if level >= 3:
        return "maximum"
    if units > 1:
        return "merged"
    return "single"


def district_label(spec: DistrictSpec, level: int) -> str:
    if spec.kind == "government":
        return spec.base_label
    if level >= 3:
        return f"Dense {spec.base_label}"
    return spec.base_label


def asset_key_for(kind: MapTileKind, scale: str) -> str:
    if scale in {"merged", "maximum"} and kind in {"residential", "factory", "farm", "market"}:
        return f"merged_{kind}"
    return kind


def road_type_for(connections: list[RoadDirection]) -> RoadType:
    count = len(connections)
    if count <= 1:
        return "end"
    if count == 4:
        return "cross"
    if count == 3:
        return "t"
    if ("n" in connections and "s" in connections) or ("e" in connections and "w" in connections):
        return "straight"
    return "corner"


def road_label(road_type: RoadType | None) -> str:
    labels: dict[RoadType, str] = {
        "end": "Road End",
        "straight": "Straight Road",
        "corner": "Road Corner",
        "t": "T-Junction",
        "cross": "Crossroad",
    }
    return labels[road_type] if road_type else "Road"


def lot_id(point: GridPoint, roads: set[GridPoint]) -> str:
    nearest_x = min((x for x, _ in roads), key=lambda road_x: abs(road_x - point[0]))
    nearest_y = min((y for _, y in roads), key=lambda road_y: abs(road_y - point[1]))
    return f"lot-{nearest_x}-{nearest_y}"


def in_bounds(point: GridPoint) -> bool:
    x, y = point
    return 0 <= x < MAP_WIDTH and 0 <= y < MAP_HEIGHT
