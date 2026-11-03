from fastapi import FastAPI

app = FastAPI(
    title="FixReadMe.md",
    description="AI-powered GitHub repository analysis and README generation.",
    version="0.1.6",
)


@app.get("/")
def root():
    return {
        "project": "FixReadMe.md",
        "version": "0.1.6",
        "message": "Backend is running",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "FixReadMe.md backend",
        "version": "0.1.6",
    }