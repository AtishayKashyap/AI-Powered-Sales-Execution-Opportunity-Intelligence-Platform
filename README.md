# SalesForge — AI Sales Execution Copilot

SalesForge is a portfolio-grade, AI-assisted CPG sales execution platform.

## Product thesis

Most analytics systems stop at:

`data → dashboard → insight`

SalesForge is designed around:

`data → detection → prioritization → recommendation → action → outcome → feedback`

The system identifies outlet-level sales opportunities and risks, prioritizes them for field sales teams, explains the evidence behind each recommendation, and records intervention outcomes.

## Planned stack

- Frontend: React + TypeScript
- Backend: FastAPI
- Database: PostgreSQL
- Analytics/ML: Python, Pandas, NumPy, SciPy, scikit-learn
- AI: LLM with structured outputs and evidence-grounded prompts
- Visualization: React charts / tables
- Automation: scheduled Python pipeline; optional n8n integration
- Deployment target: Docker + a cloud host

## Current milestone

This repository starts with the product specification, relational data model, and a reproducible synthetic CPG data generator.

### First implementation sequence

1. Generate synthetic CPG data.
2. Load and validate it.
3. Build feature tables.
4. Implement deterministic opportunity detection.
5. Implement opportunity scoring.
6. Build recommendation/task workflow.
7. Add evidence-grounded LLM explanations.
8. Build FastAPI endpoints.
9. Build React application.
10. Add intervention outcomes and feedback loop.
11. Test, containerize, document, and deploy.

## Important data note

The initial dataset is synthetic. It is intentionally generated with realistic business relationships and controlled scenarios such as declining outlets, cross-sell opportunities, inactive outlets, stock-risk signals, seasonal effects, and territory performance variation. No real company's proprietary data is represented.
