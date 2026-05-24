from __future__ import annotations

import json
import shutil
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
PACK_ROOT = ROOT / "frontend" / "src" / "assets" / "citybuilder-svg-mvp-v2" / "citybuilder_svg_mvp_v2"
MANIFEST_PATH = PACK_ROOT / "metadata" / "asset_image_adjacency_128.json"
SOURCE_DIR = PACK_ROOT / "metadata" / "imagegen_sources"
TILE_SIZE = 128


@dataclass(frozen=True)
class SliceSpec:
    asset_id: str
    category_dir: str
    row: int
    col: int
    max_side: int = 118
    mode: str = "cutout"
    crop_inset: int = 0
    alpha_scale: float = 1.0


@dataclass(frozen=True)
class SheetSpec:
    source_name: str
    generated_file: str
    key_rgb: tuple[int, int, int]
    slices: list[SliceSpec]


SHEETS = [
    SheetSpec(
        "residential_buildings_2x2.png",
        "ig_0c6a6c423fdce68e016a10ba33cc5c8191aa689148a25c7f40.png",
        (0, 255, 0),
        [
            SliceSpec("cottage_house", "buildings", 0, 0, 112),
            SliceSpec("suburban_house", "buildings", 0, 1, 118),
            SliceSpec("townhouse", "buildings", 1, 0, 120),
            SliceSpec("apartment_block", "buildings", 1, 1, 120),
        ],
    ),
    SheetSpec(
        "commercial_buildings_2x2.png",
        "ig_0c6a6c423fdce68e016a113982bcac8191a5091dede76816e2.png",
        (0, 255, 0),
        [
            SliceSpec("corner_shop", "buildings", 0, 0, 120),
            SliceSpec("grocery_store", "buildings", 0, 1, 122),
            SliceSpec("cafe", "buildings", 1, 0, 120),
            SliceSpec("office_building", "buildings", 1, 1, 120),
        ],
    ),
    SheetSpec(
        "civic_buildings_2x2.png",
        "ig_0c6a6c423fdce68e016a1139f219708191ae4ab97880a0e6c6.png",
        (0, 255, 0),
        [
            SliceSpec("small_market", "buildings", 0, 0, 118),
            SliceSpec("clinic", "buildings", 0, 1, 118),
            SliceSpec("school", "buildings", 1, 0, 120),
            SliceSpec("police_station", "buildings", 1, 1, 118),
        ],
    ),
    SheetSpec(
        "industrial_utility_buildings_2x2.png",
        "ig_0c6a6c423fdce68e016a113a3ad04081918dff5e8de9f6cafb.png",
        (0, 255, 0),
        [
            SliceSpec("factory", "buildings", 0, 0, 118),
            SliceSpec("warehouse", "buildings", 0, 1, 118),
            SliceSpec("power_plant", "buildings", 1, 0, 118),
            SliceSpec("water_plant", "buildings", 1, 1, 118),
        ],
    ),
    SheetSpec(
        "farm_nature_2x2.png",
        "ig_0c6a6c423fdce68e016a113abc949c81918e8fed8d31d2d9ef.png",
        (255, 0, 255),
        [
            SliceSpec("farm_barn", "farms", 0, 0, 118),
            SliceSpec("greenhouse", "farms", 0, 1, 118),
            SliceSpec("tree", "props", 1, 0, 112),
            SliceSpec("bush_cluster", "props", 1, 1, 108),
        ],
    ),
    SheetSpec(
        "props_vehicle_2x2.png",
        "ig_0c6a6c423fdce68e016a113b7f5424819196eec7916ee42d6d.png",
        (255, 0, 255),
        [
            SliceSpec("fountain", "props", 0, 0, 110),
            SliceSpec("streetlight", "props", 0, 1, 112),
            SliceSpec("rock_cluster", "props", 1, 0, 108),
            SliceSpec("car", "props", 1, 1, 112),
        ],
    ),
    SheetSpec(
        "terrain_basic_2x2.png",
        "ig_0c6a6c423fdce68e016a11dc7d294c8191a2b6daf081a8e42c.png",
        (0, 0, 0),
        [
            SliceSpec("grass_tile_a", "terrain", 0, 0, mode="full", crop_inset=3),
            SliceSpec("grass_tile_b", "terrain", 0, 1, mode="full", crop_inset=3),
            SliceSpec("dirt_tile", "terrain", 1, 0, mode="full", crop_inset=3),
            SliceSpec("sand_tile", "terrain", 1, 1, mode="full", crop_inset=3),
        ],
    ),
    SheetSpec(
        "terrain_misc_2x2.png",
        "ig_0c6a6c423fdce68e016a11dccd8fbc8191be727082832bdf66.png",
        (0, 0, 0),
        [
            SliceSpec("empty_lot_tile", "terrain", 0, 0, mode="full", crop_inset=3),
            SliceSpec("farm_ground_tile", "terrain", 0, 1, mode="full", crop_inset=3),
            SliceSpec("park_ground_tile", "terrain", 1, 0, mode="full", crop_inset=3),
            SliceSpec("pond_tile", "terrain", 1, 1, mode="full", crop_inset=3),
        ],
    ),
    SheetSpec(
        "water_coast_2x2.png",
        "ig_0c6a6c423fdce68e016a11dd3ddd0c8191abb63bd29758d54a.png",
        (0, 0, 0),
        [
            SliceSpec("water_tile", "terrain", 0, 0, mode="full", crop_inset=3),
            SliceSpec("coast_edge_north", "terrain", 0, 1, mode="full", crop_inset=3),
            SliceSpec("coast_edge_corner", "terrain", 1, 0, mode="full", crop_inset=3),
            SliceSpec("coast_inlet_tile", "terrain", 1, 1, mode="full", crop_inset=3),
        ],
    ),
    SheetSpec(
        "roads_basic_2x2.png",
        "ig_0c6a6c423fdce68e016a11dd9382388191b96612af5b1627e8.png",
        (0, 0, 0),
        [
            SliceSpec("road_straight", "roads", 0, 0, mode="full", crop_inset=5),
            SliceSpec("road_vertical", "roads", 0, 1, mode="full", crop_inset=5),
            SliceSpec("road_corner", "roads", 1, 0, mode="full", crop_inset=5),
            SliceSpec("road_t_junction", "roads", 1, 1, mode="full", crop_inset=5),
        ],
    ),
    SheetSpec(
        "roads_more_2x2.png",
        "ig_0c6a6c423fdce68e016a11ddf57704819182bd88f28dd83301.png",
        (0, 0, 0),
        [
            SliceSpec("road_cross", "roads", 0, 0, mode="full", crop_inset=5),
            SliceSpec("road_dead_end", "roads", 0, 1, mode="full", crop_inset=5),
            SliceSpec("road_avenue", "roads", 1, 0, mode="full", crop_inset=5),
            SliceSpec("road_bridge", "roads", 1, 1, mode="full", crop_inset=5),
        ],
    ),
    SheetSpec(
        "civic_transport_2x2.png",
        "ig_0c6a6c423fdce68e016a11de57d7a88191a156acda5e426d54.png",
        (255, 0, 255),
        [
            SliceSpec("road_roundabout", "roads", 0, 0, mode="full", crop_inset=5),
            SliceSpec("sidewalk_plaza", "civic", 0, 1, mode="full", crop_inset=4),
            SliceSpec("rail_crossing", "roads", 1, 0, mode="full", crop_inset=5),
            SliceSpec("build_preview_overlay", "overlays", 1, 1, 118, mode="cutout_all", alpha_scale=0.78),
        ],
    ),
    SheetSpec(
        "farm_base_tiles_2x2.png",
        "ig_0c6a6c423fdce68e016a11debcbbfc8191bf9a3fb3f846f129.png",
        (0, 0, 0),
        [
            SliceSpec("wheat_farm", "farms", 0, 0, mode="full", crop_inset=3),
            SliceSpec("vegetable_farm", "farms", 0, 1, mode="full", crop_inset=3),
            SliceSpec("orchard_farm", "farms", 1, 0, mode="full", crop_inset=3),
            SliceSpec("livestock_ranch", "farms", 1, 1, mode="full", crop_inset=3),
        ],
    ),
    SheetSpec(
        "overlay_controls_2x2.png",
        "ig_0c6a6c423fdce68e016a11df2007448191bea114403eaf15b1.png",
        (255, 0, 255),
        [
            SliceSpec("road_preview_overlay", "overlays", 0, 0, 118, mode="cutout_all", alpha_scale=0.95),
            SliceSpec("selection_overlay", "overlays", 0, 1, 118, mode="cutout_all", alpha_scale=0.78),
            SliceSpec("invalid_overlay", "overlays", 1, 0, 118, mode="cutout_all", alpha_scale=0.82),
            SliceSpec("grid_overlay", "overlays", 1, 1, 120, mode="cutout_all", alpha_scale=0.55),
        ],
    ),
    SheetSpec(
        "zone_overlays_2x2.png",
        "ig_0c6a6c423fdce68e016a11df703af081919040effb8f3480d9.png",
        (255, 0, 255),
        [
            SliceSpec("zone_residential", "overlays", 0, 0, 118, mode="cutout_all", alpha_scale=0.58),
            SliceSpec("zone_commercial", "overlays", 0, 1, 118, mode="cutout_all", alpha_scale=0.58),
            SliceSpec("zone_industrial", "overlays", 1, 0, 118, mode="cutout_all", alpha_scale=0.58),
            SliceSpec("build_preview_overlay", "overlays", 1, 1, 118, mode="cutout_all", alpha_scale=0.72),
        ],
    ),
]


