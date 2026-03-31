import logging
import os
import re
import time
import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.agent import check_missing_fields, parse_profile_from_text
from app.chat import ask_agent_question
from app.db.database import get_database_status, get_db_pool, get_db_session
from app.db.models import (
    ChatLog as DBChatLog,
    ProjectProfile as DBProjectProfile,
    RiskAssessment as DBRiskAssessment,
)
from app.engine import evaluate_project
from app.evidence import build_analysis_evidence
from app.llm_tracker import clear_tracking_context, set_tracking_context
from app.models import (
    AnalysisDetailResponse,
    AnalysisHistoryItem,
    AnalysisHistoryResponse,
    AnalysisRequest,
    AnalysisResponse,
    AuditStatus,
    ChainType,
    ChatHistoryEntry,
    ChatRequest,
    ChatResponse,
    ProjectProfile as PydanticProjectProfile,
    ProtocolCategory,
    RiskAssessment as PydanticRiskAssessment,
)
from app.rag import ingest_document_to_db
from app.reporting import generate_risk_report

load_dotenv()


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _allowed_cors_origins() -> list[str]:
    raw_value = os.getenv("CORS_ORIGINS", "")
    if raw_value.strip():
        return [origin.strip() for origin in raw_value.split(",") if origin.strip()]
    return [
        "http://127.0.0.1:8501",
        "http://localhost:8501",
    ]


def _safe_download_name(value: str | None) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", (value or "").strip())
    cleaned = cleaned.strip("._")
    return cleaned or "project"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up API Server...")
    try:
        db_status = await get_database_status()
        if db_status["connected"]:
            logger.info("Database connection verified successfully during startup.")
        else:
            logger.warning("Database unavailable during startup: %s", db_status["detail"])
    except Exception as exc:  # pragma: no cover - depends on environment
        logger.warning("Database startup check failed: %s", exc)

    yield

    logger.info("Shutting down API Server...")
    try:
        pool = await get_db_pool()
        if pool:
            await pool.close()
    except Exception as exc:  # pragma: no cover - depends on environment
        logger.warning("Database pool shutdown was skipped: %s", exc)


