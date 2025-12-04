import uuid
from typing import List

from database.pg.prompt_template_ops.prompt_template_crud import (
    bookmark_template,
    create_prompt_template,
    delete_prompt_template,
    get_all_prompt_templates_for_user,
    get_prompt_template_by_id,
    get_public_prompt_templates,
    get_user_bookmarked_templates,
    unbookmark_template,
    update_prompt_template,
)
from fastapi import APIRouter, Depends, HTTPException, Request, status
from models.usersDTO import PromptTemplateCreate, PromptTemplateRead, PromptTemplateUpdate
from pydantic import BaseModel
from services.auth import get_current_user_id

router = APIRouter(prefix="/prompt-templates", tags=["prompt-templates"])


class PromptLibraryResponse(BaseModel):
    created: List[PromptTemplateRead]
    bookmarked: List[PromptTemplateRead]


@router.get("/library", response_model=List[PromptTemplateRead])
async def get_user_library(request: Request, user_id: str = Depends(get_current_user_id)):
    """
    Get all prompt templates created by the current user.
    """
    pg_engine = request.app.state.pg_engine
    user_uuid = uuid.UUID(user_id)
    templates = await get_all_prompt_templates_for_user(pg_engine, user_uuid)
    return templates


@router.get("/marketplace", response_model=List[PromptTemplateRead])
async def get_marketplace_templates(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """
    Get all public prompt templates, excluding the current user's own templates.
    """
    pg_engine = request.app.state.pg_engine
    user_uuid = uuid.UUID(user_id)
    templates = await get_public_prompt_templates(pg_engine, exclude_user_id=user_uuid)
    return templates


@router.get("/library/combined", response_model=PromptLibraryResponse)
async def get_combined_library(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """
    Get both user-created and bookmarked templates in a single request.
    """
    pg_engine = request.app.state.pg_engine
    user_uuid = uuid.UUID(user_id)

    created = await get_all_prompt_templates_for_user(pg_engine, user_uuid)
    bookmarked = await get_user_bookmarked_templates(pg_engine, user_uuid)

    return {
        "created": created,
        "bookmarked": bookmarked,
    }


@router.get("/bookmarks", response_model=List[PromptTemplateRead])
async def get_bookmarks(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """
    Get all templates bookmarked by the current user.
    """
    pg_engine = request.app.state.pg_engine
    user_uuid = uuid.UUID(user_id)
    templates = await get_user_bookmarked_templates(pg_engine, user_uuid)
    return templates


@router.get("/{template_id}", response_model=PromptTemplateRead)
async def get_template_details(
    template_id: uuid.UUID,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """
    Get a specific prompt template by ID.
    Accessible if the user owns it OR if it is public.
    """
    pg_engine = request.app.state.pg_engine
    db_template = await get_prompt_template_by_id(pg_engine, template_id)

    if not db_template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Check permissions
    if str(db_template.user_id) != user_id and not db_template.is_public:
        raise HTTPException(status_code=403, detail="Access denied")

    return db_template


@router.post("", response_model=PromptTemplateRead)
async def create_template(
    request: Request,
    template_data: PromptTemplateCreate,
    user_id: str = Depends(get_current_user_id),
):
    """
    Create a new prompt template for the current user.
    """
    pg_engine = request.app.state.pg_engine
    user_uuid = uuid.UUID(user_id)
    new_template = await create_prompt_template(pg_engine, user_uuid, template_data)
    return new_template


@router.put("/{template_id}", response_model=PromptTemplateRead)
async def update_template(
    template_id: uuid.UUID,
    template_data: PromptTemplateUpdate,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """
    Update an existing prompt template for the current user.
    """
    pg_engine = request.app.state.pg_engine
    db_template = await get_prompt_template_by_id(pg_engine, template_id)
    if not db_template or str(db_template.user_id) != user_id:
        raise HTTPException(status_code=404, detail="Template not found or access denied")

    updated_template = await update_prompt_template(db_template, template_data, pg_engine)
    return updated_template


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: uuid.UUID,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """
    Delete a prompt template for the current user.
    """
    pg_engine = request.app.state.pg_engine
    db_template = await get_prompt_template_by_id(pg_engine, template_id)
    if not db_template or str(db_template.user_id) != user_id:
        raise HTTPException(status_code=404, detail="Template not found or access denied")

    await delete_prompt_template(db_template, pg_engine)
    return None


@router.post("/{template_id}/bookmark", status_code=status.HTTP_204_NO_CONTENT)
async def add_bookmark(
    template_id: uuid.UUID,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """
    Bookmark a prompt template.
    """
    pg_engine = request.app.state.pg_engine
    user_uuid = uuid.UUID(user_id)

    # Verify template exists
    template = await get_prompt_template_by_id(pg_engine, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    await bookmark_template(pg_engine, user_uuid, template_id)
    return None


@router.delete("/{template_id}/bookmark", status_code=status.HTTP_204_NO_CONTENT)
async def remove_bookmark(
    template_id: uuid.UUID,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """
    Remove a bookmark for a prompt template.
    """
    pg_engine = request.app.state.pg_engine
    user_uuid = uuid.UUID(user_id)
    await unbookmark_template(pg_engine, user_uuid, template_id)
    return None
