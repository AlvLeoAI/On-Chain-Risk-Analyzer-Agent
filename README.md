# On-Chain Due Diligence Workstation

An AI-powered crypto due diligence workstation that turns protocol documents into structured, evidence-backed assessments you can revisit and extend over time.

## Overview

This project helps review crypto protocols from the materials analysts already use: whitepapers, audit reports, docs pages, and raw notes. The backend extracts a structured protocol profile with Gemini, scores risk with deterministic rules, stores the result in PostgreSQL, and returns evidence-backed findings to a Streamlit workstation built for repeatable review.

The current implementation is document-driven. It is not a full autonomous security scanner, and live on-chain verification is intentionally limited to a small set of EVM chains (see [Current Limitations](#current-limitations)).

## Key Features

- Multi-source intake from pasted text, uploaded PDFs, and fetched documentation URLs
- Structured protocol extraction into a consistent project profile
- Deterministic risk scoring across audit status, admin control, tokenomics, and identified vulnerabilities
- Evidence panel that surfaces supporting source snippets for profile claims and findings
- Session-based follow-up chat using saved analysis context and document retrieval
- Saved analysis history with session reload
- PDF export for a completed assessment
- Basic LLM usage tracking for token and cost visibility

## Architecture

### Frontend

`Frontend/` is a Streamlit workstation for:

- source intake
- session state
- result review
- evidence inspection
- follow-up chat
- saved-session recovery

### Backend

`Backend/` is a FastAPI service that:

- accepts analysis requests
- chunks and embeds documents
- extracts protocol data with Gemini
- applies deterministic scoring rules
- stores profiles, assessments, chat logs, embeddings, and usage events
- generates PDF reports

### Data Layer

PostgreSQL stores the durable analysis state, and `pgvector` powers retrieval over embedded document chunks.

### External Services

Gemini is used for structured extraction, embeddings, and follow-up answers. Public EVM RPC endpoints are used for a narrow contract-code presence check on supported chains.

## Tech Stack

- Python 3.12
- FastAPI
- Streamlit
- PostgreSQL
- SQLAlchemy
- Alembic
- pgvector
- Google Gemini via `google-genai`
- `web3.py`
- `fpdf2`

## Local Setup

### 1. Backend

```bash
cd Backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Required backend configuration:

- `DATABASE_URL`
- a Gemini API key via the env vars documented in [`Backend/.env.example`](Backend/.env.example)

### 2. Frontend

```bash
cd Frontend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
.venv/bin/python -m streamlit run Home.py
```

The frontend defaults to `http://127.0.0.1:8000` and can be overridden with `BACKEND_URL`.

## Usage & API Examples

### Basic usage flow

1. Start the backend (`uvicorn`) and the frontend (`streamlit run Home.py`).
2. In the workstation, paste a whitepaper, upload a PDF, or fetch a documentation URL.
3. Run the assessment to generate a structured profile and risk score.
4. Review the findings and use the chat panel for follow-up questions.
5. Export a PDF report from the workspace once you are satisfied with the analysis.

### Health check

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{
  "status": "ok",
  "database": "ok"
}
```

### Run an analysis

```bash
curl -X POST http://127.0.0.1:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{
        "session_id": "demo-session-001",
        "document_text": "ExampleDAO is a decentralized lending protocol on Base. Audited by Certik in Q4 2024. Total supply: 100,000,000 EXD. Team allocation: 15%, vested over 4 years. Liquidity is locked for 12 months.",
        "source_url": null
      }'
```

Truncated sample response:

```json
{
  "session_id": "demo-session-001",
  "project_profile": {
    "project_name": "ExampleDAO",
    "chain": "BASE",
    "category": "LENDING",
    "audit_status": "AUDITED",
    "tokenomics": {
      "total_supply": 100000000,
      "team_allocation_percentage": 15,
      "liquidity_locked": true
    }
  },
  "risk_assessment": {
    "risk_score": 88,
    "risk_level": "Safe",
    "flagged_issues": [],
    "positive_signals": [
      "Audited by Certik",
      "Liquidity locked for 12 months"
    ],
    "recommended_action": "Proceed with standard diligence."
  },
  "evidence": [
    {
      "field": "audit_status",
      "status": "Explicit",
      "snippet": "Audited by Certik in Q4 2024."
    }
  ]
}
```

### Ask a follow-up question

```bash
curl -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
        "session_id": "demo-session-001",
        "question": "What is the team allocation and how is it vested?"
      }'
```

Sample response:

```json
{
  "answer": "The team allocation is 15% of the 100,000,000 EXD total supply, vested over 4 years."
}
```

> The examples above use placeholder payloads. Do not paste real API keys into request bodies; the backend reads `GOOGLE_API_KEY` from the environment.

## Repository Structure

- [`Backend/`](Backend): FastAPI API, risk engine, database models, migrations, tests, eval assets, and developer verification scripts
- [`Frontend/`](Frontend): Streamlit workstation and frontend utilities
- [`docs/`](docs): product, UX, and audit documentation
- [`README.md`](README.md): public project overview

## Security And Configuration Notes

- Do not commit `.env` files, API keys, database URLs, or local deployment credentials.
- Use the example files in [`Backend/.env.example`](Backend/.env.example) and [`Frontend/.env.example`](Frontend/.env.example) as the public-safe starting point.
- Backend CORS defaults are limited to local Streamlit origins and can be overridden with `CORS_ORIGINS` when needed.
- The current app is best treated as a personal or single-operator workstation. If you deploy it for shared use, add authentication, authorization, and rate limiting first.
- Source documents and chat history are persisted in the backend database, so database access should be treated as sensitive.

## Current Limitations

- **Document-first scope.** The system is designed for document-driven due diligence, not real-time on-chain monitoring. Analysis quality depends on the completeness of the submitted source documents.
- **Limited on-chain verification.** Contract verification currently supports only Ethereum, Base, and Arbitrum. Projects on Solana, Hedera, or other chains will show 'unverified' for contract status, though the rest of the analysis still runs normally.
- **Single-operator workstation.** There is no authentication, tenant isolation, or collaboration model yet. Treat the deployed instance as a personal tool unless you add an auth layer first.
- **No frontend test suite.** Streamlit pages are exercised manually; only the backend has automated test coverage.
- **Lighter operational hardening.** Input-size limits, rate limiting, and observability are intentionally minimal compared with what a multi-user production deployment would need.

## Roadmap

- Add analyst notes to saved sessions
- Add watchlist and tagging workflows for recurring protocol coverage
- Improve provenance by tying evidence back to document names and page locations
- Harden the product for multi-user deployment with auth and better operational controls
- Expand supported verification paths beyond the current limited EVM checks

## Notes

This is a working diligence tool, not a source of authoritative financial, legal, or security advice. It is strongest as an analyst assistant that speeds up first-pass protocol review while keeping the output structured and explainable.
