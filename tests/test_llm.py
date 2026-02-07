import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from gw2_data import llm
from gw2_data.cache import CacheClient
from gw2_data.exceptions import ExtractionError
from gw2_data.llm import ExtractionResult, _parse_llm_response, _strip_confidence_fields


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
            "acquisitions": [
                {
                    "type": "mystic_forge",
                    "confidence": 0.95,
                    "outputQuantity": 1,
                    "requirements": [
                        {"itemName": "Mystic Coin", "quantity": 1},
                        {"itemName": "Glob of Ectoplasm", "quantity": 1},
                    ],
                    "metadata": {"recipeType": "mystic_forge"},
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
        text = '{"acquisitions": [], "overallConfidence": 1.0}'
        result = _parse_llm_response(text)
        assert result == {"acquisitions": [], "overallConfidence": 1.0}

    def test_parses_json_with_code_fences(self):
        text = '```json\n{"acquisitions": [], "overallConfidence": 1.0}\n```'
        result = _parse_llm_response(text)
        assert result == {"acquisitions": [], "overallConfidence": 1.0}

    def test_parses_json_with_bare_code_fences(self):
        text = '```\n{"acquisitions": []}\n```'
        result = _parse_llm_response(text)
        assert result == {"acquisitions": []}

    def test_raises_on_invalid_json(self):
        with pytest.raises(ExtractionError, match="Failed to parse LLM response"):
            _parse_llm_response("not json at all")

    def test_handles_whitespace(self):
        text = '  \n  {"acquisitions": []}  \n  '
        result = _parse_llm_response(text)
        assert result == {"acquisitions": []}


class TestStripConfidenceFields:
    def test_strips_confidence_and_returns_values(self):
        acqs = [
            {"type": "vendor", "confidence": 0.9, "outputQuantity": 1},
            {"type": "crafting", "confidence": 0.7, "outputQuantity": 2},
        ]
        stripped, confidences = _strip_confidence_fields(acqs)
        assert confidences == [0.9, 0.7]
        assert all("confidence" not in a for a in stripped)
        assert stripped[0]["type"] == "vendor"
        assert stripped[1]["outputQuantity"] == 2

    def test_defaults_missing_confidence_to_zero(self):
        acqs = [{"type": "vendor", "outputQuantity": 1}]
        stripped, confidences = _strip_confidence_fields(acqs)
        assert confidences == [0.0]

    def test_does_not_mutate_original(self):
        acqs = [{"type": "vendor", "confidence": 0.9}]
        _strip_confidence_fields(acqs)
        assert "confidence" in acqs[0]


class TestExtractAcquisitions:
    def test_returns_extraction_result(self, mocker, cache_client, api_data, llm_response_json):
        _mock_claude_cli(mocker, llm_response_json)

        result = llm.extract_acquisitions(
            123, "Test Item", "<html>test</html>", api_data, cache=cache_client
        )

        assert isinstance(result, ExtractionResult)
        assert result.item_data["id"] == 123
        assert result.item_data["name"] == "Test Item"
        assert result.item_data["type"] == "Weapon"
        assert result.overall_confidence == 0.9
        assert result.acquisition_confidences == [0.95]
        assert result.notes == "Test note"

    def test_item_data_has_correct_fields(self, mocker, cache_client, api_data, llm_response_json):
        _mock_claude_cli(mocker, llm_response_json)

        result = llm.extract_acquisitions(
            123, "Test Item", "<html>test</html>", api_data, cache=cache_client
        )

        data = result.item_data
        assert data["rarity"] == "Exotic"
        assert data["level"] == 80
        assert data["wikiUrl"] == "https://wiki.guildwars2.com/wiki/Test_Item"
        assert "lastUpdated" in data
        assert len(data["acquisitions"]) == 1
        assert data["acquisitions"][0]["type"] == "mystic_forge"
        assert "confidence" not in data["acquisitions"][0]

    def test_uses_current_date(self, mocker, cache_client, api_data, llm_response_json):
        _mock_claude_cli(mocker, llm_response_json)

        result = llm.extract_acquisitions(
            123, "Test Item", "<html>test</html>", api_data, cache=cache_client
        )

        expected_date = datetime.now(UTC).date().isoformat()
        assert result.item_data["lastUpdated"] == expected_date

    def test_caches_result(self, mocker, cache_client, api_data, llm_response_json):
        mock_run = _mock_claude_cli(mocker, llm_response_json)

        result1 = llm.extract_acquisitions(
            123, "Test Item", "<html>test</html>", api_data, cache=cache_client
        )
        result2 = llm.extract_acquisitions(
            123, "Test Item", "<html>test</html>", api_data, cache=cache_client
        )

        assert result1.item_data == result2.item_data
        assert result1.overall_confidence == result2.overall_confidence
        assert mock_run.call_count == 1

    def test_different_content_different_cache(self, mocker, api_data, llm_response_json):
        _mock_claude_cli(mocker, llm_response_json)

        mock_cache = MagicMock()
        mock_cache.get_llm_extraction.return_value = None

        llm.extract_acquisitions(
            123, "Test Item", "<html>Version 1</html>", api_data, cache=mock_cache
        )
        llm.extract_acquisitions(
            123, "Test Item", "<html>Version 2</html>", api_data, cache=mock_cache
        )

        assert mock_cache.set_llm_extraction.call_count == 2
        call1_hash = mock_cache.set_llm_extraction.call_args_list[0][0][2]
        call2_hash = mock_cache.set_llm_extraction.call_args_list[1][0][2]
        assert call1_hash != call2_hash

    def test_wiki_url_handles_spaces(self, mocker, cache_client, llm_response_json):
        _mock_claude_cli(mocker, llm_response_json)
        api_data = {
            "id": 123,
            "name": "Test Item With Spaces",
            "type": "Weapon",
            "rarity": "Exotic",
            "level": 80,
        }

        result = llm.extract_acquisitions(
            123, "Test Item With Spaces", "<html>test</html>", api_data, cache=cache_client
        )

        assert (
            result.item_data["wikiUrl"] == "https://wiki.guildwars2.com/wiki/Test_Item_With_Spaces"
        )

    def test_passes_model_override(self, mocker, cache_client, api_data, llm_response_json):
        mock_run = _mock_claude_cli(mocker, llm_response_json)

        llm.extract_acquisitions(
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

        llm.extract_acquisitions(
            123, "Test Item", "<html>test</html>", api_data, cache=cache_client, model="haiku"
        )
        llm.extract_acquisitions(
            123, "Test Item", "<html>test</html>", api_data, cache=cache_client, model="sonnet"
        )

        assert mock_run.call_count == 2

    def test_same_model_uses_cache(self, mocker, cache_client, api_data, llm_response_json):
        mock_run = _mock_claude_cli(mocker, llm_response_json)

        llm.extract_acquisitions(
            123, "Test Item", "<html>test</html>", api_data, cache=cache_client, model="haiku"
        )
        llm.extract_acquisitions(
            123, "Test Item", "<html>test</html>", api_data, cache=cache_client, model="haiku"
        )

        assert mock_run.call_count == 1

    def test_empty_acquisitions(self, mocker, cache_client, api_data):
        empty_response = json.dumps(
            {
                "acquisitions": [],
                "overallConfidence": 1.0,
            }
        )
        _mock_claude_cli(mocker, empty_response)

        result = llm.extract_acquisitions(
            123, "Test Item", "<html>test</html>", api_data, cache=cache_client
        )

        assert result.item_data["acquisitions"] == []
        assert result.overall_confidence == 1.0
        assert result.acquisition_confidences == []
        assert result.notes is None

    def test_raises_on_bad_llm_response(self, mocker, cache_client, api_data):
        _mock_claude_cli(mocker, "not valid json")

        with pytest.raises(ExtractionError, match="Failed to parse LLM response"):
            llm.extract_acquisitions(
                123, "Test Item", "<html>test</html>", api_data, cache=cache_client
            )

    def test_raises_on_cli_failure(self, mocker, cache_client, api_data):
        _mock_claude_cli(mocker, "", returncode=1, stderr="auth error")

        with pytest.raises(ExtractionError, match="claude CLI failed"):
            llm.extract_acquisitions(
                123, "Test Item", "<html>test</html>", api_data, cache=cache_client
            )

    def test_raises_on_cli_not_found(self, mocker, cache_client, api_data):
        mocker.patch(
            "gw2_data.llm.subprocess.run",
            side_effect=FileNotFoundError(),
        )

        with pytest.raises(ExtractionError, match="claude CLI not found"):
            llm.extract_acquisitions(
                123, "Test Item", "<html>test</html>", api_data, cache=cache_client
            )

    def test_raises_on_timeout(self, mocker, cache_client, api_data):
        mocker.patch(
            "gw2_data.llm.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=120),
        )

        with pytest.raises(ExtractionError, match="timed out"):
            llm.extract_acquisitions(
                123, "Test Item", "<html>test</html>", api_data, cache=cache_client
            )

    def test_pipes_prompt_via_stdin(self, mocker, cache_client, api_data, llm_response_json):
        mock_run = _mock_claude_cli(mocker, llm_response_json)

        llm.extract_acquisitions(
            123, "Test Item", "<html>test</html>", api_data, cache=cache_client
        )

        call_kwargs = mock_run.call_args[1]
        assert "input" in call_kwargs
        assert "<html>test</html>" in call_kwargs["input"]
        cmd = mock_run.call_args[0][0]
        assert cmd[-1] == "-"

    def test_prompt_change_busts_cache(self, mocker, cache_client, api_data, llm_response_json):
        mock_run = _mock_claude_cli(mocker, llm_response_json)

        llm.extract_acquisitions(
            123, "Test Item", "<html>test</html>", api_data, cache=cache_client
        )
        assert mock_run.call_count == 1

        original_hash = llm._PROMPT_HASH
        mocker.patch.object(llm, "_PROMPT_HASH", "different_prompt_hash")

        llm.extract_acquisitions(
            123, "Test Item", "<html>test</html>", api_data, cache=cache_client
        )
        assert mock_run.call_count == 2

        mocker.patch.object(llm, "_PROMPT_HASH", original_hash)
