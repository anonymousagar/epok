from fastapi import FastAPI
from api.routes.linear import router as linear_router
from api.routes.slack import router as slack_router
from api.routes.github import router as github_router

app = FastAPI(
    title="Epok Agentic Gateway",
    description="Webhook Ingestion & Agent Swarm Gateway",
    version="0.1.0"
)

app.include_router(linear_router)
app.include_router(slack_router)
app.include_router(github_router)


@app.get("/healthz", tags=["Health"])
async def health_check():
    return {"status": "ok"}