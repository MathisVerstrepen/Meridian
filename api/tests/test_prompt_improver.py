import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from database.pg.models import PromptImproverChange, PromptImproverChangeStatusEnum
from services.prompt_improver import TAXONOMY_DEFINITIONS, _build_diff_clusters, compose_prompt


def test_prompt_improver_taxonomy_contains_25_dimensions():
    assert len(TAXONOMY_DEFINITIONS) == 25


def test_build_diff_clusters_detects_insert_replace_and_delete():
    source = "Write a short summary.\nUse bullet points.\n"
    improved = "Write a concise summary.\nUse 3 bullet points.\nCite the source.\n"

    changes = _build_diff_clusters(source, improved)

    assert len(changes) >= 1
    assert any(
        "concise" in change["suggested_text"] and "summary" in change["suggested_text"]
        for change in changes
    )
    assert any("Cite the source." in change["suggested_text"] for change in changes)


def test_compose_prompt_uses_review_status_to_build_final_prompt():
    source = "Line one\nLine two\nLine three\n"
    changes = [
        PromptImproverChange(
            order_index=0,
            run_id="00000000-0000-0000-0000-000000000000",
            source_start=0,
            source_end=8,
            source_text="Line one",
            suggested_text="Better one",
            review_status=PromptImproverChangeStatusEnum.ACCEPTED,
        ),
        PromptImproverChange(
            order_index=1,
            run_id="00000000-0000-0000-0000-000000000000",
            source_start=18,
            source_end=28,
            source_text="Line three",
            suggested_text="Better three",
            review_status=PromptImproverChangeStatusEnum.REJECTED,
        ),
    ]

    result = compose_prompt(source, changes)

    assert result == "Better one\nLine two\nLine three\n"
