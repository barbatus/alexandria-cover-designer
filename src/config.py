"""Central runtime configuration for Alexandria Cover Designer (Prompt 2A)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = PROJECT_ROOT / os.getenv("INPUT_DIR", "Input Covers")
OUTPUT_DIR = PROJECT_ROOT / os.getenv("OUTPUT_DIR", "Output Covers")
TMP_DIR = PROJECT_ROOT / os.getenv("TMP_DIR", "tmp")
DATA_DIR = PROJECT_ROOT / os.getenv("DATA_DIR", "data")
CONFIG_DIR = PROJECT_ROOT / os.getenv("CONFIG_DIR", "config")

PROMPTS_PATH = CONFIG_DIR / os.getenv("PROMPTS_FILE", "book_prompts.json")
BOOK_CATALOG_PATH = CONFIG_DIR / os.getenv("BOOK_CATALOG_FILE", "book_catalog.json")
PROMPT_TEMPLATES_PATH = CONFIG_DIR / os.getenv("PROMPT_TEMPLATES_FILE", "prompt_templates.json")
PROMPT_LIBRARY_PATH = CONFIG_DIR / os.getenv("PROMPT_LIBRARY_FILE", "prompt_library.json")

# Provider defaults
AI_PROVIDER = os.getenv("AI_PROVIDER", "openrouter").strip().lower()
AI_MODEL = os.getenv("AI_MODEL", "flux-2-pro").strip()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
FAL_API_KEY = os.getenv("FAL_API_KEY", "")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GDRIVE_OUTPUT_FOLDER_ID = os.getenv("GDRIVE_OUTPUT_FOLDER_ID", "1Vr184ZsX3k38xpmZkd8g2vwB5y9LYMRC")
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "")

ALL_MODELS = [
    m.strip()
    for m in os.getenv(
        "ALL_MODELS",
        "flux-2-pro,flux-2-schnell,gpt-image-1-high,gpt-image-1-medium,imagen-4-ultra,imagen-4-fast,nano-banana-pro",
    ).split(",")
    if m.strip()
]

MODEL_PROVIDER_MAP: dict[str, str] = {
    "flux-2-pro": "openrouter",
    "flux-2-schnell": "openrouter",
    "gpt-image-1-high": "openai",
    "gpt-image-1-medium": "openai",
    "imagen-4-ultra": "google",
    "imagen-4-fast": "google",
    "nano-banana-pro": "openrouter",
}

MODEL_COST_USD: dict[str, float] = {
    "flux-2-pro": 0.055,
    "flux-2-schnell": 0.003,
    "gpt-image-1-high": 0.167,
    "gpt-image-1-medium": 0.040,
    "imagen-4-ultra": 0.060,
    "imagen-4-fast": 0.030,
    "nano-banana-pro": 0.067,
}

VARIANTS_PER_COVER = int(os.getenv("VARIANTS_PER_COVER", "5"))
BATCH_CONCURRENCY = int(os.getenv("BATCH_CONCURRENCY", "1"))
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "1.0"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

PROVIDER_REQUEST_DELAY = {
    "openrouter": float(os.getenv("OPENROUTER_REQUEST_DELAY", str(REQUEST_DELAY))),
    "fal": float(os.getenv("FAL_REQUEST_DELAY", str(REQUEST_DELAY))),
    "replicate": float(os.getenv("REPLICATE_REQUEST_DELAY", str(REQUEST_DELAY))),
    "openai": float(os.getenv("OPENAI_REQUEST_DELAY", str(REQUEST_DELAY))),
    "google": float(os.getenv("GOOGLE_REQUEST_DELAY", str(REQUEST_DELAY))),
}

GEN_WIDTH = int(os.getenv("GEN_WIDTH", "1024"))
GEN_HEIGHT = int(os.getenv("GEN_HEIGHT", "1024"))
GEN_OUTPUT_FORMAT = os.getenv("GEN_OUTPUT_FORMAT", "png").strip().lower()

MIN_QUALITY_SCORE = float(os.getenv("MIN_QUALITY_SCORE", "0.6"))
MAX_COST_USD = float(os.getenv("MAX_COST_USD", "200.00"))

BOOK_SCOPE_LIMIT = int(os.getenv("BOOK_SCOPE_LIMIT", "20"))
MAX_EXPORT_VARIANTS = int(os.getenv("MAX_EXPORT_VARIANTS", "20"))

FAILURES_PATH = DATA_DIR / "generation_failures.json"
GENERATION_PLAN_PATH = DATA_DIR / "generation_plan.json"


def ensure_runtime_dirs() -> None:
    """Ensure runtime directories exist."""
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def get_initial_scope_book_numbers(limit: int | None = None) -> list[int]:
    """Return the first N book numbers from catalog for D23 scope."""
    payload = _load_json(BOOK_CATALOG_PATH)
    if not isinstance(payload, list):
        return []

    max_items = limit if limit is not None else BOOK_SCOPE_LIMIT
    values: list[int] = []
    for entry in payload:
        number = entry.get("number")
        if isinstance(number, int):
            values.append(number)
        if len(values) >= max_items:
            break
    return values


@dataclass(slots=True)
class Config:
    """Typed runtime configuration snapshot.

    Includes compatibility attributes used by existing project tests.
    """

    project_root: Path = PROJECT_ROOT
    input_dir: Path = INPUT_DIR
    output_dir: Path = OUTPUT_DIR
    tmp_dir: Path = TMP_DIR
    data_dir: Path = DATA_DIR
    config_dir: Path = CONFIG_DIR

    prompts_path: Path = PROMPTS_PATH
    book_catalog_path: Path = BOOK_CATALOG_PATH
    prompt_templates_path: Path = PROMPT_TEMPLATES_PATH
    prompt_library_path: Path = PROMPT_LIBRARY_PATH

    ai_provider: str = AI_PROVIDER
    ai_model: str = AI_MODEL
    all_models: list[str] = field(default_factory=lambda: ALL_MODELS.copy())

    openrouter_api_key: str = OPENROUTER_API_KEY
    fal_api_key: str = FAL_API_KEY
    replicate_api_token: str = REPLICATE_API_TOKEN
    openai_api_key: str = OPENAI_API_KEY
    google_api_key: str = GOOGLE_API_KEY
    gdrive_output_folder_id: str = GDRIVE_OUTPUT_FOLDER_ID
    google_credentials_path: str = GOOGLE_CREDENTIALS_PATH

    request_delay: float = REQUEST_DELAY
    max_retries: int = MAX_RETRIES
    batch_concurrency: int = BATCH_CONCURRENCY
    variants_per_cover: int = VARIANTS_PER_COVER
    provider_request_delay: dict[str, float] = field(default_factory=lambda: PROVIDER_REQUEST_DELAY.copy())

    image_width: int = GEN_WIDTH
    image_height: int = GEN_HEIGHT
    image_output_format: str = GEN_OUTPUT_FORMAT

    min_quality_score: float = MIN_QUALITY_SCORE
    max_cost_usd: float = MAX_COST_USD

    model_provider_map: dict[str, str] = field(default_factory=lambda: MODEL_PROVIDER_MAP.copy())
    model_cost_usd: dict[str, float] = field(default_factory=lambda: MODEL_COST_USD.copy())

    failures_path: Path = FAILURES_PATH
    generation_plan_path: Path = GENERATION_PLAN_PATH

    book_scope_limit: int = BOOK_SCOPE_LIMIT
    max_export_variants: int = MAX_EXPORT_VARIANTS

    # Compatibility aliases
    input_covers_dir: Path = INPUT_DIR
    output_covers_dir: Path = OUTPUT_DIR
    cost_per_image_usd: float = MODEL_COST_USD.get(AI_MODEL, 0.04)

    @property
    def provider_keys(self) -> dict[str, str]:
        return {
            "openrouter": self.openrouter_api_key,
            "fal": self.fal_api_key,
            "replicate": self.replicate_api_token,
            "openai": self.openai_api_key,
            "google": self.google_api_key,
        }

    def has_any_api_key(self) -> bool:
        return any(bool(v.strip()) for v in self.provider_keys.values())

    def get_api_key(self, provider: str) -> str:
        return self.provider_keys.get(provider.lower(), "")

    def resolve_model_provider(self, model: str, default_provider: str | None = None) -> str:
        """Resolve provider for a model, supporting provider/model notation."""
        if "/" in model:
            prefix = model.split("/", 1)[0].strip().lower()
            if prefix in self.provider_keys:
                return prefix
        return self.model_provider_map.get(model, (default_provider or self.ai_provider).lower())

    def get_model_cost(self, model: str) -> float:
        normalized = model.split("/", 1)[-1] if "/" in model else model
        return float(self.model_cost_usd.get(normalized, self.model_cost_usd.get(model, 0.04)))


RuntimeConfig = Config


def get_config() -> Config:
    ensure_runtime_dirs()
    return Config()
