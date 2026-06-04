"""app/main.py — FastAPI application entry point"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router

app = FastAPI(
    title       = "Plagiarism Signal Panel",
    description = "Similarity heuristics for LMS coding assignments. Day 2–3 sprint.",
    version     = "1.0.0",
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],   # tighten in production
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

app.include_router(router)


@app.get("/health", tags=["Meta"])
def health():
    return {"status": "ok"}
