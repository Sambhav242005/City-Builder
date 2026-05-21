from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "frontend" / "src" / "assets" / "map-sprites" / "road.png"
OUT_DIR = ROOT / "frontend" / "src" / "assets" / "map-sprites" / "roads"

DIRECTIONS = ("n", "e", "s", "w")
ENDPOINTS = {
    "n": (0.50, 0.10),
    "e": (0.91, 0.51),
    "s": (0.50, 0.90),
    "w": (0.09, 0.49),
}

ARM_POLYGONS = {
    "n": ((0.50, 0.50), (0.33, 0.30), (0.50, 0.05), (0.67, 0.30)),
    "e": ((0.50, 0.50), (0.67, 0.30), (0.98, 0.50), (0.67, 0.70)),
    "s": ((0.50, 0.50), (0.67, 0.70), (0.50, 0.95), (0.33, 0.70)),
    "w": ((0.50, 0.50), (0.33, 0.70), (0.02, 0.50), (0.33, 0.30)),
}


def apply_mask(image: Image.Image, mask: Image.Image) -> Image.Image:
    masked = image.copy()
    alpha = masked.getchannel("A")
    masked.putalpha(ImageChops.multiply(alpha, mask))
    return masked


def arm_mask(size: tuple[int, int], direction: str) -> Image.Image:
    width, height = size
    center = (round(width * 0.5), round(height * 0.5))
    points = [
        (round(width * x), round(height * y))
        for x, y in ARM_POLYGONS[direction]
    ]
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.polygon(points, fill=255)
    draw.polygon(
        [
            (center[0], round(height * 0.29)),
            (round(width * 0.70), center[1]),
            (center[0], round(height * 0.71)),
            (round(width * 0.30), center[1]),
        ],
        fill=255,
    )
    return mask.filter(ImageFilter.GaussianBlur(radius=0.5))


def dim_for_overlay(image: Image.Image, opacity: float) -> Image.Image:
    overlay = image.copy()
    alpha = overlay.getchannel("A").point(lambda value: round(value * opacity))
    overlay.putalpha(alpha)
    return overlay


def compose_variant(
    primary_axis: Image.Image,
    secondary_axis: Image.Image,
    connections: tuple[str, ...],
) -> Image.Image:
    if set(connections) == {"e", "w"}:
        return primary_axis.copy()
    if set(connections) == {"n", "s"}:
        return secondary_axis.copy()
    if set(connections) == set(DIRECTIONS):
        canvas = dim_for_overlay(primary_axis, 0.92)
        canvas.alpha_composite(dim_for_overlay(secondary_axis, 0.88))
        return canvas

    canvas = Image.new("RGBA", primary_axis.size, (0, 0, 0, 0))
    for direction in connections:
        axis = secondary_axis if direction in {"n", "s"} else primary_axis
        canvas.alpha_composite(apply_mask(axis, arm_mask(axis.size, direction)))
    return canvas


def variant_name(connections: tuple[str, ...]) -> str:
    if len(connections) == 1:
        return f"road-end-{connections[0]}"
    if set(connections) == {"e", "w"}:
        return "road-straight-ew"
    if set(connections) == {"n", "s"}:
        return "road-straight-ns"
    if len(connections) == 2:
        return f"road-corner-{''.join(connections)}"
    if len(connections) == 3:
        missing = next(direction for direction in DIRECTIONS if direction not in connections)
        return f"road-t-{missing}"
    return "road-cross"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = Image.open(SOURCE).convert("RGBA")
    primary_axis = ImageEnhance.Contrast(source).enhance(1.04)
    secondary_axis = ImageEnhance.Contrast(source.transpose(Image.Transpose.FLIP_LEFT_RIGHT)).enhance(1.04)

    variants: list[tuple[str, ...]] = [
        ("n",),
        ("e",),
        ("s",),
        ("w",),
        ("n", "s"),
        ("e", "w"),
        ("n", "e"),
        ("e", "s"),
        ("s", "w"),
        ("n", "w"),
        ("n", "e", "s"),
        ("e", "s", "w"),
        ("n", "s", "w"),
        ("n", "e", "w"),
        ("n", "e", "s", "w"),
    ]

    for connections in variants:
        sprite = compose_variant(primary_axis, secondary_axis, connections)
        output = OUT_DIR / f"{variant_name(connections)}.png"
        sprite.save(output, optimize=True)
        print(output.relative_to(ROOT))


if __name__ == "__main__":
    main()
