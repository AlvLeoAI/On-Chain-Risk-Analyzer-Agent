import logging
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from google import genai
except ImportError:  # pragma: no cover - depends on local environment
    genai = None

from app.models import (
    ProjectProfile, 
    ChainType, 
    AuditStatus, 
    ProtocolCategory
)
from app.llm_tracker import track_gemini_usage
from app.rag import retrieve_relevant_chunks_from_db

logger = logging.getLogger(__name__)


def _get_client():
    if genai is None:
        raise RuntimeError("google-genai is not installed")
    return genai.Client()

async def parse_profile_from_text(text_block: str, db: AsyncSession | None = None, project_id: str | None = None) -> ProjectProfile:
    """
    Extracts structured protocol data from unstructured text using Gemini 2.5 Flash.
    If project_id and db are provided, it can use RAG to supplement context for large documents.
    """
    
    context = text_block
    
    # If the text is very large and we have DB access, we can use RAG to find specific details
    # for critical fields like Audit Status, Tokenomics, and Vulnerabilities.
    if db and project_id and len(text_block) > 10000:
        logger.info(f"Document is very large ({len(text_block)} chars). Supplementing with RAG context.")
        
        # We can perform targeted searches for different sections of the profile
        audit_context = await retrieve_relevant_chunks_from_db(db, project_id, "audit report status, security reviews, certifications", top_k=3)
        tokenomics_context = await retrieve_relevant_chunks_from_db(db, project_id, "tokenomics, supply, allocation, vesting, liquidity lock", top_k=5)
        vulnerability_context = await retrieve_relevant_chunks_from_db(db, project_id, "vulnerabilities, security risks, centralization, admin keys, ownership", top_k=5)
        
        # Combine the original text (truncated) with the RAG-retrieved context
        context = f"""
[OVERVIEW (TRUNCATED)]
{text_block[:5000]}

[TARGETED SECURITY CONTEXT]
{audit_context}

[TARGETED TOKENOMICS CONTEXT]
{tokenomics_context}

[TARGETED VULNERABILITY CONTEXT]
{vulnerability_context}
"""

    system_prompt = """You are an expert Smart Contract Auditor and Crypto Fundamentals Analyst.
Your ONLY job is to convert raw unstructured text (whitepapers, READMEs, audit reports) into a structured JSON profile representing a crypto project or protocol.

RULES:
1. Extract exact values. Do not infer or guess if information is completely absent.
2. If a value is missing, set it to null.
3. Categorize the 'chain' strictly based on the provided enums. If it's a minor L2 or unlisted, use 'Other'.
4. IDENTIFIED VULNERABILITIES - Extract ANY mentions of security risks, centralization vectors (like owner wallets, admin keys), lack of multisig, reentrancy, or rugpull risks.
5. TOKENOMICS - Look closely for total supply, team allocation percentages, and whether liquidity is locked.
6. AUDIT STATUS - If the text explicitly mentions "audited by Certik/Consensys/etc.", mark as Audited. If no mention, mark Unaudited.
"""

    try:
        client = _get_client()
        # Use the async gemini-2.5-flash model for fast, structured extraction
        response = await client.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                {"role": "user", "parts": [{"text": system_prompt}]},
                {"role": "user", "parts": [{"text": context}]}
            ],
            config={
                'response_mime_type': 'application/json',
                'response_schema': ProjectProfile,
                'temperature': 0.1, # Low temperature for more deterministic extraction
            }
        )

        await track_gemini_usage(response)

        profile_json = response.text
        profile = ProjectProfile.model_validate_json(profile_json)

        if not profile.project_name:
            profile.project_name = "Unknown Project"

        return profile
        
    except Exception as e:
        logger.error(f"Extraction Error: {e}")
        return ProjectProfile(
            project_name="Unknown Project",
            chain=ChainType.OTHER,
            category=ProtocolCategory.OTHER,
            audit_status=AuditStatus.UNAUDITED
        )

def check_missing_fields(profile: ProjectProfile) -> list[str]:
    """
    Deterministic check for mandatory fields needed to run a full risk analysis.
    """
    missing = []
    
    if not profile.project_name or profile.project_name == "Unknown Project":
        missing.append("project_name")
        
    if profile.audit_status is None:
        missing.append("audit_status")
        
    if profile.category is None:
        missing.append("category")
        
    if profile.chain is None:
        missing.append("chain")
        
    # Enforce tokenomics info if it's a token-centric category
    if profile.category in [ProtocolCategory.MEMECOIN, ProtocolCategory.YIELD, ProtocolCategory.DEX]:
        if not profile.tokenomics or profile.tokenomics.team_allocation_percentage is None:
             missing.append("tokenomics.team_allocation_percentage")
             
    logger.info(f"MISSING FIELDS DETECTED: {missing}")
    return missing
