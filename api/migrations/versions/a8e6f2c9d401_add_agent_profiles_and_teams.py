from alembic import op
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "a8e6f2c9d401"
down_revision = "4e7a9c2b6d10"
branch_labels = None
depends_on = None

metadata = MetaData()
# Referenced existing tables are metadata-only and never created by this revision.
Table("users", metadata, Column("id", UUID(as_uuid=True), primary_key=True))
Table("graphs", metadata, Column("id", UUID(as_uuid=True), primary_key=True))


def identity():
    return Column("id", UUID(as_uuid=True), primary_key=True)


def owner():
    return Column(
        "owner_id",
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


def timestamp(name):
    return Column(name, DateTime(timezone=True), nullable=False, server_default=func.now())


agents = Table(
    "agent_profiles",
    metadata,
    identity(),
    owner(),
    Column("handle", String(50), nullable=False),
    Column("profile", JSONB, nullable=False),
    Column("version", Integer, nullable=False, server_default="1"),
    Column("verified", Boolean, nullable=False, server_default="false"),
    Column("source_id", UUID(as_uuid=True), ForeignKey("agent_profiles.id", ondelete="SET NULL")),
    Column("source_version", Integer),
    timestamp("created_at"),
    timestamp("updated_at"),
    UniqueConstraint("owner_id", "handle"),
)
versions = Table(
    "agent_versions",
    metadata,
    Column(
        "agent_id",
        UUID(as_uuid=True),
        ForeignKey("agent_profiles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("version", Integer, primary_key=True),
    Column("profile", JSONB, nullable=False),
    timestamp("created_at"),
)
teams = Table(
    "agent_teams",
    metadata,
    identity(),
    owner(),
    Column("name", String(100), nullable=False),
    Column("description", String(2000), nullable=False),
    timestamp("updated_at"),
)
memberships = Table(
    "agent_team_members",
    metadata,
    Column(
        "team_id",
        UUID(as_uuid=True),
        ForeignKey("agent_teams.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "agent_id",
        UUID(as_uuid=True),
        ForeignKey("agent_profiles.id", ondelete="RESTRICT"),
        primary_key=True,
    ),
    Column("position", Integer, nullable=False),
    UniqueConstraint("team_id", "position"),
)
bookmarks = Table(
    "agent_bookmarks",
    metadata,
    Column(
        "agent_id",
        UUID(as_uuid=True),
        ForeignKey("agent_profiles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    ),
    timestamp("created_at"),
)
ratings = Table(
    "agent_ratings",
    metadata,
    Column(
        "agent_id",
        UUID(as_uuid=True),
        ForeignKey("agent_profiles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    ),
    Column("value", Integer, nullable=False),
    CheckConstraint("value BETWEEN 1 AND 5"),
    timestamp("updated_at"),
)
usage = Table(
    "agent_usage",
    metadata,
    identity(),
    Column(
        "agent_id",
        UUID(as_uuid=True),
        ForeignKey("agent_profiles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    ),
    Column(
        "user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    ),
    timestamp("created_at"),
)
executions = Table(
    "agent_executions",
    metadata,
    identity(),
    owner(),
    Column(
        "graph_id", UUID(as_uuid=True), ForeignKey("graphs.id", ondelete="CASCADE"), nullable=False
    ),
    Column("node_id", String, nullable=False),
    Column("state", JSONB, nullable=False),
    timestamp("updated_at"),
)
AGENT_TABLES = [agents, versions, teams, memberships, bookmarks, ratings, usage, executions]


def upgrade() -> None:
    for table in AGENT_TABLES:
        table.create(op.get_bind(), checkfirst=False)


def downgrade() -> None:
    for table in reversed(AGENT_TABLES):
        table.drop(op.get_bind(), checkfirst=False)