app = FastAPI(
    title="On-Chain Fundamentals & Risk Analyzer API",
    description="API for evaluating smart contract and protocol risk from unstructured text using LLMs.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    db_status = await get_database_status()
    return {
        "status": "healthy" if db_status["connected"] else "degraded",
        "service": "on-chain-analyzer",
        "database": db_status,
    }


def _to_pydantic_profile(db_profile: DBProjectProfile) -> PydanticProjectProfile:
    return PydanticProjectProfile(
        project_name=db_profile.project_name,
        chain=db_profile.chain,
        category=db_profile.category,
        audit_status=db_profile.audit_status,
        is_open_source=db_profile.is_open_source,
        admin_key_controlled=db_profile.admin_key_controlled,
        token_ticker=db_profile.token_ticker,
        summary=db_profile.summary,
        tokenomics=db_profile.tokenomics,
        identified_vulnerabilities=db_profile.identified_vulnerabilities or [],
    )


def _to_pydantic_assessment(
    db_profile: DBProjectProfile,
    db_assessment: DBRiskAssessment,
) -> PydanticRiskAssessment:
    return PydanticRiskAssessment(
        project_name=db_profile.project_name,
        overall_risk_level=db_assessment.overall_risk_level,
        risk_score=db_assessment.risk_score,
        flagged_issues=db_assessment.flagged_issues or [],
        positive_signals=db_assessment.positive_signals or [],
        recommended_action=db_assessment.recommended_action,
    )


async def _build_analysis_payload(
    db: AsyncSession,
    db_profile: DBProjectProfile,
    db_assessment: DBRiskAssessment,
    fallback_text: str | None = None,
    include_chat_history: bool = False,
) -> AnalysisResponse | AnalysisDetailResponse:
    profile = _to_pydantic_profile(db_profile)
    assessment = _to_pydantic_assessment(db_profile, db_assessment)
    evidence = await build_analysis_evidence(
        db=db,
        project_id=db_profile.id,
        profile=profile,
        assessment=assessment,
        fallback_text=fallback_text,
    )

    payload = {
        "session_id": db_profile.session_id,
        "created_at": db_profile.created_at,
        "extracted_profile": profile,
        "risk_assessment": assessment,
        "missing_fields": check_missing_fields(profile),
        "evidence": evidence,
    }

    if not include_chat_history:
        return AnalysisResponse(**payload)

    chat_result = await db.execute(
        select(DBChatLog)
        .where(DBChatLog.session_id == db_profile.session_id)
        .order_by(DBChatLog.created_at.asc())
    )
    payload["chat_history"] = [
        ChatHistoryEntry(role=entry.role, content=entry.content, created_at=entry.created_at)
        for entry in chat_result.scalars().all()
    ]
    return AnalysisDetailResponse(**payload)


@app.post("/api/v1/analyze", response_model=AnalysisResponse)
async def analyze_protocol(request: AnalysisRequest, db: AsyncSession = Depends(get_db_session)):
    """
    Main endpoint for analyzing a protocol.
    Expects unstructured text (whitepaper, docs) and returns a structured risk assessment.
    """
    session_id = request.session_id if request.session_id and request.session_id != "default" else str(uuid.uuid4())
    logger.info("Starting analysis for session: %s", session_id)
    start_time = time.time()

    all_docs = list(request.documents or [])
    if request.document_text:
        all_docs.append(request.document_text)

    if not all_docs:
        raise HTTPException(status_code=400, detail="No documents provided for analysis.")

    combined_text = "\n\n--- NEXT DOCUMENT ---\n\n".join(all_docs)

    set_tracking_context(session_id, "/api/v1/analyze")
    try:
        db_profile = DBProjectProfile(
            session_id=session_id,
            project_name="Pending Analysis...",
            chain=ChainType.OTHER,
            category=ProtocolCategory.OTHER,
            audit_status=AuditStatus.UNAUDITED,
        )
        db.add(db_profile)
        await db.flush()
        project_id = db_profile.id

        logger.info("Ingesting %s documents...", len(all_docs))
        for doc in all_docs:
            await ingest_document_to_db(db, project_id, doc)

        logger.info("Extracting data via LLM...")
        profile = await parse_profile_from_text(combined_text, db=db, project_id=project_id)

        logger.info("Evaluating protocol through Risk Engine...")
        assessment = await evaluate_project(profile, combined_text)

        logger.info("Updating results in database...")
        db_profile.project_name = profile.project_name
        db_profile.chain = profile.chain
        db_profile.category = profile.category
        db_profile.audit_status = profile.audit_status
        db_profile.is_open_source = profile.is_open_source
        db_profile.admin_key_controlled = profile.admin_key_controlled
        db_profile.token_ticker = profile.token_ticker
        db_profile.tokenomics = profile.tokenomics.model_dump() if profile.tokenomics else None
        db_profile.identified_vulnerabilities = [v.model_dump() for v in profile.identified_vulnerabilities]
        db_profile.summary = profile.summary

        db_assessment = DBRiskAssessment(
            project_id=db_profile.id,
            overall_risk_level=assessment.overall_risk_level,
            risk_score=assessment.risk_score,
            flagged_issues=assessment.flagged_issues,
            positive_signals=assessment.positive_signals,
            recommended_action=assessment.recommended_action,
        )
        db.add(db_assessment)
        await db.commit()
        await db.refresh(db_profile)
        await db.refresh(db_assessment)

        processing_time = time.time() - start_time
        logger.info("Analysis completed in %.2fs", processing_time)

        return await _build_analysis_payload(
            db=db,
            db_profile=db_profile,
            db_assessment=db_assessment,
            fallback_text=combined_text,
        )
    except Exception as e:
        await db.rollback()
        logger.exception("Error during analysis")
        raise HTTPException(
            status_code=500,
            detail="The assessment could not be completed. Please review the source documents and try again.",
        )
    finally:
        clear_tracking_context()


@app.get("/api/v1/report/{session_id}")
async def get_pdf_report(session_id: str, db: AsyncSession = Depends(get_db_session)):
    """Generates a PDF report for a session."""
    try:
        profile_result = await db.execute(
            select(DBProjectProfile)
            .where(DBProjectProfile.session_id == session_id)
            .order_by(DBProjectProfile.created_at.desc())
        )
        db_profile = profile_result.scalars().first()
        if not db_profile:
            raise HTTPException(status_code=404, detail="Profile not found")

        assessment_result = await db.execute(
            select(DBRiskAssessment)
            .where(DBRiskAssessment.project_id == db_profile.id)
            .order_by(DBRiskAssessment.created_at.desc())
        )
        db_assessment = assessment_result.scalars().first()
        if not db_assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")

        pdf_bytes = generate_risk_report(
            _to_pydantic_profile(db_profile),
            _to_pydantic_assessment(db_profile, db_assessment),
        )

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    f"attachment; filename=Security_Report_{_safe_download_name(db_profile.project_name)}.pdf"
                )
            },
        )
    except Exception as e:
        logger.exception("Report error")
        raise HTTPException(
            status_code=500,
            detail="The PDF report could not be generated for this session.",
        )


