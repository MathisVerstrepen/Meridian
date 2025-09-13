import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import sentry_sdk
from database.pg.token_ops.refresh_token_crud import (
    create_db_refresh_token,
    delete_all_refresh_tokens_for_user,
    find_user_id_by_used_token,
)
from database.pg.user_ops.user_crud import does_user_exist
from database.pg.user_ops.user_password_crud import update_user_password
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from models.auth import UserPass
from pydantic import ValidationError
from services.crypto import get_password_hash
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15  # 15 minutes
REFRESH_TOKEN_EXPIRE_DAYS = 30  # 30 days

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/auth/token")

logger = logging.getLogger("uvicorn.error")


async def create_refresh_token(pg_engine: SQLAlchemyAsyncEngine, user_id: str) -> str:
    """
    Creates a secure, random refresh token and stores it in the database.
    """
    with sentry_sdk.start_span(op="auth.token", description="Create Refresh Token") as span:
        span.set_tag("user_id_hash", hashlib.sha256(user_id.encode("utf-8")).hexdigest())
        token = secrets.token_hex(32)
        expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        await create_db_refresh_token(pg_engine, user_id, token, expires_at)
        sentry_sdk.metrics.incr("auth.refresh_token.created")
        return token


async def handle_refresh_token_theft(pg_engine: SQLAlchemyAsyncEngine, used_token: str):
    """
    Handles a potential refresh token theft scenario.

    If a refresh token is not found in the valid tokens table, it might have been
    stolen and used by an attacker. This function checks if the token exists in a
    "used" state. If it does, it's a confirmed replay attack, and we must
    invalidate all sessions for that user to contain the breach.

    Args:
        pg_engine: The database engine.
        used_token: The refresh token string that was just attempted.
    """
    with sentry_sdk.start_span(op="auth.security", description="Handle Refresh Token Theft"):
        compromised_user_id = await find_user_id_by_used_token(pg_engine, used_token)

        if compromised_user_id:
            user_id_hash = hashlib.sha256(str(compromised_user_id).encode("utf-8")).hexdigest()
            sentry_sdk.set_tag("compromised_user_id_hash", user_id_hash)
            logger.warning(
                f"""REPLAY ATTACK DETECTED: User {compromised_user_id} session compromised. 
                Invalidating all refresh tokens for this user."""
            )
            sentry_sdk.capture_message(
                "Refresh token replay attack detected for user", level="warning"
            )
            sentry_sdk.metrics.incr("auth.refresh_token.replay_detected")
            await delete_all_refresh_tokens_for_user(pg_engine, str(compromised_user_id))


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """
    Creates a JWT token with the provided data and expiration time.
    Args:
        data (dict): The data to encode in the JWT.
        expires_delta (Optional[timedelta]): The expiration time for the token.
    Returns:
        str: The encoded JWT token.
    Raises:
        ValueError: If the JWT secret key is not set in the environment.
    """
    with sentry_sdk.start_span(op="auth.token", description="Create Access Token") as span:
        try:
            SECRET_KEY = os.getenv("JWT_SECRET_KEY")
            if not SECRET_KEY:
                raise ValueError("JWT_SECRET_KEY is not set in the environment")

            to_encode = data.copy()
            if expires_delta:
                expire = datetime.now(timezone.utc) + expires_delta
            else:
                expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            to_encode.update({"exp": expire})
            encoded_jwt = jwt.encode(claims=to_encode, key=SECRET_KEY, algorithm=ALGORITHM)
            sentry_sdk.metrics.incr("auth.access_token.created")
            span.set_status("ok")
            return encoded_jwt
        except ValueError as e:
            sentry_sdk.capture_exception(e)
            span.set_status("internal_error")
            raise


async def get_current_user_id(request: Request, token: str = Depends(oauth2_scheme)) -> str:
    """
    Decodes the JWT, validates it, and returns the user ID (from the 'sub' claim).
    This function will be used as a dependency in protected routes.
    Args:
        token (str): The JWT token to decode.
    Returns:
        str: The user ID extracted from the token.
    Raises:
        HTTPException: If the token is invalid or expired.
        ValueError: If the JWT secret key is not set in the environment.
    """
    SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    if not SECRET_KEY:
        exc = ValueError("JWT_SECRET_KEY is not set in the environment")
        sentry_sdk.capture_exception(exc)
        raise exc

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    with sentry_sdk.start_span(op="auth.jwt", description="Verify JWT and Get User") as span:
        try:
            sentry_sdk.add_breadcrumb(category="auth", message="Decoding JWT", level="info")
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id: str = payload.get("sub")
            if user_id is None:
                span.set_status("unauthenticated")
                raise credentials_exception

            sentry_sdk.add_breadcrumb(
                category="auth", message="Checking user existence in DB", level="info"
            )
            user_exists = await does_user_exist(request.app.state.pg_engine, user_id)
            if not user_exists:
                span.set_status("unauthenticated")
                raise credentials_exception

            # Set user context for Sentry
            user_id_hash = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
            sentry_sdk.set_user(
                {
                    "id": user_id_hash,
                    "username": f"User-{user_id_hash[:8]}",
                }
            )
            span.set_tag("user_id_hash", user_id_hash)
            span.set_status("ok")
            sentry_sdk.add_breadcrumb(
                category="auth", message="JWT validation successful", level="info"
            )
        except (JWTError, ValidationError) as e:
            span.set_status("unauthenticated")
            sentry_sdk.add_breadcrumb(
                category="auth",
                message=f"JWT validation failed: {e.__class__.__name__}",
                level="warning",
            )
            raise credentials_exception from e

    return user_id


def parse_userpass(userpass: str) -> list[UserPass]:
    """
    Parses a userpass string into a dictionary.
    Args:
        userpass (str): The userpass string in the format "username:password".
    Returns:
        dict: A dictionary with 'username' and 'password' keys.
    Raises:
        ValueError: If the userpass string is not in the correct format.
    """
    with sentry_sdk.start_span(
        op="auth.startup", description="Parse USERPASS environment variable"
    ):
        if not userpass:
            logger.warning("No userpass provided, no users will be created.")
            return []
        try:
            if ":" not in userpass:
                raise ValueError(
                    "Invalid userpass format. Expected 'username1:password1,username2:password2'"
                )

            userpass_list = userpass.split(",")
            userpass_dicts = []
            for up in userpass_list:
                username, password = up.split(":")
                userpass_dicts.append(
                    UserPass(username=username, password=get_password_hash(password))
                )
            sentry_sdk.metrics.set("auth.startup.users_configured", len(userpass_dicts))
            return userpass_dicts
        except ValueError as e:
            sentry_sdk.capture_exception(e)
            raise


async def handle_password_update(
    pg_engine: SQLAlchemyAsyncEngine, user_id: str, new_password: str
) -> None:
    """
    Updates the user's password in the database.

    Args:
        db (AsyncSession): The database session.
        user_id (str): The ID of the user to update.
        new_password (str): The new password for the user.

    Returns:
        None
    """
    with sentry_sdk.start_span(op="auth.user", description="Update User Password") as span:
        user_id_hash = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
        span.set_tag("user_id_hash", user_id_hash)
        sentry_sdk.add_breadcrumb(
            category="auth", message="Updating password for user", level="info"
        )
        hashed_password = get_password_hash(new_password)
        await update_user_password(pg_engine, user_id, hashed_password)
        sentry_sdk.metrics.incr("auth.password.update.success")
