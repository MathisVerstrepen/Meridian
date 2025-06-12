import os
import uuid
import mimetypes


async def save_file(
    file_contents: bytes, filename: str, directory: str = "uploads"
) -> str:
    """
    Save a file to the specified directory and return the file path.
    """
    if not os.path.exists(directory):
        os.makedirs(directory)

    _, ext = os.path.splitext(filename)
    if not ext:
        ext = mimetypes.guess_extension(mimetypes.guess_type(filename)[0] or "")

    new_file_id = str(uuid.uuid4())
    new_filename = new_file_id + (ext or "")

    file_path = os.path.join("data", directory, new_filename)
    with open(file_path, "wb") as f:
        f.write(file_contents)

    return new_file_id, file_path