def is_background_candidate(
    pixel: tuple[int, int, int, int],
    key_rgb: tuple[int, int, int],
    loose: bool = False,
) -> bool:
    r, g, b, a = pixel
    if a == 0:
        return True
    kr, kg, kb = key_rgb
    tolerance = 82 if loose else 48
    if abs(r - kr) <= tolerance and abs(g - kg) <= tolerance and abs(b - kb) <= tolerance:
        return True
    if loose:
        if key_rgb == (0, 255, 0):
            return g > 130 and g > r + 24 and g > b + 24
        return r > 130 and b > 130 and r > g + 24 and b > g + 24
    if key_rgb == (0, 255, 0):
        return g > 150 and g > r + 44 and g > b + 44
    return r > 150 and b > 150 and r > g + 44 and b > g + 44


def connected_chroma_mask(image: Image.Image, key_rgb: tuple[int, int, int]) -> Image.Image:
    """Mask only chroma-key regions connected to the image border."""
    rgba = image.convert("RGBA")
    width, height = rgba.size
    pixels = rgba.load()
    visited = bytearray(width * height)
    mask = Image.new("L", rgba.size, 0)
    mask_pixels = mask.load()
    queue: deque[tuple[int, int]] = deque()

    def push(x: int, y: int) -> None:
        index = y * width + x
        if visited[index]:
            return
        visited[index] = 1
        if is_background_candidate(pixels[x, y], key_rgb):
            queue.append((x, y))

    for x in range(width):
        push(x, 0)
        push(x, height - 1)
    for y in range(height):
        push(0, y)
        push(width - 1, y)

    while queue:
        x, y = queue.popleft()
        mask_pixels[x, y] = 255
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if nx < 0 or ny < 0 or nx >= width or ny >= height:
                continue
            index = ny * width + nx
            if visited[index]:
                continue
            visited[index] = 1
            if is_background_candidate(pixels[nx, ny], key_rgb):
                queue.append((nx, ny))

    fringe = mask
    for _ in range(2):
        expanded = fringe.filter(ImageFilter.MaxFilter(3))
        expanded_pixels = expanded.load()
        fringe_pixels = fringe.load()
        for y in range(height):
            for x in range(width):
                if expanded_pixels[x, y] and is_background_candidate(pixels[x, y], key_rgb, loose=True):
                    fringe_pixels[x, y] = 255

    return fringe