@app.get("/api/v1/history", response_model=AnalysisHistoryResponse)
async def list_analysis_history(limit: int = 20, db: AsyncSession = Depends(get_db_session)):
    """Returns recent saved analyses."""
    try:
        limit = max(1, min(limit, 100))
        profile_result = await db.execute(
            select(DBProjectProfile)
            .where(DBProjectProfile.session_id.is_not(None))
            .order_by(DBProjectProfile.created_at.desc())
            .limit(limit)
        )
        profiles = profile_result.scalars().all()

        items = []
        for profile in profiles:
            assessment_result = await db.execute(
                select(DBRiskAssessment)
                .where(DBRiskAssessment.project_id == profile.id)
                .order_by(DBRiskAssessment.created_at.desc())
            )
            assessment = assessment_result.scalars().first()
            if not assessment or not profile.session_id:
                continue
            try:
                items.append(
                    AnalysisHistoryItem(
                        session_id=profile.session_id,
                        project_name=profile.project_name,
                        chain=profile.chain,
                        category=profile.category,
                        overall_risk_level=assessment.overall_risk_level,
                        risk_score=assessment.risk_score,
                        recommended_action=assessment.recommended_action,
                        created_at=profile.created_at,
                    )
                )
            except Exception:
                logger.warning("Skipping invalid history record for profile_id=%s", profile.id, exc_info=True)
                continue

        return AnalysisHistoryResponse(items=items)
    except Exception:
        logger.exception("History list error")
        raise HTTPException(
            status_code=500,
            detail="Saved analyses could not be loaded right now.",
        )


@app.get("/api/v1/history/{session_id}", response_model=AnalysisDetailResponse)
async def get_analysis_history_detail(session_id: str, db: AsyncSession = Depends(get_db_session)):
    """Loads a saved analysis session, including evidence and chat history."""
    try:
        profile_result = await db.execute(
            select(DBProjectProfile)
            .where(DBProjectProfile.session_id == session_id)
            .order_by(DBProjectProfile.created_at.desc())
        )
        db_profile = profile_result.scalars().first()
        if not db_profile:
            raise HTTPException(status_code=404, detail="Analysis session not found.")

        assessment_result = await db.execute(
            select(DBRiskAssessment)
            .where(DBRiskAssessment.project_id == db_profile.id)
            .order_by(DBRiskAssessment.created_at.desc())
        )
        db_assessment = assessment_result.scalars().first()
        if not db_assessment:
            raise HTTPException(status_code=404, detail="Risk assessment not found.")

        return await _build_analysis_payload(
            db=db,
            db_profile=db_profile,
            db_assessment=db_assessment,
            include_chat_history=True,
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("History detail error for session_id=%s", session_id)
        raise HTTPException(
            status_code=500,
            detail="This saved session could not be reopened right now.",
        )


@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat_with_agent(request: ChatRequest, db: AsyncSession = Depends(get_db_session)):
    """Follow-up questions with RAG."""
    result = await db.execute(
        select(DBProjectProfile.id)
        .where(DBProjectProfile.session_id == request.session_id)
        .order_by(DBProjectProfile.created_at.desc())
    )
    project_id = result.scalars().first()

    all_docs = list(request.documents or [])
    if request.document_text:
        all_docs.append(request.document_text)
    combined_text = "\n\n--- NEXT DOCUMENT ---\n\n".join(all_docs)

    set_tracking_context(request.session_id, "/api/v1/chat")
    try:
        user_log = DBChatLog(session_id=request.session_id, role="user", content=request.message)
        db.add(user_log)
        await db.commit()

        answer = await ask_agent_question(
            document_text=combined_text,
            question=request.message,
            session_id=request.session_id,
            db=db,
            project_id=project_id,
        )

        agent_log = DBChatLog(session_id=request.session_id, role="assistant", content=answer)
        db.add(agent_log)
        await db.commit()

        return ChatResponse(response=answer)
    except Exception as e:
        await db.rollback()
        logger.exception("Chat error")
        raise HTTPException(
            status_code=500,
            detail="The follow-up response could not be generated for this session.",
        )
    finally:
        clear_tracking_context()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, timeout_keep_alive=300)
