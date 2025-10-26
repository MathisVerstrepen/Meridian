import asyncio
import logging
import os

import bcrypt
from Crypto.Cipher import AES

logger = logging.getLogger("uvicorn.error")

bcrypt.__about__ = bcrypt  # type: ignore


async def encrypt_api_key(raw_api_key_str: str) -> str | None:
    """
    Takes a raw API key (received over HTTPS), encrypts it with the
    backend secret using AES-GCM, and returns a string safe for database storage.
    This operation is performed in a separate thread to avoid blocking the event loop.

    Args:
        raw_api_key_str (str): The raw, plaintext API key from the frontend.

    Returns:
        str | None: The encrypted payload ready for database storage, or None on failure.

    Raises:
        ValueError: If the backend secret is not set in the environment.
    """
    if not raw_api_key_str:
        return None

    backend_secret_hex = os.getenv("BACKEND_SECRET")
    if not backend_secret_hex:
        logger.error("BACKEND_SECRET is not set. Cannot encrypt API key.")
        raise ValueError("BACKEND_SECRET is not set in the environment.")

    def _encrypt_in_thread() -> str:
        """Synchronous helper function to run in a thread pool."""
        backend_key_bytes = bytes.fromhex(backend_secret_hex)
        raw_api_key_bytes = raw_api_key_str.encode("utf-8")

        cipher = AES.new(backend_key_bytes, AES.MODE_GCM)
        ciphertext, tag = cipher.encrypt_and_digest(raw_api_key_bytes)

        return f"{cipher.nonce.hex()}:{tag.hex()}:{ciphertext.hex()}"

    try:
        return await asyncio.to_thread(_encrypt_in_thread)
    except Exception as e:
        logger.error(f"Backend encryption failed: {e}")
        return None


async def decrypt_api_key(db_payload: str) -> str | None:
    """
    Fetches the encrypted payload from the DB and decrypts it using the
    backend secret to get the raw API key, ready for use.
    This operation is performed in a separate thread to avoid blocking the event loop.

    Args:
        db_payload (str): The encrypted payload stored in the database.

    Returns:
        str | None: The decrypted API key, or None if decryption fails.
    """
    if not db_payload:
        return None

    backend_secret_hex = os.getenv("BACKEND_SECRET")
    if not backend_secret_hex:
        logger.error("BACKEND_SECRET is not set. Cannot decrypt API key.")
        raise ValueError("BACKEND_SECRET is not set in the environment.")

    try:
        nonce_hex, tag_hex, ciphertext_hex = db_payload.split(":")
        nonce = bytes.fromhex(nonce_hex)
        tag = bytes.fromhex(tag_hex)
        ciphertext = bytes.fromhex(ciphertext_hex)

        def _decrypt_in_thread() -> str:
            """Synchronous helper function to run in a thread pool."""
            backend_key_bytes = bytes.fromhex(backend_secret_hex)
            cipher = AES.new(backend_key_bytes, AES.MODE_GCM, nonce=nonce)
            decrypted_bytes = cipher.decrypt_and_verify(ciphertext, tag)
            return decrypted_bytes.decode("utf-8")

        return await asyncio.to_thread(_decrypt_in_thread)
    except (ValueError, KeyError) as e:
        logger.error(f"Backend decryption failed: {e}. The data may be corrupt or tampered with.")
        return None


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain password against a hashed one asynchronously.
    This operation is performed in a separate thread to avoid blocking the event loop.
    """
    return await asyncio.to_thread(
        bcrypt.checkpw,
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


async def get_password_hash(password: str) -> str:
    """
    Hashes a plain password asynchronously.
    This operation is performed in a separate thread to avoid blocking the event loop.
    """
    hashed_bytes = await asyncio.to_thread(
        bcrypt.hashpw, password.encode("utf-8"), bcrypt.gensalt()
    )
    return hashed_bytes.decode("utf-8")
