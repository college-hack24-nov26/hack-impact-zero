from fastapi import FastAPI

app = FastAPI(
    title="FixReadMe.md",
    description="AI-powered GitHub repository analysis and README generation.",
    version="0.1.4",
)


@app.get("/")
def root():
    return {
        "project": "FixReadMe.md",
        "version": "0.1.4",
        "message": "Backend is running"
    }