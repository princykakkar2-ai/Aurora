"""
backend/main.py
---------------
Main FastAPI application entrypoint for the Drug Interaction Graph Explorer.

Features:
  - Registers route modules: /drugs, /interactions, /stats
  - Root endpoint GET / with project info
  - Health endpoint GET /health
  - Automatic Swagger documentation available at /docs
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes import drugs, interactions, stats

# Initialize FastAPI app with descriptive metadata
app = FastAPI(
    title="Drug Interaction Graph Explorer API",
    version="1.0.0",
    description=(
        "Educational and research backend API for querying drug-drug interaction networks.\n\n"
        "**DISCLAIMER**: This application is for educational and research demonstration only. "
        "It reports strictly documented interactions from the dataset and DOES NOT provide clinical "
        "or medical advice."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

# Optional CORS middleware to support future frontend integration smoothly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register route modules
app.include_router(drugs.router)
app.include_router(interactions.router)
app.include_router(stats.router)


@app.get(
    "/",
    tags=["General"],
    summary="Root information endpoint",
    description="Returns welcome message and links to API documentation.",
)
def read_root():
    return {
        "message": "Drug Interaction Graph Explorer API",
        "docs_url": "/docs",
        "health_check": "/health",
        "version": "1.0.0",
    }


@app.get(
    "/health",
    tags=["General"],
    summary="API health status",
    description="Simple probe endpoint to verify that the API server is operational.",
)
def health_check():
    return {"status": "ok"}
