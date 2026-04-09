from pathlib import Path

import pybase64 as base64


def encode_file_as_data_uri(file_path: Path, mime_type: str) -> str:
    """Read a file and encode it into a base64 data URI."""
    with open(file_path, "rb") as file_handle:
        encoded_data = base64.b64encode(file_handle.read()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded_data}"
