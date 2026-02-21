"""Prompt 2A image generation pipeline with provider abstraction and all-model mode."""

from __future__ import annotations

import argparse
import base64
import io
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import requests
from PIL import Image, ImageDraw

try:
    from src import config
    from src.prompt_library import PromptLibrary
except ModuleNotFoundError:  # pragma: no cover
    import config  # type: ignore
    from prompt_library import PromptLibrary  # type: ignore


logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


@dataclass(slots=True)
class GenerationResult:
    """Result for one generated image."""

    book_number: int
    variant: int
    prompt: str
    model: str
    image_path: Path | None
    success: bool
    error: str | None
    generation_time: float
    cost: float
    provider: str
    skipped: bool = False
    dry_run: bool = False
    attempts: int = 0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["image_path"] = str(self.image_path) if self.image_path else None
        return payload


class GenerationError(Exception):
    """Terminal generation error."""


class RetryableGenerationError(GenerationError):
    """Generation error that should be retried."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class BaseProvider:
    """Provider interface."""

    name = "base"

    def __init__(self, model: str, api_key: str = "", timeout: float = 120.0):
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    def generate(self, prompt: str, negative_prompt: str, width: int, height: int) -> Image.Image:
        raise NotImplementedError


class SyntheticProvider(BaseProvider):
    """Offline synthetic generator used when API keys are unavailable."""

    name = "synthetic"

    def generate(self, prompt: str, negative_prompt: str, width: int, height: int) -> Image.Image:
        del negative_prompt
        prompt_lower = prompt.lower()
        image = Image.new("RGB", (width, height), (26, 39, 68))
        draw = ImageDraw.Draw(image, "RGBA")

        if any(token in prompt_lower for token in ("whale", "sea", "ocean", "ship", "ahab")):
            self._draw_whale_scene(draw, width, height)
        elif any(token in prompt_lower for token in ("dracula", "vampire", "castle", "gothic")):
            self._draw_gothic_scene(draw, width, height)
        elif any(token in prompt_lower for token in ("oil painting", "chiaroscuro", "dramatic")):
            self._draw_oil_scene(draw, width, height)
        else:
            self._draw_classical_scene(draw, width, height)

        self._overlay_engraving_texture(draw, width, height)
        return image

    @staticmethod
    def _draw_whale_scene(draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
        draw.rectangle((0, int(height * 0.55), width, height), fill=(19, 65, 118, 220))

        for idx in range(14):
            y = int(height * 0.55 + idx * (height * 0.028))
            draw.arc(
                (-80, y - 26, width + 80, y + 26),
                0,
                180,
                fill=(120, 176, 219, 170),
                width=3,
            )

        draw.ellipse(
            (
                int(width * 0.18),
                int(height * 0.30),
                int(width * 0.82),
                int(height * 0.72),
            ),
            fill=(215, 221, 232, 235),
        )
        draw.polygon(
            [
                (int(width * 0.18), int(height * 0.52)),
                (int(width * 0.05), int(height * 0.60)),
                (int(width * 0.19), int(height * 0.64)),
            ],
            fill=(192, 203, 220, 225),
        )

        draw.polygon(
            [
                (int(width * 0.52), int(height * 0.73)),
                (int(width * 0.75), int(height * 0.73)),
                (int(width * 0.68), int(height * 0.82)),
                (int(width * 0.46), int(height * 0.82)),
            ],
            fill=(108, 78, 54, 240),
        )
        draw.line(
            (
                int(width * 0.60),
                int(height * 0.74),
                int(width * 0.60),
                int(height * 0.57),
            ),
            fill=(224, 198, 158, 230),
            width=4,
        )
        draw.polygon(
            [
                (int(width * 0.60), int(height * 0.58)),
                (int(width * 0.74), int(height * 0.66)),
                (int(width * 0.60), int(height * 0.66)),
            ],
            fill=(240, 231, 211, 195),
        )

    @staticmethod
    def _draw_gothic_scene(draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
        draw.rectangle((0, 0, width, height), fill=(29, 22, 42, 220))
        draw.ellipse(
            (int(width * 0.62), int(height * 0.10), int(width * 0.90), int(height * 0.38)),
            fill=(176, 43, 59, 210),
        )
        draw.rectangle(
            (int(width * 0.22), int(height * 0.40), int(width * 0.52), int(height * 0.84)),
            fill=(17, 14, 25, 230),
        )
        draw.ellipse(
            (int(width * 0.58), int(height * 0.36), int(width * 0.82), int(height * 0.74)),
            fill=(38, 30, 45, 230),
        )

    @staticmethod
    def _draw_oil_scene(draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
        draw.rectangle((0, 0, width, height), fill=(68, 54, 42, 210))
        draw.ellipse(
            (int(width * 0.10), int(height * 0.10), int(width * 0.46), int(height * 0.46)),
            fill=(248, 196, 112, 150),
        )
        draw.polygon(
            [
                (0, height),
                (int(width * 0.5), int(height * 0.58)),
                (width, height),
            ],
            fill=(22, 18, 26, 135),
        )
        draw.ellipse(
            (int(width * 0.32), int(height * 0.34), int(width * 0.70), int(height * 0.84)),
            fill=(125, 88, 68, 205),
        )

    @staticmethod
    def _draw_classical_scene(draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
        draw.rectangle((0, 0, width, height), fill=(42, 53, 72, 210))
        draw.ellipse(
            (int(width * 0.15), int(height * 0.15), int(width * 0.85), int(height * 0.85)),
            fill=(146, 123, 90, 145),
        )
        draw.rectangle(
            (int(width * 0.25), int(height * 0.45), int(width * 0.75), int(height * 0.80)),
            fill=(92, 78, 62, 185),
        )

    @staticmethod
    def _overlay_engraving_texture(draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
        step = max(6, width // 120)
        for y in range(0, height, step):
            draw.line((0, y, width, y + step // 2), fill=(233, 205, 158, 36), width=1)


class OpenAIProvider(BaseProvider):
    """OpenAI Images API."""

    name = "openai"

    def generate(self, prompt: str, negative_prompt: str, width: int, height: int) -> Image.Image:
        if not self.api_key:
            raise GenerationError("Missing OPENAI_API_KEY")

        payload = {
            "model": self.model,
            "prompt": f"{prompt}\nAvoid: {negative_prompt}",
            "size": f"{width}x{height}",
            "response_format": "b64_json",
        }
        response = requests.post(
            "https://api.openai.com/v1/images/generations",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout,
        )
        if response.status_code in RETRYABLE_STATUS_CODES:
            raise RetryableGenerationError(
                f"OpenAI temporary error {response.status_code}: {response.text[:240]}",
                status_code=response.status_code,
            )
        if response.status_code >= 400:
            raise GenerationError(f"OpenAI error {response.status_code}: {response.text[:300]}")

        body = response.json()
        encoded = body.get("data", [{}])[0].get("b64_json")
        if not encoded:
            raise GenerationError("OpenAI response missing image payload")
        image_bytes = base64.b64decode(encoded)
        return Image.open(io.BytesIO(image_bytes)).convert("RGB")


class OpenRouterProvider(BaseProvider):
    """OpenRouter image endpoint (OpenAI-compatible schema)."""

    name = "openrouter"

    def generate(self, prompt: str, negative_prompt: str, width: int, height: int) -> Image.Image:
        if not self.api_key:
            raise GenerationError("Missing OPENROUTER_API_KEY")

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": f"{prompt}\nAvoid: {negative_prompt}\nTarget size: {width}x{height}.",
                }
            ],
            "modalities": ["image"],
            "stream": False,
        }
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://alexandria-cover-designer.local",
                "X-Title": "Alexandria Cover Designer",
            },
            json=payload,
            timeout=self.timeout,
        )
        if response.status_code in RETRYABLE_STATUS_CODES:
            raise RetryableGenerationError(
                f"OpenRouter temporary error {response.status_code}: {response.text[:240]}",
                status_code=response.status_code,
            )
        if response.status_code >= 400:
            raise GenerationError(f"OpenRouter error {response.status_code}: {response.text[:300]}")

        body = response.json()
        choices = body.get("choices") or []
        if choices:
            message = choices[0].get("message", {})
            images = message.get("images") or []
            for image_row in images:
                image_url = ""
                if isinstance(image_row, dict):
                    image_ref = image_row.get("image_url")
                    if isinstance(image_ref, dict):
                        image_url = str(image_ref.get("url", ""))
                    elif isinstance(image_ref, str):
                        image_url = image_ref
                if not image_url:
                    continue
                if image_url.startswith("data:image") and "," in image_url:
                    encoded = image_url.split(",", 1)[1]
                    image_bytes = base64.b64decode(encoded)
                    return Image.open(io.BytesIO(image_bytes)).convert("RGB")
                if image_url.startswith("http"):
                    return _download_image(image_url, timeout=self.timeout)

        # Backward-compatible fallback (older OpenAI-compatible image schema).
        candidate = (body.get("data") or [{}])[0]
        if isinstance(candidate, dict):
            if candidate.get("b64_json"):
                image_bytes = base64.b64decode(candidate["b64_json"])
                return Image.open(io.BytesIO(image_bytes)).convert("RGB")
            if candidate.get("url"):
                return _download_image(candidate["url"], timeout=self.timeout)

        raise GenerationError("OpenRouter response missing image payload")


class FalProvider(BaseProvider):
    """fal.ai generation endpoint."""

    name = "fal"

    def generate(self, prompt: str, negative_prompt: str, width: int, height: int) -> Image.Image:
        if not self.api_key:
            raise GenerationError("Missing FAL_API_KEY")

        endpoint_model = self.model.replace("fal/", "")
        response = requests.post(
            f"https://fal.run/{endpoint_model}",
            headers={
                "Authorization": f"Key {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "image_size": {"width": width, "height": height},
            },
            timeout=self.timeout,
        )
        if response.status_code in RETRYABLE_STATUS_CODES:
            raise RetryableGenerationError(
                f"fal.ai temporary error {response.status_code}: {response.text[:240]}",
                status_code=response.status_code,
            )
        if response.status_code >= 400:
            raise GenerationError(f"fal.ai error {response.status_code}: {response.text[:300]}")

        body = response.json()
        images = body.get("images") or body.get("output", {}).get("images") or []
        if not images:
            raise GenerationError("fal.ai response missing images")
        first = images[0]
        if isinstance(first, dict):
            url = first.get("url")
        else:
            url = str(first)
        if not url:
            raise GenerationError("fal.ai response image URL missing")
        return _download_image(url, timeout=self.timeout)


class ReplicateProvider(BaseProvider):
    """Replicate Predictions API."""

    name = "replicate"

    def generate(self, prompt: str, negative_prompt: str, width: int, height: int) -> Image.Image:
        if not self.api_key:
            raise GenerationError("Missing REPLICATE_API_TOKEN")

        create_response = requests.post(
            "https://api.replicate.com/v1/predictions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "version": self.model,
                "input": {
                    "prompt": prompt,
                    "negative_prompt": negative_prompt,
                    "width": width,
                    "height": height,
                },
            },
            timeout=self.timeout,
        )

        if create_response.status_code in RETRYABLE_STATUS_CODES:
            raise RetryableGenerationError(
                f"Replicate temporary error {create_response.status_code}: {create_response.text[:240]}",
                status_code=create_response.status_code,
            )
        if create_response.status_code >= 400:
            raise GenerationError(
                f"Replicate error {create_response.status_code}: {create_response.text[:300]}"
            )

        prediction = create_response.json()
        prediction_id = prediction.get("id")
        if not prediction_id:
            raise GenerationError("Replicate response missing prediction id")

        poll_url = f"https://api.replicate.com/v1/predictions/{prediction_id}"
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            poll = requests.get(
                poll_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout,
            )
            if poll.status_code in RETRYABLE_STATUS_CODES:
                time.sleep(1.0)
                continue
            if poll.status_code >= 400:
                raise GenerationError(f"Replicate poll error {poll.status_code}: {poll.text[:300]}")

            body = poll.json()
            status = body.get("status")
            if status == "succeeded":
                output = body.get("output")
                if isinstance(output, list) and output:
                    first = output[0]
                    if isinstance(first, dict):
                        output_url = first.get("url")
                        if output_url:
                            return _download_image(str(output_url), timeout=self.timeout)
                    return _download_image(str(first), timeout=self.timeout)
                if isinstance(output, str):
                    return _download_image(output, timeout=self.timeout)
                raise GenerationError("Replicate succeeded but output is empty")
            if status in {"failed", "canceled"}:
                raise GenerationError(f"Replicate prediction {status}: {body.get('error', 'unknown error')}")
            time.sleep(1.0)

        raise RetryableGenerationError("Replicate timed out while polling")


class GoogleCloudProvider(BaseProvider):
    """Google Generative API image endpoint (API key flow)."""

    name = "google"

    def generate(self, prompt: str, negative_prompt: str, width: int, height: int) -> Image.Image:
        if not self.api_key:
            raise GenerationError("Missing GOOGLE_API_KEY")

        model_name = self.model if self.model.startswith("models/") else f"models/{self.model}"
        url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent"
        prompt_text = f"{prompt}. Avoid: {negative_prompt}"
        payload = {
            "contents": [{"parts": [{"text": prompt_text}]}],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {"width": width, "height": height},
            },
        }
        response = requests.post(
            url,
            headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=self.timeout,
        )

        # Some models reject width/height imageConfig; retry once with modality-only config.
        if response.status_code == 400:
            fallback_payload = {
                "contents": [{"parts": [{"text": prompt_text}]}],
                "generationConfig": {
                    "responseModalities": ["IMAGE"],
                },
            }
            response = requests.post(
                url,
                headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
                json=fallback_payload,
                timeout=self.timeout,
            )

        if response.status_code in RETRYABLE_STATUS_CODES:
            raise RetryableGenerationError(
                f"Google temporary error {response.status_code}: {response.text[:240]}",
                status_code=response.status_code,
            )
        if response.status_code >= 400:
            raise GenerationError(f"Google error {response.status_code}: {response.text[:300]}")

        body = response.json()
        candidates = body.get("candidates", [])
        for candidate in candidates:
            parts = candidate.get("content", {}).get("parts", [])
            for part in parts:
                inline = part.get("inlineData", {}) or part.get("inline_data", {})
                data = inline.get("data")
                if data:
                    image_bytes = base64.b64decode(data)
                    return Image.open(io.BytesIO(image_bytes)).convert("RGB")

        generated_images = body.get("generatedImages", []) or body.get("generated_images", [])
        for item in generated_images:
            encoded = item.get("image", {}).get("imageBytes") if isinstance(item, dict) else None
            if encoded:
                image_bytes = base64.b64decode(encoded)
                return Image.open(io.BytesIO(image_bytes)).convert("RGB")

        raise GenerationError("Google response missing image bytes")


_PROVIDER_CLASS_MAP = {
    "openrouter": OpenRouterProvider,
    "fal": FalProvider,
    "replicate": ReplicateProvider,
    "openai": OpenAIProvider,
    "google": GoogleCloudProvider,
}


class ProviderRateLimiter:
    """Simple per-provider request limiter."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_call: dict[str, float] = {}

    def wait(self, provider: str, delay: float) -> None:
        if delay <= 0:
            return

        with self._lock:
            now = time.monotonic()
            last = self._last_call.get(provider, 0.0)
            wait_for = delay - (now - last)
            if wait_for > 0:
                time.sleep(wait_for)
            self._last_call[provider] = time.monotonic()


