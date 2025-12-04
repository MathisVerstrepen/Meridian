import uuid
from typing import List

from database.pg.models import PromptTemplate, TemplateBookmark
from models.usersDTO import PromptTemplateCreate, PromptTemplateUpdate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlmodel import and_
from sqlmodel.ext.asyncio.session import AsyncSession


async def create_prompt_template(
    pg_engine: SQLAlchemyAsyncEngine, user_id: uuid.UUID, template_data: PromptTemplateCreate
) -> PromptTemplate:
    async with AsyncSession(pg_engine, expire_on_commit=False) as session:
        # Get current max order index to append to the end
        stmt = select(PromptTemplate).where(and_(PromptTemplate.user_id == user_id))
        result = await session.exec(stmt)  # type: ignore
        existing_templates = result.scalars().all()
        next_index = len(existing_templates)

        db_template = PromptTemplate.model_validate(
            template_data, update={"user_id": user_id, "order_index": next_index}
        )
        session.add(db_template)
        await session.commit()
        await session.refresh(db_template)
        return db_template


async def get_all_prompt_templates_for_user(
    pg_engine: SQLAlchemyAsyncEngine, user_id: uuid.UUID
) -> List[PromptTemplate]:
    async with AsyncSession(pg_engine) as session:
        stmt = (
            select(PromptTemplate)
            .where(and_(PromptTemplate.user_id == user_id))
            .order_by(PromptTemplate.order_index)  # type: ignore
        )
        result = await session.exec(stmt)  # type: ignore
        return result.scalars().all()  # type: ignore


async def get_public_prompt_templates(
    pg_engine: SQLAlchemyAsyncEngine, exclude_user_id: uuid.UUID | None = None
) -> List[PromptTemplate]:
    async with AsyncSession(pg_engine) as session:
        conditions = [PromptTemplate.is_public == True]  # noqa: E712
        if exclude_user_id:
            conditions.append(PromptTemplate.user_id != exclude_user_id)

        stmt = select(PromptTemplate).where(and_(*conditions))
        result = await session.exec(stmt)  # type: ignore
        return result.scalars().all()  # type: ignore


async def get_prompt_template_by_id(
    pg_engine: SQLAlchemyAsyncEngine, template_id: uuid.UUID
) -> PromptTemplate | None:
    async with AsyncSession(pg_engine) as session:
        return await session.get(PromptTemplate, template_id)


async def update_prompt_template(
    db_template: PromptTemplate,
    template_data: PromptTemplateUpdate,
    pg_engine: SQLAlchemyAsyncEngine,
) -> PromptTemplate:
    async with AsyncSession(pg_engine, expire_on_commit=False) as session:
        update_data = template_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_template, key, value)
        session.add(db_template)
        await session.commit()
        await session.refresh(db_template)
        return db_template


async def delete_prompt_template(
    db_template: PromptTemplate, pg_engine: SQLAlchemyAsyncEngine
) -> None:
    async with AsyncSession(pg_engine) as session:
        await session.delete(db_template)
        await session.commit()


async def reorder_prompt_templates(
    pg_engine: SQLAlchemyAsyncEngine, user_id: uuid.UUID, ordered_ids: List[uuid.UUID]
) -> None:
    async with AsyncSession(pg_engine) as session:
        stmt = select(PromptTemplate).where(and_(PromptTemplate.user_id == user_id))
        result = await session.exec(stmt)  # type: ignore
        templates = result.scalars().all()

        template_map = {t.id: t for t in templates}

        for index, t_id in enumerate(ordered_ids):
            if t_id in template_map:
                template = template_map[t_id]
                if template.order_index != index:
                    template.order_index = index
                    session.add(template)

        await session.commit()


# --- Bookmark Operations ---


async def bookmark_template(
    pg_engine: SQLAlchemyAsyncEngine, user_id: uuid.UUID, template_id: uuid.UUID
) -> None:
    async with AsyncSession(pg_engine) as session:
        # Check if already bookmarked
        stmt = select(TemplateBookmark).where(
            and_(
                TemplateBookmark.user_id == user_id,
                TemplateBookmark.template_id == template_id,
            )
        )
        result = await session.exec(stmt)  # type: ignore
        if result.scalars().first():
            return

        bookmark = TemplateBookmark(user_id=user_id, template_id=template_id)
        session.add(bookmark)
        await session.commit()


async def unbookmark_template(
    pg_engine: SQLAlchemyAsyncEngine, user_id: uuid.UUID, template_id: uuid.UUID
) -> None:
    async with AsyncSession(pg_engine) as session:
        stmt = select(TemplateBookmark).where(
            and_(
                TemplateBookmark.user_id == user_id,
                TemplateBookmark.template_id == template_id,
            )
        )
        result = await session.exec(stmt)  # type: ignore

        bookmark = result.scalars().first()

        if bookmark:
            await session.delete(bookmark)
            await session.commit()


async def get_user_bookmarked_templates(
    pg_engine: SQLAlchemyAsyncEngine, user_id: uuid.UUID
) -> List[PromptTemplate]:
    async with AsyncSession(pg_engine) as session:
        stmt = (
            select(PromptTemplate)
            .join(
                TemplateBookmark, TemplateBookmark.template_id == PromptTemplate.id  # type: ignore
            )
            .where(and_(TemplateBookmark.user_id == user_id))
        )
        result = await session.exec(stmt)  # type: ignore
        return result.scalars().all()  # type: ignore
