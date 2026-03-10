#!/usr/bin/env python3
"""Validate Alexandria prompt templates and resolved prompt relevance at catalog scale."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import quality_review as qr  # noqa: E402
from src.prompt_library import PromptLibrary  # noqa: E402


DEFAULT_PROMPT_LIBRARY = PROJECT_ROOT / "config/prompt_library.json"
DEFAULT_BOOKS = PROJECT_ROOT / "config/book_catalog_enriched.json"
REQUIRED_TEMPLATE_TOKENS = (
    "book cover illustration only",
    "this circular medallion illustration must depict",
    "the mood is {mood}. era reference: {era}.",
    "circular vignette composition with soft edges. square format, high resolution, print-ready.",
)
GENERIC_CONTENT_MARKERS = (
    "iconic turning point",
    "central protagonist",
    "atmospheric setting moment",
    "defining confrontation involving",
    "historically grounded era",
    "circular medallion-ready",
    "pivotal narrative tableau",
    "{title}",
    "{author}",
    "{scene}",
    "{mood}",
    "{era}",
)


@dataclass
class ValidationIssue:
    kind: str
    prompt_id: str
    prompt_name: str
    book_number: int = 0
    book_title: str = ""
    variant_index: int = 0
    details: list[str] | None = None


def _load_books(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        rows = payload.get("rows", payload.get("books", []))
    else:
        rows = payload
    return [row for row in rows if isinstance(row, dict)]


def _alexandria_prompts(path: Path) -> list[Any]:
    library = PromptLibrary(path)
    prompts = []
    for prompt in library.get_prompts():
        tags = {str(tag or "").strip().lower() for tag in (prompt.tags or [])}
        if "alexandria" not in tags:
            continue
        if str(prompt.category or "").strip().lower() not in {"builtin", "wildcard"}:
            continue
        prompts.append(prompt)
    return prompts


def _template_issues(prompt: Any) -> list[str]:
    text = " ".join(str(getattr(prompt, "prompt_template", "") or "").lower().split()).strip()
    issues: list[str] = []
    if not text:
        return ["missing prompt template"]
    for token in REQUIRED_TEMPLATE_TOKENS:
        if token not in text:
            issues.append(f"missing required template fragment: {token}")
    for placeholder in ("{scene}", "{mood}", "{era}"):
        if placeholder not in text:
            issues.append(f"missing placeholder: {placeholder.upper()}")
    scene_index = text.find("{scene}")
    if scene_index < 0:
        issues.append("missing {SCENE} placeholder")
    elif scene_index > 250:
        issues.append(f"{{SCENE}} appears too late at char {scene_index}")
    return issues


def _scene_variant_count(book: dict[str, Any], *, max_scene_variants: int) -> int:
    enrichment = book.get("enrichment", {}) if isinstance(book.get("enrichment"), dict) else {}
    scene_count = len(qr._filtered_enrichment_scenes(enrichment))
    return max(1, min(max_scene_variants, scene_count or 1))


def _book_variant_contexts(book: dict[str, Any], *, max_scene_variants: int) -> list[dict[str, str]]:
    contexts: list[dict[str, str]] = []
    for variant_index in range(_scene_variant_count(book, max_scene_variants=max_scene_variants)):
        replacements = qr._alexandria_placeholder_replacements(book, variant_index=variant_index)
        contexts.append(
            {
                "scene": str(replacements.get("SCENE", "") or "").strip(),
                "mood": str(replacements.get("MOOD", "") or "").strip(),
                "era": str(replacements.get("ERA", "") or "").strip(),
            }
        )
    return contexts or [{"scene": "", "mood": "", "era": ""}]


def _resolve_prompt(prompt_template: str, context: dict[str, str]) -> str:
    return (
        str(prompt_template or "")
        .replace("{SCENE}", str(context.get("scene", "") or ""))
        .replace("{MOOD}", str(context.get("mood", "") or ""))
        .replace("{ERA}", str(context.get("era", "") or ""))
        .strip()
    )


def _resolved_prompt_warnings(prompt: str) -> list[str]:
    text = str(prompt or "").strip()
    lowered = text.lower()
    warnings: list[str] = []
    if not text:
        return ["Prompt is empty"]
    for placeholder in ("{SCENE}", "{MOOD}", "{ERA}", "{title}", "{author}"):
        if placeholder.lower() in lowered:
            warnings.append(f"Unresolved placeholder: {placeholder}")
    first_300 = lowered[:300]
    generic_marker = next((marker for marker in GENERIC_CONTENT_MARKERS if marker in first_300), "")
    if generic_marker:
        warnings.append(f"Generic content: '{generic_marker}'")
    if not any(needle in first_300 for needle in ("scene:", "must depict", "illustration must")):
        warnings.append("Scene content does not appear in first 300 characters")
    if len(text) < 200:
        warnings.append(f"Prompt too short ({len(text)} chars)")
    return warnings


def validate_catalog(
    *,
    prompt_library_path: Path,
    books_path: Path,
    max_scene_variants: int,
    sample_limit: int,
) -> tuple[dict[str, Any], list[ValidationIssue]]:
    prompts = _alexandria_prompts(prompt_library_path)
    books = _load_books(books_path)
    issues: list[ValidationIssue] = []
    resolved_samples: list[dict[str, Any]] = []
    total_combinations = 0

    for prompt in prompts:
        template_issues = _template_issues(prompt)
        if template_issues:
            issues.append(
                ValidationIssue(
                    kind="template",
                    prompt_id=str(prompt.id),
                    prompt_name=str(prompt.name),
                    details=template_issues,
                )
            )

    for book in books:
        contexts = _book_variant_contexts(book, max_scene_variants=max_scene_variants)
        for prompt in prompts:
            for variant_index, context in enumerate(contexts):
                total_combinations += 1
                resolved = _resolve_prompt(
                    str(prompt.prompt_template or ""),
                    context,
                )
                warnings = _resolved_prompt_warnings(resolved)
                if len(resolved_samples) < sample_limit:
                    resolved_samples.append(
                        {
                            "book_number": int(book.get("number", 0) or 0),
                            "book_title": str(book.get("title", "") or ""),
                            "prompt_id": str(prompt.id),
                            "prompt_name": str(prompt.name),
                            "variant_index": variant_index,
                            "prompt_preview": resolved[:400],
                        }
                    )
                if warnings:
                    issues.append(
                        ValidationIssue(
                            kind="resolved_prompt",
                            prompt_id=str(prompt.id),
                            prompt_name=str(prompt.name),
                            book_number=int(book.get("number", 0) or 0),
                            book_title=str(book.get("title", "") or ""),
                            variant_index=variant_index,
                            details=warnings,
                        )
                    )

    summary = {
        "ok": not issues,
        "books": len(books),
        "alexandria_prompts": len(prompts),
        "prompt_templates_checked": len(prompts),
        "resolved_prompt_combinations_checked": total_combinations,
        "issues": len(issues),
        "samples": resolved_samples,
    }
    return summary, issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Alexandria prompt relevance at catalog scale")
    parser.add_argument("--prompt-library", type=Path, default=DEFAULT_PROMPT_LIBRARY)
    parser.add_argument("--books", type=Path, default=DEFAULT_BOOKS)
    parser.add_argument("--max-scene-variants", type=int, default=5)
    parser.add_argument("--sample-limit", type=int, default=12)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    logging.getLogger("scripts.quality_review").setLevel(logging.ERROR)
    logging.getLogger("pikepdf").setLevel(logging.ERROR)

    started = time.time()
    summary, issues = validate_catalog(
        prompt_library_path=args.prompt_library,
        books_path=args.books,
        max_scene_variants=max(1, int(args.max_scene_variants or 1)),
        sample_limit=max(1, int(args.sample_limit or 1)),
    )
    summary["duration_seconds"] = round(time.time() - started, 3)
    summary["issue_samples"] = [asdict(issue) for issue in issues[:40]]

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    if issues:
        print(
            "FAILED — "
            f"{summary['issues']} issues across {summary['resolved_prompt_combinations_checked']} resolved prompts "
            f"({summary['alexandria_prompts']} Alexandria templates, {summary['books']} books)."
        )
        for issue in issues[:20]:
            book_ref = f" book={issue.book_number} {issue.book_title!r}" if issue.book_number else ""
            print(f"  x {issue.kind} prompt={issue.prompt_id}{book_ref}: {', '.join(issue.details or [])}")
        if len(issues) > 20:
            print(f"  ... {len(issues) - 20} more")
        return 1

    print(
        "PASSED — "
        f"{summary['alexandria_prompts']} Alexandria prompts validated across "
        f"{summary['books']} books and {summary['resolved_prompt_combinations_checked']} resolved prompts."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