_RATE_LIMITER = ProviderRateLimiter()


def generate_image(prompt: str, negative_prompt: str, model: str, params: dict[str, Any]) -> bytes:
    """Generate a single image via the specified model/provider."""
    runtime = config.get_config()

    provider = params.get("provider") or runtime.resolve_model_provider(model)
    provider = str(provider).lower()
    provider_model = _resolve_provider_model_name(provider=provider, model=model)
    width = int(params.get("width", runtime.image_width))
    height = int(params.get("height", runtime.image_height))

    request_delay = float(params.get("request_delay", _provider_request_delay(runtime, provider)))
    _RATE_LIMITER.wait(provider, request_delay)

    provider_instance = _create_provider_instance(
        runtime=runtime,
        provider=provider,
        model=provider_model,
        allow_synthetic_fallback=bool(params.get("allow_synthetic_fallback", True)),
    )

    image = provider_instance.generate(
        prompt=prompt,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
    )

    processed = _post_process_image(image, width=width, height=height)
    if _is_blank_or_solid(processed):
        raise GenerationError("Generated image rejected by blank/solid-color quality check")

    buffer = io.BytesIO()
    processed.save(buffer, format="PNG")
    return buffer.getvalue()


def generate_all_models(
    book_number: int,
    prompt: str,
    negative_prompt: str,
    models: list[str],
    variants_per_model: int,
    output_dir: Path,
    *,
    resume: bool = True,
    dry_run: bool = False,
    provider_override: str | None = None,
) -> list[GenerationResult]:
    """Fire ALL models concurrently for the same prompt."""
    runtime = config.get_config()
    output_dir.mkdir(parents=True, exist_ok=True)

    if variants_per_model < 1:
        raise ValueError("variants_per_model must be >= 1")
    if not models:
        raise ValueError("models list cannot be empty")

    results: list[GenerationResult] = []
    failures: list[GenerationResult] = []
    dry_run_plan: list[dict[str, Any]] = []

    tasks: list[tuple[str, int, Path, str]] = []
    for model in models:
        model_dir = output_dir / str(book_number) / _model_to_directory(model)
        model_dir.mkdir(parents=True, exist_ok=True)

        provider = provider_override or runtime.resolve_model_provider(model)
        provider = provider.lower()

        for variant in range(1, variants_per_model + 1):
            image_path = model_dir / f"variant_{variant}.png"
            if resume and image_path.exists():
                logger.info(
                    'Skipping existing image for book %s model "%s" variant %s',
                    book_number,
                    model,
                    variant,
                )
                results.append(
                    GenerationResult(
                        book_number=book_number,
                        variant=variant,
                        prompt=prompt,
                        model=model,
                        image_path=image_path,
                        success=True,
                        error=None,
                        generation_time=0.0,
                        cost=0.0,
                        provider=provider,
                        skipped=True,
                        attempts=0,
                    )
                )
                continue

            if dry_run:
                dry_run_plan.append(
                    {
                        "book_number": book_number,
                        "model": model,
                        "provider": provider,
                        "variant": variant,
                        "prompt": prompt,
                        "negative_prompt": negative_prompt,
                        "output_path": str(image_path),
                        "estimated_cost": runtime.get_model_cost(model),
                    }
                )
                results.append(
                    GenerationResult(
                        book_number=book_number,
                        variant=variant,
                        prompt=prompt,
                        model=model,
                        image_path=None,
                        success=True,
                        error=None,
                        generation_time=0.0,
                        cost=runtime.get_model_cost(model),
                        provider=provider,
                        dry_run=True,
                        attempts=0,
                    )
                )
                continue

            tasks.append((model, variant, image_path, provider))

    if dry_run:
        _append_generation_plan(runtime.generation_plan_path, dry_run_plan)
        return _sort_results(results)

    max_workers = min(len(tasks), max(len(models), runtime.batch_concurrency, 1)) if tasks else 1
    if tasks:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(
                    _generate_one,
                    book_number=book_number,
                    variant=variant,
                    prompt=prompt,
                    negative_prompt=negative_prompt,
                    model=model,
                    provider=provider,
                    output_path=image_path,
                    resume=resume,
                ): (model, variant)
                for model, variant, image_path, provider in tasks
            }

            for future in as_completed(future_map):
                result = future.result()
                results.append(result)
                if not result.success:
                    failures.append(result)

    if failures:
        _append_failures(runtime.failures_path, failures)

    return _sort_results(results)


