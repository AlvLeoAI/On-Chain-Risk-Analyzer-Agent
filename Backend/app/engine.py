import logging
from typing import Optional
from app.models import (
    ProjectProfile, 
    RiskAssessment, 
    RiskLevel, 
    AuditStatus, 
    ProtocolCategory,
    ChainType
)
from app.services.blockchain import blockchain_service

logger = logging.getLogger(__name__)

# =============================================================================
# RISK SCORING WEIGHTS & CONSTANTS
# =============================================================================
BASE_SCORE = 100

# Deductions
PENALTY_UNAUDITED = -30
PENALTY_ADMIN_KEY = -25
PENALTY_NO_OPEN_SOURCE = -20
PENALTY_MINT_FUNCTION = -15
PENALTY_CRITICAL_VULN = -40
PENALTY_HIGH_VULN = -20
PENALTY_MODERATE_VULN = -10
PENALTY_HIGH_TEAM_ALLOCATION = -15
PENALTY_LIQUIDITY_UNLOCKED = -25
PENALTY_ON_CHAIN_UNVERIFIED = -20  # Address exists but no code (EOA)

# Additions (Positive Signals)
BONUS_AUDITED = 10
BONUS_LIQUIDITY_LOCKED = 10
BONUS_NO_ADMIN_KEY = 10
BONUS_ON_CHAIN_VERIFIED = 15      # Address is a verified contract with code

# Thresholds
THRESHOLD_CRITICAL = 40
THRESHOLD_HIGH = 65
THRESHOLD_MODERATE = 85

# =============================================================================
# EVALUATION LOGIC
# =============================================================================

