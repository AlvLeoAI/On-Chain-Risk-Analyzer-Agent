# On-Chain Due Diligence Workstation

An AI-powered crypto due diligence workstation that turns protocol documents into structured, evidence-backed assessments you can revisit and extend over time.

## Overview

This project helps review crypto protocols from the materials analysts already use: whitepapers, audit reports, docs pages, and raw notes. The backend extracts a structured protocol profile with Gemini, scores risk with deterministic rules, stores the result in PostgreSQL, and returns evidence-backed findings to a Streamlit workstation built for repeatable review.

The current implementation is document-driven first. It is not a full autonomous security scanner, and its live on-chain verification is intentionally limited.

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

- The product is document-first and should not be presented as a full smart contract audit platform.
- Live on-chain verification is limited to contract-code presence checks on Ethereum, Base, and Arbitrum.
- There is no auth, tenant isolation, or collaboration model yet.
- Frontend automated tests are not in place yet.
- Input-size and deployment hardening are still lighter than a production multi-user system would require.

## Roadmap

- Add analyst notes to saved sessions
- Add watchlist and tagging workflows for recurring protocol coverage
- Improve provenance by tying evidence back to document names and page locations
- Harden the product for multi-user deployment with auth and better operational controls
- Expand supported verification paths beyond the current limited EVM checks

## Notes

This is a working diligence tool, not a claim of authoritative financial, legal, or security advice. It is strongest as an analyst assistant that speeds up first-pass protocol review while keeping the output structured and explainable.
