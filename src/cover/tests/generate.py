"""Generate real AI art for test fixtures, using the same prompt
pipeline as the production system."""

from __future__ import annotations

from pathlib import Path

from src import config, image_generator, safe_json


def _load_book_prompt(book_number: int = 1) -> tuple[str, str]:
    """Load prompt and negative_prompt for a book from the prompts catalog."""
    runtime = config.get_config()
    prompts = safe_json.load_json(runtime.prompts_path, {"books": []})
    books = prompts.get("books", [])

    book = next((b for b in books if b.get("number") == book_number), None)
    if not book:
        raise ValueError(f"Book #{book_number} not found in prompts catalog")

    variants = book.get("variants", [])
    if not variants:
        raise ValueError(f"Book #{book_number} has no prompt variants")

    v = variants[0]
    return v.get("prompt", ""), v.get("negative_prompt", "")


def generate_art(
    output_path: Path,
    *,
    book_number: int = 1,
    prompt: str | None = None,
    negative_prompt: str | None = None,
    model: str | None = None,
    provider: str = "openrouter",
    width: int = 1024,
    height: int = 1024,
    seed: int | None = None,
) -> Path:
    """Generate a single AI art image and save it as PNG.

    If prompt is not given, loads the first variant prompt for *book_number*
    from the prompts catalog — the same prompt the pipeline would use.
    """
    if prompt is None or negative_prompt is None:
        cat_prompt, cat_negative = _load_book_prompt(book_number)
        prompt = prompt or cat_prompt
        negative_prompt = negative_prompt or cat_negative

    runtime = config.get_config()
    model = model or runtime.ai_model

    params: dict = {
        "width": width,
        "height": height,
    }
    params["provider"] = provider

    png_bytes: bytes = image_generator.generate_image(
        prompt=prompt,
        negative_prompt=negative_prompt,
        model=model,
        params=params,
        seed=seed,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(png_bytes)
    return output_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate test fixture art")
    parser.add_argument("--book", type=int, default=1, help="Book number")
    parser.add_argument("--model", default=None, help="Model override")
    parser.add_argument(
        "--output",
        default="src/cover/tests/fixtures/sample_art.png",
        help="Output path",
    )
    args = parser.parse_args()

    out = generate_art(
        Path(args.output),
        book_number=args.book,
        model=args.model,
    )
    print(f"Saved: {out}")
