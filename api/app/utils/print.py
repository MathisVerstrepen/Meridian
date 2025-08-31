from models.message import MessageContentTypeEnum
from rich import print as rprint


def _trunc(s: str | None, n: int = 100) -> str | None:
    if s is None:
        return None
    s = str(s)
    return s if len(s) <= n else s[:n] + "..."


def pydantic_print(model):
    printable = []
    for m in model:
        msg_repr = {
            "role": getattr(m, "role", None),
            "node_id": getattr(m, "node_id", None),
            "type": getattr(m, "type", None),
            "content": [],
        }

        for c in getattr(m, "content", []) or []:
            c_type = getattr(c, "type", None)
            if c_type == MessageContentTypeEnum.text or str(c_type) == str(
                MessageContentTypeEnum.text
            ):
                msg_repr["content"].append(
                    {"type": c_type, "text": _trunc(getattr(c, "text", None), 100)}
                )
            else:
                # Collect string-like attributes and truncate them
                attrs = {}
                for attr in (
                    "fileId",
                    "file_id",
                    "name",
                    "url",
                    "id",
                    "text",
                    "content",
                ):
                    val = getattr(c, attr, None)
                    if val is not None:
                        attrs[attr] = _trunc(val, 100)
                # Fallback: if no known attrs found, include repr truncated
                if not attrs:
                    attrs["repr"] = _trunc(repr(c), 100)
                attrs["type"] = c_type
                msg_repr["content"].append(attrs)

        printable.append(msg_repr)

    rprint(printable)
