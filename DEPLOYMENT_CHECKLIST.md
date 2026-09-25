# SalesForge Deployment Checklist

## Before pushing

- [ ] `npm run build` passes in `frontend/`
- [ ] `pytest -q tests/test_ai_grounding.py` returns `2 passed`
- [ ] PostgreSQL-backed `/health` returns `status: ok`
- [ ] `/opportunities/top` returns the curated queue
- [ ] AI explanation works locally through Ollama
- [ ] Action persistence works
- [ ] Outcome persistence works
- [ ] Outcome-learning endpoint works
- [ ] No secrets or `.env` files are committed
- [ ] Large local model files are not committed
- [ ] Temporary QA ZIPs are not committed

## Render

The supplied `render.yaml` defines:

1. `salesforge-api` â€” FastAPI
2. `salesforge-frontend` â€” Vite static site
3. `salesforge-db` â€” PostgreSQL

After connecting the Git repository to Render:

### API environment variables

Set:

```text
DATABASE_URL = automatically supplied by the Render Postgres reference
CORS_ORIGINS = https://YOUR-SALESFORGE-FRONTEND.onrender.com
```

### Frontend environment variable

Set:

```text
VITE_API_URL = https://YOUR-SALESFORGE-API.onrender.com
```

Redeploy after setting the production API URL.

## Important AI deployment note

The current AI implementation calls a local Ollama endpoint:

```text
http://localhost:11434/api/generate
```

That is appropriate for the local technical demo but not for a normal hosted Render deployment.

Do not publish a deployment that silently claims live Qwen inference if the hosted API cannot reach Ollama.

For the portfolio demo, either:

- keep live AI as a local/demo capability and deploy the rest of the product, or
- add a separately hosted inference provider later.

## Render references

- FastAPI deployment: https://render.com/docs/deploy-fastapi
- Blueprint reference: https://render.com/docs/blueprint-spec
- Monorepo support: https://render.com/docs/monorepo-support
