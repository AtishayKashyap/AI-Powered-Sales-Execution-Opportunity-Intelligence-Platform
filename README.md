# SalesForge

### AI-Powered CPG Sales Execution Intelligence

SalesForge is an end-to-end sales-execution system that transforms outlet-level CPG sales, inventory, visit, and target data into **prioritized opportunities and actionable recommendations for field sales representatives**.

Instead of stopping at dashboards and descriptive analytics, SalesForge closes the loop:

**Detect → Prioritize → Explain → Act → Record Outcome → Recover Execution State**

> **Core principle:** deterministic analytics decides **WHAT** needs attention; the AI layer helps explain **WHY** it matters and communicates the recommended action using grounded evidence.

---

## Live Demo

**Application:** https://salesforge-frontend.onrender.com

**API:** https://salesforge-api-5c6d.onrender.com

---

## Why SalesForge?

Field sales teams can have thousands of outlets but limited time to visit them.

A traditional analytics workflow might expose:

```text
Sales Data → Dashboard → Human Interpretation → Manual Decision
```

SalesForge turns that into:

```text
Sales / Inventory / Visit Data
            ↓
     Opportunity Detection
            ↓
      Priority Scoring
            ↓
       Action Queue
            ↓
  Evidence-Grounded Explanation
            ↓
       Field Action
            ↓
      Outcome Capture
            ↓
     Execution Feedback
```

The goal is not to replace the sales representative's judgment. It is to help the representative spend limited field time on the opportunities that deserve attention.

---

## Key Capabilities

| Capability | Description |
|---|---|
| Opportunity Detection | Identifies revenue recovery, inactive outlet, stock risk, and cross-sell opportunities |
| Priority Scoring | Scores and prioritizes detected opportunities |
| Action Queue | Produces a focused queue of high-priority outlet actions |
| Evidence-Grounded AI | Explains recommendations using structured opportunity evidence |
| Field Execution | Allows representatives to record actions taken |
| Outcome Capture | Records the result of an executed action |
| Execution State | Recovers the latest action/outcome after page refresh |
| PostgreSQL Persistence | Stores opportunities, actions, outcomes, and AI explanations |
| Production Deployment | React frontend + FastAPI backend + PostgreSQL |

---

## Opportunity Types

### Revenue Recovery

Detects meaningful deterioration in outlet revenue and surfaces the outlet for investigation and recovery action.

### Inactive Outlet

Identifies outlets showing a lack of recent ordering/activity and recommends re-engagement.

### Stock Risk

Identifies repeated stockout or low-stock behavior and surfaces the outlet for replenishment or availability investigation.

### Cross-Sell

Identifies outlets eligible for additional product/category opportunities based on the project's controlled cross-sell eligibility logic.

---

## Architecture

The high-level architecture is:

```text
Synthetic CPG Data
        ↓
Feature Engineering
        ↓
Opportunity Detection
        ↓
Priority Scoring
        ↓
Top Action Selection
        ↓
Evidence-Grounded Explanation
        ↓
React Sales Copilot
        ↓
Field Action
        ↓
FastAPI
        ↓
PostgreSQL
        ↓
Execution State
        ↓
React Sales Copilot
```

SalesForge deliberately separates **business decisioning** from **language generation**.

```text
Structured Data
      ↓
Deterministic Analytics
      ↓
Opportunity + Evidence + Priority
      ↓
AI Explanation
      ↓
Human Field Execution
```

The AI layer does not decide that an outlet has a revenue or inventory problem. Those signals are produced by the analytics pipeline.

