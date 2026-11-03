from fastapi import FastAPI

from app.api.repository import router as repository_router

app = FastAPI(
    title="FixReadMe.md",
    description="AI-powered GitHub repository analysis and README generation.",
    version="0.2.1",
)


app.include_router(repository_router)


@app.get("/")
def root():
    return {
        "project": "FixReadMe.md",
        "version": "0.2.1",
        "message": "Backend is running",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "FixReadMe.md backend",
        "version": "0.2.1",
    }