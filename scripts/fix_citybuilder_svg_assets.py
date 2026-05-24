from __future__ import annotations

import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACK_ROOT = ROOT / "frontend" / "src" / "assets" / "citybuilder-svg-mvp-v2" / "citybuilder_svg_mvp_v2"
ASSET_ROOT = PACK_ROOT / "assets"
CATALOG_PATH = PACK_ROOT / "metadata" / "asset_catalog.json"
ACTION_SCHEMA_PATH = PACK_ROOT / "metadata" / "action_schema.json"
SAMPLE_MAP_STATE_PATH = PACK_ROOT / "metadata" / "sample_map_state.json"

SIZE = 160
TILE_X = 24
TILE_Y = 24
TILE_SIZE = 112
TILE_MAX = TILE_X + TILE_SIZE
TILE = (
    f'<rect x="{TILE_X}" y="{TILE_Y}" width="{TILE_SIZE}" height="{TILE_SIZE}" '
    'rx="10" fill="{fill}" stroke="{stroke}" stroke-width="3"/>'
)


def slug(value: str) -> str:
    return value.replace("_", "-")


def shadow_def(asset_id: str) -> str:
    return f"""  <defs>
    <filter id="{slug(asset_id)}-shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="8" stdDeviation="5" flood-color="#000000" flood-opacity="0.28"/>
    </filter>
  </defs>"""


def svg(asset_id: str, title: str, body: str, use_shadow: bool = True) -> str:
    defs = f"\n{shadow_def(asset_id)}\n" if use_shadow else ""
    wrapped = (
        f'<g filter="url(#{slug(asset_id)}-shadow)">\n{body}\n  </g>'
        if use_shadow
        else body
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SIZE} {SIZE}" width="{SIZE}" height="{SIZE}" role="img" aria-label="{html.escape(title)}">{defs}
  {wrapped}
