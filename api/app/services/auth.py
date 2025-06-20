from fastapi import Request, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime, timedelta, timezone
from pydantic import ValidationError
from jose import JWTError, jwt
from typing import Optional
import logging
import os

from services.crypto import get_password_hash
from database.pg.crud import does_user_exist
from models.auth import UserPass

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/auth/token")

logger = logging.getLogger("uvicorn.error")


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
    SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    if not SECRET_KEY:
        raise ValueError("JWT_SECRET_KEY is not set in the environment")

    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(claims=to_encode, key=SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user_id(
    request: Request, token: str = Depends(oauth2_scheme)
) -> str:
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
        raise ValueError("JWT_SECRET_KEY is not set in the environment")

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception

        user_exists = await does_user_exist(request.app.state.pg_engine, user_id)
        if not user_exists:
            raise credentials_exception
    except (JWTError, ValidationError):
        raise credentials_exception

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

    if not userpass:
        logger.warning("No userpass provided, no users will be created.")
        return []

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
    return userpass_dicts
