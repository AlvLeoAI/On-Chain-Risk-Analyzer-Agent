import os
import uuid
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, JSON, Enum as SQLEnum, text, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
from pgvector.sqlalchemy import Vector

# Import the Base from our new database.py
from app.db.database import Base

# Also import enums from our Pydantic models for mapping
from app.models import ChainType, AuditStatus, ProtocolCategory, RiskLevel

def generate_uuid():
    return str(uuid.uuid4())

class DocumentEmbedding(Base):
    __tablename__ = "document_embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(String, ForeignKey("project_profiles.id", ondelete="CASCADE"), nullable=False)
    content = Column(String, nullable=False)
    embedding = Column(Vector(768), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))

class ProjectProfile(Base):
    __tablename__ = "project_profiles"

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, nullable=True, index=True) # Added for session tracking
    project_name = Column(String, nullable=False, index=True)
    chain = Column(SQLEnum(ChainType), nullable=False)
    category = Column(SQLEnum(ProtocolCategory), nullable=False)
    
    # Contract & Security
    audit_status = Column(SQLEnum(AuditStatus), nullable=False)
    is_open_source = Column(Boolean, nullable=True)
    admin_key_controlled = Column(Boolean, nullable=True)
    
    # Token & Economics
    token_ticker = Column(String, nullable=True)
    tokenomics = Column(JSONB, nullable=True)  # Stores the Tokenomics model as JSON
    
    # Identified Risks
    identified_vulnerabilities = Column(JSONB, nullable=True)  # Stores list of Vulnerability models as JSON
    
    # General Context
    summary = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))
    updated_at = Column(DateTime(timezone=True), onupdate=text("now()"))

class RiskAssessment(Base):
    __tablename__ = "risk_assessments"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("project_profiles.id", ondelete="CASCADE"), nullable=False)
    
    overall_risk_level = Column(SQLEnum(RiskLevel), nullable=False)
    risk_score = Column(Integer, nullable=False)
    
    flagged_issues = Column(JSONB, nullable=True)  # List of strings
    positive_signals = Column(JSONB, nullable=True)  # List of strings
    recommended_action = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=text("now()"))

class LLMUsageEvent(Base):
    __tablename__ = "llm_usage_events"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, nullable=False, index=True)
    endpoint = Column(String, nullable=False)
    prompt_tokens = Column(Integer, nullable=False, default=0)
    completion_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    input_cost_usd = Column(Numeric(12, 8), nullable=False, default=0.0)
    output_cost_usd = Column(Numeric(12, 8), nullable=False, default=0.0)
    total_cost_usd = Column(Numeric(12, 8), nullable=False, default=0.0)
    
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))

class ChatLog(Base):
    __tablename__ = "chat_logs"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, nullable=False, index=True)
    role = Column(String, nullable=False) # "user" or "assistant"
    content = Column(String, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))
