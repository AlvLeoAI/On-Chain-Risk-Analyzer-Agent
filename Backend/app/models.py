from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


# --- Enums ---
class ChainType(str, Enum):
    HEDERA = "Hedera"
    SOLANA = "Solana"
    STELLAR = "Stellar"
    ETHEREUM = "Ethereum"
    BASE = "Base"
    ARBITRUM = "Arbitrum"
    OTHER = "Other"

class AuditStatus(str, Enum):
    AUDITED = "Audited"
    UNAUDITED = "Unaudited"
    PENDING = "Pending"
    PARTIAL = "Partial"

class RiskLevel(str, Enum):
    SAFE = "Safe"
    MODERATE = "Moderate"
    HIGH = "High"
    CRITICAL = "Critical"


class EvidenceStatus(str, Enum):
    EXPLICIT = "explicit"
    INFERRED = "inferred"
    MISSING = "missing"

class ProtocolCategory(str, Enum):
    DEX = "DEX"
    LENDING = "Lending"
    YIELD = "Yield"
    BRIDGE = "Bridge"
    NFT = "NFT"
    MEMECOIN = "Memecoin"
    INFRASTRUCTURE = "Infrastructure"
    OTHER = "Other"


# --- Sub-models ---
class Vulnerability(BaseModel):
    name: str = Field(description="Name of the vulnerability (e.g., 'Reentrancy', 'Centralization Risk')")
    description: Optional[str] = Field(None, description="Explanation of the risk within the context of this protocol")
    severity: RiskLevel = Field(description="Estimated severity of this specific vulnerability")
    mitigated: bool = Field(False, description="Has this vulnerability been patched or acknowledged with a fix?")


class Tokenomics(BaseModel):
    total_supply: Optional[str] = Field(None, description="Total token supply as a string, e.g., '1,000,000,000'")
    team_allocation_percentage: Optional[float] = Field(None, description="Percentage of tokens allocated to the team", ge=0, le=100)
    liquidity_locked: Optional[bool] = Field(None, description="Is the liquidity pool locked?")
    mint_function_present: Optional[bool] = Field(None, description="Does the contract contain an owner-controlled mint function?")


class ProjectProfile(BaseModel):
    """
    The core schema used by the LLM agent to extract protocol details from unstructured text 
    (whitepapers, audit reports, GitHub READMEs).
    """
    project_name: str = Field(description="Name of the project or protocol")
    chain: ChainType = Field(description="The blockchain network this project operates on")
    category: ProtocolCategory = Field(description="What type of application is this?")
    
    # Contract & Security
    audit_status: AuditStatus = Field(description="Current audit status of the smart contracts")
    is_open_source: Optional[bool] = Field(None, description="Are the smart contracts open source and verified?")
    admin_key_controlled: Optional[bool] = Field(None, description="Is the protocol controlled by a single admin key (EOA) rather than a multisig or DAO?")
    
    # Token & Economics
    token_ticker: Optional[str] = Field(None, description="Ticker symbol of the native token, if applicable")
    tokenomics: Optional[Tokenomics] = Field(None, description="Details about token supply and distribution")
    
    # Identified Risks
    identified_vulnerabilities: List[Vulnerability] = Field(
        default_factory=list, 
        description="Any security risks, centralization vectors, or vulnerabilities identified in the text."
    )
    
    # General Context
    summary: Optional[str] = Field(None, description="A brief 2-sentence summary of what the protocol does.")


# --- Request/Response Models ---
class AnalysisRequest(BaseModel):
    session_id: str = "default"
    document_text: Optional[str] = Field(None, description="Legacy: The raw text of a single document")
    documents: Optional[List[str]] = Field(default_factory=list, description="A list of document texts to analyze together")


class RiskAssessment(BaseModel):
    """
    Replaces the 'Decision' model. Represents the final deterministic output of the engine.
    """
    project_name: str
    overall_risk_level: RiskLevel
    risk_score: int = Field(description="Aggregate risk score from 1-100 (100 being perfectly safe)")
    flagged_issues: List[str] = Field(default_factory=list, description="List of reasons why points were deducted")
    positive_signals: List[str] = Field(default_factory=list, description="List of positive fundamentals (e.g., Audited, Multisig used)")
    recommended_action: str = Field(description="E.g., 'Safe to interact', 'Proceed with extreme caution', 'Do not interact'")

class ChatRequest(BaseModel):
    session_id: str = "default"
    document_text: Optional[str] = Field(None, description="Legacy: The context document to answer questions from")
    documents: Optional[List[str]] = Field(default_factory=list, description="A list of context documents")
    message: str = Field(description="The user's question about the protocol")

class ChatResponse(BaseModel):
    response: str = Field(description="The agent's answer")


class EvidenceItem(BaseModel):
    key: str
    label: str
    value: Optional[str] = None
    status: EvidenceStatus
    rationale: str
    snippets: List[str] = Field(default_factory=list)


class AnalysisEvidence(BaseModel):
    profile_claims: List[EvidenceItem] = Field(default_factory=list)
    flagged_issue_evidence: List[EvidenceItem] = Field(default_factory=list)
    positive_signal_evidence: List[EvidenceItem] = Field(default_factory=list)


class ChatHistoryEntry(BaseModel):
    role: str
    content: str
    created_at: Optional[datetime] = None


class AnalysisResponse(BaseModel):
    session_id: str
    created_at: Optional[datetime] = None
    extracted_profile: ProjectProfile
    risk_assessment: RiskAssessment
    missing_fields: List[str] = Field(default_factory=list)
    evidence: AnalysisEvidence = Field(default_factory=AnalysisEvidence)


class AnalysisDetailResponse(AnalysisResponse):
    chat_history: List[ChatHistoryEntry] = Field(default_factory=list)


class AnalysisHistoryItem(BaseModel):
    session_id: str
    project_name: str
    chain: ChainType
    category: ProtocolCategory
    overall_risk_level: RiskLevel
    risk_score: int
    recommended_action: str
    created_at: Optional[datetime] = None


class AnalysisHistoryResponse(BaseModel):
    items: List[AnalysisHistoryItem] = Field(default_factory=list)
