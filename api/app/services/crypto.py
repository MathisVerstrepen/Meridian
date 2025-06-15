import os
import base64
from hashlib import md5

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad


def decrypt_cryptojs_payload(encrypted_b64_str: str, password: str) -> bytes:
    """
    Decrypts a payload encrypted by the frontend using CryptoJS.AES.encrypt.
    This replicates the key derivation and decryption process.

    Args:
        encrypted_b64_str (str): The base64-encoded encrypted string.
        password (str): The password used for encryption.

    Returns:
        bytes: The decrypted bytes, or None if decryption fails.

    Raises:
        ValueError: If the decryption fails due to incorrect password or data corruption.
    """
    try:
        encrypted_data = base64.b64decode(encrypted_b64_str)

        salt = encrypted_data[8:16]
        ciphertext = encrypted_data[16:]

        key_iv = b""
        temp = b""
        while len(key_iv) < 48:
            temp = md5(temp + password.encode("utf-8") + salt).digest()
            key_iv += temp

        key = key_iv[:32]
        iv = key_iv[32:48]

        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted_padded = cipher.decrypt(ciphertext)

        return unpad(decrypted_padded, AES.block_size)
    except (ValueError, IndexError) as e:
        print(f"Decryption failed: {e}")
        return None


def store_api_key(frontend_encrypted_key: str, user_id: str) -> str | None:
    """
    Takes the frontend-encrypted key, decrypts it, re-encrypts it with the
    backend secret, and returns a string safe for database storage.

    Args:
        frontend_encrypted_key (str): The encrypted API key from the frontend.
        user_id (str): The user ID for whom the key is being stored.

    Returns:
        str | None: The encrypted payload ready for database storage, or None if decryption fails.

    Raises:
        ValueError: If the backend secret is not set in the environment.
    """
    raw_api_key = decrypt_cryptojs_payload(frontend_encrypted_key, user_id)

    if not raw_api_key:
        return None

    backend_secret_hex = os.getenv("BACKEND_SECRET")
    backend_key_bytes = bytes.fromhex(backend_secret_hex)

    cipher = AES.new(backend_key_bytes, AES.MODE_GCM)
    ciphertext, tag = cipher.encrypt_and_digest(raw_api_key)

    db_payload = f"{cipher.nonce.hex()}:{tag.hex()}:{ciphertext.hex()}"

    return db_payload


def retrieve_and_decrypt_api_key(db_payload: str) -> str | None:
    """
    Fetches the encrypted payload from the DB and decrypts it using the
    backend secret to get the raw API key, ready for use.

    Args:
        db_payload (str): The encrypted payload stored in the database.

    Returns:
        str | None: The decrypted API key, or None if decryption fails.

    Raises:
        ValueError: If the backend secret is not set in the environment.
    """

    try:
        nonce_hex, tag_hex, ciphertext_hex = db_payload.split(":")

        nonce = bytes.fromhex(nonce_hex)
        tag = bytes.fromhex(tag_hex)
        ciphertext = bytes.fromhex(ciphertext_hex)

        backend_secret_hex = os.getenv("BACKEND_SECRET")
        backend_key_bytes = bytes.fromhex(backend_secret_hex)
        cipher = AES.new(backend_key_bytes, AES.MODE_GCM, nonce=nonce)

        raw_api_key = cipher.decrypt_and_verify(ciphertext, tag)
        return raw_api_key.decode("utf-8")
    except (ValueError, KeyError) as e:
        print(
            f"Backend decryption failed: {e}. The data may be corrupt or tampered with."
        )
        return None
