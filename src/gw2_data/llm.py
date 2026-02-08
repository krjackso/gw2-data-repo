import hashlib
import json
import logging
import re
import subprocess
from dataclasses import dataclass

from gw2_data import wiki
from gw2_data.cache import CacheClient
from gw2_data.config import get_settings
from gw2_data.exceptions import ExtractionError
from gw2_data.types import GW2Item
from prompts.extract_acquisitions import SYSTEM_PROMPT, build_user_prompt

log = logging.getLogger(__name__)

_CONTENT_HASH_LENGTH = 16
_PROMPT_HASH = hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()[:_CONTENT_HASH_LENGTH]


@dataclass
class ExtractionResult:
    entries: list[dict]
    overall_confidence: float
    entry_confidences: list[float]
    notes: str | None


def _parse_llm_response(text: str) -> dict:
    cleaned = text.strip()
    match = re.match(r"^```(?:json)?\s*\n?(.*?)\n?\s*```$", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(1).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ExtractionError(f"Failed to parse LLM response as JSON: {e}") from e


def _call_llm(
    item_id: int,
    item_name: str,
    item_type: str,
    rarity: str,
    wiki_html: str,
    model: str | None = None,
) -> dict:
    settings = get_settings()

    user_prompt = build_user_prompt(
        item_id=item_id,
        name=item_name,
        item_type=item_type,
        rarity=rarity,
        wiki_html=wiki_html,
    )

    cmd = [
        "claude",
        "--print",
        "--output-format",
        "text",
        "--system-prompt",
        SYSTEM_PROMPT,
        "--model",
        model or settings.llm_model,
        "--no-session-persistence",
        "-",
    ]

    try:
        result = subprocess.run(
            cmd,
            input=user_prompt,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            cwd="/tmp",
        )
    except FileNotFoundError:
        raise ExtractionError(
            "claude CLI not found. Install Claude Code: https://docs.anthropic.com/en/docs/claude-code"
        )
    except subprocess.TimeoutExpired:
        raise ExtractionError("claude CLI timed out after 120 seconds")

    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        details = stderr or stdout or "(no output)"
        raise ExtractionError(f"claude CLI failed (exit {result.returncode}): {details}")

    return _parse_llm_response(result.stdout)


def extract_entries(
    item_id: int,
    item_name: str,
    wiki_html: str,
    api_data: GW2Item,
    cache: CacheClient,
    model: str | None = None,
) -> ExtractionResult:
    settings = get_settings()
    effective_model = model or settings.llm_model

    html_limit = wiki.get_html_limit_for_model(effective_model)
    processed_html = wiki.extract_acquisition_sections(wiki_html, max_length=html_limit)

    content_hash = hashlib.sha256(processed_html.encode()).hexdigest()[:_CONTENT_HASH_LENGTH]
    cache_hash = f"{_PROMPT_HASH}:{content_hash}"
    rarity = api_data["rarity"]

    cached = cache.get_llm_extraction(item_id, item_name, cache_hash, effective_model, rarity)
    if cached is not None:
        log.info(
            "LLM extraction for '%s': using cached result (model=%s)", item_name, effective_model
        )
        return ExtractionResult(
            entries=cached["entries"],
            overall_confidence=cached["overall_confidence"],
            entry_confidences=cached["entry_confidences"],
            notes=cached["notes"],
        )

    log.info("LLM extraction for '%s': calling claude CLI (model=%s)", item_name, effective_model)
    llm_output = _call_llm(
        item_id=item_id,
        item_name=item_name,
        item_type=api_data["type"],
        rarity=api_data["rarity"],
        wiki_html=processed_html,
        model=effective_model,
    )

    entries = llm_output.get("entries", [])
    overall_confidence = llm_output.get("overallConfidence", 0.0)
    notes = llm_output.get("notes")

    entry_confidences = [e.get("confidence", 0.0) for e in entries]

    cache_entry = {
        "entries": entries,
        "overall_confidence": overall_confidence,
        "entry_confidences": entry_confidences,
        "notes": notes,
    }
    cache.set_llm_extraction(item_id, item_name, cache_hash, effective_model, rarity, cache_entry)

    return ExtractionResult(
        entries=entries,
        overall_confidence=overall_confidence,
        entry_confidences=entry_confidences,
        notes=notes,
    )
