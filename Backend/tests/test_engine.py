import asyncio
from app.agent import check_missing_fields
from app.engine import evaluate_project
from app.models import (
    ProjectProfile,
    ChainType,
    ProtocolCategory,
    AuditStatus,
    Tokenomics,
    Vulnerability,
    RiskLevel
)


# ---------------------------------------------------------------------------
# Original tests
# ---------------------------------------------------------------------------

def test_safe_project():
    """Test a fully audited, safe project."""
    profile = ProjectProfile(
        project_name="SafeDex",
        chain=ChainType.ETHEREUM,
        category=ProtocolCategory.DEX,
        audit_status=AuditStatus.AUDITED,
        is_open_source=True,
        admin_key_controlled=False,
        tokenomics=Tokenomics(
            team_allocation_percentage=10.0,
            liquidity_locked=True,
            mint_function_present=False
        )
    )
    assessment = asyncio.run(evaluate_project(profile))
    assert assessment.overall_risk_level == RiskLevel.SAFE
    assert assessment.risk_score >= 100 # Should have bonuses

def test_critical_project():
    """Test a highly risky project (unaudited, admin key, high team alloc)."""
    profile = ProjectProfile(
        project_name="ScamProtocol",
        chain=ChainType.OTHER,
        category=ProtocolCategory.MEMECOIN,
        audit_status=AuditStatus.UNAUDITED,
        is_open_source=False,
        admin_key_controlled=True,
        tokenomics=Tokenomics(
            team_allocation_percentage=50.0,
            liquidity_locked=False,
            mint_function_present=True
        )
    )
    assessment = asyncio.run(evaluate_project(profile))
    assert assessment.overall_risk_level == RiskLevel.CRITICAL
    assert assessment.risk_score < 40 # Should be heavily penalized

def test_vulnerability_penalty():
    """Test penalties applied from identified vulnerabilities."""
    profile = ProjectProfile(
        project_name="VulnProtocol",
        chain=ChainType.BASE,
        category=ProtocolCategory.LENDING,
        audit_status=AuditStatus.AUDITED,
        identified_vulnerabilities=[
            Vulnerability(
                name="Centralization",
                severity=RiskLevel.HIGH,
                mitigated=False
            )
        ]
    )
    assessment = asyncio.run(evaluate_project(profile))
    # Audited bonus but high vuln penalty
    assert any("HIGH VULNERABILITY" in issue for issue in assessment.flagged_issues)


# ---------------------------------------------------------------------------
# Threshold boundary tests
# ---------------------------------------------------------------------------
# All penalties/bonuses are multiples of 5, base=100, so scores are multiples of 5.
# Thresholds: <=40 Critical, <=65 High, <=85 Moderate, >85 Safe.
# Use ChainType.OTHER to avoid on-chain verification side effects.

def _make_profile(**overrides) -> ProjectProfile:
    """Helper to build profiles with sensible defaults and selective overrides."""
    defaults = dict(
        project_name="TestProject",
        chain=ChainType.OTHER,
        category=ProtocolCategory.INFRASTRUCTURE,
        audit_status=AuditStatus.PARTIAL,  # no penalty, no bonus
    )
    defaults.update(overrides)
    return ProjectProfile(**defaults)


def test_threshold_score_40_is_critical():
    """100 - 30(unaudited) - 20(not open source) - 10(moderate vuln) = 40."""
    profile = _make_profile(
        audit_status=AuditStatus.UNAUDITED,
        is_open_source=False,
        identified_vulnerabilities=[
            Vulnerability(name="Minor issue", severity=RiskLevel.MODERATE, mitigated=False),
        ],
    )
    assessment = asyncio.run(evaluate_project(profile))
    assert assessment.risk_score == 40
    assert assessment.overall_risk_level == RiskLevel.CRITICAL


def test_threshold_score_45_is_high():
    """100 - 30(unaudited) - 25(admin key) = 45. Just above critical."""
    profile = _make_profile(
        audit_status=AuditStatus.UNAUDITED,
        admin_key_controlled=True,
    )
    assessment = asyncio.run(evaluate_project(profile))
    assert assessment.risk_score == 45
    assert assessment.overall_risk_level == RiskLevel.HIGH