def generate_single_book(
    book_number: int,
    prompts_path: Path,
    output_dir: Path,
    models: list[str] | None = None,
    variants: int = 5,
    *,
    prompt_variant: int = 1,
    prompt_text: str | None = None,
    negative_prompt: str | None = None,
    provider_override: str | None = None,
    library_prompt_id: str | None = None,
    resume: bool = True,
    dry_run: bool = False,
) -> list[GenerationResult]:
    """Primary single-cover entry point for iterative generation (D19)."""
    runtime = config.get_config()

    payload = _load_prompts_payload(prompts_path)
    book_entry = _find_book_entry(payload, book_number)
    title = str(book_entry.get("title", f"Book {book_number}"))

    base_variant = _find_variant(book_entry, prompt_variant)
    selected_negative_prompt = negative_prompt or str(base_variant.get("negative_prompt", ""))

    selected_prompt = prompt_text
    if library_prompt_id:
        prompt_library = PromptLibrary(runtime.prompt_library_path)
        library_matches = [prompt for prompt in prompt_library.get_prompts() if prompt.id == library_prompt_id]
        if not library_matches:
            raise KeyError(f"Prompt id '{library_prompt_id}' not found in prompt library")
        selected_prompt = library_matches[0].prompt_template.format(title=title)
        if not negative_prompt:
            selected_negative_prompt = library_matches[0].negative_prompt

    if not selected_prompt:
        selected_prompt = str(base_variant.get("prompt", "")).strip()

    active_models = models[:] if models else runtime.all_models[:]
    if not active_models:
        active_models = [runtime.ai_model]

    logger.info(
        "Generating single book %s using %d model(s), %d variant(s)/model",
        book_number,
        len(active_models),
        variants,
    )

    return generate_all_models(
        book_number=book_number,
        prompt=selected_prompt,
        negative_prompt=selected_negative_prompt,
        models=active_models,
        variants_per_model=variants,
        output_dir=output_dir,
        resume=resume,
        dry_run=dry_run,
        provider_override=provider_override,
    )


