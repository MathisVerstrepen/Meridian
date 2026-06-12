import uuid

from database.pg.models import CustomImageTonePreset, Files
from fastapi import HTTPException
from schemas.images import CustomImageTonePresetCreate
from services.image_playground.constants import MAX_CUSTOM_TONE_PRESETS_PER_USER
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlmodel import and_, col
from sqlmodel.ext.asyncio.session import AsyncSession


async def count_custom_image_tone_presets(session: AsyncSession, user_id: uuid.UUID) -> int:
    result = await session.exec(  # type: ignore
        select(func.count())
        .select_from(CustomImageTonePreset)
        .where(col(CustomImageTonePreset.user_id) == user_id)
    )
    return int(result.one())


async def list_custom_image_tone_presets(
    pg_engine: SQLAlchemyAsyncEngine,
    user_id: uuid.UUID,
) -> list[CustomImageTonePreset]:
    async with AsyncSession(pg_engine) as session:
        stmt = (
            select(CustomImageTonePreset)
            .where(and_(CustomImageTonePreset.user_id == user_id))
            .order_by(CustomImageTonePreset.created_at)  # type: ignore[arg-type]
        )
        result = await session.exec(stmt)  # type: ignore
        return result.scalars().all()  # type: ignore


async def create_custom_image_tone_preset(
    pg_engine: SQLAlchemyAsyncEngine,
    user_id: uuid.UUID,
    payload: CustomImageTonePresetCreate,
) -> CustomImageTonePreset:
    label = payload.label.strip()
    suffix = payload.suffix.strip()
    description = payload.description.strip() if payload.description else None

    if not label or not suffix:
        raise HTTPException(status_code=400, detail="Tone name and instructions are required.")

    async with AsyncSession(pg_engine, expire_on_commit=False) as session:
        existing_count = await count_custom_image_tone_presets(session, user_id)
        if existing_count >= MAX_CUSTOM_TONE_PRESETS_PER_USER:
            raise HTTPException(
                status_code=429,
                detail=(
                    "Too many custom tone presets. "
                    f"You can save up to {MAX_CUSTOM_TONE_PRESETS_PER_USER} presets."
                ),
            )

        if payload.image_id:
            stmt = select(Files).where(
                and_(
                    Files.id == payload.image_id,
                    Files.user_id == user_id,
                    Files.type == "file",
                )
            )
            result = await session.exec(stmt)  # type: ignore
            preview_file = result.scalars().first()
            if not preview_file or not (preview_file.content_type or "").startswith("image/"):
                raise HTTPException(status_code=404, detail="Tone preview image not found.")

        preset = CustomImageTonePreset(
            user_id=user_id,
            label=label,
            suffix=suffix,
            description=description,
            image_id=payload.image_id,
        )
        session.add(preset)
        await session.commit()
        await session.refresh(preset)
        return preset


async def delete_custom_image_tone_preset(
    pg_engine: SQLAlchemyAsyncEngine,
    user_id: uuid.UUID,
    preset_id: uuid.UUID,
) -> None:
    async with AsyncSession(pg_engine) as session:
        stmt = select(CustomImageTonePreset).where(
            and_(
                col(CustomImageTonePreset.id) == preset_id,
                col(CustomImageTonePreset.user_id) == user_id,
            )
        )
        result = await session.exec(stmt)  # type: ignore
        preset = result.scalars().first()
        if not preset:
            raise HTTPException(status_code=404, detail="Custom tone preset not found.")

        await session.delete(preset)
        await session.commit()
