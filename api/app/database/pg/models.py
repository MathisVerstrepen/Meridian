# mypy: disable-error-code=call-arg
import datetime
import logging
import uuid
from datetime import timezone
from typing import Any, Optional

from models.auth import UserPass
from sqlalchemy import Column, ForeignKeyConstraint, Index, PrimaryKeyConstraint, func, select
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION, JSONB, TEXT, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Field, ForeignKey, Relationship, SQLModel, and_


class Graph(SQLModel, table=True):
    __tablename__ = "graphs"

    id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            primary_key=True,
            server_default=func.uuid_generate_v4(),
            nullable=False,
        ),
    )
    user_id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    name: str = Field(index=True, max_length=255, nullable=False)
    description: Optional[str] = Field(default=None, sa_column=Column(TEXT))  # not used
    temporary: bool = Field(default=False, nullable=False)
    pinned: bool = Field(default=False, nullable=False)

    created_at: Optional[datetime.datetime] = Field(
        default=None,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            server_default=func.now(),
            nullable=False,
        ),
    )
    updated_at: Optional[datetime.datetime] = Field(
        default=None,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        ),
    )

    # Model config for all nodes in canvas
    custom_instructions: list[str] = Field(default=None, sa_column=Column(JSONB, nullable=True))
    max_tokens: Optional[int] = Field(
        default=None, sa_column=Column(DOUBLE_PRECISION, nullable=True, default=None)
    )
    temperature: Optional[float] = Field(
        default=None, sa_column=Column(DOUBLE_PRECISION, nullable=True, default=None)
    )
    top_p: Optional[float] = Field(
        default=None, sa_column=Column(DOUBLE_PRECISION, nullable=True, default=None)
    )
    top_k: Optional[int] = Field(
        default=None, sa_column=Column(DOUBLE_PRECISION, nullable=True, default=None)
    )
    frequency_penalty: Optional[float] = Field(
        default=None, sa_column=Column(DOUBLE_PRECISION, nullable=True, default=None)
    )
    presence_penalty: Optional[float] = Field(
        default=None, sa_column=Column(DOUBLE_PRECISION, nullable=True, default=None)
    )
    repetition_penalty: Optional[float] = Field(
        default=None, sa_column=Column(DOUBLE_PRECISION, nullable=True, default=None)
    )
    reasoning_effort: Optional[str] = Field(
        default=None, sa_column=Column(TEXT, nullable=True, default=None)
    )

    nodes: list["Node"] = Relationship(back_populates="graph")
    edges: list["Edge"] = Relationship(back_populates="graph")

    node_count: Optional[int] = (
        None  # This will be set dynamically in the query, not stored in the database
    )

    __table_args__ = (Index("idx_graphs_user_updated_at", "user_id", "updated_at"),)


class Node(SQLModel, table=True):
    __tablename__ = "nodes"

    # NOTE: 'id' here is the string ID from the frontend library
    id: str = Field(max_length=255, nullable=False)
    graph_id: uuid.UUID = Field(foreign_key="graphs.id", nullable=False)
    type: str = Field(index=True, max_length=100, nullable=False)
    position_x: float = Field(sa_column=Column(DOUBLE_PRECISION, nullable=False))
    position_y: float = Field(sa_column=Column(DOUBLE_PRECISION, nullable=False))
    width: str = Field(default="100px", max_length=255)
    height: str = Field(default="100px", max_length=255)
    parent_node_id: Optional[str] = Field(default=None, max_length=255, nullable=True)

    data: Optional[dict[str, Any] | list[Any]] = Field(default=None, sa_column=Column(JSONB))

    graph: Optional[Graph] = Relationship(back_populates="nodes")
    outgoing_edges: list["Edge"] = Relationship(
        back_populates="source_node",
        sa_relationship_kwargs={
            "foreign_keys": "[Edge.graph_id, Edge.source_node_id]",
            "overlaps": "edges",
        },
    )
    incoming_edges: list["Edge"] = Relationship(
        back_populates="target_node",
        sa_relationship_kwargs={
            "foreign_keys": "[Edge.graph_id, Edge.target_node_id]",
            "overlaps": "edges,outgoing_edges",
        },
    )

    __table_args__ = (
        PrimaryKeyConstraint("graph_id", "id"),
        ForeignKeyConstraint(["graph_id"], ["graphs.id"], ondelete="CASCADE"),
        Index("idx_nodes_graph_id", "graph_id"),
        Index("idx_nodes_type", "type"),
    )


