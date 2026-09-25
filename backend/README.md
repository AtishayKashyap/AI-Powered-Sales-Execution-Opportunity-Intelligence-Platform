# SalesForge FastAPI Backend

Phase 1 backend for the SalesForge AI Sales Execution Copilot.

## Run

From the SalesForge repository root:

```bash
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload
```

Then open:

```text
http://127.0.0.1:8000/docs
```

## Endpoints

- `GET /health`
- `GET /opportunities`
- `GET /opportunities/top`
- `GET /opportunities/{opportunity_id}`
- `POST /opportunities/{opportunity_id}/outcome`

The API reads the deterministic V5 CSV outputs. It does not modify the detector or priority logic.

## Architecture

Detector -> Priority Engine -> API -> React UI

AI explanation generation will plug into the opportunity detail endpoint after the
provider adapter is connected.
