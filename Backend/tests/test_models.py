import pytest
from app.models import (
    ProjectProfile,
    ChainType,
    ProtocolCategory,
    AuditStatus,
    RiskLevel,
    Tokenomics,
    Vulnerability
)

def test_project_profile_creation():
    """Test valid creation of ProjectProfile."""
    profile = ProjectProfile(
        project_name="TestProtocol",
        chain=ChainType.SOLANA,
        category=ProtocolCategory.DEX,
        audit_status=AuditStatus.AUDITED,
        is_open_source=True,
        admin_key_controlled=False,
        token_ticker="TEST",
        tokenomics=Tokenomics(
            total_supply="1000000",
            team_allocation_percentage=15.0,
            liquidity_locked=True,
            mint_function_present=False
        ),
        identified_vulnerabilities=[],
        summary="A test protocol on Solana."
    )
    assert profile.project_name == "TestProtocol"
    assert profile.chain == ChainType.SOLANA
    assert profile.audit_status == AuditStatus.AUDITED

def test_vulnerability_validation():
    """Test Vulnerability creation."""
    vuln = Vulnerability(
        name="Reentrancy",
        description="Possible reentrancy in deposit function.",
        severity=RiskLevel.HIGH,
        mitigated=False
    )
    assert vuln.name == "Reentrancy"
    assert vuln.severity == RiskLevel.HIGH
    assert not vuln.mitigated
