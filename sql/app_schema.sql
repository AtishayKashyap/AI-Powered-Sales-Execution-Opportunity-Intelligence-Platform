-- SalesForge PostgreSQL application schema.
-- SQLAlchemy models are the canonical application definition.

CREATE TABLE IF NOT EXISTS opportunities (
    opportunity_id VARCHAR(100) PRIMARY KEY,
    outlet_id VARCHAR(100) NOT NULL,
    opportunity_type VARCHAR(80) NOT NULL,
    score DOUBLE PRECISION NOT NULL,
    priority VARCHAR(10),
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    recommended_action TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_opportunities_outlet
    ON opportunities(outlet_id);

CREATE INDEX IF NOT EXISTS idx_opportunities_type
    ON opportunities(opportunity_type);

CREATE TABLE IF NOT EXISTS opportunity_actions (
    action_id SERIAL PRIMARY KEY,
    opportunity_id VARCHAR(100) NOT NULL REFERENCES opportunities(opportunity_id) ON DELETE CASCADE,
    outlet_id VARCHAR(100) NOT NULL,
    action_type VARCHAR(50) NOT NULL,
    rep_id VARCHAR(100),
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_actions_opportunity
    ON opportunity_actions(opportunity_id);

CREATE TABLE IF NOT EXISTS opportunity_outcomes (
    outcome_id SERIAL PRIMARY KEY,
    action_id INTEGER NOT NULL REFERENCES opportunity_actions(action_id) ON DELETE CASCADE,
    outcome VARCHAR(50) NOT NULL,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_outcomes_action
    ON opportunity_outcomes(action_id);

CREATE TABLE IF NOT EXISTS ai_explanations (
    explanation_id SERIAL PRIMARY KEY,
    opportunity_id VARCHAR(100) NOT NULL REFERENCES opportunities(opportunity_id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    why_it_matters TEXT NOT NULL,
    recommended_action TEXT NOT NULL,
    evidence_used JSONB NOT NULL DEFAULT '[]'::jsonb,
    confidence VARCHAR(20) NOT NULL,
    provider VARCHAR(50) NOT NULL DEFAULT 'unknown',
    model VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_explanations_opportunity
    ON ai_explanations(opportunity_id);