</svg>
"""


def tile(fill: str, stroke: str = "#cfe8b6") -> str:
    return f"    {TILE.format(fill=fill, stroke=stroke)}"


def tile_clip_def(asset_id: str) -> str:
    clip_id = f"{slug(asset_id)}-tile-clip"
    return (
        f'    <defs><clipPath id="{clip_id}">'
        f'<rect x="{TILE_X}" y="{TILE_Y}" width="{TILE_SIZE}" height="{TILE_SIZE}" rx="10"/>'
        "</clipPath></defs>"
    )


def clipped_tile_group(asset_id: str, body: str) -> str:
    return "\n".join([
        tile_clip_def(asset_id),
        f'    <g clip-path="url(#{slug(asset_id)}-tile-clip)">',
        body,
        "    </g>",
    ])


EXTRA_ASSETS: list[dict[str, object]] = [
    {
        "id": "wheat_farm",
        "title": "Wheat Farm",
        "category": "farm",
        "file": "assets/farms/wheat_farm.svg",
        "viewBox": "0 0 160 160",
        "size": [1, 1],
        "requiresRoad": True,
        "tags": ["farm", "food", "grain", "price_supply"],
        "economy": {
            "outputs": {"food": 14, "grain": 10},
            "priceEffects": {"food": -0.05, "grain": -0.08},
            "waterUse": 3,
            "labor": 4,
        },
    },
    {
        "id": "vegetable_farm",
        "title": "Vegetable Farm",
        "category": "farm",
        "file": "assets/farms/vegetable_farm.svg",
        "viewBox": "0 0 160 160",
        "size": [1, 1],
        "requiresRoad": True,
        "tags": ["farm", "food", "produce", "fresh_market"],
        "economy": {
            "outputs": {"food": 10, "produce": 12},
            "priceEffects": {"food": -0.03, "produce": -0.09},
            "waterUse": 5,
            "labor": 6,
            "happinessDelta": 0.01,
        },
    },
    {
        "id": "orchard_farm",
        "title": "Orchard Farm",
        "category": "farm",
        "file": "assets/farms/orchard_farm.svg",
        "viewBox": "0 0 160 160",
        "size": [1, 1],
        "requiresRoad": True,
        "tags": ["farm", "food", "fruit", "slow_yield"],
        "economy": {
            "outputs": {"food": 8, "fruit": 14},
            "priceEffects": {"fruit": -0.1},
            "waterUse": 4,
            "labor": 5,
            "happinessDelta": 0.015,
        },
    },
    {
        "id": "livestock_ranch",
        "title": "Livestock Ranch",
        "category": "farm",
        "file": "assets/farms/livestock_ranch.svg",
        "viewBox": "0 0 160 160",
        "size": [1, 1],
        "requiresRoad": True,
        "tags": ["farm", "protein", "dairy", "pollution"],
        "economy": {
            "outputs": {"food": 9, "protein": 12},
            "priceEffects": {"protein": -0.08},
            "waterUse": 6,
            "labor": 7,
            "pollution": 2,
        },
    },
]


SPECIAL_ASSET_UPDATES: dict[str, dict[str, object]] = {
    "sidewalk_plaza": {
        "category": "civic",
        "file": "assets/civic/sidewalk_plaza.svg",
        "tags": ["civic", "plaza", "walkable", "happiness"],
        "requiresRoad": True,
        "economy": {"happinessDelta": 0.025, "maintenance": 2, "commerceBoost": 0.03},
    },
    "road_roundabout": {
        "tags": ["road", "intersection", "traffic_flow"],
        "traffic": {"connects": ["n", "e", "s", "w"], "flowBonus": 0.12},
    },
    "road_preview_overlay": {
        "category": "overlay",
        "file": "assets/overlays/road_preview_overlay.svg",
        "tags": ["overlay", "road_preview", "placement"],
    },
    "farm_barn": {
        "category": "farm",
        "file": "assets/farms/farm_barn.svg",
        "tags": ["farm", "storage", "food_buffer"],
        "economy": {"storageBonus": {"food": 20}, "spoilageReduction": 0.05, "labor": 2},
    },
    "greenhouse": {
        "category": "farm",
        "file": "assets/farms/greenhouse.svg",
        "tags": ["farm", "produce", "high_yield", "power_use"],
        "economy": {
            "outputs": {"food": 12, "produce": 16},
            "priceEffects": {"produce": -0.12},
            "waterUse": 2,
            "powerUse": 3,
            "seasonResilience": 0.2,
        },
    },
    "streetlight": {
        "tags": ["prop", "utility", "safety", "night_visibility"],
        "placement": {"layer": "prop", "blocksBuild": False, "radius": 2},
        "economy": {"safetyDelta": 0.015, "maintenance": 1, "powerUse": 0.2},
    },
    "rock_cluster": {
        "tags": ["prop", "decoration", "landscape"],
        "placement": {"layer": "prop", "blocksBuild": False},
    },
}


def normalize_assets(assets: list[dict[str, object]]) -> list[dict[str, object]]:
    by_id = {str(asset["id"]): dict(asset) for asset in assets}
    for asset_id, updates in SPECIAL_ASSET_UPDATES.items():
        if asset_id in by_id:
            by_id[asset_id].update(updates)
    for asset in EXTRA_ASSETS:
        by_id[str(asset["id"])] = dict(asset)
    return list(by_id.values())


def terrain(asset_id: str) -> str:
    if asset_id == "grass_tile_a":
        return "\n".join([
            tile("#78b83f", "#b5df58"),
            '    <path d="M44 52 q5 -7 10 0 M77 44 q5 -7 10 0 M104 68 q5 -7 10 0 M58 96 q5 -7 10 0" stroke="#4f8f24" stroke-width="3" fill="none" stroke-linecap="round"/>',
            '    <circle cx="48" cy="68" r="3" fill="#d8e65a"/><circle cx="111" cy="51" r="3" fill="#d8e65a"/><ellipse cx="101" cy="95" rx="7" ry="4" fill="#6e6a5a"/>',
        ])
    if asset_id == "grass_tile_b":
        return "\n".join([
            tile("#85c948", "#b5df58"),
            '    <path d="M45 85 q5 -8 10 0 M66 57 q5 -8 10 0 M91 41 q5 -8 10 0 M112 92 q5 -8 10 0" stroke="#4f8f24" stroke-width="3" fill="none" stroke-linecap="round"/>',
            '    <circle cx="60" cy="100" r="3" fill="#d8e65a"/><circle cx="121" cy="61" r="3" fill="#d8e65a"/><ellipse cx="72" cy="77" rx="7" ry="4" fill="#6e6a5a"/>',
        ])
    if asset_id == "dirt_tile":
        return "\n".join([
            tile("#a66b34", "#c98946"),
            '    <circle cx="49" cy="64" r="3" fill="#7c5634"/><circle cx="85" cy="51" r="3" fill="#7c5634"/><circle cx="111" cy="84" r="3" fill="#7c5634"/><circle cx="65" cy="101" r="3" fill="#7c5634"/>',
        ])
    if asset_id == "empty_lot_tile":
        return "\n".join([
            tile("#6f913a", "#b5df58"),
            '    <path d="M40 44 H120 M40 68 H120 M40 92 H120 M40 116 H120 M44 40 V120 M68 40 V120 M92 40 V120 M116 40 V120" stroke="#d8e8ae" stroke-width="2" opacity=".45"/>',
            '    <circle cx="115" cy="51" r="4" fill="#b5df58"/>',
        ])
    if asset_id == "sand_tile":
        return "\n".join([
            tile("#e3bd78", "#f5d894"),
            '    <circle cx="55" cy="56" r="2.5" fill="#b89058"/><circle cx="91" cy="46" r="2.5" fill="#b89058"/><circle cx="110" cy="92" r="2.5" fill="#b89058"/>',
            '    <path d="M43 96 q25 -14 51 0 q18 9 34 0" stroke="#f5d894" stroke-width="4" fill="none" opacity=".65"/>',
        ])
    if asset_id == "farm_ground_tile":
        return "\n".join([
            tile("#7aa63c", "#b8d85a"),
            '    <path d="M38 46 H122 M38 60 H122 M38 74 H122 M38 88 H122 M38 102 H122 M38 116 H122" stroke="#b98139" stroke-width="5"/>',
            '    <path d="M38 53 H122 M38 67 H122 M38 81 H122 M38 95 H122 M38 109 H122" stroke="#5c8d2f" stroke-width="3"/>',
        ])
    if asset_id == "park_ground_tile":
        return "\n".join([
            tile("#79b842", "#b5df58"),
            '    <path d="M46 111 C75 72 93 75 118 42" stroke="#b49669" stroke-width="8" fill="none" stroke-linecap="round"/>',
            '    <circle cx="103" cy="55" r="14" fill="#51a348"/><circle cx="55" cy="56" r="12" fill="#5db653"/><path d="M46 96 h34" stroke="#7d5435" stroke-width="5" stroke-linecap="round"/>',
            '    <polygon points="116,39 129,51 116,63 103,51" fill="#4bb7ff" stroke="#d8f5ff" stroke-width="2"/>',
        ])
    if asset_id == "water_tile":
        return "\n".join([
            tile("#1598c2", "#9ff6ff"),
            '    <path d="M42 63 q11 -9 22 0 q11 9 22 0 q11 -9 22 0" stroke="#9ff6ff" stroke-width="4" fill="none" opacity=".7"/>',
            '    <path d="M47 93 q11 -9 22 0 q11 9 22 0 q11 -9 22 0" stroke="#9ff6ff" stroke-width="4" fill="none" opacity=".55"/>',
        ])
    if asset_id == "coast_edge_north":
        return "\n".join([
            tile("#e3bd78", "#f5d894"),
            '    <path d="M24 24 H136 V75 C104 59 72 89 24 72 Z" fill="#1598c2" stroke="#9ff6ff" stroke-width="3"/>',
            '    <circle cx="49" cy="83" r="5" fill="#706958"/><circle cx="114" cy="73" r="5" fill="#706958"/>',
        ])
    if asset_id == "coast_edge_corner":
        return "\n".join([
            tile("#e3bd78", "#f5d894"),
            '    <path d="M24 24 H136 V136 C101 106 66 105 24 83 Z" fill="#1598c2" stroke="#9ff6ff" stroke-width="3"/>',
        ])
    if asset_id == "coast_inlet_tile":
        return "\n".join([
            tile("#e3bd78", "#f5d894"),
            '    <path d="M24 24 H136 V63 C117 54 99 57 85 72 C68 91 74 108 55 119 C43 126 33 125 24 119 Z" fill="#1598c2"/>',
            '    <path d="M136 63 C117 54 99 57 85 72 C68 91 74 108 55 119 C43 126 33 125 24 119" stroke="#9ff6ff" stroke-width="4" fill="none" stroke-linecap="round"/>',
            '    <path d="M40 48 q18 -9 36 0 M57 102 q14 -8 29 0 M96 66 q14 -8 29 0" stroke="#76ddf0" stroke-width="3" fill="none" opacity=".72" stroke-linecap="round"/>',
            '    <circle cx="112" cy="103" r="4" fill="#766d5d"/><circle cx="68" cy="57" r="3" fill="#766d5d"/>',
        ])
    if asset_id == "pond_tile":
        return "\n".join([
            tile("#79b842", "#b5df58"),
            '    <ellipse cx="78" cy="82" rx="39" ry="28" fill="#168bb7" stroke="#9ff6ff" stroke-width="4"/>',
            '    <path d="M49 82 q12 -9 24 0 q12 9 24 0" stroke="#9ff6ff" stroke-width="3" fill="none" opacity=".65"/>',
            '    <path d="M111 56 q13 -21 28 -22 M120 64 q10 -11 22 -8" stroke="#70c255" stroke-width="5" fill="none" stroke-linecap="round"/>',
        ])
    return tile("#78b83f", "#b5df58")


def lane_line_horizontal(y: int = 80) -> str:
    return f'<path d="M34 {y} H126" stroke="#f4f4e9" stroke-width="4" stroke-linecap="round" stroke-dasharray="15 12"/>'


def lane_line_vertical(x: int = 80) -> str:
    return f'<path d="M{x} 34 V126" stroke="#f4f4e9" stroke-width="4" stroke-linecap="round" stroke-dasharray="15 12"/>'


def roads(asset_id: str) -> str:
    road = "#4a5058"
    edge = "#9da399"
    if asset_id == "road_preview_overlay":
        return '    <path d="M32 80 H128" stroke="#4bb7ff" stroke-width="10" stroke-linecap="round" stroke-dasharray="12 9" fill="none"/>\n    <circle cx="34" cy="80" r="8" fill="#4bb7ff"/><circle cx="126" cy="80" r="8" fill="#4bb7ff"/>'
    base = tile("#6f913a", "#b5df58")
    if asset_id == "road_straight":
        body = "\n".join([f'      <rect x="24" y="58" width="112" height="44" fill="{road}" stroke="{edge}" stroke-width="3"/>', f"      {lane_line_horizontal()}"])
        return "\n".join([base, clipped_tile_group(asset_id, body)])
    if asset_id == "road_vertical":
        body = "\n".join([f'      <rect x="58" y="24" width="44" height="112" fill="{road}" stroke="{edge}" stroke-width="3"/>', f"      {lane_line_vertical()}"])
        return "\n".join([base, clipped_tile_group(asset_id, body)])
    if asset_id == "road_corner":
        body = "\n".join([
            f'      <path d="M58 24 H102 V58 H136 V102 H58 Z" fill="{road}" stroke="{edge}" stroke-width="3"/>',
            '      <path d="M80 36 V80 H124" stroke="#f4f4e9" stroke-width="4" stroke-dasharray="14 10" fill="none" stroke-linecap="round"/>',
        ])
        return "\n".join([base, clipped_tile_group(asset_id, body)])
    if asset_id == "road_t_junction":
        body = "\n".join([
            f'      <path d="M58 24 H102 V58 H136 V102 H24 V58 H58 Z" fill="{road}" stroke="{edge}" stroke-width="3"/>',
            f"      {lane_line_horizontal()}",
            '      <path d="M80 36 V72" stroke="#f4f4e9" stroke-width="4" stroke-linecap="round" stroke-dasharray="14 10"/>',
        ])
        return "\n".join([base, clipped_tile_group(asset_id, body)])
    if asset_id == "road_cross":
        body = "\n".join([
            f'      <path d="M58 24 H102 V58 H136 V102 H102 V136 H58 V102 H24 V58 H58 Z" fill="{road}" stroke="{edge}" stroke-width="3"/>',
            f"      {lane_line_horizontal()}",
            f"      {lane_line_vertical()}",
        ])
        return "\n".join([base, clipped_tile_group(asset_id, body)])
    if asset_id == "road_dead_end":
        body = "\n".join([
            f'      <rect x="24" y="58" width="77" height="44" fill="{road}" stroke="{edge}" stroke-width="3"/>',
            '<path d="M35 80 H86" stroke="#f4f4e9" stroke-width="4" stroke-linecap="round" stroke-dasharray="13 10"/>',
            '      <rect x="94" y="61" width="7" height="38" fill="#ffd95e"/>',
        ])
        return "\n".join([base, clipped_tile_group(asset_id, body)])
    if asset_id == "road_avenue":
        body = "\n".join([
            f'      <rect x="24" y="50" width="112" height="60" fill="{road}" stroke="{edge}" stroke-width="3"/>',
            '      <path d="M24 80 H136" stroke="#ffd95e" stroke-width="4"/><path d="M40 65 H120 M40 95 H120" stroke="#f4f4e9" stroke-width="3" stroke-dasharray="13 12"/>',
        ])
        return "\n".join([base, clipped_tile_group(asset_id, body)])
    if asset_id == "road_bridge":
        body = "\n".join(['      <rect x="24" y="56" width="112" height="48" fill="#4a5058" stroke="#d0c7b5" stroke-width="5"/>', f"      {lane_line_horizontal()}"])
        return "\n".join([terrain("water_tile"), clipped_tile_group(asset_id, body)])
    if asset_id == "road_roundabout":
        body = "\n".join([
            f'      <rect x="24" y="56" width="112" height="48" fill="{road}"/>',
            f'      <rect x="56" y="24" width="48" height="112" fill="{road}"/>',
            f'      <circle cx="80" cy="80" r="52" fill="{road}" stroke="{edge}" stroke-width="5"/>',
            '      <circle cx="80" cy="80" r="27" fill="#79b842" stroke="#b5df58" stroke-width="4"/>',
            '      <circle cx="80" cy="80" r="40" fill="none" stroke="#f4f4e9" stroke-width="4" stroke-dasharray="12 10"/>',
            '      <path d="M80 24 V34 M80 126 V136 M24 80 H34 M126 80 H136" stroke="#f4f4e9" stroke-width="4" stroke-linecap="round" stroke-dasharray="12 8"/>',
        ])
        return "\n".join([base, clipped_tile_group(asset_id, body)])
    if asset_id == "rail_crossing":
        body = "\n".join([
            f'      <rect x="24" y="58" width="112" height="44" fill="{road}" stroke="{edge}" stroke-width="3"/>',
            '      <path d="M37 123 L123 37" stroke="#5d4b3a" stroke-width="12"/><path d="M37 123 L123 37" stroke="#c7b89b" stroke-width="3"/><path d="M49 111 l11 11 M67 93 l11 11 M85 75 l11 11 M103 57 l11 11" stroke="#c7b89b" stroke-width="3"/>',
        ])
        return "\n".join([base, clipped_tile_group(asset_id, body)])
    return base


def building_body(asset_id: str) -> str:
    bodies: dict[str, str] = {
        "cottage_house": '<polygon points="45,57 80,40 115,57 115,104 80,121 45,104" fill="#d84d31" stroke="#793222" stroke-width="3"/><path d="M80 40 V121 M45 57 L80 73 L115 57 M45 104 L80 88 L115 104" stroke="#f1c095" stroke-width="3" fill="none" opacity=".8"/><rect x="70" y="74" width="20" height="14" rx="3" fill="#f1dfbd" opacity=".85"/><circle cx="41" cy="113" r="7" fill="#60ad55"/><circle cx="120" cy="111" r="7" fill="#60ad55"/>',
        "suburban_house": '<path d="M40 53 H94 V68 H120 V111 H40 Z" fill="#d84b2f" stroke="#763321" stroke-width="3"/><path d="M48 62 H88 M54 104 H110 M94 68 V111" stroke="#f3c19a" stroke-width="3" opacity=".78"/><rect x="53" y="72" width="26" height="19" rx="3" fill="#ece0ca" opacity=".82"/><rect x="97" y="79" width="14" height="17" rx="2" fill="#6db7d9" opacity=".8"/><circle cx="36" cy="101" r="7" fill="#60ad55"/>',
        "townhouse": '<rect x="30" y="53" width="100" height="58" rx="5" fill="#c74d33" stroke="#793222" stroke-width="3"/><path d="M30 72 H130 M63 53 V111 M96 53 V111 M46 56 V108 M80 56 V108 M114 56 V108" stroke="#f0b38c" stroke-width="3" opacity=".78"/><rect x="40" y="78" width="14" height="19" rx="2" fill="#e9d2ad" opacity=".86"/><rect x="73" y="78" width="14" height="19" rx="2" fill="#e9d2ad" opacity=".86"/><rect x="106" y="78" width="14" height="19" rx="2" fill="#e9d2ad" opacity=".86"/>',
        "apartment_block": '<rect x="44" y="32" width="72" height="96" rx="6" fill="#bfc8ca" stroke="#626870" stroke-width="3"/><rect x="58" y="48" width="18" height="18" rx="3" fill="#8abacb"/><rect x="84" y="48" width="18" height="18" rx="3" fill="#8abacb"/><rect x="58" y="78" width="18" height="18" rx="3" fill="#d7dcdd"/><rect x="84" y="78" width="18" height="18" rx="3" fill="#d7dcdd"/><rect x="68" y="107" width="24" height="12" rx="2" fill="#555b60"/><path d="M50 39 H110 M50 121 H110" stroke="#e6eded" stroke-width="3" opacity=".7"/>',
        "corner_shop": '<path d="M38 54 H112 V79 H124 V111 H38 Z" fill="#3a4550" stroke="#1b222a" stroke-width="3"/><path d="M46 62 H104 M46 75 H112 M76 54 V111" stroke="#f7e8ad" stroke-width="3" opacity=".72"/><rect x="50" y="87" width="20" height="14" rx="2" fill="#e0b17c"/><rect x="92" y="88" width="20" height="13" rx="2" fill="#e0b17c"/><circle cx="120" cy="102" r="4" fill="#ffd460"/>',
        "grocery_store": '<rect x="36" y="54" width="88" height="58" rx="6" fill="#4d6b56" stroke="#294131" stroke-width="3"/><path d="M48 65 H112 M48 78 H112 M48 91 H112" stroke="#f4e1a8" stroke-width="3" opacity=".72"/><rect x="55" y="98" width="50" height="9" rx="2" fill="#e2c199"/><circle cx="119" cy="50" r="5" fill="#ff7040"/><circle cx="108" cy="46" r="5" fill="#78c64c"/>',
        "cafe": '<rect x="43" y="60" width="74" height="46" rx="9" fill="#f1cfa5" stroke="#8c4c35" stroke-width="3"/><path d="M47 68 H113 M47 78 H113" stroke="#e45454" stroke-width="4" stroke-dasharray="10 7"/><circle cx="48" cy="116" r="9" fill="#f4d872" stroke="#8c4c35" stroke-width="2"/><circle cx="70" cy="119" r="8" fill="#e45454" stroke="#8c4c35" stroke-width="2"/><circle cx="96" cy="119" r="8" fill="#f4d872" stroke="#8c4c35" stroke-width="2"/>',
        "office_building": '<rect x="48" y="32" width="64" height="96" rx="5" fill="#9ab1bd" stroke="#4f5e66" stroke-width="3"/><path d="M58 45 H102 M58 60 H102 M58 75 H102 M58 90 H102 M58 105 H102" stroke="#d2f7ff" stroke-width="4" opacity=".75"/><rect x="68" y="113" width="24" height="10" rx="2" fill="#4f5e66"/><rect x="59" y="38" width="14" height="14" rx="2" fill="#d7e5e9"/><rect x="87" y="38" width="14" height="14" rx="2" fill="#d7e5e9"/>',
        "small_market": '<rect x="38" y="58" width="84" height="50" rx="7" fill="#d0bc8e" stroke="#7f4b2a" stroke-width="3"/><path d="M38 70 q21 -14 42 0 q21 -14 42 0" fill="none" stroke="#f2d56c" stroke-width="7" stroke-linecap="round"/><rect x="52" y="88" width="56" height="11" rx="2" fill="#463b32"/><circle cx="113" cy="108" r="5" fill="#e84b3c"/><circle cx="101" cy="112" r="5" fill="#69b64a"/>',
        "clinic": '<rect x="42" y="47" width="76" height="68" rx="6" fill="#f8fbfb" stroke="#8c9a9f" stroke-width="3"/><rect x="64" y="63" width="32" height="32" rx="4" fill="#ffffff" stroke="#cdd7da" stroke-width="2"/><path d="M80 69 v20 M70 79 h20" stroke="#e43d3d" stroke-width="7" stroke-linecap="round"/><rect x="98" y="89" width="13" height="14" rx="2" fill="#8bd5ed"/>',
        "school": '<rect x="38" y="53" width="84" height="58" rx="6" fill="#e6c18a" stroke="#bd7848" stroke-width="3"/><path d="M46 63 H114 M46 77 H114 M46 91 H114 M65 53 V111 M95 53 V111" stroke="#6f3f25" stroke-width="3" opacity=".58"/><polygon points="97,36 109,55 86,55" fill="#ffd85d" stroke="#bd7848" stroke-width="3"/><rect x="67" y="97" width="18" height="10" rx="2" fill="#65412b"/><circle cx="38" cy="101" r="7" fill="#60ad55"/>',
        "police_station": '<rect x="42" y="54" width="76" height="58" rx="6" fill="#e5e9ee" stroke="#667383" stroke-width="3"/><rect x="53" y="65" width="54" height="26" rx="3" fill="#2d4f9a"/><path d="M80 65 V91 M60 102 H100" stroke="#ffffff" stroke-width="4" opacity=".78"/><circle cx="108" cy="64" r="7" fill="#ffcf4e"/><rect x="67" y="96" width="26" height="11" rx="2" fill="#667383"/>',
        "factory": '<rect x="35" y="55" width="90" height="58" rx="5" fill="#b6bec1" stroke="#596268" stroke-width="3"/><path d="M39 62 H65 L74 54 H96 L105 62 H121 V79 H39 Z" fill="#6d8796" stroke="#283037" stroke-width="3"/><circle cx="113" cy="42" r="10" fill="#676e73" stroke="#283037" stroke-width="3"/><circle cx="130" cy="34" r="12" fill="#d6d6d6" opacity=".62"/><rect x="55" y="87" width="34" height="15" fill="#31576b"/><rect x="94" y="87" width="22" height="10" fill="#cad3d6"/>',
        "warehouse": '<rect x="34" y="52" width="92" height="62" rx="5" fill="#caa46e" stroke="#6f7983" stroke-width="3"/><path d="M42 64 H118 M42 78 H118 M42 92 H118" stroke="#6f7983" stroke-width="4" opacity=".68"/><rect x="59" y="98" width="34" height="11" fill="#51585f"/><path d="M59 102 H93" stroke="#d5dde0" stroke-width="3"/><rect x="100" y="66" width="17" height="16" fill="#6fb5d4"/>',
        "power_plant": '<rect x="35" y="62" width="89" height="48" rx="5" fill="#cdd2d2" stroke="#596268" stroke-width="3"/><rect x="93" y="53" width="33" height="45" rx="5" fill="#9fa7a8" stroke="#596268" stroke-width="3"/><circle cx="57" cy="62" r="19" fill="#cbbf9e" stroke="#5d5750" stroke-width="3"/><circle cx="88" cy="62" r="19" fill="#cbbf9e" stroke="#5d5750" stroke-width="3"/><circle cx="57" cy="62" r="9" fill="#8b8170"/><circle cx="88" cy="62" r="9" fill="#8b8170"/><path d="M73 77 l-10 18 h12 l-7 17 l21 -26 h-12 l8 -9z" fill="#ffe24c" stroke="#715f18" stroke-width="2"/><path d="M46,113 H119" stroke="#f4c84a" stroke-width="5"/><path d="M52,113 l10,-7 M71,113 l10,-7 M90,113 l10,-7 M109,113 l10,-7" stroke="#2f363d" stroke-width="2"/>',
        "water_plant": '<rect x="38" y="58" width="84" height="54" rx="6" fill="#c1d5db" stroke="#5d747c" stroke-width="3"/><circle cx="65" cy="84" r="19" fill="#1f93c2" stroke="#d8ffff" stroke-width="4"/><circle cx="96" cy="84" r="19" fill="#1f93c2" stroke="#d8ffff" stroke-width="4"/><path d="M51 84 H79 M82 84 H110" stroke="#a9f0ff" stroke-width="4" opacity=".72"/><path d="M50 114 C72 121 92 121 114 114" stroke="#a9f0ff" stroke-width="5" fill="none"/>',
        "farm_barn": '<rect x="42" y="55" width="76" height="58" rx="5" fill="#b54833" stroke="#6b2c24" stroke-width="3"/><path d="M42 72 H118 M80 55 V113 M53 84 H107" stroke="#e7c48d" stroke-width="4" opacity=".75"/><rect x="66" y="91" width="28" height="15" fill="#6b2c24"/><path d="M66,91 l28,15 M94,91 l-28,15" stroke="#e7c48d" stroke-width="3"/><path d="M36,72 C51,65 64,65 78,72 M94,116 C106,108 121,107 134,112" stroke="#d7bd57" stroke-width="4" fill="none"/>',
        "greenhouse": '<rect x="37" y="56" width="86" height="56" rx="10" fill="#a5e8f2" opacity=".68" stroke="#d9ffff" stroke-width="4"/><path d="M39,84 H121 M59,58 V110 M80,57 V112 M101,58 V110 M44 68 C58 62 69 62 80 68 M80 68 C92 62 105 62 117 68" stroke="#ffffff" stroke-width="3" opacity=".8"/><path d="M48 98 q10 -14 22 0 M78 98 q10 -14 22 0 M100,113 C112,106 125,105 136,110" stroke="#4cae3a" stroke-width="4" fill="none"/>',
    }
    return bodies[asset_id]


def buildings(asset_id: str) -> str:
    return f"    {building_body(asset_id)}"


def farms(asset_id: str) -> str:
    if asset_id == "wheat_farm":
        return "\n".join([
            tile("#d8b557", "#f0d77a"),
            '    <path d="M41 43 H119 M41 57 H119 M41 71 H119 M41 85 H119 M41 99 H119 M41 113 H119" stroke="#8f7a2a" stroke-width="4"/>',
            '    <path d="M48 43 v70 M64 43 v70 M80 43 v70 M96 43 v70 M112 43 v70" stroke="#efd96b" stroke-width="3"/>',
            '    <path d="M43 119 C61 105 82 105 101 119" stroke="#c38c2f" stroke-width="5" fill="none"/>',
        ])
    if asset_id == "vegetable_farm":
        return "\n".join([
            tile("#5f9d3f", "#a8d36a"),
            '    <path d="M42 46 H118 M42 64 H118 M42 82 H118 M42 100 H118" stroke="#2f7c32" stroke-width="8" stroke-linecap="round"/>',
            '    <circle cx="55" cy="46" r="4" fill="#ff7040"/><circle cx="86" cy="64" r="4" fill="#ffd95e"/><circle cx="111" cy="82" r="4" fill="#d84b6a"/><circle cx="67" cy="100" r="4" fill="#ff7040"/>',
            '    <path d="M39 120 H122" stroke="#8c5e2d" stroke-width="5" stroke-linecap="round"/>',
        ])
    if asset_id == "orchard_farm":
        return "\n".join([
            tile("#79b842", "#b5df58"),
            '    <circle cx="51" cy="52" r="13" fill="#4fa83d"/><circle cx="80" cy="52" r="13" fill="#4fa83d"/><circle cx="109" cy="52" r="13" fill="#4fa83d"/>',
            '    <circle cx="51" cy="84" r="13" fill="#4fa83d"/><circle cx="80" cy="84" r="13" fill="#4fa83d"/><circle cx="109" cy="84" r="13" fill="#4fa83d"/>',
            '    <circle cx="51" cy="116" r="13" fill="#4fa83d"/><circle cx="80" cy="116" r="13" fill="#4fa83d"/><circle cx="109" cy="116" r="13" fill="#4fa83d"/>',
            '    <circle cx="83" cy="49" r="3" fill="#e34e3b"/><circle cx="108" cy="84" r="3" fill="#e34e3b"/><circle cx="54" cy="116" r="3" fill="#e34e3b"/>',
        ])
    if asset_id == "livestock_ranch":
        return "\n".join([
            tile("#b99559", "#e2ca8b"),
            '    <path d="M39 42 H121 V118 H39 Z" fill="none" stroke="#7f5b34" stroke-width="5" stroke-dasharray="13 9"/>',
            '    <ellipse cx="63" cy="77" rx="15" ry="10" fill="#f3eee2" stroke="#7a756a" stroke-width="3"/><circle cx="75" cy="73" r="3" fill="#7a756a"/>',
            '    <ellipse cx="101" cy="95" rx="16" ry="10" fill="#d8c7aa" stroke="#7a5b3d" stroke-width="3"/><circle cx="93" cy="91" r="3" fill="#7a5b3d"/>',
            '    <path d="M50 119 C70 105 94 105 116 119" stroke="#8c5e2d" stroke-width="5" fill="none"/>',
        ])
    if asset_id in {"farm_barn", "greenhouse"}:
        return buildings(asset_id)
    raise ValueError(f"Unknown farm asset: {asset_id}")


def civic(asset_id: str) -> str:
    if asset_id == "sidewalk_plaza":
        return "\n".join([
            tile("#a79f91", "#d6ccba"),
            '    <path d="M40 40 H120 M40 64 H120 M40 88 H120 M40 112 H120 M40 40 V120 M64 40 V120 M88 40 V120 M112 40 V120" stroke="#d6ccba" stroke-width="2" opacity=".85"/>',
            '    <circle cx="80" cy="80" r="18" fill="#cfd7cf" stroke="#8f9a96" stroke-width="3"/><circle cx="80" cy="80" r="11" fill="#1f93c2" stroke="#d8ffff" stroke-width="3"/>',
            '    <rect x="45" y="56" width="28" height="7" rx="3" fill="#7f5b34"/><rect x="88" y="105" width="28" height="7" rx="3" fill="#7f5b34"/>',
            '    <circle cx="46" cy="106" r="8" fill="#65a542"/><circle cx="118" cy="50" r="8" fill="#65a542"/>',
        ])
    raise ValueError(f"Unknown civic asset: {asset_id}")


def props(asset_id: str) -> str:
    if asset_id == "tree":
        return '<circle cx="80" cy="80" r="34" fill="#63bf42"/><circle cx="61" cy="87" r="24" fill="#4b9f34"/><circle cx="98" cy="91" r="25" fill="#559f37"/><circle cx="80" cy="88" r="7" fill="#795530" opacity=".82"/>'
    if asset_id == "bush_cluster":
        return '<circle cx="60" cy="85" r="18" fill="#68b84d"/><circle cx="82" cy="74" r="22" fill="#77c957"/><circle cx="104" cy="89" r="17" fill="#5fae43"/>'
    if asset_id == "fountain":
        return '<circle cx="80" cy="80" r="38" fill="#cfd7cf" stroke="#8f9a96" stroke-width="4"/><circle cx="80" cy="80" r="25" fill="#1f93c2" stroke="#d8ffff" stroke-width="4"/><path d="M80 55 V78 M68 71 q12 -15 24 0" stroke="#d8ffff" stroke-width="4" fill="none" stroke-linecap="round"/>'
    if asset_id == "streetlight":
        return '<circle cx="80" cy="80" r="44" fill="#f4e77b" opacity=".16"/><circle cx="80" cy="80" r="10" fill="#f4e77b" stroke="#f8ffc6" stroke-width="4"/><circle cx="80" cy="80" r="4" fill="#5c4731"/><path d="M80 80 L116 66" stroke="#5c4731" stroke-width="5" stroke-linecap="round"/><circle cx="116" cy="66" r="7" fill="#f4e77b" opacity=".85"/>'
    if asset_id == "rock_cluster":
        return '<ellipse cx="80" cy="111" rx="48" ry="12" fill="#000000" opacity=".18"/><ellipse cx="58" cy="85" rx="25" ry="17" fill="#777466" stroke="#5b5a52" stroke-width="3"/><ellipse cx="88" cy="78" rx="31" ry="20" fill="#8c887b" stroke="#67655c" stroke-width="3"/><ellipse cx="108" cy="101" rx="23" ry="15" fill="#6e6a5a" stroke="#55534c" stroke-width="3"/><ellipse cx="76" cy="104" rx="18" ry="12" fill="#9b978a" stroke="#6b685f" stroke-width="3"/>'
    if asset_id == "car":
        return '<rect x="48" y="61" width="64" height="38" rx="10" fill="#2e80c9" stroke="#d8f5ff" stroke-width="3"/><rect x="64" y="56" width="32" height="23" rx="7" fill="#9edff0"/><circle cx="60" cy="101" r="6" fill="#1f2a31"/><circle cx="100" cy="101" r="6" fill="#1f2a31"/>'
    return ""


def overlays(asset_id: str) -> str:
    if asset_id == "road_preview_overlay":
        return '<path d="M32 80 H128" stroke="#4bb7ff" stroke-width="10" stroke-linecap="round" stroke-dasharray="12 9" fill="none"/><circle cx="34" cy="80" r="8" fill="#4bb7ff"/><circle cx="126" cy="80" r="8" fill="#4bb7ff"/>'
    if asset_id == "selection_overlay":
        return '<rect x="24" y="24" width="112" height="112" rx="10" fill="#0e2b23" opacity=".28" stroke="#61ff80" stroke-width="5"/><circle cx="24" cy="24" r="6" fill="#61ff80"/><circle cx="136" cy="24" r="6" fill="#61ff80"/><circle cx="136" cy="136" r="6" fill="#61ff80"/><circle cx="24" cy="136" r="6" fill="#61ff80"/>'
    if asset_id == "invalid_overlay":
        return '<rect x="24" y="24" width="112" height="112" rx="10" fill="#3a1116" opacity=".32" stroke="#ff5e66" stroke-width="5"/><path d="M52 52 L108 108 M108 52 L52 108" stroke="#ff5e66" stroke-width="7" stroke-linecap="round"/>'
    if asset_id == "zone_residential":
        return '<rect x="24" y="24" width="112" height="112" rx="10" fill="#4f9a5b" opacity=".42" stroke="#77d685" stroke-width="3"/>'
    if asset_id == "zone_commercial":
        return '<rect x="24" y="24" width="112" height="112" rx="10" fill="#2f7ab4" opacity=".44" stroke="#66b9f0" stroke-width="3"/>'
    if asset_id == "zone_industrial":
        return '<rect x="24" y="24" width="112" height="112" rx="10" fill="#7950a8" opacity=".44" stroke="#b084e0" stroke-width="3"/>'
    if asset_id == "grid_overlay":
        return '<rect x="24" y="24" width="112" height="112" rx="10" fill="none" stroke="#9cc1df" stroke-width="2" opacity=".8"/><path d="M52 24 V136 M80 24 V136 M108 24 V136 M24 52 H136 M24 80 H136 M24 108 H136" stroke="#9cc1df" stroke-width="2" opacity=".55"/>'
    if asset_id == "build_preview_overlay":
        return '<rect x="24" y="24" width="112" height="112" rx="10" fill="#54ff8f" opacity=".16" stroke="#54ff8f" stroke-width="4" stroke-dasharray="10 7"/><path d="M80 51 V109 M51 80 H109" stroke="#54ff8f" stroke-width="8" stroke-linecap="round"/>'
    return ""


def body_for(asset: dict[str, object]) -> tuple[str, bool]:
    asset_id = str(asset["id"])
    category = str(asset["category"])
    if category == "terrain":
        return terrain(asset_id), True
    if category == "road":
        return roads(asset_id), asset_id != "road_preview_overlay"
    if category == "building":
        return buildings(asset_id), True
    if category == "farm":
        return farms(asset_id), True
    if category == "civic":
        return civic(asset_id), True
    if category == "prop":
        return props(asset_id), True
    if category == "overlay":
        return overlays(asset_id), False
    raise ValueError(f"Unknown category: {category}")


def preview_css() -> str:
    return """  :root {
    color-scheme: dark;
    --bg:#07111b; --panel:#0d1d2b; --text:#f5f7fb;
    --muted:#9cc1df; --line:#1e3d54; --accent:#54ff8f;
  }
  * { box-sizing: border-box; }
  body {
    margin:0; background: radial-gradient(circle at 20% 0%, #102f44 0%, var(--bg) 42%, #04080d 100%);
    font-family: Inter, Segoe UI, Arial, sans-serif; color:var(--text);
  }
  header {
    position: sticky; top:0; z-index:10; padding:18px 22px; border-bottom:1px solid var(--line);
    background: rgba(5,13,20,.92); backdrop-filter: blur(8px);
  }
  h1 { margin:0 0 4px; font-size:24px; letter-spacing:0; }
  .subtitle { margin:0; color:var(--muted); font-size:14px; }
  .toolbar { display:flex; flex-wrap:wrap; gap:10px; margin-top:14px; }
  button {
    border:1px solid #1c405b; background:#0a1b2a; color:var(--text); border-radius:8px;
    padding:10px 16px; font-size:15px; cursor:pointer;
  }
  button.active { border-color:var(--accent); color:var(--accent); background:#0c2b22; }
  main { padding:26px; max-width:1380px; margin:auto; }
  .notice {
    border:1px solid #205c3c; background:rgba(21,97,58,.16); border-radius:8px; padding:14px 16px;
    color:#c7ffd9; margin-bottom:22px; line-height:1.45;
  }
  .grid { display:grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap:20px; }
  .card {
    min-height:250px; border:1px solid var(--line); background:linear-gradient(180deg, rgba(17,40,58,.82), rgba(8,20,31,.9));
    border-radius:8px; display:flex; flex-direction:column; align-items:center; justify-content:center;
    padding:18px; box-shadow:0 12px 28px rgba(0,0,0,.22);
  }
  .art, .art img, .art svg { width:160px; height:160px; display:block; }
  h3 { margin:12px 0 6px; font-size:16px; text-align:center; }
  p { margin:0; color:var(--muted); font-size:13px; text-align:center; }
  footer { padding:22px 26px; color:var(--muted); border-top:1px solid var(--line); }"""


def preview_script() -> str:
    return """const buttons = [...document.querySelectorAll('button[data-filter]')];
const cards = [...document.querySelectorAll('.card')];
buttons.forEach(button => {
  button.addEventListener('click', () => {
    buttons.forEach(item => item.classList.toggle('active', item === button));
    const filter = button.dataset.filter;
    cards.forEach(card => {
      card.hidden = filter !== 'all' && card.dataset.category !== filter;
    });
  });
});"""


def render_preview(relative: bool, assets: list[dict[str, object]]) -> str:
    subtitle = "Top-down preview: colored terrain tiles, clipped road tiles, transparent building sprites, and prop overlays."
    notice = (
        "Relative preview uses the SVG files from the assets folder."
        if relative
        else "Standalone preview embeds every top-down SVG inline with unique IDs."
    )
    category_order = ["terrain", "road", "farm", "building", "civic", "prop", "overlay"]
    categories = [category for category in category_order if any(str(asset["category"]) == category for asset in assets)]
    buttons = ['<button class="active" data-filter="all">All</button>']
    for cat in categories:
        buttons.append(f'<button data-filter="{cat}">{cat.title()}</button>')

    cards = []
    for asset in assets:
        title = str(asset["title"])
        asset_id = str(asset["id"])
        category = str(asset["category"])
        file_path = str(asset["file"])
        if relative:
            art = f'<div class="art"><img src="{html.escape(file_path)}" alt="{html.escape(title)}"></div>'
        else:
            art = f'<div class="art">{(PACK_ROOT / file_path).read_text(encoding="utf-8")}</div>'
        cards.append(
            f"""      <article class="card" data-category="{html.escape(category)}">
        {art}
        <h3>{html.escape(title)}</h3>
        <p>{html.escape(asset_id)} - {html.escape(category)}</p>
      </article>"""
        )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>CityBuilder SVG Top-Down Preview</title>
<style>
{preview_css()}
</style>
</head>
<body>
<header>
  <h1>CityBuilder SVG MVP Pack v2</h1>
  <p class="subtitle">{html.escape(subtitle)}</p>
  <div class="toolbar">{"".join(buttons)}</div>
</header>
<main>
  <div class="notice">{html.escape(notice)}</div>
  <section class="grid">
{chr(10).join(cards)}
  </section>
</main>
<footer>{len(assets)} SVG assets. Top-down view, gameplay categories, compact defs, unique inline IDs, consistent alignment.</footer>
<script>
{preview_script()}
</script>
</body>
</html>
"""


def update_previews(assets: list[dict[str, object]]) -> None:
    (PACK_ROOT / "preview_relative.html").write_text(render_preview(True, assets), encoding="utf-8", newline="\n")
    (PACK_ROOT / "preview_standalone.html").write_text(render_preview(False, assets), encoding="utf-8", newline="\n")


def update_alignment_check() -> None:
    html_text = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>CityBuilder SVG Top-Down Alignment Check</title>
<style>
  :root { color-scheme: dark; --bg:#07111b; --line:#1e3d54; --text:#f5f7fb; --muted:#9cc1df; --accent:#54ff8f; }
  * { box-sizing: border-box; }
  body { margin:0; min-height:100vh; background:radial-gradient(circle at 20% 0%, #102f44 0%, var(--bg) 42%, #04080d 100%); color:var(--text); font-family:Inter, Segoe UI, Arial, sans-serif; }
  header { padding:18px 22px; border-bottom:1px solid var(--line); background:rgba(5,13,20,.92); }
  h1 { margin:0 0 5px; font-size:24px; letter-spacing:0; }
  p { margin:0; color:var(--muted); font-size:14px; }
  main { width:min(1180px,100%); margin:0 auto; padding:26px; }
  .stage-shell { border:1px solid var(--line); border-radius:8px; background:linear-gradient(180deg, rgba(17,40,58,.82), rgba(8,20,31,.9)); overflow:hidden; }
  .stage-head { display:flex; justify-content:space-between; gap:16px; padding:14px 16px; border-bottom:1px solid var(--line); color:var(--muted); font-size:13px; }
  .stage-head strong { color:var(--accent); }
  .stage { display:grid; grid-template-columns:repeat(6,160px); grid-auto-rows:160px; justify-content:center; gap:0; padding:28px; background:linear-gradient(90deg, rgba(255,255,255,.04) 1px, transparent 1px),linear-gradient(0deg, rgba(255,255,255,.04) 1px, transparent 1px); background-size:160px 160px; }
  .asset { width:160px; height:160px; display:block; }
</style>
</head>
<body>
<header>
  <h1>CityBuilder SVG Top-Down Alignment Check</h1>
  <p>Mixed terrain, roads, farms, buildings, civic tiles, props, and overlays in a tile grid.</p>
</header>
<main>
  <section class="stage-shell">
    <div class="stage-head">
      <span><strong>Pass condition:</strong> every asset has the right map role, footprint, and readable shadow.</span>
      <span>160 x 160 SVG assets</span>
    </div>
    <div class="stage">
      <img class="asset" src="assets/terrain/grass_tile_a.svg" alt="">
      <img class="asset" src="assets/roads/road_straight.svg" alt="">
      <img class="asset" src="assets/roads/road_vertical.svg" alt="">
      <img class="asset" src="assets/roads/road_cross.svg" alt="">
      <img class="asset" src="assets/terrain/empty_lot_tile.svg" alt="">
      <img class="asset" src="assets/civic/sidewalk_plaza.svg" alt="">
      <img class="asset" src="assets/terrain/water_tile.svg" alt="">
      <img class="asset" src="assets/farms/wheat_farm.svg" alt="">
      <img class="asset" src="assets/farms/vegetable_farm.svg" alt="">
      <img class="asset" src="assets/farms/orchard_farm.svg" alt="">
      <img class="asset" src="assets/farms/livestock_ranch.svg" alt="">
      <img class="asset" src="assets/props/tree.svg" alt="">
      <img class="asset" src="assets/overlays/selection_overlay.svg" alt="">
      <img class="asset" src="assets/terrain/coast_edge_north.svg" alt="">
      <img class="asset" src="assets/buildings/cottage_house.svg" alt="">
      <img class="asset" src="assets/buildings/corner_shop.svg" alt="">
      <img class="asset" src="assets/buildings/factory.svg" alt="">
      <img class="asset" src="assets/buildings/apartment_block.svg" alt="">
      <img class="asset" src="assets/buildings/school.svg" alt="">
      <img class="asset" src="assets/buildings/power_plant.svg" alt="">
      <img class="asset" src="assets/buildings/water_plant.svg" alt="">
      <img class="asset" src="assets/overlays/road_preview_overlay.svg" alt="">
      <img class="asset" src="assets/roads/road_bridge.svg" alt="">
      <img class="asset" src="assets/farms/farm_barn.svg" alt="">
      <img class="asset" src="assets/farms/greenhouse.svg" alt="">
      <img class="asset" src="assets/roads/road_t_junction.svg" alt="">
      <img class="asset" src="assets/roads/road_roundabout.svg" alt="">
      <img class="asset" src="assets/buildings/office_building.svg" alt="">
    </div>
  </section>
</main>
</body>
</html>
"""
    (PACK_ROOT / "alignment_check.html").write_text(html_text, encoding="utf-8", newline="\n")


def update_report() -> None:
    report = """# CityBuilder SVG MVP Pack v2 - Review Report

## Fix Summary

**Status: converted to a top-down simulation asset vocabulary.**

The asset pack now uses a flat map perspective instead of the earlier isometric/2.5D look. It is organized around gameplay roles instead of decorative icons, so the dummy map/model flow can reason about what each tile does.

Changes made:

- Rebuilt all SVGs as top-down assets.
- Removed 2.5D side faces and isometric diamond bases.
- Removed terrain/foundation backgrounds from standalone building sprites.
- Kept shadows using per-asset filter IDs, so inline SVGs do not collide.
- Clipped road geometry to the visible tile footprint, so roads cannot spill outside the tile.
- Converted buildings into top-down roof/footprint sprites instead of front-facing facades.
- Fixed `coast_inlet_tile.svg` so it reads as a coast inlet instead of a pond icon.
- Converted `sidewalk_plaza` from a road into a civic/amenity tile.
- Converted `road_preview_overlay.svg` into a real transparent overlay, not a full road tile.
- Added farm variants with economy metadata for price/supply effects: wheat, vegetable, orchard, and livestock.
- Reclassified `farm_barn` and `greenhouse` as farm assets.
- Added placement/economy metadata for props such as streetlights and decorative rock clusters.
- Regenerated preview and alignment HTML files from the fixed SVG sources.

## Alignment Rules

Every asset still uses `viewBox=\"0 0 160 160\"`.

Terrain, farm, civic, and road assets use the same top-down tile footprint:

- Main footprint: `x=24 y=24 width=112 height=112 rx=10`
- Roads are clipped to the footprint, including connectors, roundabouts, bridges, and rail crossings.
- Buildings are transparent sprites intended to sit on top of terrain/zone tiles.
- Overlays are transparent and do not contain terrain or road bases.
- Props live on the prop layer and should not block building placement unless metadata explicitly says so.

## Asset Count

| Category | Count |
|---|---:|
| building | 16 |
| civic | 1 |
| farm | 6 |
| overlay | 8 |
| prop | 6 |
| road | 10 |
| terrain | 12 |

Total: **59 SVG assets**

## Preview

Use `preview_relative.html` inside the pack folder to check the real SVG files.

Use `preview_standalone.html` for a single self-contained inline preview.

Use `alignment_check.html` to verify mixed tile alignment in a top-down grid.
"""
    (PACK_ROOT / "REVIEW_REPORT.md").write_text(report, encoding="utf-8", newline="\n")


def asset_ids(assets: list[dict[str, object]], category: str) -> list[str]:
    return [str(asset["id"]) for asset in assets if str(asset["category"]) == category]


def update_action_schema(assets: list[dict[str, object]]) -> None:
    building_ids = asset_ids(assets, "building")
    farm_ids = asset_ids(assets, "farm")
    civic_ids = asset_ids(assets, "civic")
    prop_ids = asset_ids(assets, "prop")
    road_ids = asset_ids(assets, "road")
    terrain_ids = asset_ids(assets, "terrain")

    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "CityBuilder AI Map Action",
        "description": (
            "Actions the model can take in the isolated map preview. Asset ids come from "
            "asset_catalog.json; farm assets include economy.priceEffects so placement can "
            "affect prices and supply."
        ),
        "type": "object",
        "oneOf": [
            {
                "title": "Add building",
                "description": "Place a residential, commercial, industrial, or utility building.",
                "required": ["action", "kind"],
                "additionalProperties": False,
                "properties": {
                    "action": {"const": "add_building"},
                    "kind": {"type": "string", "enum": building_ids},
                    "x": {"type": "integer", "minimum": 0},
                    "y": {"type": "integer", "minimum": 0},
                    "placement": {"enum": ["auto", "manual"], "default": "auto"},
                    "count": {"type": "integer", "minimum": 1, "default": 1},
                },
            },
            {
                "title": "Add farm",
                "description": "Place a farm variant. Each variant changes different market prices.",
                "required": ["action", "kind"],
                "additionalProperties": False,
                "properties": {
                    "action": {"const": "add_farm"},
                    "kind": {"type": "string", "enum": farm_ids},
                    "x": {"type": "integer", "minimum": 0},
                    "y": {"type": "integer", "minimum": 0},
                    "placement": {"enum": ["auto", "manual"], "default": "auto"},
                    "count": {"type": "integer", "minimum": 1, "default": 1},
                },
            },
            {
                "title": "Add civic tile",
                "description": "Place civic/amenity map tiles such as plazas.",
                "required": ["action", "kind"],
                "additionalProperties": False,
                "properties": {
                    "action": {"const": "add_civic"},
                    "kind": {"type": "string", "enum": civic_ids},
                    "x": {"type": "integer", "minimum": 0},
                    "y": {"type": "integer", "minimum": 0},
                    "placement": {"enum": ["auto", "manual"], "default": "auto"},
                },
            },
            {
                "title": "Add road",
                "description": "Draw or place road connector tiles, including roundabouts and rail crossings.",
                "required": ["action", "from", "to"],
                "additionalProperties": False,
                "properties": {
                    "action": {"const": "add_road"},
                    "from": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 2,
                        "maxItems": 2,
                    },
                    "to": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 2,
                        "maxItems": 2,
                    },
                    "kind": {"type": "string", "enum": road_ids, "default": "road_straight"},
                },
            },
            {
                "title": "Set terrain",
                "description": "Replace the base terrain tile before adding roads, buildings, farms, or props.",
                "required": ["action", "kind", "x", "y"],
                "additionalProperties": False,
                "properties": {
                    "action": {"const": "set_terrain"},
                    "kind": {"type": "string", "enum": terrain_ids},
                    "x": {"type": "integer", "minimum": 0},
                    "y": {"type": "integer", "minimum": 0},
                },
            },
            {
                "title": "Place prop",
                "description": "Place non-blocking props such as streetlights, trees, fountains, cars, or rocks.",
                "required": ["action", "kind"],
                "additionalProperties": False,
                "properties": {
                    "action": {"const": "place_prop"},
                    "kind": {"type": "string", "enum": prop_ids},
                    "x": {"type": "integer", "minimum": 0},
                    "y": {"type": "integer", "minimum": 0},
                    "placement": {
                        "enum": ["auto", "tile_center", "road_edge", "park_edge"],
                        "default": "auto",
                    },
                },
            },
            {
                "title": "Remove map item",
                "description": "Remove an existing asset instance by id or by layer coordinate.",
                "required": ["action", "layer"],
                "additionalProperties": False,
                "properties": {
                    "action": {"const": "remove_asset"},
                    "layer": {"enum": ["building", "farm", "civic", "prop", "road", "terrain"]},
                    "targetId": {"type": "string"},
                    "x": {"type": "integer", "minimum": 0},
                    "y": {"type": "integer", "minimum": 0},
                },
            },
        ],
    }
    ACTION_SCHEMA_PATH.write_text(json.dumps(schema, indent=2), encoding="utf-8", newline="\n")


def economy_for(assets: list[dict[str, object]], asset_id: str) -> dict[str, object]:
    for asset in assets:
        if asset["id"] == asset_id:
            return dict(asset.get("economy", {}))
    return {}


def update_sample_map_state(assets: list[dict[str, object]]) -> None:
    width = 12
    height = 8
    terrain_layer = []
    for y in range(height):
        for x in range(width):
            asset_id = "grass_tile_b" if (x + y) % 5 == 0 else "grass_tile_a"
            if x == 0:
                asset_id = "water_tile"
            elif x == 1:
                asset_id = "sand_tile"
            elif (x, y) in {(2, 5), (3, 5), (4, 5), (5, 5), (2, 6), (3, 6)}:
                asset_id = "farm_ground_tile"
            elif (x, y) in {(8, 1), (8, 2), (9, 1), (9, 2)}:
                asset_id = "park_ground_tile"
            terrain_layer.append({"assetId": asset_id, "x": x, "y": y})

    farm_instances = [
        ("f_001", "wheat_farm", 2, 5),
        ("f_002", "vegetable_farm", 3, 5),
        ("f_003", "orchard_farm", 4, 5),
        ("f_004", "livestock_ranch", 5, 5),
        ("f_005", "farm_barn", 2, 6),
        ("f_006", "greenhouse", 3, 6),
    ]
    farms = [
        {
            "instanceId": instance_id,
            "assetId": asset_id,
            "x": x,
            "y": y,
            "economyPreview": economy_for(assets, asset_id),
        }
        for instance_id, asset_id, x, y in farm_instances
    ]

    state = {
        "mapId": "demo_map_01",
        "width": width,
        "height": height,
        "tileSize": [160, 160],
        "purpose": "Dummy state for the isolated map preview endpoint.",
        "economy": {
            "basePrices": {"food": 1.0, "grain": 1.0, "produce": 1.0, "fruit": 1.0, "protein": 1.0},
            "note": "Farm economyPreview.priceEffects tells the preview/model how farm variants affect prices.",
        },
        "layers": {
            "terrain": terrain_layer,
            "roads": [
                {"assetId": "road_straight", "x": 2, "y": 3},
                {"assetId": "road_straight", "x": 3, "y": 3},
                {"assetId": "road_straight", "x": 4, "y": 3},
                {"assetId": "road_straight", "x": 5, "y": 3},
                {"assetId": "road_roundabout", "x": 6, "y": 3},
                {"assetId": "road_straight", "x": 7, "y": 3},
                {"assetId": "road_straight", "x": 8, "y": 3},
                {"assetId": "road_straight", "x": 9, "y": 3},
                {"assetId": "road_straight", "x": 10, "y": 3},
                {"assetId": "road_vertical", "x": 6, "y": 1},
                {"assetId": "road_vertical", "x": 6, "y": 2},
                {"assetId": "road_vertical", "x": 6, "y": 4},
                {"assetId": "road_vertical", "x": 6, "y": 5},
                {"assetId": "road_vertical", "x": 6, "y": 6},
                {"assetId": "rail_crossing", "x": 10, "y": 4},
            ],
            "farms": farms,
            "civic": [
                {
                    "instanceId": "c_001",
                    "assetId": "sidewalk_plaza",
                    "x": 8,
                    "y": 2,
                    "effects": economy_for(assets, "sidewalk_plaza"),
                }
            ],
            "buildings": [
                {"instanceId": "b_001", "assetId": "cottage_house", "x": 3, "y": 2},
                {"instanceId": "b_002", "assetId": "corner_shop", "x": 5, "y": 2},
                {"instanceId": "b_003", "assetId": "factory", "x": 7, "y": 4},
                {"instanceId": "b_004", "assetId": "power_plant", "x": 9, "y": 5},
                {"instanceId": "b_005", "assetId": "water_plant", "x": 9, "y": 1},
            ],
            "props": [
                {"assetId": "tree", "x": 8, "y": 1, "placement": "park_edge"},
                {
                    "assetId": "streetlight",
                    "x": 6,
                    "y": 3,
                    "placement": "road_edge",
                    "effects": economy_for(assets, "streetlight"),
                },
                {"assetId": "rock_cluster", "x": 4, "y": 1, "placement": "tile_center"},
                {"assetId": "fountain", "x": 9, "y": 2, "placement": "tile_center"},
            ],
            "overlays": [
                {"assetId": "selection_overlay", "x": 7, "y": 4},
                {"assetId": "road_preview_overlay", "x": 7, "y": 3},
            ],
        },
        "sampleActions": [
            {"action": "add_farm", "kind": "orchard_farm", "placement": "auto", "count": 2},
            {"action": "add_civic", "kind": "sidewalk_plaza", "x": 8, "y": 2},
            {"action": "place_prop", "kind": "streetlight", "placement": "road_edge"},
            {"action": "add_road", "from": [5, 3], "to": [7, 3], "kind": "road_roundabout"},
        ],
    }
    SAMPLE_MAP_STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8", newline="\n")


def write_assets() -> list[dict[str, object]]:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    assets = normalize_assets(catalog["assets"])
    active_files = {str(asset["file"]) for asset in assets}
    for svg_path in ASSET_ROOT.rglob("*.svg"):
        relative = svg_path.relative_to(PACK_ROOT).as_posix()
        if relative not in active_files:
            svg_path.unlink()
    for asset in assets:
        body, use_shadow = body_for(asset)
        out = svg(str(asset["id"]), str(asset["title"]), body, use_shadow=use_shadow)
        path = PACK_ROOT / str(asset["file"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(out, encoding="utf-8", newline="\n")
    catalog.update(
        {
            "version": "2.2",
            "renderMode": "SVG top-down",
            "note": "Top-down simulation asset vocabulary with separate colored terrain tiles, transparent building sprites, clipped road tiles, farm economy metadata, civic tiles, props, and overlays.",
            "assets": assets,
        }
    )
    CATALOG_PATH.write_text(json.dumps(catalog, indent=2), encoding="utf-8", newline="\n")
    return assets


def main() -> None:
    if not PACK_ROOT.exists():
        raise SystemExit(f"Pack root does not exist: {PACK_ROOT}")
    assets = write_assets()
    update_previews(assets)
    update_alignment_check()
    update_action_schema(assets)
    update_sample_map_state(assets)
    update_report()


if __name__ == "__main__":
    main()
