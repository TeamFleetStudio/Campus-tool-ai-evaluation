from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers.api import router
from app.routers.build import router as build_router

app = FastAPI(
    title="Prompt Evaluation API",
    description="Evaluate participant prompting answers and build outputs using GPT-4o.",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(build_router)


@app.on_event("startup")
def on_startup():
    init_db()
