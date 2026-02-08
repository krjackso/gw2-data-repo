import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from gw2_data import llm
from gw2_data.cache import CacheClient
from gw2_data.exceptions import ExtractionError
from gw2_data.llm import ExtractionResult, _parse_llm_response


@pytest.fixture
def cache_client(tmp_path: Path) -> CacheClient:
    return CacheClient(tmp_path / "test_cache")


@pytest.fixture
def api_data() -> dict:
    return {
        "id": 123,
        "name": "Test Item",
        "type": "Weapon",
        "rarity": "Exotic",
        "level": 80,
    }


@pytest.fixture
def llm_response_json() -> str:
    return json.dumps(
        {
            "entries": [
                {
                    "name": "Test Item",
                    "wikiSection": "recipe",
                    "wikiSubsection": "mystic_forge",
                    "confidence": 0.95,
                    "quantity": 1,
                    "ingredients": [
                        {"name": "Mystic Coin", "quantity": 1},
                        {"name": "Glob of Ectoplasm", "quantity": 1},
                    ],
                    "metadata": {},
                }
            ],
            "overallConfidence": 0.9,
            "notes": "Test note",
        }
    )


def _mock_claude_cli(mocker, stdout: str, returncode: int = 0, stderr: str = "") -> MagicMock:
    mock_result = MagicMock(spec=subprocess.CompletedProcess)
    mock_result.stdout = stdout
    mock_result.stderr = stderr
    mock_result.returncode = returncode

    mock_run = mocker.patch("gw2_data.llm.subprocess.run", return_value=mock_result)
    return mock_run


class TestParseLlmResponse:
    def test_parses_plain_json(self):
        text = '{"entries": [], "overallConfidence": 1.0}'
        result = _parse_llm_response(text)
        assert result == {"entries": [], "overallConfidence": 1.0}

    def test_parses_json_with_code_fences(self):
        text = '```json\n{"entries": [], "overallConfidence": 1.0}\n```'
        result = _parse_llm_response(text)
        assert result == {"entries": [], "overallConfidence": 1.0}

    def test_parses_json_with_bare_code_fences(self):
        text = '```\n{"entries": []}\n```'
        result = _parse_llm_response(text)
        assert result == {"entries": []}

    def test_raises_on_invalid_json(self):
        with pytest.raises(ExtractionError, match="Failed to parse LLM response"):
            _parse_llm_response("not json at all")

    def test_handles_whitespace(self):
        text = '  \n  {"entries": []}  \n  '
        result = _parse_llm_response(text)
        assert result == {"entries": []}


