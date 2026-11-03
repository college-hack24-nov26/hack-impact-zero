# FixReadme Studio (Groq API Edition)

An automated documentation transformation engine that extracts, scores, and beautifies GitHub or local repository README files using Groq API.

## Features
- **Groq API LLM**: Powered by `llama-3.1-8b-instant` via Groq Cloud API.
- **GitHub Repository Extractor**: Auto-fetches raw README and detects tech stack from repo file trees.
- **30+ Shields.io Badges**: Integrated language, framework, database, and repository metrics badges.
- **Documentation Scoring Engine**: Evaluates documentation quality out of 100 before and after transformation.
- **Dual-Pane Interface**: Split raw vs enhanced editor with copy and download actions.

## Quick Start

### 1. Backend Setup
```bash
cd backend
python -m venv venv
# Windows PowerShell:
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt
cp .env.example .env
# Edit .env and set your GROQ_API_KEY=gsk_...

uvicorn app.main:app --reload --port 8000
```

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
