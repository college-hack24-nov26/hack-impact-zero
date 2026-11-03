from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

load_dotenv()

from app.api.repository import router as repository_router

app = FastAPI(title="FixReadme Engine (Groq Powered)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(repository_router, prefix="/api")

@app.get("/")
def read_root():
    return {"status": "FixReadme Engine Running", "llm_provider": "Groq API"}