class TestExtractEntries:
    def test_returns_extraction_result(self, mocker, cache_client, api_data, llm_response_json):
        _mock_claude_cli(mocker, llm_response_json)

        result = llm.extract_entries(
            123, "Test Item", "<html>test</html>", api_data, cache=cache_client
        )

        assert isinstance(result, ExtractionResult)
        assert len(result.entries) == 1
        assert result.entries[0]["wikiSection"] == "recipe"
        assert result.overall_confidence == 0.9
        assert result.entry_confidences == [0.95]
        assert result.notes == "Test note"

    def test_entries_have_correct_fields(self, mocker, cache_client, api_data, llm_response_json):
        _mock_claude_cli(mocker, llm_response_json)

        result = llm.extract_entries(
            123, "Test Item", "<html>test</html>", api_data, cache=cache_client
        )

        assert len(result.entries) == 1
        assert result.entries[0]["wikiSection"] == "recipe"
        assert result.entries[0]["confidence"] == 0.95

    def test_caches_result(self, mocker, cache_client, api_data, llm_response_json):
        mock_run = _mock_claude_cli(mocker, llm_response_json)

        result1 = llm.extract_entries(
            123, "Test Item", "<html>test</html>", api_data, cache=cache_client
        )
        result2 = llm.extract_entries(
            123, "Test Item", "<html>test</html>", api_data, cache=cache_client
        )

        assert result1.entries == result2.entries
        assert result1.overall_confidence == result2.overall_confidence
        assert mock_run.call_count == 1

    def test_different_content_different_cache(self, mocker, api_data, llm_response_json):
        _mock_claude_cli(mocker, llm_response_json)

        mock_cache = MagicMock()
        mock_cache.get_llm_extraction.return_value = None

        llm.extract_entries(123, "Test Item", "<html>Version 1</html>", api_data, cache=mock_cache)
        llm.extract_entries(123, "Test Item", "<html>Version 2</html>", api_data, cache=mock_cache)

        assert mock_cache.set_llm_extraction.call_count == 2
        call1_hash = mock_cache.set_llm_extraction.call_args_list[0][0][2]
        call2_hash = mock_cache.set_llm_extraction.call_args_list[1][0][2]
        assert call1_hash != call2_hash

    def test_passes_model_override(self, mocker, cache_client, api_data, llm_response_json):
        mock_run = _mock_claude_cli(mocker, llm_response_json)

        llm.extract_entries(
            123,
            "Test Item",
            "<html>test</html>",
            api_data,
            cache=cache_client,
            model="sonnet",
        )

        cmd = mock_run.call_args[0][0]
        model_idx = cmd.index("--model")
        assert cmd[model_idx + 1] == "sonnet"

    def test_different_models_use_different_cache(
        self, mocker, cache_client, api_data, llm_response_json
    ):
        mock_run = _mock_claude_cli(mocker, llm_response_json)

        llm.extract_entries(
            123, "Test Item", "<html>test</html>", api_data, cache=cache_client, model="haiku"
        )
        llm.extract_entries(
            123, "Test Item", "<html>test</html>", api_data, cache=cache_client, model="sonnet"
        )

        assert mock_run.call_count == 2

    def test_same_model_uses_cache(self, mocker, cache_client, api_data, llm_response_json):
        mock_run = _mock_claude_cli(mocker, llm_response_json)

        llm.extract_entries(
            123, "Test Item", "<html>test</html>", api_data, cache=cache_client, model="haiku"
        )
        llm.extract_entries(
            123, "Test Item", "<html>test</html>", api_data, cache=cache_client, model="haiku"
        )

        assert mock_run.call_count == 1

    def test_empty_entries(self, mocker, cache_client, api_data):
        empty_response = json.dumps(
            {
                "entries": [],
                "overallConfidence": 1.0,
            }
        )
        _mock_claude_cli(mocker, empty_response)

        result = llm.extract_entries(
            123, "Test Item", "<html>test</html>", api_data, cache=cache_client
        )

        assert result.entries == []
        assert result.overall_confidence == 1.0
        assert result.entry_confidences == []
        assert result.notes is None

    def test_raises_on_bad_llm_response(self, mocker, cache_client, api_data):
        _mock_claude_cli(mocker, "not valid json")

        with pytest.raises(ExtractionError, match="Failed to parse LLM response"):
            llm.extract_entries(123, "Test Item", "<html>test</html>", api_data, cache=cache_client)

    def test_raises_on_cli_failure(self, mocker, cache_client, api_data):
        _mock_claude_cli(mocker, "", returncode=1, stderr="auth error")

        with pytest.raises(ExtractionError, match="claude CLI failed"):
            llm.extract_entries(123, "Test Item", "<html>test</html>", api_data, cache=cache_client)

    def test_raises_on_cli_not_found(self, mocker, cache_client, api_data):
        mocker.patch(
            "gw2_data.llm.subprocess.run",
            side_effect=FileNotFoundError(),
        )

        with pytest.raises(ExtractionError, match="claude CLI not found"):
            llm.extract_entries(123, "Test Item", "<html>test</html>", api_data, cache=cache_client)

    def test_raises_on_timeout(self, mocker, cache_client, api_data):
        mocker.patch(
            "gw2_data.llm.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=120),
        )

        with pytest.raises(ExtractionError, match="timed out"):
            llm.extract_entries(123, "Test Item", "<html>test</html>", api_data, cache=cache_client)

    def test_pipes_prompt_via_stdin(self, mocker, cache_client, api_data, llm_response_json):
        mock_run = _mock_claude_cli(mocker, llm_response_json)

        llm.extract_entries(123, "Test Item", "<html>test</html>", api_data, cache=cache_client)

        call_kwargs = mock_run.call_args[1]
        assert "input" in call_kwargs
        assert "<html>test</html>" in call_kwargs["input"]
        cmd = mock_run.call_args[0][0]
        assert cmd[-1] == "-"

    def test_model_sets_html_limit(self, mocker, cache_client, api_data, llm_response_json):
        _mock_claude_cli(mocker, llm_response_json)
        mock_extract = mocker.patch(
            "gw2_data.llm.wiki.extract_acquisition_sections",
            return_value="<html>small</html>",
        )
        mocker.patch("gw2_data.llm.wiki.get_html_limit_for_model", return_value=600_000)

        llm.extract_entries(
            123, "Test Item", "<html>test</html>", api_data, cache=cache_client, model="sonnet"
        )

        mock_extract.assert_called_once_with("<html>test</html>", max_length=600_000)

    def test_prompt_change_busts_cache(self, mocker, cache_client, api_data, llm_response_json):
        mock_run = _mock_claude_cli(mocker, llm_response_json)

        llm.extract_entries(123, "Test Item", "<html>test</html>", api_data, cache=cache_client)
        assert mock_run.call_count == 1

        original_hash = llm._PROMPT_HASH
        mocker.patch.object(llm, "_PROMPT_HASH", "different_prompt_hash")

        llm.extract_entries(123, "Test Item", "<html>test</html>", api_data, cache=cache_client)
        assert mock_run.call_count == 2

        mocker.patch.object(llm, "_PROMPT_HASH", original_hash)
