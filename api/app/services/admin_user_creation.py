import os
from enum import Enum

ADMIN_USER_CREATION_ENV = "ADMIN_USER_CREATION"


class AdminUserCreationMode(str, Enum):
    NONE = ""
    FIRST = "first"
    ALL_USERPASS = "all_userpass"
    ALL = "all"


def parse_admin_user_creation_mode(value: str | None) -> AdminUserCreationMode:
    if value is None:
        return AdminUserCreationMode.FIRST

    try:
        return AdminUserCreationMode(value.strip())
    except ValueError as exc:
        valid_values = ", ".join(repr(mode.value) for mode in AdminUserCreationMode)
        raise ValueError(
            f"Invalid {ADMIN_USER_CREATION_ENV} value {value!r}. Expected one of: {valid_values}."
        ) from exc


def get_admin_user_creation_mode() -> AdminUserCreationMode:
    return parse_admin_user_creation_mode(os.getenv(ADMIN_USER_CREATION_ENV))


def should_create_initial_userpass_as_admin(
    mode: AdminUserCreationMode, userpass_index: int
) -> bool:
    return mode in {AdminUserCreationMode.ALL, AdminUserCreationMode.ALL_USERPASS} or (
        mode is AdminUserCreationMode.FIRST and userpass_index == 0
    )


def should_create_account_as_admin(mode: AdminUserCreationMode) -> bool:
    return mode is AdminUserCreationMode.ALL