For the detailed system architecture, data flow, database model, API boundaries, and evaluation methodology, see [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## Data Pipeline

The project uses a controlled synthetic CPG environment.

The generated dataset contains:

- Territories
- Distributors
- Sales representatives
- Outlets
- Products
- Orders
- Order items
- Inventory snapshots
- Visits
- Targets

The primary dataset covers:

**1 January 2025 → 31 December 2025**

The application therefore displays:

**DATA CUTOFF - 31 DEC 2025**

This is the analytical cutoff of the dataset, not the current date.

---

## Synthetic Data and Benchmarking

Public outlet-level CPG sales-execution data is generally limited because these datasets often contain commercially sensitive information.

SalesForge therefore uses controlled synthetic data so that specific scenarios can be planted and evaluated.

The V5 scenario set planted:

| Scenario | Planted |
|---|---:|
| Revenue Recovery | 120 |
| Inactive Outlet | 100 |
| Stock Risk | 110 |
| Cross-Sell | 140 |
| **Total** | **470** |

The resulting opportunity pipeline produced:

**2,060 detected opportunities**

The benchmark recovered all planted scenarios:

**470 / 470 planted scenarios detected**

This corresponds to **100% recall on the controlled planted benchmark**.

However, the additional detected opportunities are not automatically treated as false business opportunities. In a real environment, an unplanted outlet could still represent a legitimate business opportunity.

Therefore, the benchmark should be interpreted as:

> **Validation that the detector can recover known planted scenarios, not proof of commercial business performance.**

---

## Prioritized Action Queue

From the 2,060 detected opportunities, SalesForge creates a focused top-action queue.

Current queue:

**20 unique outlets**

| Opportunity Type | Actions |
|---|---:|
| Revenue Recovery | 7 |
| Cross-Sell | 5 |
| Stock Risk | 5 |
| Inactive Outlet | 3 |

The prioritization pipeline currently produces:

| Priority | Opportunities |
|---|---:|
| P1 | 148 |
| P2 | 351 |
| P3 | 1,561 |

The top-action queue turns a large opportunity universe into a manageable field-execution workload.

---

## AI Design

SalesForge uses AI downstream of the deterministic opportunity engine.

The explanation layer receives structured opportunity information such as:

- Opportunity type
- Priority
- Score
- Evidence
- Recommended action
- Supporting metrics

The system is designed so that the AI layer does not invent numeric business evidence.

### Deterministic fallback

The application also contains a deterministic explanation fallback.

If an external AI provider is unavailable, the system can still present an evidence-grounded explanation generated from the structured opportunity data.

This makes the deployed demo independent of a live LLM dependency.

---

## Execution Loop

The application is designed around an execution feedback loop rather than a one-way dashboard.

```text
Opportunity
     ↓
Explanation
     ↓
Recommended Action
     ↓
Sales Representative Executes
     ↓
Action Recorded
     ↓
Outcome Recorded
     ↓
Execution State Persisted
     ↓
State Recovered on Refresh
```

This allows the system to represent what happened after an opportunity was surfaced.

---

## Technology Stack

### Data & Analytics

- Python
- Pandas
- NumPy
- SciPy
- scikit-learn

### Backend

- FastAPI
- SQLAlchemy
- PostgreSQL
- psycopg
- Pydantic

### Frontend

- React
- TypeScript
- Vite

### Infrastructure

- Docker for local PostgreSQL
- Render for production deployment

---

## Repository Structure

```text
SalesForge/
│
├── backend/
│   └── app/
│       ├── main.py
│       ├── models.py
│       ├── db.py
│       ├── init_db.py
│       └── seed_db.py
│
├── frontend/
│   └── src/
│       └── App.tsx
│
├── scripts/
│   ├── generate_data.py
│   ├── generate_scenarios_v5.py
│   ├── build_features_v5.py
│   ├── detect_opportunities_v5.py
│   ├── prioritize_opportunities_v5.py
│   ├── select_top_actions_v5.py
│   └── explain_opportunity_v5.py
│
├── data/
│   ├── generated_v5/
│   ├── processed_v5/
│   └── seed/
│
├── render.yaml
├── requirements.txt
├── ARCHITECTURE.md
└── README.md
```

---

## Running Locally

### Prerequisites

- Python 3.11+
- Node.js
- npm
- PostgreSQL 16 or Docker

### Backend

From the project root:

```bash
pip install -r requirements.txt
```

Configure the database connection using `DATABASE_URL`.

Example local database URL:

```text
postgresql+psycopg://routeiq:routeiq@localhost:5432/routeiq
```

Initialize/seed the database:

```bash
python -m backend.app.seed_db
```

Start the API:

```bash
uvicorn backend.app.main:app --reload
```

The local API runs on:

```text
http://127.0.0.1:8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

For a production build:

```bash
npm run build
```

The frontend reads the API URL from:

```text
VITE_API_URL
```

---

## API

The backend exposes endpoints for:

- Health checks
- Opportunity retrieval
- Top-priority opportunities
- AI explanations
- Field actions
- Outcomes
- Execution-state recovery
- Analytics

One important execution endpoint is:

```text
GET /opportunities/{opportunity_id}/execution-state
```

It returns the latest saved action and outcome associated with an opportunity.

API documentation is available through FastAPI when the backend is running:

```text
http://127.0.0.1:8000/docs
```

---

## Production Deployment

SalesForge is deployed as three production components:

```text
React Static Site
       │
       ▼
FastAPI Web Service
       │
       ▼
PostgreSQL Database
```

Production frontend:

```text
https://salesforge-frontend.onrender.com
```

Production API:

```text
https://salesforge-api-5c6d.onrender.com
```

The deployment configuration is defined in:

```text
render.yaml
```

---

## Engineering Decisions

### Why deterministic detection?

Opportunity detection affects business actions, so it should be reproducible and auditable.

### Why AI after detection?

The AI layer is useful for communicating complex signals to a human user, but it should not be responsible for inventing the underlying business evidence.

### Why PostgreSQL?

The application needs persistent relational state for opportunities, actions, outcomes, and their relationships.

### Why an execution-state endpoint?

A sales-execution application must remember what happened after an opportunity was surfaced. Persistence makes the workflow stateful instead of treating every page load as a fresh analysis.

---

## Limitations

SalesForge is a portfolio/research prototype built using controlled synthetic CPG data.

The benchmark does **not** establish:

- commercial sales uplift
- real-world model accuracy
- production-scale performance
- causal impact of recommendations
- real customer adoption

A production implementation would require real transactional data, business-defined thresholds, authentication/authorization, monitoring, stronger data validation, model evaluation, and integration with existing CRM/field-sales systems.

---

## Future Extensions

Potential next steps include:

- Real CPG/retail data integration
- Rep-level personalization
- Learning from action outcomes
- Offline evaluation against historical outcomes
- More sophisticated opportunity ranking
- LLM provider integration with structured outputs
- Authentication and role-based access
- CRM integration
- Automated daily opportunity refresh
- Experimentation/A-B testing of recommended actions
- Monitoring and model/data drift detection

---

## Project Status

**Status: Working production MVP**

The current implementation supports the complete flow from opportunity detection through field-action and outcome persistence.

---

## Author

**Atishay Kashyap**

B.Tech Computer Science & Engineering

SalesForge was built as an independent portfolio project exploring the intersection of:

**Data Analytics × AI × Sales Execution × Full-Stack Engineering**
