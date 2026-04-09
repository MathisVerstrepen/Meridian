import logging
import os
import shlex
import stat
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def ssh_key_context(key_string: str):
    """
    An async context manager to handle the lifecycle of a temporary SSH key file.

    It creates a temporary file, writes the SSH key to it with secure permissions,
    yields the path to the key file and the necessary GIT_SSH_COMMAND environment,
    and ensures the file is securely deleted upon exiting the context.

    Args:
        key_string (str): The SSH private key content.

    Yields:
        dict: A dictionary containing the GIT_SSH_COMMAND environment variable.
    """
    file_descriptor, file_path_str = tempfile.mkstemp(text=True, prefix="meridian-ssh-")
    key_path = Path(file_path_str)

    try:
        # Wrap the mkstemp descriptor directly so we do not reopen the path.
        with os.fdopen(file_descriptor, "w") as f:
            f.write(key_string)
            if not key_string.endswith("\n"):
                f.write("\n")

        # Set strict permissions (read/write for owner only)
        os.chmod(key_path, stat.S_IRUSR | stat.S_IWUSR)

        # Require a pinned host key from the system/user known_hosts files.
        ssh_command = (
            f"ssh -i {shlex.quote(str(key_path))} "
            "-o IdentitiesOnly=yes "
            "-o BatchMode=yes "
            "-o StrictHostKeyChecking=yes"
        )
        git_env = {
            "GIT_SSH_COMMAND": ssh_command,
            "GIT_TERMINAL_PROMPT": "0",
        }

        yield git_env

    finally:
        # Securely clean up the temporary file
        try:
            key_path.unlink()
        except OSError as e:
            logger.error(f"Error removing temporary SSH key file {key_path}: {e}")
