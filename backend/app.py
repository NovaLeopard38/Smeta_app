import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine  # noqa: imported so database schema is created
from models import Base  # noqa: ensure models registered
from auth import ensure_admin_user, ensure_revision_seed

from routers import auth as auth_router
from routers import admin
from routers import smetas
from routers import materials
from routers import voice
from routers import leads
from routers import site
from routers import seo
from ai.router import router as ai_router

app = FastAPI(title="Сметное приложение с AI")

allowed_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins.split(",") if origin.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(admin.router)
app.include_router(smetas.router)
app.include_router(materials.router)
app.include_router(voice.router)
app.include_router(leads.router)
app.include_router(seo.router)
app.include_router(site.router)
app.include_router(ai_router)


@app.on_event("startup")
def startup():
    ensure_admin_user()
    ensure_revision_seed()
