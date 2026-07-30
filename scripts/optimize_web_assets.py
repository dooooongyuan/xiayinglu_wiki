#!/usr/bin/env python3
"""Build lightweight WebP derivatives from the wiki's source PNG assets."""

from __future__ import annotations

from pathlib import Path

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GAME_DIR = PROJECT_ROOT / "wiki" / "public" / "game"
ICON_CATEGORIES = ("equipment", "materials", "danyao", "wuxue", "zhuwen", "traps")


def resized(image: Image.Image, bounds: tuple[int, int]) -> Image.Image:
    result = image.convert("RGBA")
    result.thumbnail(bounds, Image.Resampling.LANCZOS)
    return result


def fitted(image: Image.Image, bounds: tuple[int, int]) -> Image.Image:
    source = image.convert("RGBA")
    scale = min(bounds[0] / source.width, bounds[1] / source.height)
    size = (max(1, round(source.width * scale)), max(1, round(source.height * scale)))
    return source.resize(size, Image.Resampling.LANCZOS)


def save_webp(image: Image.Image, target: Path, quality: int = 84) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, "WEBP", quality=quality, method=4, exact=True)


def optimize_named(source_name: str, target_name: str, bounds: tuple[int, int], quality: int) -> None:
    with Image.open(GAME_DIR / source_name) as image:
        save_webp(resized(image, bounds), GAME_DIR / "optimized" / target_name, quality)


def optimize_icons() -> int:
    count = 0
    for category in ICON_CATEGORIES:
        for source in sorted((GAME_DIR / category).glob("*.png")):
            with Image.open(source) as image:
                icon = fitted(image, (224, 224)) if category == "wuxue" else resized(image, (256, 256))
                canvas = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
                canvas.alpha_composite(icon, ((256 - icon.width) // 2, (256 - icon.height) // 2))
                save_webp(
                    canvas,
                    GAME_DIR / "optimized" / category / f"{source.stem}.webp",
                )
            count += 1
    return count


def optimize_characters() -> int:
    count = 0
    for source in sorted((GAME_DIR / "characters").glob("*.png")):
        with Image.open(source) as image:
            portrait = image.convert("RGBA")

            card_image = resized(portrait, (252, 428))
            card = Image.new("RGBA", (252, 428), (0, 0, 0, 0))
            card.alpha_composite(card_image, ((252 - card_image.width) // 2, 428 - card_image.height))
            save_webp(card, GAME_DIR / "characters" / "thumbs" / f"{source.stem}.webp", 82)

            detail_image = resized(portrait, (480, 720))
            detail = Image.new("RGBA", (480, 720), (0, 0, 0, 0))
            detail.alpha_composite(detail_image, ((480 - detail_image.width) // 2, 720 - detail_image.height))
            save_webp(detail, GAME_DIR / "characters" / "detail" / f"{source.stem}.webp", 86)
        count += 1
    return count


def main() -> None:
    optimize_named("wiki-logo.png", "wiki-logo-header.webp", (184, 118), 88)
    optimize_named("wiki-logo.png", "wiki-logo-hero.webp", (900, 578), 88)
    optimize_named("wiki-hero-background.png", "wiki-hero-background.webp", (2048, 988), 82)
    for category in ("wuxue", "zhuangbei", "danyao", "qita"):
        optimize_named(f"category-{category}.png", f"category-{category}.webp", (320, 564), 84)

    icon_count = optimize_icons()
    character_count = optimize_characters()
    print(f"Optimized {icon_count} icons and {character_count} character portraits.")


if __name__ == "__main__":
    main()