class Edge(SQLModel, table=True):
    __tablename__ = "edges"

    # NOTE: 'id' here is the string ID from the frontend library
    id: str = Field(max_length=255, nullable=False)
    graph_id: uuid.UUID = Field(nullable=False)
    source_node_id: str = Field(max_length=255, nullable=False)
    target_node_id: str = Field(max_length=255, nullable=False)

    source_handle_id: Optional[str] = Field(default=None, max_length=255)
    target_handle_id: Optional[str] = Field(default=None, max_length=255)
    type: Optional[str] = Field(default=None, max_length=100)
    label: Optional[str] = Field(default=None, max_length=255)
    animated: bool = Field(default=False)
    style: Optional[dict[str, Any] | list[Any]] = Field(default=None, sa_column=Column(JSONB))
    data: Optional[dict[str, Any] | list[Any]] = Field(default=None, sa_column=Column(JSONB))
    markerEnd: Optional[dict[str, Any] | list[Any]] = Field(default=None, sa_column=Column(JSONB))

    graph: Optional[Graph] = Relationship(
        back_populates="edges",
        sa_relationship_kwargs={
            "overlaps": "incoming_edges,outgoing_edges",
        },
    )

    source_node: Optional[Node] = Relationship(
        back_populates="outgoing_edges",
        sa_relationship_kwargs={
            "foreign_keys": "[Edge.graph_id, Edge.source_node_id]",
            "overlaps": "edges,graph,incoming_edges",
        },
    )
    target_node: Optional[Node] = Relationship(
        back_populates="incoming_edges",
        sa_relationship_kwargs={
            "foreign_keys": "[Edge.graph_id, Edge.target_node_id]",
            "overlaps": "edges,graph,outgoing_edges,source_node",
        },
    )

    __table_args__ = (
        PrimaryKeyConstraint("graph_id", "id"),
        ForeignKeyConstraint(
            ["graph_id", "source_node_id"],
            ["nodes.graph_id", "nodes.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["graph_id", "target_node_id"],
            ["nodes.graph_id", "nodes.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(["graph_id"], ["graphs.id"]),
        Index("idx_edges_graph_id", "graph_id"),
        Index("idx_edges_source_node", "graph_id", "source_node_id"),
        Index("idx_edges_target_node", "graph_id", "target_node_id"),
    )


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            primary_key=True,
            server_default=func.uuid_generate_v4(),
            nullable=False,
        ),
    )
    username: str = Field(index=True, max_length=255, nullable=False)
    password: Optional[str] = Field(default=None, sa_column=Column(TEXT, nullable=True))
    email: Optional[str] = Field(default=None, sa_column=Column(TEXT))
    avatar_url: Optional[str] = Field(default=None, sa_column=Column(TEXT, nullable=True))
    oauth_provider: Optional[str] = Field(default=None, sa_column=Column(TEXT, nullable=True))
    oauth_id: Optional[str] = Field(default=None, sa_column=Column(TEXT, nullable=True))
    plan_type: str = Field(
        default="free", sa_column=Column(TEXT, nullable=False)
    )  # Options: "premium", "free"
    is_admin: bool = Field(default=False, nullable=False)

    created_at: Optional[datetime.datetime] = Field(
        default=None,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            server_default=func.now(),
            nullable=False,
        ),
    )
    updated_at: Optional[datetime.datetime] = Field(
        default=None,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        ),
    )

    refresh_tokens: list["RefreshToken"] = Relationship(
        back_populates="user", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    provider_tokens: list["ProviderToken"] = Relationship(
        back_populates="user", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    repositories: list["Repository"] = Relationship(
        back_populates="user", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class Settings(SQLModel, table=True):
    __tablename__ = "settings"

    id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            primary_key=True,
            server_default=func.uuid_generate_v4(),
            nullable=False,
        ),
    )
    user_id: uuid.UUID = Field(
        foreign_key="users.id",
        nullable=False,
        index=True,
        unique=True,  # Ensures one settings entry per user
    )

    # Store all settings as a single JSONB object
    settings_data: dict[str, Any] = Field(
        default={}, sa_column=Column(JSONB, nullable=False, server_default="{}")
    )

    created_at: Optional[datetime.datetime] = Field(
        default=None,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            server_default=func.now(),
            nullable=False,
        ),
    )
    updated_at: Optional[datetime.datetime] = Field(
        default=None,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        ),
    )


class Files(SQLModel, table=True):
    __tablename__ = "files"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            primary_key=True,
            server_default=func.uuid_generate_v4(),
            nullable=False,
        ),
    )
    user_id: uuid.UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    parent_id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("files.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    name: str = Field(max_length=255, nullable=False)
    type: str = Field(max_length=50, nullable=False)  # 'file' or 'folder'
    file_path: Optional[str] = Field(
        default=None, max_length=1024, nullable=True
    )  # Path on disk for 'local' provider
    size: Optional[int] = Field(default=None, sa_column=Column(DOUBLE_PRECISION, nullable=True))
    content_type: Optional[str] = Field(default=None, sa_column=Column(TEXT, nullable=True))
    storage_provider: str = Field(default="local", max_length=50, nullable=False)
    content_hash: Optional[str] = Field(
        default=None, sa_column=Column(TEXT, nullable=True, index=True)
    )

    created_at: datetime.datetime = Field(
        default_factory=datetime.datetime.now,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            server_default=func.now(),
            nullable=False,
        ),
    )
    updated_at: datetime.datetime = Field(
        default_factory=datetime.datetime.now,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        ),
    )

    __table_args__ = (Index("idx_files_user_parent", "user_id", "parent_id"),)


