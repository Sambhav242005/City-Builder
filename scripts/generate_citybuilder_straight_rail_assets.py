from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
PACK_ROOT = ROOT / "frontend" / "src" / "assets" / "citybuilder-svg-mvp-v2" / "citybuilder_svg_mvp_v2"
PNG_ROOT = PACK_ROOT / "assets_png_128"
TILE_SIZE = 128
SCALE = 4


def scaled_canvas(background: tuple[int, int, int, int]) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGBA", (TILE_SIZE * SCALE, TILE_SIZE * SCALE), background)
    return image, ImageDraw.Draw(image)


def save_downsampled(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = image.resize((TILE_SIZE, TILE_SIZE), Image.Resampling.LANCZOS)
    image.save(path)


def draw_horizontal_rail(draw: ImageDraw.ImageDraw, alpha: int = 255) -> None:
    s = SCALE
    # Ballast bed and rails.
    draw.rounded_rectangle((0, 47 * s, 128 * s, 81 * s), radius=7 * s, fill=(91, 70, 49, alpha))
    for x in range(-8, 136, 16):
        draw.rounded_rectangle((x * s, 49 * s, (x + 8) * s, 79 * s), radius=2 * s, fill=(194, 158, 99, alpha))
    draw.line((0, 57 * s, 128 * s, 57 * s), fill=(45, 39, 34, alpha), width=4 * s)
    draw.line((0, 71 * s, 128 * s, 71 * s), fill=(45, 39, 34, alpha), width=4 * s)
    draw.line((0, 54 * s, 128 * s, 54 * s), fill=(92, 86, 78, alpha), width=1 * s)
    draw.line((0, 68 * s, 128 * s, 68 * s), fill=(92, 86, 78, alpha), width=1 * s)


def draw_vertical_rail(draw: ImageDraw.ImageDraw, alpha: int = 255) -> None:
    s = SCALE
    draw.rounded_rectangle((47 * s, 0, 81 * s, 128 * s), radius=7 * s, fill=(91, 70, 49, alpha))
    for y in range(-8, 136, 16):
        draw.rounded_rectangle((49 * s, y * s, 79 * s, (y + 8) * s), radius=2 * s, fill=(194, 158, 99, alpha))
    draw.line((57 * s, 0, 57 * s, 128 * s), fill=(45, 39, 34, alpha), width=4 * s)
    draw.line((71 * s, 0, 71 * s, 128 * s), fill=(45, 39, 34, alpha), width=4 * s)
    draw.line((54 * s, 0, 54 * s, 128 * s), fill=(92, 86, 78, alpha), width=1 * s)
    draw.line((68 * s, 0, 68 * s, 128 * s), fill=(92, 86, 78, alpha), width=1 * s)


def generate_rail_overlay() -> None:
    image, draw = scaled_canvas((0, 0, 0, 0))
    draw_horizontal_rail(draw)
    save_downsampled(image, PNG_ROOT / "overlays" / "rail_straight_overlay.png")


def generate_rail_crossing() -> None:
    road_path = PNG_ROOT / "roads" / "road_straight.png"
    base = Image.open(road_path).convert("RGBA").resize((TILE_SIZE * SCALE, TILE_SIZE * SCALE), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(base)
    draw_vertical_rail(draw)
    save_downsampled(base, PNG_ROOT / "roads" / "rail_crossing.png")


def main() -> None:
    generate_rail_overlay()
    generate_rail_crossing()
    print((PNG_ROOT / "overlays" / "rail_straight_overlay.png").relative_to(ROOT).as_posix())
    print((PNG_ROOT / "roads" / "rail_crossing.png").relative_to(ROOT).as_posix())


if __name__ == "__main__":
    main()
