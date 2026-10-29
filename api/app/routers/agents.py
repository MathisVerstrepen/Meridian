"""Authenticated Agent library. Authorization and mutations live in the domain services."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from schemas.agents import (
    AgentDescriptionRequest,
    AgentDescriptionResponse,
    AgentIconRequest,
    AgentIconResponse,
    AgentImport,
    AgentWrite,
    MentionRequest,
    RatingWrite,
    TeamWrite,
    VerificationWrite,
)
from services.agents import catalog, description, icon_generation, library, teams
from services.agents.presets import starter_presets
from services.auth import get_current_user_id
from services.inference import get_available_models_for_user


async def agent_user_id(user_id: str = Depends(get_current_user_id)) -> UUID:
    return UUID(user_id)


router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("")
async def list_agents(
    request: Request,
    user_id: UUID = Depends(agent_user_id),
    view: Literal["my", "marketplace", "bookmarked", "forked", "recent", "team", "drafts"] = "my",
    q: str = "",
    category: str = "",
    model: str = "",
    tool: str = "",
    sort: Literal["updated", "newest", "name", "rating", "bookmarks", "forks", "usage"] = "updated",
    offset: int = Query(0, ge=0),
    limit: int = Query(24, ge=1, le=100),
):
    return await library.list_profiles(
        request.app.state.pg_engine,
        user_id,
        view=view,
        q=q,
        category=category,
        model=model,
        tool=tool,
        sort=sort,
        offset=offset,
        limit=limit,
    )


@router.post("")
async def create_agent(data: AgentWrite, request: Request, user_id: UUID = Depends(agent_user_id)):
    return await library.save_profile(request.app.state.pg_engine, user_id, data)


@router.get("/presets")
async def presets(user_id: UUID = Depends(agent_user_id)):
    return starter_presets()


@router.post("/generate-description", response_model=AgentDescriptionResponse)
async def generate_description(
    data: AgentDescriptionRequest, request: Request, user_id: UUID = Depends(agent_user_id)
):
    models = await get_available_models_for_user(request.app, str(user_id))
    return await description.generate_description(
        request.app.state.pg_engine,
        str(user_id),
        data,
        request.app.state.http_client,
        [model.model_dump() for model in models.data],
    )


@router.post("/generate-icon", response_model=AgentIconResponse)
async def generate_icon(
    data: AgentIconRequest, request: Request, user_id: UUID = Depends(agent_user_id)
):
    models = await get_available_models_for_user(request.app, str(user_id))
    return await icon_generation.generate_icon(
        request.app.state.pg_engine,
        str(user_id),
        data,
        request.app.state.http_client,
        [model.model_dump() for model in models.data],
    )


@router.post("/import")
async def import_agent(data: AgentImport, request: Request, user_id: UUID = Depends(agent_user_id)):
    return await library.save_profile(
        request.app.state.pg_engine,
        user_id,
        data.profile.model_copy(update={"visibility": "private"}),
    )


@router.post("/resolve-mention")
async def mention(data: MentionRequest, request: Request, user_id: UUID = Depends(agent_user_id)):
    return await teams.resolve_mention(request.app.state.pg_engine, user_id, data.message)


@router.get("/teams")
async def list_teams(request: Request, user_id: UUID = Depends(agent_user_id)):
    return await teams.list_teams(request.app.state.pg_engine, user_id)


@router.post("/teams")
async def create_team(data: TeamWrite, request: Request, user_id: UUID = Depends(agent_user_id)):
    return await teams.save_team(request.app.state.pg_engine, user_id, data)


@router.put("/teams/{team_id}")
async def update_team(
    team_id: UUID, data: TeamWrite, request: Request, user_id: UUID = Depends(agent_user_id)
):
    return await teams.save_team(request.app.state.pg_engine, user_id, data, team_id)


@router.get("/{agent_id}")
async def get_agent(agent_id: UUID, request: Request, user_id: UUID = Depends(agent_user_id)):
    return await catalog.get_profile(request.app.state.pg_engine, user_id, agent_id)


@router.put("/{agent_id}")
async def update_agent(
    agent_id: UUID, data: AgentWrite, request: Request, user_id: UUID = Depends(agent_user_id)
):
    return await library.save_profile(request.app.state.pg_engine, user_id, data, agent_id)


@router.delete("/{agent_id}")
async def delete_agent(agent_id: UUID, request: Request, user_id: UUID = Depends(agent_user_id)):
    await library.delete_profile(request.app.state.pg_engine, user_id, agent_id)
    return {"deleted": True}


@router.post("/{agent_id}/fork")
async def fork_agent(agent_id: UUID, request: Request, user_id: UUID = Depends(agent_user_id)):
    return await library.fork_profile(request.app.state.pg_engine, str(user_id), agent_id)


@router.get("/{agent_id}/export")
async def export_agent(agent_id: UUID, request: Request, user_id: UUID = Depends(agent_user_id)):
    return await catalog.export_profile(request.app.state.pg_engine, user_id, agent_id)


@router.get("/{agent_id}/versions")
async def list_versions(agent_id: UUID, request: Request, user_id: UUID = Depends(agent_user_id)):
    return await catalog.list_versions(request.app.state.pg_engine, user_id, agent_id)


@router.post("/{agent_id}/versions/{version}/restore")
async def restore_version(
    agent_id: UUID, version: int, request: Request, user_id: UUID = Depends(agent_user_id)
):
    return await library.restore_version(request.app.state.pg_engine, user_id, agent_id, version)


@router.put("/{agent_id}/bookmark")
async def bookmark(agent_id: UUID, request: Request, user_id: UUID = Depends(agent_user_id)):
    await library.social(request.app.state.pg_engine, user_id, agent_id, bookmark=True)
    return {"bookmarked": True}


@router.delete("/{agent_id}/bookmark")
async def unbookmark(agent_id: UUID, request: Request, user_id: UUID = Depends(agent_user_id)):
    await library.social(request.app.state.pg_engine, user_id, agent_id, bookmark=False)
    return {"bookmarked": False}


@router.put("/{agent_id}/rating")
async def rate(
    agent_id: UUID, data: RatingWrite, request: Request, user_id: UUID = Depends(agent_user_id)
):
    await library.social(request.app.state.pg_engine, user_id, agent_id, rating=data.value)
    return {"rating": data.value}


@router.put("/{agent_id}/verification")
async def verify(
    agent_id: UUID,
    data: VerificationWrite,
    request: Request,
    user_id: UUID = Depends(agent_user_id),
):
    await library.social(request.app.state.pg_engine, user_id, agent_id, verified=data.verified)
    return {"verified": data.verified}
