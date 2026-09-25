# SalesForge — AI Sales Execution Copilot

SalesForge is a portfolio-grade CPG sales-execution system that turns outlet-level signals into a prioritized action queue, explains why an action matters, records field execution, and measures outcomes.

> **Data note:** SalesForge uses a controlled synthetic CPG environment. The synthetic scenarios validate system behavior and detection logic; they are not presented as evidence of commercial performance.

## Product thesis

```text
Data → Detection → Prioritization → Recommendation → Action → Outcome → Feedback
```

The core design separates deterministic decisioning from generative explanation:

- **Deterministic engine:** decides WHAT opportunity exists and WHAT should be prioritized.
- **LLM layer:** explains WHY the opportunity matters using only supplied evidence.
- **Execution layer:** records the action taken by a field representative.
- **Feedback layer:** measures observed outcomes without prematurely changing the detector.

## Architecture

```text
Synthetic CPG Data
       │
       ▼
Feature Store
       │
       ▼
Opportunity Detector
 ┌─────┼──────────┬──────────┐
 ▼     ▼          ▼          ▼
Revenue Inactive Stock     Cross-Sell
Recovery Outlet   Risk
 └─────┴──────────┴──────────┘
       │
       ▼
Priority Engine
       │
       ▼
Top-Action Queue
       │
       ├──────────────► AI Explanation
       │                    │
       ▼                    ▼
Field Action ◄──────── Recommended Action
       │
       ▼
Outcome
       │
       ▼
Outcome Learning
```

## Opportunity engine

The frozen V5 detector identifies:

- Revenue Recovery
- Inactive Outlet
- Stock Risk
- Cross-Sell

The priority engine assigns P1/P2/P3 bands using deterministic evidence-derived scoring. The top-action selector adds diversity constraints and preserves the original priority score.

## AI explanation layer

The LLM receives only the opportunity type, deterministic evidence, and the engine's recommended action.

The prompt explicitly prohibits:

- invented numbers
- invented products or causes
- invented customer facts
- unsupported dates or business events
- recomputation of supplied metrics
- outlet/opportunity identifiers in the explanation

The local implementation uses **Ollama / Qwen3:8B**.

Every generated explanation passes through schema validation and an evidence-grounding validator before being stored.

### Grounding QA

The project includes tests for both sides of the contract:

1. A grounded explanation is accepted.
2. An unsupported numeric claim is rejected.

Run:

```powershell
pytest -q tests/test_ai_grounding.py
```

Expected:

```text
2 passed
```

## Execution loop

Actions and outcomes are persisted in PostgreSQL:

```text
Opportunity
    ↓
OpportunityAction
    ↓
OpportunityOutcome
```

The frontend exposes this as:

**Select opportunity → AI explanation → plan action → record outcome**

The latest execution state can be retrieved from the backend.

## Outcome learning

The feedback layer currently reports:

- total actions
- outcomes recorded
- resolved outcomes
- resolution rate
- performance by opportunity type
- performance by action type

A minimum threshold is enforced before feedback is considered sufficient for future learning.

This is intentionally observational. A small number of synthetic outcomes does **not** automatically alter detection or priority logic.

## Evaluation

V5 benchmark results:

| Opportunity type | Planted | Detected | True positives | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| Revenue Recovery | 120 | 685 | 120 | 17.52% | 100% | 29.81% |
| Inactive Outlet | 100 | 477 | 100 | 20.96% | 100% | 34.66% |
| Stock Risk | 110 | 110 | 110 | 100% | 100% | 100% |
| Cross-Sell | 140 | 788 | 140 | 17.77% | 100% | 30.17% |
| **Overall** | **470** | **2,060** | **470** | **22.82%** | **100%** | **37.15%** |

These figures are benchmark measurements inside the controlled synthetic environment. Unplanted detections are not automatically equivalent to real-world false positives; the benchmark validates planted-scenario detection rather than commercial ground truth.

## Stack

### Data / analytics
- Python
- Pandas
- NumPy
- SciPy / scikit-learn where applicable
- Synthetic CPG transaction, inventory, visit and target data

### Backend
- FastAPI
- SQLAlchemy
- PostgreSQL
- Pydantic

### AI
- Ollama
- Qwen3:8B
- Structured JSON output
- Evidence-grounding validation

### Frontend
- React
- TypeScript
- Vite
- Lucide React

## Local setup

### PostgreSQL

Start the local database:

```powershell
docker compose -f docker-compose.postgres.yml up -d
```

### Backend

From the repository root:

```powershell
pip install -r requirements.txt
uvicorn backend.app.main:app --reload --port 8000
```

Health check:

```text
http://127.0.0.1:8000/health
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

The frontend reads the API URL from:

```text
VITE_API_URL
```

If it is not supplied, it defaults to:

```text
http://127.0.0.1:8000
```

## Deployment architecture

For a public portfolio deployment, use separate services:

```text
React/Vite static site
        │
        ▼
Public FastAPI service
        │
        ▼
Managed PostgreSQL
```

The local Ollama/Qwen process is deliberately **not** treated as a normal hosted dependency. A hosted AI provider or a separately managed inference service is required if the public deployment must generate live AI explanations.

The safest portfolio setup is therefore:

- deploy the dashboard and API/database independently;
- keep local Ollama/Qwen as the reproducible AI demonstration;
- clearly label any deployed fallback behavior rather than pretending local inference is hosted.

## Limitations

1. The data is synthetic.
2. Scenario labels are used only for evaluation, not detector decisioning.
3. The current feedback sample is intentionally insufficient for automatic model/priority recalibration.
4. Local Qwen inference is not equivalent to a production managed inference service.
5. Detection metrics should not be interpreted as commercial ROI.

## Product walkthrough

A strong demo should follow one opportunity end-to-end:

```text
1. Open Command Center
2. Select a P1 opportunity
3. Inspect deterministic evidence
4. Generate / view grounded AI explanation
5. Plan the field action
6. Record the outcome
7. Open Team / Outcome Learning
8. Show the execution metric update
9. Show that learning remains locked until the outcome threshold is met
```