def generate_batch(
    prompts_path: Path,
    output_dir: Path,
    resume: bool = True,
    *,
    books: list[int] | None = None,
    model: str | None = None,
    dry_run: bool = False,
    max_books: int = 20,
) -> list[GenerationResult]:
    """Batch generation mode for validated model/prompt combinations.

    D23 scope default: first 20 titles only.
    """
    runtime = config.get_config()
    payload = _load_prompts_payload(prompts_path)

    all_books = sorted(payload.get("books", []), key=lambda item: int(item.get("number", 0)))
    if books:
        wanted = {int(num) for num in books}
        all_books = [item for item in all_books if int(item.get("number", 0)) in wanted]
    else:
        all_books = all_books[:max_books]

    chosen_model = model or runtime.ai_model
    chosen_provider = runtime.resolve_model_provider(chosen_model)

    total_jobs = sum(min(runtime.variants_per_cover, len(entry.get("variants", []))) for entry in all_books)
    completed = 0

    results: list[GenerationResult] = []
    failures: list[GenerationResult] = []
    dry_run_plan: list[dict[str, Any]] = []

    for book_entry in all_books:
        book_number = int(book_entry.get("number", 0))
        title = str(book_entry.get("title", f"Book {book_number}"))
        variants = sorted(book_entry.get("variants", []), key=lambda item: int(item.get("variant_id", 0)))
        variants = variants[: runtime.variants_per_cover]

        for variant_entry in variants:
            completed += 1
            variant_id = int(variant_entry.get("variant_id", completed))
            prompt = str(variant_entry.get("prompt", ""))
            negative_prompt = str(variant_entry.get("negative_prompt", ""))
            image_path = output_dir / str(book_number) / f"variant_{variant_id}.png"

            if resume and image_path.exists():
                logger.info(
                    "[%d/%d] Skipping Variant %d for \"%s\" (already exists)",
                    completed,
                    total_jobs,
                    variant_id,
                    title,
                )
                results.append(
                    GenerationResult(
                        book_number=book_number,
                        variant=variant_id,
                        prompt=prompt,
                        model=chosen_model,
                        image_path=image_path,
                        success=True,
                        error=None,
                        generation_time=0.0,
                        cost=0.0,
                        provider=chosen_provider,
                        skipped=True,
                        attempts=0,
                    )
                )
                continue

            logger.info(
                "[%d/%d] Generating Variant %d for \"%s\"...",
                completed,
                total_jobs,
                variant_id,
                title,
            )

            if dry_run:
                dry_run_plan.append(
                    {
                        "book_number": book_number,
                        "model": chosen_model,
                        "provider": chosen_provider,
                        "variant": variant_id,
                        "prompt": prompt,
                        "negative_prompt": negative_prompt,
                        "output_path": str(image_path),
                        "estimated_cost": runtime.get_model_cost(chosen_model),
                    }
                )
                results.append(
                    GenerationResult(
                        book_number=book_number,
                        variant=variant_id,
                        prompt=prompt,
                        model=chosen_model,
                        image_path=None,
                        success=True,
                        error=None,
                        generation_time=0.0,
                        cost=runtime.get_model_cost(chosen_model),
                        provider=chosen_provider,
                        dry_run=True,
                        attempts=0,
                    )
                )
                continue

            result = _generate_one(
                book_number=book_number,
                variant=variant_id,
                prompt=prompt,
                negative_prompt=negative_prompt,
                model=chosen_model,
                provider=chosen_provider,
                output_path=image_path,
                resume=resume,
            )
            results.append(result)
            if not result.success:
                failures.append(result)

    if dry_run and dry_run_plan:
        _append_generation_plan(runtime.generation_plan_path, dry_run_plan)

    if failures:
        _append_failures(runtime.failures_path, failures)

    return _sort_results(results)