def remove_connected_chroma(image: Image.Image, key_rgb: tuple[int, int, int]) -> Image.Image:
    rgba = image.convert("RGBA")
    mask = connected_chroma_mask(rgba, key_rgb)
    alpha = rgba.getchannel("A")
    alpha_pixels = alpha.load()
    mask_pixels = mask.load()
    width, height = rgba.size
    for y in range(height):
        for x in range(width):
            if mask_pixels[x, y]:
                alpha_pixels[x, y] = 0
    rgba.putalpha(alpha)
    return rgba


def remove_all_chroma(image: Image.Image, key_rgb: tuple[int, int, int]) -> Image.Image:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    pixels = rgba.load()
    alpha_pixels = alpha.load()
    width, height = rgba.size
    for y in range(height):
        for x in range(width):
            if is_background_candidate(pixels[x, y], key_rgb, loose=True):
                alpha_pixels[x, y] = 0
    rgba.putalpha(alpha)
    return rgba


def apply_alpha_scale(image: Image.Image, alpha_scale: float) -> Image.Image:
    if alpha_scale >= 0.999:
        return image
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    alpha = alpha.point(lambda value: round(value * alpha_scale))
    rgba.putalpha(alpha)
    return rgba


def trim_and_fit(image: Image.Image, max_side: int) -> Image.Image:
    bbox = image.getchannel("A").getbbox()
    if not bbox:
        raise ValueError("Slice became fully transparent after chroma removal.")

    cropped = image.crop(bbox)
    width, height = cropped.size
    scale = min(max_side / width, max_side / height)
    resized = cropped.resize((round(width * scale), round(height * scale)), Image.Resampling.LANCZOS)

    canvas = Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (0, 0, 0, 0))
    x = (TILE_SIZE - resized.width) // 2
    y = (TILE_SIZE - resized.height) // 2
    canvas.alpha_composite(resized, (x, y))
    return canvas


