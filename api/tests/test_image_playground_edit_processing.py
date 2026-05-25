import base64
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from PIL import Image

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from schemas.images import ImageEditSelectionPayload
from services.image_playground import edit_processing
from services.image_playground.edit_processing import (
    analyze_image_edit_mask,
    build_image_edit_instruction,
    build_image_edit_prompt,
    classify_image_edit_intent,
    composite_image_edit_result,
    format_image_edit_mask_margins,
    get_padded_edit_crop,
    image_bytes_as_data_uri,
    normalize_image_edit_selection,
    resize_image_to_cover,
)


def _selection(x: int, y: int, width: int, height: int) -> ImageEditSelectionPayload:
    return ImageEditSelectionPayload(x=x, y=y, width=width, height=height)


def test_image_bytes_as_data_uri_encodes_png_payload():
    image = Image.new("RGB", (2, 2), "red")

    data_uri = image_bytes_as_data_uri(image)

    prefix, encoded = data_uri.split(",", 1)
    assert prefix == "data:image/png;base64"
    assert base64.b64decode(encoded).startswith(b"\x89PNG")


def test_normalize_image_edit_selection_clamps_inside_image_bounds():
    selection = _selection(80, 70, 50, 40)

    assert normalize_image_edit_selection(selection, 100, 90) == (80, 70, 100, 90)


def test_normalize_image_edit_selection_rejects_outside_selection():
    with pytest.raises(HTTPException) as exc_info:
        normalize_image_edit_selection(_selection(120, 20, 10, 10), 100, 90)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Edit selection is outside the image."


def test_get_padded_edit_crop_uses_only_configured_padding_and_exact_mask():
    image = Image.new("RGB", (100, 80), "white")

    cropped_image, cropped_mask, crop_box, selection_box = get_padded_edit_crop(
        image,
        _selection(20, 10, 40, 20),
        padding_pct=0.25,
    )

    assert crop_box == (10, 5, 70, 35)
    assert selection_box == (20, 10, 60, 30)
    assert cropped_image.size == (60, 30)
    assert cropped_mask.getbbox() == (10, 5, 50, 25)


def test_analyze_image_edit_mask_reports_per_edge_margins():
    mask = Image.new("L", (100, 100), 0)
    mask.paste(255, (10, 20, 90, 100))

    analysis = analyze_image_edit_mask(mask)

    assert analysis.left_margin_pct == pytest.approx(0.10)
    assert analysis.top_margin_pct == pytest.approx(0.20)
    assert analysis.right_margin_pct == pytest.approx(0.10)
    assert analysis.bottom_margin_pct == pytest.approx(0.0)
    assert analysis.min_margin_pct == pytest.approx(0.0)
    assert analysis.margin_pct == pytest.approx(0.10)
    assert not analysis.is_central
    assert format_image_edit_mask_margins(analysis) == "left 10%, top 20%, right 10%, bottom 0%"


def test_classify_image_edit_intent_prefers_specific_prompt_verbs():
    assert classify_image_edit_intent("") == "remove"
    assert classify_image_edit_intent("erase the lamp") == "remove"
    assert classify_image_edit_intent("add a vase") == "add"
    assert classify_image_edit_intent("make it look watercolor") == "style_transfer"
    assert classify_image_edit_intent("replace the chair") == "replace"


def test_build_image_edit_instruction_uses_safe_default_remove_prompt():
    instruction = build_image_edit_instruction("", "remove")

    assert "remove the selected subject" in instruction
    assert "Do not introduce any new objects" in instruction


def test_build_image_edit_prompt_includes_asymmetric_margin_guidance():
    crop = Image.new("RGB", (100, 100), "white")
    mask = Image.new("L", (100, 100), 0)
    mask.paste(255, (10, 20, 90, 100))

    prompt = build_image_edit_prompt(
        user_prompt="remove the plant",
        model="google/gemini-3.1-pro-image",
        cropped_image=crop,
        cropped_mask=mask,
    )

    assert "TASK: Edit only the selected region" in prompt
    assert "asymmetric context margins" in prompt
    assert "left 10%, top 20%, right 10%, bottom 0%" in prompt
    assert "remove remove the plant" in prompt


def test_resize_image_to_cover_preserves_target_size_without_distortion_requirement():
    image = Image.new("RGB", (80, 40), "blue")

    resized = resize_image_to_cover(image, (40, 40))

    assert resized.size == (40, 40)


def test_composite_image_edit_result_falls_back_to_feathered_mask(monkeypatch):
    original = Image.new("RGB", (10, 10), "black")
    edited_crop = Image.new("RGB", (4, 4), "white")
    mask = Image.new("L", (4, 4), 0)
    mask.paste(255, (1, 1, 3, 3))

    monkeypatch.setattr(
        edit_processing, "align_edited_crop_to_original_crop", lambda *args: args[1]
    )
    monkeypatch.setattr(edit_processing, "color_transfer_image_edit_crop", lambda *args: args[1])
    monkeypatch.setattr(
        edit_processing,
        "laplacian_composite_image_edit_result",
        lambda *args: (_ for _ in ()).throw(RuntimeError("force fallback")),
    )

    result = composite_image_edit_result(original, edited_crop, mask, (3, 3, 7, 7))

    assert result.size == original.size
    assert result.getpixel((0, 0)) == (0, 0, 0)
    assert result.getpixel((5, 5)) != (0, 0, 0)
