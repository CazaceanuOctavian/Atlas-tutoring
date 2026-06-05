# Import all models BEFORE creating tables
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from db.session import engine
from models.base import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables (DEV ONLY)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

app = FastAPI(lifespan=lifespan)

def create_app() -> FastAPI:
    app = FastAPI(
        title="Tutoring Platform API",
        version="1.0.0",
        description="Backend API for tutoring platform",
        lifespan=lifespan,
    )

    # ---------------------------
    # CORS (adjust for production)
    # ---------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # change in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---------------------------
    # Health Check
    # ---------------------------
    @app.get("/health", tags=["Health"])
    def health_check():
        return {"status": "ok"}

    return app


app = create_app()