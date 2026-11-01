"""initial schema

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reps",
        sa.Column("rep_id", sa.String(length=20), nullable=False),
        sa.Column("rep_name", sa.String(length=100), nullable=False),
        sa.Column("territory", sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint("rep_id"),
    )
    op.create_table(
        "outlets",
        sa.Column("outlet_id", sa.String(length=20), nullable=False),
        sa.Column("outlet_name", sa.String(length=120), nullable=False),
        sa.Column("outlet_type", sa.String(length=40), nullable=False),
        sa.Column("tier", sa.String(length=1), nullable=False),
        sa.Column("city", sa.String(length=60), nullable=False),
        sa.Column("territory", sa.String(length=50), nullable=False),
        sa.Column("rep_id", sa.String(length=20), nullable=False),
        sa.Column("baseline_monthly_revenue", sa.Float(), nullable=False),
        sa.Column("days_since_last_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["rep_id"],
            ["reps.rep_id"],
        ),
        sa.PrimaryKeyConstraint("outlet_id"),
    )
    op.create_index(op.f("ix_outlets_rep_id"), "outlets", ["rep_id"], unique=False)
    op.create_table(
        "opportunities",
        sa.Column("opportunity_id", sa.String(length=20), nullable=False),
        sa.Column("outlet_id", sa.String(length=20), nullable=False),
        sa.Column(
            "opportunity_type",
            sa.Enum("Revenue Recovery", "Inactive Outlet", "Stock Risk", "Cross-Sell", name="opportunity_type"),
            nullable=False,
        ),
        sa.Column("severity", sa.Float(), nullable=False),
        sa.Column("value_at_stake", sa.Float(), nullable=False),
        sa.Column("priority_score", sa.Float(), nullable=False),
        sa.Column("priority_band", sa.String(length=2), nullable=False),
        sa.Column("queue_rank", sa.Integer(), nullable=True),
        sa.Column(
            "evidence", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False
        ),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(
            ["outlet_id"],
            ["outlets.outlet_id"],
        ),
        sa.PrimaryKeyConstraint("opportunity_id"),
        sa.UniqueConstraint("queue_rank"),
    )
    op.create_index(op.f("ix_opportunities_outlet_id"), "opportunities", ["outlet_id"], unique=False)
    op.create_index("ix_opportunities_priority", "opportunities", ["priority_score"], unique=False)
    op.create_index(
        "ix_opportunities_type_priority", "opportunities", ["opportunity_type", "priority_score"], unique=False
    )
    op.create_table(
        "actions",
        sa.Column("action_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("opportunity_id", sa.String(length=20), nullable=False),
        sa.Column("rep_id", sa.String(length=20), nullable=False),
        sa.Column("action_type", sa.Enum("visit", "call", name="action_type"), nullable=False),
        sa.Column("note", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.opportunity_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["rep_id"],
            ["reps.rep_id"],
        ),
        sa.PrimaryKeyConstraint("action_id"),
    )
    op.create_index("ix_actions_opportunity_created", "actions", ["opportunity_id", "created_at"], unique=False)
    op.create_table(
        "explanations",
        sa.Column("opportunity_id", sa.String(length=20), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("why_it_matters", sa.Text(), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column(
            "evidence_used",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.opportunity_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("opportunity_id"),
    )
    op.create_table(
        "outcomes",
        sa.Column("action_id", sa.Integer(), nullable=False),
        sa.Column(
            "outcome",
            sa.Enum("resolved", "follow_up", "no_response", "not_viable", name="outcome_type"),
            nullable=False,
        ),
        sa.Column("note", sa.String(length=1000), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["action_id"], ["actions.action_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("action_id"),
    )


def downgrade() -> None:
    op.drop_table("outcomes")
    op.drop_table("explanations")
    op.drop_index("ix_actions_opportunity_created", table_name="actions")
    op.drop_table("actions")
    op.drop_index("ix_opportunities_type_priority", table_name="opportunities")
    op.drop_index("ix_opportunities_priority", table_name="opportunities")
    op.drop_index(op.f("ix_opportunities_outlet_id"), table_name="opportunities")
    op.drop_table("opportunities")
    op.drop_index(op.f("ix_outlets_rep_id"), table_name="outlets")
    op.drop_table("outlets")
    op.drop_table("reps")
    for enum_name in ("outcome_type", "action_type", "opportunity_type"):
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