def _generate_one(
    *,
    book_number: int,
    variant: int,
    prompt: str,
    negative_prompt: str,
    model: str,
    provider: str,
    output_path: Path,
    resume: bool,
) -> GenerationResult:
    runtime = config.get_config()

    if resume and output_path.exists():
        return GenerationResult(
            book_number=book_number,
            variant=variant,
            prompt=prompt,
            model=model,
            image_path=output_path,
            success=True,
            error=None,
            generation_time=0.0,
            cost=0.0,
            provider=provider,
            skipped=True,
            attempts=0,
        )

    start = time.perf_counter()
    last_error: str | None = None

    for attempt in range(1, runtime.max_retries + 1):
        try:
            image_bytes = generate_image(
                prompt=prompt,
                negative_prompt=negative_prompt,
                model=model,
                params={
                    "provider": provider,
                    "width": runtime.image_width,
                    "height": runtime.image_height,
                    "request_delay": _provider_request_delay(runtime, provider),
                    "allow_synthetic_fallback": True,
                },
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(image_bytes)

            elapsed = time.perf_counter() - start
            return GenerationResult(
                book_number=book_number,
                variant=variant,
                prompt=prompt,
                model=model,
                image_path=output_path,
                success=True,
                error=None,
                generation_time=elapsed,
                cost=runtime.get_model_cost(model),
                provider=provider,
                attempts=attempt,
            )
        except RetryableGenerationError as exc:
            last_error = str(exc)
            if attempt >= runtime.max_retries:
                break
            backoff = runtime.request_delay * (2 ** (attempt - 1))
            logger.warning(
                "Retryable error for book %s model %s variant %s (%d/%d): %s",
                book_number,
                model,
                variant,
                attempt,
                runtime.max_retries,
                exc,
            )
            time.sleep(backoff)
        except GenerationError as exc:
            last_error = str(exc)
            break
        except requests.RequestException as exc:
            last_error = f"Request failure: {exc}"
            if attempt >= runtime.max_retries:
                break
            backoff = runtime.request_delay * (2 ** (attempt - 1))
            logger.warning(
                "Network retry for book %s model %s variant %s (%d/%d): %s",
                book_number,
                model,
                variant,
                attempt,
                runtime.max_retries,
                exc,
            )
            time.sleep(backoff)

    elapsed = time.perf_counter() - start
    return GenerationResult(
        book_number=book_number,
        variant=variant,
        prompt=prompt,
        model=model,
        image_path=None,
        success=False,
        error=last_error or "Unknown generation failure",
        generation_time=elapsed,
        cost=0.0,
        provider=provider,
        attempts=runtime.max_retries,
    )


def _provider_request_delay(runtime: config.Config, provider: str) -> float:
    return float(runtime.provider_request_delay.get(provider, runtime.request_delay))


def _create_provider_instance(
    *,
    runtime: config.Config,
    provider: str,
    model: str,
    allow_synthetic_fallback: bool,
) -> BaseProvider:
    api_key = runtime.get_api_key(provider)

    if provider not in _PROVIDER_CLASS_MAP:
        raise GenerationError(f"Unsupported provider: {provider}")

    if not api_key and allow_synthetic_fallback:
        logger.info(
            "No API key configured for provider '%s'; using synthetic provider fallback for local iteration",
            provider,
        )
        return SyntheticProvider(model=model)

    provider_class = _PROVIDER_CLASS_MAP[provider]
    return provider_class(model=model, api_key=api_key)


def _resolve_provider_model_name(provider: str, model: str) -> str:
    """Strip provider prefix from provider/model notation."""
    token = model.strip()
    if "/" not in token:
        return token

    prefix, suffix = token.split("/", 1)
    if prefix.lower() == provider.lower() and suffix:
        return suffix
    return token


def _post_process_image(image: Image.Image, width: int, height: int) -> Image.Image:
    processed = image.convert("RGBA").resize((width, height), Image.LANCZOS)

    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, width - 1, height - 1), fill=255)
    processed.putalpha(mask)

    return processed


