from typing import Optional, Any
import datetime
import logging
import uuid

from sqlalchemy import (
    Column,
    ForeignKeyConstraint,
    Index,
    PrimaryKeyConstraint,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.dialects.postgresql import JSONB, DOUBLE_PRECISION, TEXT, TIMESTAMP
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine, AsyncSession

from sqlmodel import Field, Relationship, SQLModel, ForeignKey

from models.auth import UserPass


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
    description: Optional[str] = Field(default=None, sa_column=Column(TEXT)) # not used

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
    custom_instructions: Optional[str] = Field(
        default=None, sa_column=Column(TEXT, nullable=True)
    )
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

    data: Optional[dict[str, Any] | list[Any]] = Field(
        default=None, sa_column=Column(JSONB)
    )

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
    style: Optional[dict[str, Any] | list[Any]] = Field(
        default=None, sa_column=Column(JSONB)
    )
    data: Optional[dict[str, Any] | list[Any]] = Field(
        default=None, sa_column=Column(JSONB)
    )
    markerEnd: Optional[dict[str, Any] | list[Any]] = Field(
        default=None, sa_column=Column(JSONB)
    )

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
    avatar_url: Optional[str] = Field(
        default=None, sa_column=Column(TEXT, nullable=True)
    )
    oauth_provider: Optional[str] = Field(
        default=None, sa_column=Column(TEXT, nullable=True)
    )
    oauth_id: Optional[str] = Field(default=None, sa_column=Column(TEXT, nullable=True))

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
    filename: str = Field(max_length=255, nullable=False)
    file_path: str = Field(max_length=255, nullable=False)
    size: Optional[int] = Field(
        default=None, sa_column=Column(DOUBLE_PRECISION, nullable=True)
    )
    content_type: Optional[str] = Field(
        default=None, sa_column=Column(TEXT, nullable=True)
    )
    created_at: Optional[datetime.datetime] = Field(
        default=None,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            server_default=func.now(),
            nullable=False,
        ),
    )


async def init_db(
    engine: SQLAlchemyAsyncEngine, userpass: list[UserPass] = None
) -> list[User]:
    """
    Initialize the database by creating all tables defined in SQLModel models.

    This function creates all tables in the database that are defined in the
    SQLModel models. It uses the provided engine to connect to the database.

    Args:
        engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine instance connected to the database.

    Example:
        ```python
        from sqlmodel import SQLModel
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = await get_async_engine()
        await init_db(engine)
        ```
    """
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    users = []
    if userpass:
        async with AsyncSession(engine) as session:
            for user in userpass:
                stmt = (
                    select(User)
                    .where(User.username == user.username)
                    .where(User.oauth_provider == "userpass")
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

            for user in users:
                await session.refresh(user)

            logging.info(f"Processed {len(userpass)} users from userpass string.")

    return users
