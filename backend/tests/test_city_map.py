from collections import Counter

from app.city_map import build_city_map
from app.models import WorldState


def test_city_map_uses_connected_road_metadata():
    layout = build_city_map(WorldState())
    tiles = {(tile.x, tile.y): tile for tile in layout.tiles}
    roads = [tile for tile in layout.tiles if tile.kind == "road"]

    assert roads
    assert any(tile.road_type == "cross" for tile in roads)
    for tile in roads:
        assert tile.road_type is not None
        for direction in tile.road_connections:
            dx, dy = {
                "n": (0, -1),
                "e": (1, 0),
                "s": (0, 1),
                "w": (-1, 0),
            }[direction]
            neighbor = tiles[(tile.x + dx, tile.y + dy)]
            assert neighbor.kind == "road"


def test_building_districts_do_not_overlap_and_respect_upper_limits():
    layout = build_city_map(WorldState())
    occupied_tiles = [tile for tile in layout.tiles if tile.building_id]
    occupied_by_building = Counter(tile.building_id for tile in occupied_tiles)

    assert any(building.units > 1 for building in layout.buildings)
    for building in layout.buildings:
        assert building.units <= building.max_units
        assert occupied_by_building[building.id] == building.width * building.height


def test_building_districts_stay_off_roads_and_water():
    layout = build_city_map(WorldState(roads=8))

    for tile in layout.tiles:
        if tile.building_id:
            assert tile.kind not in {"road", "water"}


def test_initial_city_counts_still_match_simulation_units():
    state = WorldState()
    layout = build_city_map(state)
    units_by_kind = Counter(building.kind for building in layout.buildings for _ in range(building.units))

    assert units_by_kind["farm"] == state.farms
    assert units_by_kind["factory"] == state.factories
    assert units_by_kind["residential"] == state.housing
    assert units_by_kind["market"] == state.markets
    assert units_by_kind["power_plant"] == state.power_plants
