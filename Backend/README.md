# On-Chain Fundamentals & Risk Analyzer - Backend

## Overview
The backend is a FastAPI application that powers the On-Chain Fundamentals & Risk Analyzer. It orchestrates the extraction of project fundamentals using Gemini 2.5 Flash and evaluates the risk using a deterministic risk scoring engine.

## Tech Stack
- **Framework:** FastAPI, Python 3.12+
- **LLM:** `google-genai` (Gemini 2.5 Flash)
- **Database:** PostgreSQL (Supabase) via SQLAlchemy (asyncpg)
- **Migrations:** Alembic

## Core Modules
- `app/agent.py`: Uses `google-genai` to act as a Smart Contract Auditor, extracting structured protocol data (Tokenomics, Vulnerabilities) from unstructured text.
- `app/engine.py`: Contains the deterministic risk engine that computes a final `RiskLevel` (Safe, Moderate, High, Critical) based on extracted data.
- `app/models.py` / `app/db/models.py`: Pydantic and SQLAlchemy models for `ProjectProfile`, `RiskAssessment`, etc.
- `main.py`: The main FastAPI application exposing the `/api/v1/analyze` endpoint.

## Setup & Execution
1. Install dependencies:
   ```bash
   python -m venv .venv
   . .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Configure environment variables (copy `.env.example` to `.env` if available, and set your `GEMINI_API_KEY`, `DATABASE_URL`, etc.).
3. Run database migrations:
   ```bash
   .venv/bin/alembic upgrade head
   ```
4. Start the development server:
   ```bash
   .venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```
   *Note: Ensure you run this from within the `Backend/` directory.*

## Testing
Run tests using pytest:
```bash
.venv/bin/python -m pytest
```
