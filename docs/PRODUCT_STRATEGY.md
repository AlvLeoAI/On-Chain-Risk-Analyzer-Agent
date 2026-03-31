# Product Strategy

## Product Positioning
Inference: the clearest product positioning supported by the current codebase is:

**An AI-assisted protocol due diligence tool that converts messy crypto project documentation into a structured, explainable risk assessment.**

This framing is stronger and more accurate than describing the system as a full autonomous security scanner. The implementation is document-first: it analyzes whitepapers, audits, PDFs, and URLs, then combines LLM extraction with deterministic scoring and limited live on-chain checks.

## Who This Product Is For
The most credible current audience is:

- Crypto researchers performing protocol due diligence.
- Security-minded investors or analysts reviewing early-stage DeFi projects.
- Builders, auditors, or ecosystem teams who want a fast first-pass protocol review.
- Portfolio reviewers who need a standardized summary instead of reading raw documentation end to end.

Inference: the product currently feels best suited for individual analysts or small internal workflows, not yet for enterprise compliance or large-team collaboration.

## Core User Problem
Protocol due diligence is slow, inconsistent, and fragmented across multiple sources. A user may need to read a whitepaper, audit PDF, docs site, and GitHub README before forming even a basic view of audit status, admin control, tokenomics risk, or obvious red flags.

This product addresses the first layer of that problem: turning unstructured protocol materials into a consistent profile, risk score, and follow-up question workflow.

## Proposed Value Proposition
**Upload protocol documentation and receive a structured profile, deterministic risk score, explainable findings, and a reusable session for follow-up analysis.**

Why that matters:
- It reduces time spent manually extracting basic diligence signals.
- It gives users a repeatable output format across different protocols.
- It pairs LLM flexibility with rule-based scoring, which makes the result more explainable than a pure chat response.
- It preserves context through chat history, embeddings, and downloadable reporting.

## Main Inputs
Supported inputs in the current implementation:

- Pasted raw text.
- Uploaded PDF files.
- URL-based text extraction.
- Multiple documents submitted within one analysis session.

Operational inputs on the backend:
- Gemini API access.
- PostgreSQL with Alembic-managed schema and pgvector support.
- Public RPC endpoints for limited EVM contract-code checks.

## Main Outputs
Current outputs include:

- A structured `ProjectProfile`.
- A deterministic `RiskAssessment` with risk score, level, flagged issues, positive signals, and recommended action.
- A list of missing fields the model could not confidently extract.
- Session-based follow-up chat responses.
- A generated PDF report.
- Persisted backend records for projects, assessments, embeddings, chat logs, and LLM usage events.

## MVP Scope
The MVP boundary supported by the repository is:

- Single-session protocol analysis through a Streamlit dashboard.
- Multi-document ingestion for one protocol review.
- LLM-assisted extraction into a defined schema.
- Deterministic scoring for common protocol risk factors.
- Persisted analysis state and follow-up chat.
- Exportable PDF summary.

Out of scope for the current MVP:
- Wallet integrations.
- Real-time monitoring or alerting.
- Team collaboration, auth, or permissions.
- Broad on-chain forensic analysis.
- Production-grade analyst dashboards or portfolio-level analytics.
- A polished commercial SaaS workflow.

## What Is Already Implemented
Implemented capabilities visible in the codebase:

- FastAPI endpoints for health, analysis, chat, and report download.
- Gemini-based extraction and Q&A.
- Session-aware storage of profiles, assessments, embeddings, usage events, and chat logs.
- RAG-style retrieval using pgvector-backed document embeddings.
- Deterministic scoring across audit status, centralization, tokenomics, vulnerabilities, and basic on-chain contract presence.
- Streamlit intake flow for text, PDFs, and URLs.
- Report generation in PDF format.
- Basic backend tests, evaluation assets, sample payloads, and local verification scripts.

## What Seems Partial or Missing
Observed gaps or incompleteness:

- Live verification is limited and only implemented for a subset of EVM networks.
- Product messaging currently implies broader chain coverage than the code demonstrates.
- Frontend remains a thin single-page workflow rather than a polished product surface.
- No evidence of auth, user accounts, saved workspaces, or analyst collaboration.
- Frontend automated tests are absent.
- Some setup and packaging details appear out of sync with code, including dependency declarations and CI references.
- Deployment documentation is still minimal.

## Key Differentiators
What makes this project stand out as a portfolio piece:

- It combines **LLM extraction** with **deterministic scoring**, which is more credible than an AI-only summary tool.
- It supports **multi-format intake**: pasted text, PDFs, and URLs.
- It preserves analytical context through **session-based chat** instead of treating each prompt as stateless.
- It stores analysis artifacts in a real backend data model rather than remaining a pure demo app.
- It includes **cost tracking** for Gemini usage, which shows operational awareness beyond a prototype.
- It produces an exportable PDF, making the output more presentation-ready for a diligence workflow.

## Risks and Limitations
- The system depends heavily on the quality and completeness of the supplied documents.
- LLM extraction improves speed, but it does not eliminate ambiguity or hallucination risk.
- The deterministic engine is explainable, but it reflects the scoring assumptions currently encoded in `app/engine.py`.
- On-chain verification is narrow and should not be confused with full contract auditing.
- Current repository drift in tests, dependencies, and deployment config makes the product feel earlier-stage than the core concept deserves.
- The product should be presented as a **diligence assistant**, not as authoritative financial, legal, or security advice.

## Best Portfolio/Resume Description
**Portfolio framing:**  
Built an AI-assisted crypto protocol due diligence platform that ingests whitepapers, audits, PDFs, and URLs, extracts structured protocol fundamentals with Gemini, applies deterministic risk scoring, supports follow-up RAG-based analysis, and generates exportable PDF reports through a FastAPI + Streamlit architecture.

**Resume framing:**  
Developed a document-driven protocol risk analysis system using FastAPI, Streamlit, PostgreSQL/pgvector, and Gemini to turn unstructured crypto project materials into structured risk assessments, persistent analysis sessions, and analyst-friendly reports.

## Suggested Next Milestone
**Suggested milestone: Analyst-Ready v1**

Goal: turn the current impressive prototype into a credible, demo-ready product for recruiters, collaborators, and early users.

Recommended scope:
- Align product messaging with actual supported chain coverage.
- Fix setup credibility issues such as dependency mismatches, stale CI references, and deployment entrypoints.
- Add one polished demo dataset and one end-to-end evaluation/report artifact that can be shown publicly.
- Introduce a small set of benchmark cases that demonstrate safe, moderate, and critical outcomes.
- Add concise deployment and API documentation so the project can be run without tribal knowledge.
