from datetime import datetime

from const.prompts import PROMPT_REFERENCES
from const.settings import DEFAULT_SETTINGS
from database.pg.settings_ops.settings_crud import get_settings
from models.usersDTO import SettingsDTO, SystemPrompt
from sqlalchemy.ext.asyncio import AsyncEngine


def concat_system_prompts(prompts: list[SystemPrompt], include_ids: list[str]) -> str:
    enabled_prompts = [p.prompt for p in prompts if p.enabled and p.id in include_ids]
    return "\n".join(enabled_prompts)


def _parse_system_prompt(prompt: SystemPrompt) -> SystemPrompt:
    final_prompt = prompt.prompt

    print("Parsing system prompt:", prompt)

    if prompt.reference:
        final_prompt = PROMPT_REFERENCES.get(prompt.reference, prompt.prompt)

    final_prompt = final_prompt.replace("{{CURRENT_DATE}}", datetime.today().strftime("%B %d, %Y"))

    return SystemPrompt(
        id=prompt.id,
        name=prompt.name,
        prompt=final_prompt,
        enabled=prompt.enabled,
        editable=prompt.editable,
        reference=prompt.reference,
    )


async def get_user_settings(pg_engine: AsyncEngine, user_id: str) -> SettingsDTO:
    """
    Retrieve user settings from the database.

    Args:
        pg_engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine instance.
        user_id (str): The UUID of the user whose settings are to be retrieved.

    Returns:
        SettingsDTO: The Settings object containing the user's settings.

    Raises:
        HTTPException: Status 404 if the user with the given ID is not found.
    """
    settings_db = await get_settings(pg_engine, user_id)
    settings = SettingsDTO.model_validate(settings_db)

    if not settings:
        settings = DEFAULT_SETTINGS

    settings.models.systemPrompt = [_parse_system_prompt(p) for p in settings.models.systemPrompt]

    return settings
