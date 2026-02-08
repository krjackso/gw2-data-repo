import json
import logging
import re
import subprocess
import sys
from pathlib import Path

import yaml

from gw2_data import wiki
from gw2_data.cache import CacheClient
from gw2_data.config import get_settings
from gw2_data.exceptions import ExtractionError

log = logging.getLogger(__name__)

INDEX_DIR = Path("data/index")
GATHERING_NODES_PATH = INDEX_DIR / "gathering_nodes.yaml"


def _parse_llm_response(text: str) -> dict:
    cleaned = text.strip()
    match = re.match(r"^```(?:json)?\s*\n?(.*?)\n?\s*```$", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(1).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ExtractionError(f"Failed to parse LLM response as JSON: {e}") from e


def _call_llm(system_prompt: str, user_prompt: str, model: str) -> dict:
    cmd = [
        "claude",
        "--print",
        "--output-format",
        "text",
        "--system-prompt",
        system_prompt,
        "--model",
        model,
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
            "claude CLI not found. "
            "Install Claude Code: https://docs.anthropic.com/en/docs/claude-code"
        )
    except subprocess.TimeoutExpired:
        raise ExtractionError("claude CLI timed out after 120 seconds")

    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        details = stderr or stdout or "(no output)"
        raise ExtractionError(f"claude CLI failed (exit {result.returncode}): {details}")

    return _parse_llm_response(result.stdout)


def build_gathering_index(cache: CacheClient) -> None:
    from prompts.extract_gathering_nodes import SYSTEM_PROMPT, build_user_prompt

    print("Fetching Gathering wiki page...")
    wiki_html = wiki.get_page_html("Gathering", cache=cache)

    if not wiki_html:
        print("ERROR: Failed to fetch Gathering wiki page", file=sys.stderr)
        sys.exit(1)

    settings = get_settings()
    model = settings.llm_model

    print(f"Extracting gathering node names via LLM (model={model})...")
    user_prompt = build_user_prompt(wiki_html)
    llm_output = _call_llm(SYSTEM_PROMPT, user_prompt, model)

    nodes = llm_output.get("nodes", [])
    if not nodes:
        print("WARNING: LLM returned no gathering nodes", file=sys.stderr)
        sys.exit(1)

    sorted_nodes = sorted(set(nodes))

    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    with GATHERING_NODES_PATH.open("w") as f:
        yaml.dump(sorted_nodes, f, allow_unicode=True, sort_keys=False)

    print(f"\nGathering node index written to {GATHERING_NODES_PATH}")
    print(f"  Total nodes indexed: {len(sorted_nodes)}")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )

    settings = get_settings()
    cache = CacheClient(settings.cache_dir)

    try:
        build_gathering_index(cache)
    except ExtractionError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
