import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.llm_tracker import track_gemini_usage
from app.rag import retrieve_relevant_chunks_from_db
from app.db.models import ProjectProfile as DBProjectProfile, RiskAssessment as DBRiskAssessment

try:
    from google import genai
except ImportError:  # pragma: no cover - depends on local environment
    genai = None

try:
    from google.api_core.exceptions import GoogleAPIError
except ImportError:  # pragma: no cover - depends on local environment
    class GoogleAPIError(Exception):  # type: ignore[no-redef]
        """Fallback when google-api-core is not installed."""
        pass

logger = logging.getLogger(__name__)


def _get_client():
    if genai is None:
        raise RuntimeError("google-genai is not installed")
    return genai.Client()

async def ask_agent_question(document_text: str, question: str, session_id: str = "default", db: AsyncSession | None = None, project_id: str | None = None) -> str:
    """
    Uses Gemini to answer a specific question about a provided protocol document.
    Uses persistent RAG to retrieve relevant context across multiple documents.
    """
    
    analysis_context = ""
    
    # 1. Fetch the structured analysis if project_id is available
    if db and project_id:
        try:
            # Fetch profile and latest risk assessment
            profile_result = await db.execute(select(DBProjectProfile).where(DBProjectProfile.id == project_id))
            db_profile = profile_result.scalars().first()
            
            assessment_result = await db.execute(
                select(DBRiskAssessment).where(DBRiskAssessment.project_id == project_id).order_by(DBRiskAssessment.created_at.desc())
            )
            db_assessment = assessment_result.scalars().first()
            
            if db_profile and db_assessment:
                analysis_context = f"""
[AUDITOR'S PREVIOUS FINDINGS]
Project: {db_profile.project_name}
Chain: {db_profile.chain}
Risk Score: {db_assessment.risk_score}/100
Risk Level: {db_assessment.overall_risk_level}
Audit Status: {db_profile.audit_status}
Flagged Issues: {", ".join(db_assessment.flagged_issues) if db_assessment.flagged_issues else "None"}
Positive Signals: {", ".join(db_assessment.positive_signals) if db_assessment.positive_signals else "None"}
Recommended Action: {db_assessment.recommended_action}
Summary: {db_profile.summary}
"""
        except Exception as e:
            logger.error(f"Error fetching analysis context for chat: {e}")

    # 2. Determine document context source via RAG
    doc_context = ""
    if db and project_id:
        logger.info(f"Using database RAG for session {session_id}, project {project_id}")
        doc_context = await retrieve_relevant_chunks_from_db(db, project_id, question, top_k=5)
        
        if not doc_context.strip() and document_text:
            doc_context = document_text[:8000]
    else:
        doc_context = document_text[:12000]

    # 3. Build the Prompt
    system_prompt = """You are an expert Smart Contract Auditor and Crypto Fundamentals Analyst.
Your job is to answer questions about a crypto project based on the provided context (raw documents AND your previous analysis findings).

GUIDELINES:
1. If the user asks about the "Risk Level", "Score", or "Findings", refer to the [AUDITOR'S PREVIOUS FINDINGS] section.
2. Provide objective, professional security assessments.
3. If the context does not contain enough information to answer a specific factual question, state that clearly, but always use the provided analysis findings if they exist.
4. Maintain a professional, analytical, and cautious tone.
"""

    prompt = f"""{analysis_context}

[RAW DOCUMENT CONTEXT]
{doc_context}

User Question:
{question}"""

    # Initialize the client defensively. A missing key or provider import failure
    # should not propagate as an unhandled exception to the API layer.
    try:
        client = _get_client()
    except Exception as e:
        logger.error("Failed to initialize Gemini client for chat: %s", e)
        return "I'm sorry, the chat service is not available right now. Please try again later."

    try:
        response = await client.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                {"role": "user", "parts": [{"text": system_prompt}]},
                {"role": "user", "parts": [{"text": prompt}]}
            ],
            config={
                'temperature': 0.2, # Keep it factual
            }
        )
        await track_gemini_usage(response)
        return response.text
    except GoogleAPIError as e:
        # Gemini-side failures: rate limits, quota, transient server errors, bad requests.
        logger.error("Gemini API error during chat (%s): %s", type(e).__name__, e, exc_info=True)
        return "I'm sorry, the analysis service is temporarily unavailable. Please try your question again in a moment."
    except Exception as e:
        logger.error("Chat generation failed (%s): %s", type(e).__name__, e, exc_info=True)
        return "I'm sorry, I encountered an error processing your question. Please try again."