def _is_blank_or_solid(image: Image.Image) -> bool:
    rgb = np.array(image.convert("RGB"), dtype=np.uint8)
    std = float(rgb.std())
    min_val = int(rgb.min())
    max_val = int(rgb.max())
    unique_ratio = float(np.unique(rgb.reshape(-1, 3), axis=0).shape[0]) / float(rgb.shape[0] * rgb.shape[1])
    return std < 4.0 or (max_val - min_val) < 8 or unique_ratio < 0.00001


def _download_image(url: str, timeout: float = 120.0) -> Image.Image:
    response = requests.get(url, timeout=timeout)
    if response.status_code in RETRYABLE_STATUS_CODES:
        raise RetryableGenerationError(
            f"Temporary download error {response.status_code} for {url}",
            status_code=response.status_code,
        )
    if response.status_code >= 400:
        raise GenerationError(f"Image download failed {response.status_code}: {url}")
    return Image.open(io.BytesIO(response.content)).convert("RGB")


def _load_prompts_payload(prompts_path: Path) -> dict[str, Any]:
    payload = json.loads(prompts_path.read_text(encoding="utf-8"))
    books = payload.get("books")
    if not isinstance(books, list):
        raise ValueError(f"Invalid prompts file at {prompts_path}: missing 'books' list")
    return payload