async def evaluate_project(profile: ProjectProfile, full_context: Optional[str] = None) -> RiskAssessment:
    """
    Evaluates a parsed ProjectProfile and returns a RiskAssessment object.
    Uses deterministic scoring based on common DeFi / On-Chain risk vectors.
    """
    logger.info(f"Starting risk evaluation for project: {profile.project_name}")
    
    score = BASE_SCORE
    flagged_issues = []
    positive_signals = []

    # 1. Audit Status Check
    if profile.audit_status == AuditStatus.UNAUDITED:
        score += PENALTY_UNAUDITED
        flagged_issues.append("Project is unaudited. Extreme risk of smart contract exploits.")
    elif profile.audit_status == AuditStatus.AUDITED:
        score += BONUS_AUDITED
        positive_signals.append("Smart contracts have been audited.")
    elif profile.audit_status == AuditStatus.PENDING:
        score += PENALTY_MODERATE_VULN
        flagged_issues.append("Audit is currently pending. Interact with caution.")

    # 2. Open Source Check
    if profile.is_open_source is False:
        score += PENALTY_NO_OPEN_SOURCE
        flagged_issues.append("Smart contracts are not open-source or verified. Code cannot be publicly reviewed.")
    elif profile.is_open_source is True:
        positive_signals.append("Code is open-source and verifiable.")

    # 3. Centralization / Admin Key Check
    if profile.admin_key_controlled is True:
        score += PENALTY_ADMIN_KEY
        flagged_issues.append("Protocol is controlled by a single Admin Key/EOA. High risk of rugpull or malicious upgrades.")
    elif profile.admin_key_controlled is False:
        score += BONUS_NO_ADMIN_KEY
        positive_signals.append("Protocol does not rely on a single admin key (decentralized or multisig).")

    # 4. Tokenomics Check
    if profile.tokenomics:
        if profile.tokenomics.team_allocation_percentage is not None:
            team_alloc = profile.tokenomics.team_allocation_percentage
            if team_alloc > 20.0:
                score += PENALTY_HIGH_TEAM_ALLOCATION
                flagged_issues.append(f"High team token allocation ({team_alloc}%). Risk of price manipulation/dumping.")
            else:
                positive_signals.append(f"Reasonable team allocation ({team_alloc}%).")
                
        if profile.tokenomics.mint_function_present is True:
            score += PENALTY_MINT_FUNCTION
            flagged_issues.append("Contract contains an owner-controlled mint function. Risk of infinite inflation/rugpull.")
            
        if profile.tokenomics.liquidity_locked is False:
            score += PENALTY_LIQUIDITY_UNLOCKED
            flagged_issues.append("Liquidity pool is not locked. Extreme risk of liquidity rugpull.")
        elif profile.tokenomics.liquidity_locked is True:
            score += BONUS_LIQUIDITY_LOCKED
            positive_signals.append("Liquidity pool is locked.")

    # 5. On-Chain Verification (NEW)
    # Extract addresses from the summary or full context provided
    extraction_text = (profile.summary or "") + (full_context or "")
    addresses = blockchain_service.extract_addresses(extraction_text)
    
    # Map ChainType to RPC-supported chains
    chain_map = {
        ChainType.ETHEREUM: "ETHEREUM",
        ChainType.BASE: "BASE",
        ChainType.ARBITRUM: "ARBITRUM"
    }
    
    # We only verify if the chain is supported
    mapped_chain = chain_map.get(profile.chain)
    if mapped_chain and addresses["EVM"]:
        logger.info(f"Found {len(addresses['EVM'])} EVM addresses to verify on {mapped_chain}")
        for addr in addresses["EVM"][:2]: # Verify first 2 addresses to avoid too many RPC calls
            on_chain_data = await blockchain_service.verify_contract_status(addr, mapped_chain)
            if "error" not in on_chain_data:
                if on_chain_data["is_contract"]:
                    score += BONUS_ON_CHAIN_VERIFIED
                    positive_signals.append(f"On-Chain Verified: Contract found at {addr[:10]}...")
                else:
                    score += PENALTY_ON_CHAIN_UNVERIFIED
                    flagged_issues.append(f"Centralization Risk: Address {addr[:10]}... is an EOA (wallet), not a contract.")

    # 6. Identified Vulnerabilities
    for vuln in profile.identified_vulnerabilities:
        if not vuln.mitigated:
            if vuln.severity == RiskLevel.CRITICAL:
                score += PENALTY_CRITICAL_VULN
                flagged_issues.append(f"CRITICAL VULNERABILITY: {vuln.name} - {vuln.description}")
            elif vuln.severity == RiskLevel.HIGH:
                score += PENALTY_HIGH_VULN
                flagged_issues.append(f"HIGH VULNERABILITY: {vuln.name} - {vuln.description}")
            elif vuln.severity == RiskLevel.MODERATE:
                score += PENALTY_MODERATE_VULN
                flagged_issues.append(f"MODERATE VULNERABILITY: {vuln.name} - {vuln.description}")
        else:
             positive_signals.append(f"Mitigated vulnerability: {vuln.name}.")

    # 7. Final Score Calculation
    final_score = max(0, min(100, score))
    
    if final_score <= THRESHOLD_CRITICAL:
        overall_level = RiskLevel.CRITICAL
        action = "DO NOT INTERACT. Extreme risk of total loss of funds."
    elif final_score <= THRESHOLD_HIGH:
        overall_level = RiskLevel.HIGH
        action = "PROCEED WITH EXTREME CAUTION. Significant risk vectors identified."
    elif final_score <= THRESHOLD_MODERATE:
        overall_level = RiskLevel.MODERATE
        action = "MODERATE RISK. Ensure you understand the flagged issues before interacting."
    else:
        overall_level = RiskLevel.SAFE
        action = "GENERALLY SAFE. Fundamentals look strong, but always practice standard DeFi safety."

    if profile.category == ProtocolCategory.MEMECOIN and overall_level == RiskLevel.SAFE:
        overall_level = RiskLevel.MODERATE
        action = "MODERATE RISK (Category adjustment: Memecoins are highly volatile despite technical safety)."
        flagged_issues.append("Asset is a Memecoin; high inherent market volatility.")

    return RiskAssessment(
        project_name=profile.project_name,
        overall_risk_level=overall_level,
        risk_score=final_score,
        flagged_issues=flagged_issues,
        positive_signals=positive_signals,
        recommended_action=action
    )
