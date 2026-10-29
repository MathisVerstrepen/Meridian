"""Extract one generated icon; never embed the model's surrounding text or markup."""

import re

from services.node import strip_thinking_blocks
from utils.svg_icon import MAX_SVG_LENGTH, normalize_svg_icon


def normalize_icon_output(response: str) -> str:
    text = strip_thinking_blocks(response).strip()
    if not text:
        raise ValueError("The model returned no SVG content.")
    if len(text) > MAX_SVG_LENGTH * 4:
        raise ValueError("The model output exceeded the icon size limit.")
    match = re.search(r"<svg(?=[\s>])[\s\S]*?</svg\s*>", text, re.IGNORECASE)
    if not match:
        raise ValueError("The model did not return a complete SVG element.")
    return normalize_svg_icon(match.group(0))
