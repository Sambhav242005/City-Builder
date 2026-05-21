from __future__ import annotations

from collections import deque
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "frontend" / "src" / "assets"
OUT_DIR = SOURCE_DIR / "map-sprites"
MAX_SIZE = 360

SPRITES = {
    "asset_residential.png": "residential.png",
    "asset_factory.png": "factory.png",
    "asset_farm.png": "farm.png",
    "asset_government.png": "government.png",
    "asset_market.png": "market.png",
    "asset_park.png": "park.png",
    "asset_power_plant.png": "power-plant.png",
    "asset_road.png": "road.png",
    "asset_water.png": "water.png",
}


def background_like(pixel: tuple[int, int, int, int]) -> bool:
    r, g, b, _ = pixel
    max_channel = max(r, g, b)
    min_channel = min(r, g, b)
    neutral = max_channel - min_channel <= 48
    checker_white = min_channel >= 218
    checker_gray = 132 <= r <= 228 and 132 <= g <= 228 and 132 <= b <= 228
    return neutral and (checker_white or checker_gray)


def flood_background(image: Image.Image) -> bytearray:
    width, height = image.size
    pixels = image.load()
    visited = bytearray(width * height)
    queue: deque[tuple[int, int]] = deque()

    def index(x: int, y: int) -> int:
        return y * width + x

    def add(x: int, y: int) -> None:
        if x < 0 or y < 0 or x >= width or y >= height:
            return
        offset = index(x, y)
        if visited[offset]:
            return
        if background_like(pixels[x, y]):
            visited[offset] = 1
            queue.append((x, y))

    for x in range(width):
        add(x, 0)
        add(x, height - 1)
    for y in range(height):
        add(0, y)
        add(width - 1, y)

    while queue:
        x, y = queue.popleft()
        add(x + 1, y)
        add(x - 1, y)
        add(x, y + 1)
        add(x, y - 1)

    return visited


def trim_and_resize(image: Image.Image, mask: bytearray) -> Image.Image:
    width, height = image.size
    pixels = image.load()
    min_x, min_y = width, height
    max_x, max_y = 0, 0

    for y in range(height):
        for x in range(width):
            offset = y * width + x
            r, g, b, a = pixels[x, y]
            if mask[offset]:
                pixels[x, y] = (r, g, b, 0)
            else:
                pixels[x, y] = (r, g, b, a)
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)

    if min_x >= width or min_y >= height:
        raise RuntimeError("No foreground pixels detected")

    pad = 10
    min_x = max(0, min_x - pad)
    min_y = max(0, min_y - pad)
    max_x = min(width - 1, max_x + pad)
    max_y = min(height - 1, max_y + pad)

    cropped = image.crop((min_x, min_y, max_x + 1, max_y + 1))
    scale = min(MAX_SIZE / cropped.width, MAX_SIZE / cropped.height, 1)
    if scale < 1:
        target_size = (max(1, round(cropped.width * scale)), max(1, round(cropped.height * scale)))
        cropped = cropped.resize(target_size, Image.Resampling.LANCZOS)
    return cropped


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for source_name, output_name in SPRITES.items():
        source_path = SOURCE_DIR / source_name
        output_path = OUT_DIR / output_name
        image = Image.open(source_path).convert("RGBA")
        mask = flood_background(image)
        sprite = trim_and_resize(image, mask)
        sprite.save(output_path, optimize=True)
        print(f"{source_name} -> {output_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