def test_threshold_score_65_is_high():
    """100 - 10(pending) - 25(admin key) = 65. Exactly at the high boundary."""
    profile = _make_profile(
        audit_status=AuditStatus.PENDING,
        admin_key_controlled=True,
    )
    assessment = asyncio.run(evaluate_project(profile))
    assert assessment.risk_score == 65
    assert assessment.overall_risk_level == RiskLevel.HIGH


def test_threshold_score_70_is_moderate():
    """100 - 20(not open source) - 10(moderate vuln) = 70. Just above high."""
    profile = _make_profile(
        is_open_source=False,
        identified_vulnerabilities=[
            Vulnerability(name="Minor issue", severity=RiskLevel.MODERATE, mitigated=False),
        ],
    )
    assessment = asyncio.run(evaluate_project(profile))
    assert assessment.risk_score == 70
    assert assessment.overall_risk_level == RiskLevel.MODERATE


def test_threshold_score_85_is_moderate():
    """100 - 15(mint function) = 85. Exactly at the moderate boundary."""
    profile = _make_profile(
        tokenomics=Tokenomics(
            team_allocation_percentage=10.0,
            mint_function_present=True,
        ),
    )
    assessment = asyncio.run(evaluate_project(profile))
    assert assessment.risk_score == 85
    assert assessment.overall_risk_level == RiskLevel.MODERATE


def test_threshold_score_90_is_safe():
    """100 - 10(moderate vuln) = 90. Just above moderate."""
    profile = _make_profile(
        identified_vulnerabilities=[
            Vulnerability(name="Minor issue", severity=RiskLevel.MODERATE, mitigated=False),
        ],
    )
    assessment = asyncio.run(evaluate_project(profile))
    assert assessment.risk_score == 90
    assert assessment.overall_risk_level == RiskLevel.SAFE


# ---------------------------------------------------------------------------
# Memecoin downgrade
# ---------------------------------------------------------------------------

def test_memecoin_downgrade_safe_to_moderate():
    """A memecoin that scores Safe should be downgraded to Moderate."""
    profile = _make_profile(
        category=ProtocolCategory.MEMECOIN,
        audit_status=AuditStatus.AUDITED,
        admin_key_controlled=False,
        tokenomics=Tokenomics(
            team_allocation_percentage=5.0,
            liquidity_locked=True,
            mint_function_present=False,
        ),
    )
    assessment = asyncio.run(evaluate_project(profile))
    assert assessment.risk_score > 85, "Raw score should be Safe range"
    assert assessment.overall_risk_level == RiskLevel.MODERATE
    assert any("Memecoin" in issue for issue in assessment.flagged_issues)


def test_memecoin_critical_not_upgraded():
    """A critical memecoin should stay Critical, not be raised to Moderate."""
    profile = _make_profile(
        category=ProtocolCategory.MEMECOIN,
        audit_status=AuditStatus.UNAUDITED,
        is_open_source=False,
        admin_key_controlled=True,
    )
    assessment = asyncio.run(evaluate_project(profile))
    assert assessment.overall_risk_level == RiskLevel.CRITICAL


# ---------------------------------------------------------------------------
# check_missing_fields
# ---------------------------------------------------------------------------

def test_missing_fields_complete_profile():
    """Fully populated profile should flag no missing fields."""
    profile = _make_profile(
        project_name="CompleteDex",
        category=ProtocolCategory.DEX,
        tokenomics=Tokenomics(team_allocation_percentage=10.0),
    )
    missing = check_missing_fields(profile)
    assert missing == []


def test_missing_fields_flags_tokenomics_for_dex():
    """DEX without tokenomics team_allocation should flag it."""
    profile = _make_profile(
        project_name="IncompleteDex",
        category=ProtocolCategory.DEX,
    )
    missing = check_missing_fields(profile)
    assert "tokenomics.team_allocation_percentage" in missing


def test_missing_fields_flags_unknown_project_name():
    """Profile with 'Unknown Project' name should flag project_name."""
    profile = _make_profile(project_name="Unknown Project")
    missing = check_missing_fields(profile)
    assert "project_name" in missing


def test_missing_fields_infrastructure_no_tokenomics_ok():
    """Infrastructure category doesn't require tokenomics."""
    profile = _make_profile(
        project_name="Bridge",
        category=ProtocolCategory.INFRASTRUCTURE,
    )
    missing = check_missing_fields(profile)
    assert "tokenomics.team_allocation_percentage" not in missing