def resize_full_tile(image: Image.Image, crop_inset: int) -> Image.Image:
    rgba = image.convert("RGBA")
    if crop_inset:
        width, height = rgba.size
        rgba = rgba.crop((crop_inset, crop_inset, width - crop_inset, height - crop_inset))
    tile = rgba.resize((TILE_SIZE, TILE_SIZE), Image.Resampling.LANCZOS)
    opaque = Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (0, 0, 0, 255))
    opaque.alpha_composite(tile)
    return opaque


def export_sheet(sheet_path: Path, specs: list[SliceSpec], source_name: str, key_rgb: tuple[int, int, int]) -> list[Path]:
    source = Image.open(sheet_path).convert("RGBA")
    cell_width = source.width // 2
    cell_height = source.height // 2

    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(sheet_path, SOURCE_DIR / source_name)

    written: list[Path] = []
    for spec in specs:
        left = spec.col * cell_width
        upper = spec.row * cell_height
        right = source.width if spec.col == 1 else left + cell_width
        lower = source.height if spec.row == 1 else upper + cell_height
        cell = source.crop((left, upper, right, lower))
        if spec.mode == "full":
            asset = resize_full_tile(cell, spec.crop_inset)
        else:
            cleaned = remove_all_chroma(cell, key_rgb) if spec.mode == "cutout_all" else remove_connected_chroma(cell, key_rgb)
            asset = trim_and_fit(cleaned, spec.max_side)
            asset = apply_alpha_scale(asset, spec.alpha_scale)

        out_path = PACK_ROOT / "assets_png_128" / spec.category_dir / f"{spec.asset_id}.png"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        asset.save(out_path)
        written.append(out_path)

    return written


def annotate_manifest(sheet_name: str, specs: list[SliceSpec], written: list[Path]) -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    by_id = {asset["id"]: asset for asset in manifest["assets"]}
    for spec, out_path in zip(specs, written):
        asset = by_id[spec.asset_id]
        asset["imagegenSource"] = {
            "sheet": f"metadata/imagegen_sources/{sheet_name}",
            "slice": {"row": spec.row, "col": spec.col, "grid": [2, 2]},
            "processing": "full_tile_crop_resize" if spec.mode == "full" else spec.mode,
            "output": out_path.relative_to(PACK_ROOT).as_posix(),
        }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    generated_root = Path(r"C:\Users\hp\.codex\generated_images\019e513d-6394-7890-b709-18b7a93b5c3e")
    for sheet in SHEETS:
        sheet_path = generated_root / sheet.generated_file
        if not sheet_path.exists():
            raise FileNotFoundError(sheet_path)

        written = export_sheet(sheet_path, sheet.slices, sheet.source_name, sheet.key_rgb)
        annotate_manifest(sheet.source_name, sheet.slices, written)
        for path in written:
            print(path.relative_to(ROOT).as_posix())


if __name__ == "__main__":
    main()
