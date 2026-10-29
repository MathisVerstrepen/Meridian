"""Normalize small SVG icons to a geometry-only, self-contained format."""

import math
import re
import xml.etree.ElementTree as ET

SVG_NS = "http://www.w3.org/2000/svg"
MAX_SVG_LENGTH = 24000
SHAPES = {"path", "circle", "ellipse", "rect", "line", "polyline", "polygon"}
TAGS = SHAPES | {"svg", "g", "title", "desc"}
NUMERIC = {
    "x",
    "y",
    "x1",
    "x2",
    "y1",
    "y2",
    "cx",
    "cy",
    "r",
    "rx",
    "ry",
    "width",
    "height",
    "stroke-width",
    "stroke-miterlimit",
}
OPACITY = {"opacity", "fill-opacity", "stroke-opacity"}
ENUMS = {
    "stroke-linecap": {"butt", "round", "square"},
    "stroke-linejoin": {"miter", "round", "bevel"},
    "fill-rule": {"nonzero", "evenodd"},
    "clip-rule": {"nonzero", "evenodd"},
    "vector-effect": {"none", "non-scaling-stroke"},
}
NUMBER = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")


def _number(value):
    if not NUMBER.fullmatch(value):
        raise ValueError("Invalid SVG number.")
    number = float(value)
    if not math.isfinite(number) or abs(number) > 4096:
        raise ValueError("SVG coordinates exceed the icon limits.")
    return number


def _numbers(value):
    parts = re.split(r"[\s,]+", value.strip())
    return [_number(part) for part in parts]


def _attribute(name, value):
    if name in NUMERIC:
        number = _number(value)
        if name in {"r", "rx", "ry", "width", "height", "stroke-width"} and number < 0:
            raise ValueError("SVG sizes must not be negative.")
    elif name in OPACITY:
        if not 0 <= _number(value) <= 1:
            raise ValueError("Invalid SVG opacity.")
    elif name in {"fill", "stroke"}:
        if value.lower() == "none":
            return "none"
        if value.lower() not in {"currentcolor", "black", "white"} and not re.fullmatch(
            r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})", value
        ):
            raise ValueError("SVG icons may only use solid colors.")
        return "currentColor"
    elif name in ENUMS:
        if value not in ENUMS[name]:
            raise ValueError("Invalid SVG stroke or fill rule.")
    elif name == "d":
        if (
            not value
            or len(value) > 12000
            or not re.fullmatch(r"[MmZzLlHhVvCcSsQqTtAa0-9eE+.,\s-]+", value)
        ):
            raise ValueError("Invalid SVG path.")
        for number in NUMBER.findall(value):
            _number(number)
    elif name == "points":
        numbers = _numbers(value)
        if len(numbers) < 4 or len(numbers) % 2:
            raise ValueError("Invalid SVG points.")
    elif name == "viewBox":
        numbers = _numbers(value)
        if len(numbers) != 4 or numbers[2] <= 0 or numbers[3] <= 0:
            raise ValueError("A valid SVG viewBox is required.")
    elif name == "transform":
        pattern = r"(?:(?:translate|scale|rotate|matrix|skewX|skewY)\([0-9eE+.,\s-]+\)\s*)+"
        if not re.fullmatch(pattern, value):
            raise ValueError("Invalid SVG transform.")
        for number in NUMBER.findall(value):
            _number(number)
    else:
        raise ValueError("SVG icons may only contain basic geometry attributes.")
    return value


def normalize_svg_icon(value: str) -> str:
    if len(value) > MAX_SVG_LENGTH or re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", value):
        raise ValueError("SVG icons must be small and contain no declarations.")
    # Comments and an XML prolog are harmless presentation scaffolding. Remove
    # them before parsing; declarations, entities and other processing instructions
    # remain forbidden, including UTF-16/NUL encodings rejected above.
    value = re.sub(r"<!--[\s\S]*?-->", "", value)
    value = re.sub(r"^\s*<\?xml\s+[^?]*\?>", "", value, flags=re.IGNORECASE)
    if "<!" in value or "<?" in value:
        raise ValueError("SVG icons cannot contain declarations or processing instructions.")
    try:
        root = ET.fromstring(value.strip())
    except ET.ParseError as exc:
        raise ValueError("Invalid SVG icon.") from exc
    pending = [(root, 0)]
    count = shapes = 0
    while pending:
        node, depth = pending.pop()
        count += 1
        tag = node.tag.removeprefix(f"{{{SVG_NS}}}")
        if tag not in TAGS or count > 128 or depth > 8 or (tag == "svg" and depth):
            raise ValueError("SVG icons may only contain a small set of basic shapes.")
        if depth == 0 and tag != "svg":
            raise ValueError("An SVG root is required.")
        if (
            node.text
            and node.text.strip()
            and (tag not in {"title", "desc"} or len(node.text) > 200)
        ):
            raise ValueError("SVG icons cannot contain visible text.")
        if node.tail and node.tail.strip():
            raise ValueError("Unexpected SVG text.")
        style = node.attrib.pop("style", "")
        for declaration in style.split(";"):
            if not declaration.strip():
                continue
            key, separator, text = declaration.partition(":")
            key = key.strip().lower()
            if not separator or key not in OPACITY | set(ENUMS) | {
                "fill",
                "stroke",
                "stroke-width",
                "stroke-miterlimit",
            }:
                raise ValueError("SVG styles may only set basic paint attributes.")
            node.set(key, _attribute(key, text.strip()))
        metadata = {
            "id",
            "class",
            "role",
            "aria-label",
            "aria-hidden",
            "focusable",
            "version",
            "preserveAspectRatio",
        }
        for name, text in list(node.attrib.items()):
            if name in metadata:
                del node.attrib[name]
            else:
                node.set(name, _attribute(name, text.strip()))
        node.tag = f"{{{SVG_NS}}}{tag}"
        shapes += tag in SHAPES
        pending.extend((child, depth + 1) for child in node)
    if not shapes or "viewBox" not in root.attrib:
        raise ValueError("An SVG icon needs a viewBox and at least one shape.")
    root.set("width", "24")
    root.set("height", "24")
    root.set("fill", root.get("fill", "currentColor"))
    ET.register_namespace("", SVG_NS)
    result = ET.tostring(root, encoding="unicode")
    if len(result) > MAX_SVG_LENGTH:
        raise ValueError("SVG icon is too large.")
    return result