class RefreshToken(SQLModel, table=True):
    __tablename__ = "refresh_tokens"

    id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            primary_key=True,
            server_default=func.uuid_generate_v4(),
            nullable=False,
        ),
    )
    user_id: uuid.UUID = Field(
        foreign_key="users.id",
        nullable=False,
    )
    token: str = Field(max_length=255, nullable=False)
    expires_at: datetime.datetime = Field(
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False)
    )

    user: Optional["User"] = Relationship(back_populates="refresh_tokens")


class UsedRefreshToken(SQLModel, table=True):
    __tablename__ = "used_refresh_tokens"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    token: str = Field(index=True, unique=True, nullable=False)
    user_id: uuid.UUID = Field(foreign_key="users.id", nullable=False)
    expires_at: datetime.datetime = Field(
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False)
    )
    created_at: datetime.datetime = Field(
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False),
        default_factory=lambda: datetime.datetime.now(timezone.utc),
    )


class ProviderToken(SQLModel, table=True):
    __tablename__ = "provider_tokens"

    id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            primary_key=True,
            server_default=func.uuid_generate_v4(),
            nullable=False,
        ),
    )
    user_id: uuid.UUID = Field(
        foreign_key="users.id",
        nullable=False,
        index=True,
    )
    provider: str = Field(max_length=50, nullable=False, index=True)  # e.g., 'github'
    access_token: str = Field(sa_column=Column(TEXT, nullable=False))  # Should always be encrypted
    refresh_token: Optional[str] = Field(
        default=None, sa_column=Column(TEXT)
    )  # Encrypted, if present
    scopes: Optional[str] = Field(default=None, sa_column=Column(TEXT))  # e.g., "repo,read:user"
    expires_at: Optional[datetime.datetime] = Field(
        default=None, sa_column=Column(TIMESTAMP(timezone=True))
    )
    created_at: Optional[datetime.datetime] = Field(
        default=None,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            server_default=func.now(),
            nullable=False,
        ),
    )
    updated_at: Optional[datetime.datetime] = Field(
        default=None,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        ),
    )

    user: Optional["User"] = Relationship(back_populates="provider_tokens")

    __table_args__ = (
        Index("idx_provider_tokens_user_provider", "user_id", "provider", unique=True),
    )


class Repository(SQLModel, table=True):
    __tablename__ = "repositories"

    id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            primary_key=True,
            server_default=func.uuid_generate_v4(),
            nullable=False,
        ),
    )
    user_id: uuid.UUID = Field(foreign_key="users.id", nullable=False, index=True)
    provider: str = Field(default="github", max_length=50, nullable=False)
    repo_name: str = Field(max_length=255, nullable=False)  # e.g., "my-org/my-awesome-project"
    clone_url: str = Field(sa_column=Column(TEXT, nullable=False))
    local_path_uuid: uuid.UUID = Field(default_factory=uuid.uuid4, index=True, unique=True)
    status: str = Field(
        default="unpulled", max_length=50, nullable=False
    )  # States: unpulled, pulling, pulled, error
    error_message: Optional[str] = Field(default=None, sa_column=Column(TEXT))
    last_pulled_at: Optional[datetime.datetime] = Field(
        default=None, sa_column=Column(TIMESTAMP(timezone=True))
    )
    is_global: bool = Field(default=False, nullable=False)
    filter_config: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSONB))
    created_at: Optional[datetime.datetime] = Field(
        default=None,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            server_default=func.now(),
            nullable=False,
        ),
    )
    updated_at: Optional[datetime.datetime] = Field(
        default=None,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        ),
    )

    user: Optional["User"] = Relationship(back_populates="repositories")

    __table_args__ = (
        Index(
            "idx_repositories_user_repo_provider",
            "user_id",
            "repo_name",
            "provider",
            unique=True,
        ),
    )


async def create_initial_users(
    engine: SQLAlchemyAsyncEngine, userpass: list[UserPass] = []
) -> list[User]:
    """
    Create initial users from USERPASS environment variable if they don't exist.
    """
    users = []
    if userpass:
        async with AsyncSession(engine) as session:
            for user in userpass:
                stmt = select(User).where(
                    and_(User.username == user.username, User.oauth_provider == "userpass")
                )

                result = await session.execute(stmt)
                existing_user = result.scalar_one_or_none()
                if existing_user is None:
                    new_user = User(
                        id=uuid.uuid4(),
                        username=user.username,
                        password=user.password,
                        oauth_provider="userpass",
                    )
                    session.add(new_user)
                    users.append(new_user)
                else:
                    logging.info(f"User '{user.username}' already exists, skipping.")
            await session.commit()

            for created_user in users:
                await session.refresh(created_user)

            logging.info(f"Processed {len(userpass)} users from userpass string.")

    return users
