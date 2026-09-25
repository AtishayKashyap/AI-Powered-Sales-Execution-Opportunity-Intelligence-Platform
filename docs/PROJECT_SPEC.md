# SalesForge Product Specification

## 1. Problem

Field sales managers can have large amounts of transaction, outlet, product, distributor, visit, inventory, and target data without having a clear answer to:

- Which outlets need attention today?
- Why do they need attention?
- Which action should a sales representative take?
- Which opportunities are economically meaningful?
- Did the intervention actually work?

SalesForge converts operational data into prioritized, explainable actions.

## 2. Primary users

### Regional Sales Manager
Needs:
- territory performance
- prioritized opportunities
- rep workload
- risks
- AI-generated business brief
- intervention outcomes

### Field Sales Representative
Needs:
- today's prioritized tasks
- outlet context
- reason for recommendation
- recommended action
- ability to complete/dismiss a task
- outcome capture

### Business/Operations Analyst
Needs:
- KPI definitions
- opportunity logic
- model performance
- data-quality status
- recommendation effectiveness

## 3. Core workflows

### Workflow A — Daily opportunity generation

1. Ingest latest data.
2. Validate schema and business rules.
3. Build outlet/product/rep features.
4. Detect opportunity signals.
5. Score opportunities.
6. Deduplicate overlapping signals.
7. Create recommended actions.
8. Publish daily task lists.

### Workflow B — Rep action

1. Rep opens today's tasks.
2. Reviews outlet evidence.
3. Accepts/starts task.
4. Records visit/action.
5. Records outcome.
6. System stores outcome against recommendation.

### Workflow C — Manager investigation

1. Manager selects territory.
2. Reviews KPI changes.
3. Opens opportunity clusters.
4. Requests an AI explanation.
5. AI receives only relevant structured evidence.
6. AI returns a structured explanation and recommended next investigation.

## 4. Opportunity types

### Revenue Recovery
Historical high-value outlet with material recent decline.

### Inactive Outlet
Previously active outlet with no recent order.

### Cross-Sell
Outlet has a product-assortment gap relative to comparable outlets.

### Distribution Gap
Outlet/territory has lower product penetration than comparable peers.

### Stock-Risk
Inventory/demand signals indicate possible stock-out or availability problem.

### Rep Productivity
Sales execution signal indicates unusually low productive-call or order conversion performance.

## 5. Opportunity scoring

Initial deterministic score:

`Score = 0.30 Revenue Potential
       + 0.20 Confidence
       + 0.15 Recency
       + 0.15 Outlet Value
       + 0.10 Behaviour Signal
       + 0.10 Actionability`

Each component is normalized to 0–100.

The score is a prioritization mechanism, not a claim of causal impact.

Later milestone:
- compare deterministic scoring against an ML ranking model
- evaluate precision@K / recall@K against synthetic ground-truth scenarios

## 6. Recommendation policy

The system must separate:

- evidence
- detected signal
- score
- recommended action
- AI explanation

The LLM must not create numerical evidence. All numbers in an explanation must originate from structured evidence supplied by the application.

## 7. MVP success criteria

The MVP is successful when it can:

- generate reproducible synthetic data
- validate the data
- identify planted opportunity scenarios
- rank opportunities
- show evidence for every recommendation
- assign tasks to reps
- record task outcomes
- produce an evidence-grounded AI explanation
- expose the workflow through an API and web UI

## 8. Non-goals for MVP

- Real CRM integration
- Real customer/company data
- Autonomous ordering
- Autonomous sales communication
- Financial forecasting presented as certainty
- Fully autonomous AI agents taking irreversible actions

## 9. Product differentiation

SalesForge should not become another BI dashboard.

The product's central object is an `Opportunity`, not a chart.

Every opportunity should answer:

1. What happened?
2. Why is it important?
3. What should happen next?
4. What evidence supports that recommendation?
5. What happened after the action?
