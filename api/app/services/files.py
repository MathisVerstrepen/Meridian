import asyncio
import mimetypes
import os
import uuid


async def save_file(
    file_contents: bytes, filename: str, directory: str = "uploads"
) -> tuple[str, str]:
    """
    Save a file to the specified directory and return the file path.
    """
    if not os.path.exists(directory):
        os.makedirs(directory)

    _, ext = os.path.splitext(filename)
    if not ext:
        ext = mimetypes.guess_extension(mimetypes.guess_type(filename)[0] or "") or ""

    new_file_id = str(uuid.uuid4())
    new_filename = new_file_id + (ext or "")

    file_path = os.path.join("data", directory, new_filename)
    with open(file_path, "wb") as f:
        f.write(file_contents)

    return new_file_id, file_path


async def generate_pdf_preview(id: str, directory: str = "uploads"):
    """
    Generate a PDF preview for the first page of the given file with reduced image size.
    """

    out_path = os.path.join("data", directory, f"{id}.jpg")
    in_path = os.path.join("data", directory, f"{id}.pdf")

    process = await asyncio.create_subprocess_exec(
        "convert",
        "-density",
        "100",
        f"{in_path}[0]",
        "-resize",
        "800x800",
        out_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate()