def _find_book_entry(payload: dict[str, Any], book_number: int) -> dict[str, Any]:
    for book in payload.get("books", []):
        if int(book.get("number", 0)) == int(book_number):
            return book
    raise KeyError(f"Book #{book_number} not found in prompts file")


def _find_variant(book_entry: dict[str, Any], variant_id: int) -> dict[str, Any]:
    variants = book_entry.get("variants", [])
    for item in variants:
        if int(item.get("variant_id", 0)) == int(variant_id):
            return item
    if variants:
        return variants[0]
    raise KeyError(f"Book {book_entry.get('number')} has no variants")


def _model_to_directory(model: str) -> str:
    return model.strip().lower().replace("/", "__").replace(" ", "_")


def _append_failures(path: Path, failed_results: list[GenerationResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
    else:
        payload = {}

    existing = payload.get("failures") if isinstance(payload, dict) else None
    if not isinstance(existing, list):
        existing = []

    timestamp = datetime.now(timezone.utc).isoformat()
    for result in failed_results:
        existing.append(
            {
                "timestamp": timestamp,
                "book_number": result.book_number,
                "variant": result.variant,
                "model": result.model,
                "provider": result.provider,
                "prompt": result.prompt,
                "error": result.error,
            }
        )

    output = {
        "updated_at": timestamp,
        "failures": existing,
    }
    path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")


def _append_generation_plan(path: Path, plan_rows: list[dict[str, Any]]) -> None:
    if not plan_rows:
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
    else:
        payload = {}

    existing = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(existing, list):
        existing = []

    existing.extend(plan_rows)
    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "items": existing,
    }
    path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")


def _sort_results(results: list[GenerationResult]) -> list[GenerationResult]:
    return sorted(results, key=lambda item: (item.book_number, item.model, item.variant, item.image_path is None))


def _parse_books_arg(raw: str | None) -> list[int] | None:
    if not raw:
        return None

    result: set[int] = set()
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue

        if "-" in token:
            start_str, end_str = token.split("-", 1)
            start = int(start_str)
            end = int(end_str)
            for value in range(min(start, end), max(start, end) + 1):
                result.add(value)
        else:
            result.add(int(token))

    return sorted(result)


def _build_models_from_args(args: argparse.Namespace, runtime: config.Config) -> list[str] | None:
    if args.all_models:
        return runtime.all_models[:]
    if args.models:
        return [token.strip() for token in args.models.split(",") if token.strip()]
    if args.model:
        return [args.model.strip()]
    return None


def _summarize_results(results: list[GenerationResult]) -> dict[str, Any]:
    total = len(results)
    success = sum(1 for result in results if result.success)
    failed = sum(1 for result in results if not result.success)
    skipped = sum(1 for result in results if result.skipped)
    dry_run = sum(1 for result in results if result.dry_run)
    total_cost = sum(result.cost for result in results)

    return {
        "total": total,
        "success": success,
        "failed": failed,
        "skipped": skipped,
        "dry_run": dry_run,
        "total_cost": round(total_cost, 4),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Prompt 2A image generation pipeline")
    parser.add_argument("--prompts-path", type=Path, default=config.PROMPTS_PATH)
    parser.add_argument("--output-dir", type=Path, default=config.TMP_DIR / "generated")

    parser.add_argument("--book", type=int, help="Single book number for iteration mode")
    parser.add_argument("--books", type=str, help="Batch selection, e.g. 1-20 or 2,5,8")

    parser.add_argument("--model", type=str, help="Single model, e.g. openai/gpt-image-1")
    parser.add_argument("--models", type=str, help="Comma-separated model list")
    parser.add_argument("--all-models", action="store_true", help="Use all configured models")

    parser.add_argument("--variants", type=int, default=config.VARIANTS_PER_COVER)
    parser.add_argument("--prompt-variant", type=int, default=1)
    parser.add_argument("--prompt-text", type=str, default=None)
    parser.add_argument("--negative-prompt", type=str, default=None)
    parser.add_argument("--library-prompt-id", type=str, default=None)

    parser.add_argument("--provider", type=str, default=None, help="Override provider for all requests")
    parser.add_argument("--dry-run", action="store_true", help="Save generation plan without generating images")
    parser.add_argument("--no-resume", action="store_true", help="Disable skip-existing behavior")

    parser.add_argument(
        "--max-books",
        type=int,
        default=20,
        help="Batch scope limit (default 20 per D23)",
    )

    args = parser.parse_args()
    runtime = config.get_config()

    models = _build_models_from_args(args, runtime)
    resume = not args.no_resume

    if args.book is not None:
        results = generate_single_book(
            book_number=args.book,
            prompts_path=args.prompts_path,
            output_dir=args.output_dir,
            models=models,
            variants=args.variants,
            prompt_variant=args.prompt_variant,
            prompt_text=args.prompt_text,
            negative_prompt=args.negative_prompt,
            provider_override=args.provider,
            library_prompt_id=args.library_prompt_id,
            resume=resume,
            dry_run=args.dry_run,
        )
    else:
        book_selection = _parse_books_arg(args.books)
        chosen_model = None
        if models:
            chosen_model = models[0]

        results = generate_batch(
            prompts_path=args.prompts_path,
            output_dir=args.output_dir,
            resume=resume,
            books=book_selection,
            model=chosen_model,
            dry_run=args.dry_run,
            max_books=args.max_books,
        )

    summary = _summarize_results(results)
    logger.info("Generation summary: %s", summary)
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
