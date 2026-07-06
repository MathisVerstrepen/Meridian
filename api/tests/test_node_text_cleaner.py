import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from services.node import CleanTextOption, strip_thinking_blocks, text_cleaner


def test_strip_thinking_blocks_removes_provider_thinking_markers() -> None:
    title = "[THINK]\nChoosing a concise title\n[!THINK]\nArchitecture Refactor"

    assert strip_thinking_blocks(title) == "Architecture Refactor"


def test_strip_thinking_blocks_removes_xml_thinking_tags() -> None:
    title = "<thinking>Need a short summary</thinking> API Error Handling"

    assert strip_thinking_blocks(title) == "API Error Handling"


def test_text_cleaner_remove_tags_only_keeps_thinking_text() -> None:
    text = "<think>reasoning</think> Final answer"

    assert text_cleaner(text, CleanTextOption.REMOVE_TAGS_ONLY) == "reasoning Final answer"


def test_text_cleaner_remove_tag_and_text_removes_thinking_text() -> None:
    text = "[THINK]\nreasoning\n[!THINK]\nFinal answer"

    assert text_cleaner(text, CleanTextOption.REMOVE_TAG_AND_TEXT) == "Final answer"
