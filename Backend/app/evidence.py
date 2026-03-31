from __future__ import annotations

import re
from typing import Iterable, List, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DocumentEmbedding
from app.models import (
    AnalysisEvidence,
    EvidenceItem,
    EvidenceStatus,
    ProjectProfile,
    RiskAssessment,
)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _stringify(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def _clean_keywords(keywords: Iterable[str | None]) -> list[str]:
    cleaned = []
    seen = set()
    for keyword in keywords:
        if keyword is None:
            continue
        normalized = _normalize_text(str(keyword)).lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)
    return cleaned


def _top_snippets(chunks: Sequence[str], keywords: Iterable[str | None], limit: int = 2) -> list[str]:
    normalized_keywords = _clean_keywords(keywords)
    if not chunks or not normalized_keywords:
        return []

    scored = []
    for chunk in chunks:
        chunk_text = _normalize_text(chunk)
        chunk_lower = chunk_text.lower()
        matched_terms = [keyword for keyword in normalized_keywords if keyword in chunk_lower]
        if not matched_terms:
            continue
        first_match = min(chunk_lower.find(term) for term in matched_terms)
        scored.append((len(matched_terms), -first_match, chunk_text, matched_terms))

    scored.sort(reverse=True)
    snippets = []
    seen = set()
    for _, _, chunk_text, matched_terms in scored:
        snippet = _make_excerpt(chunk_text, matched_terms[0])
        if snippet in seen:
            continue
        seen.add(snippet)
        snippets.append(snippet)
        if len(snippets) >= limit:
            break
    return snippets


def _make_excerpt(chunk: str, keyword: str, radius: int = 120) -> str:
    chunk_lower = chunk.lower()
    idx = chunk_lower.find(keyword.lower())
    if idx == -1:
        idx = 0
    start = max(0, idx - radius)
    end = min(len(chunk), idx + len(keyword) + radius)
    excerpt = chunk[start:end].strip()
    if start > 0:
        excerpt = "..." + excerpt
    if end < len(chunk):
        excerpt = excerpt + "..."
    return excerpt


def _build_item(
    *,
    key: str,
    label: str,
    value,
    rationale: str,
    chunks: Sequence[str],
    keywords: Iterable[str | None],
    treat_missing_as_inferred: bool = False,
) -> EvidenceItem:
    snippets = _top_snippets(chunks, keywords)
    value_str = _stringify(value)

    if value_str in (None, "", "[]"):
        status = EvidenceStatus.INFERRED if treat_missing_as_inferred else EvidenceStatus.MISSING
    elif snippets:
        status = EvidenceStatus.EXPLICIT
    else:
        status = EvidenceStatus.INFERRED

    return EvidenceItem(
        key=key,
        label=label,
        value=value_str,
        status=status,
        rationale=rationale,
        snippets=snippets,
    )


def _audit_keywords(profile: ProjectProfile) -> list[str]:
    status = profile.audit_status.value.lower()
    if status == "audited":
        return ["audited", "audit", "security review", "reviewed by", "certik", "trail of bits"]
    if status == "pending":
        return ["audit pending", "pending audit", "under audit"]
    if status == "partial":
        return ["partial audit", "partially audited"]
    return ["unaudited"]


def _admin_keywords(profile: ProjectProfile) -> list[str]:
    if profile.admin_key_controlled is True:
        return ["admin key", "owner", "single admin", "pause", "upgrade", "owner-controlled"]
    return ["multisig", "multisignature", "dao", "governed by", "no admin key", "5-of-9"]


def _open_source_keywords(profile: ProjectProfile) -> list[str]:
    if profile.is_open_source is True:
        return ["open source", "open-source", "github", "verified source", "source code"]
    return ["closed source", "not open source", "private repository", "unverified"]


def _mint_keywords(profile: ProjectProfile) -> list[str]:
    if not profile.tokenomics:
        return []
    if profile.tokenomics.mint_function_present is True:
        return ["mint function", "owner-controlled mint", "can mint", "mint new tokens"]
    return ["no mint function", "mint function does not exist", "cannot mint", "no owner-controlled mint"]


def _liquidity_keywords(profile: ProjectProfile) -> list[str]:
    if not profile.tokenomics:
        return []
    if profile.tokenomics.liquidity_locked is True:
        return ["liquidity", "locked", "vesting"]
    return ["liquidity", "not locked", "unlocked", "rugpull"]


def _team_keywords(profile: ProjectProfile) -> list[str]:
    if not profile.tokenomics or profile.tokenomics.team_allocation_percentage is None:
        return []
    percentage = profile.tokenomics.team_allocation_percentage
    percentage_text = f"{percentage:g}%"
    return ["team allocation", "core team", percentage_text, "allocated to the team", "vested"]


def _token_keywords(profile: ProjectProfile) -> list[str]:
    keywords = ["token", "ticker"]
    if profile.token_ticker:
        keywords.append(profile.token_ticker)
    if profile.tokenomics and profile.tokenomics.total_supply:
        keywords.extend(["total supply", profile.tokenomics.total_supply])
    return keywords


def _issue_keywords(issue: str, profile: ProjectProfile) -> list[str]:
    issue_lower = issue.lower()
    if "unaudited" in issue_lower or "audit" in issue_lower:
        return _audit_keywords(profile)
    if "open-source" in issue_lower or "open source" in issue_lower or "verified" in issue_lower:
        return _open_source_keywords(profile)
    if "admin key" in issue_lower or "eoa" in issue_lower or "wallet" in issue_lower:
        return _admin_keywords(profile)
    if "team token allocation" in issue_lower or "team allocation" in issue_lower:
        return _team_keywords(profile)
    if "mint function" in issue_lower or "inflation" in issue_lower:
        return _mint_keywords(profile)
    if "liquidity" in issue_lower:
        return _liquidity_keywords(profile)
    if "memecoin" in issue_lower:
        return ["memecoin", "meme coin"]
    if "vulnerability" in issue_lower:
        tokens = re.findall(r"[a-zA-Z]{4,}", issue)
        return tokens[:6]
    return re.findall(r"[a-zA-Z]{4,}", issue)[:6]


async def _load_chunks(db: AsyncSession, project_id: str, fallback_text: str | None = None) -> list[str]:
    result = await db.execute(
        select(DocumentEmbedding.content)
        .where(DocumentEmbedding.project_id == project_id)
        .order_by(DocumentEmbedding.created_at.asc())
    )
    chunks = [_normalize_text(row[0]) for row in result.fetchall() if row[0]]
    deduped = list(dict.fromkeys(chunks))
    if deduped:
        return deduped
    if fallback_text:
        return [_normalize_text(fallback_text)]
    return []


async def build_analysis_evidence(
    db: AsyncSession,
    project_id: str,
    profile: ProjectProfile,
    assessment: RiskAssessment,
    fallback_text: str | None = None,
) -> AnalysisEvidence:
    chunks = await _load_chunks(db, project_id, fallback_text)

    profile_claims = [
        _build_item(
            key="audit_status",
            label="Audit status",
            value=profile.audit_status,
            rationale="Shows whether the documentation explicitly mentions a completed, partial, or pending audit.",
            chunks=chunks,
            keywords=_audit_keywords(profile),
        ),
        _build_item(
            key="open_source",
            label="Open-source / verified code",
            value=profile.is_open_source,
            rationale="Helps validate whether the codebase appears reviewable or verifiable from the source material.",
            chunks=chunks,
            keywords=_open_source_keywords(profile),
        ),
        _build_item(
            key="admin_key_controlled",
            label="Admin key / governance control",
            value=profile.admin_key_controlled,
            rationale="Supports the centralization assessment by surfacing multisig, DAO, or owner-control language.",
            chunks=chunks,
            keywords=_admin_keywords(profile),
        ),
        _build_item(
            key="token_ticker",
            label="Token details",
            value=profile.token_ticker,
            rationale="Extracts token naming and supply-related evidence from the provided materials.",
            chunks=chunks,
            keywords=_token_keywords(profile),
            treat_missing_as_inferred=True,
        ),
        _build_item(
            key="team_allocation_percentage",
            label="Team allocation",
            value=profile.tokenomics.team_allocation_percentage if profile.tokenomics else None,
            rationale="Looks for explicit team allocation terms and percentages in tokenomics sections.",
            chunks=chunks,
            keywords=_team_keywords(profile),
        ),
        _build_item(
            key="liquidity_locked",
            label="Liquidity lock status",
            value=profile.tokenomics.liquidity_locked if profile.tokenomics else None,
            rationale="Supports whether the protocol claims liquidity is locked or potentially removable.",
            chunks=chunks,
            keywords=_liquidity_keywords(profile),
        ),
        _build_item(
            key="mint_function_present",
            label="Mint function",
            value=profile.tokenomics.mint_function_present if profile.tokenomics else None,
            rationale="Looks for documentation that confirms or rules out owner-controlled minting.",
            chunks=chunks,
            keywords=_mint_keywords(profile),
        ),
    ]

    for index, vulnerability in enumerate(profile.identified_vulnerabilities, start=1):
        vulnerability_keywords = [vulnerability.name, vulnerability.description, vulnerability.severity.value]
        profile_claims.append(
            _build_item(
                key=f"vulnerability_{index}",
                label=f"Identified vulnerability: {vulnerability.name}",
                value=vulnerability.severity,
                rationale="Surfaces snippets related to the extracted vulnerability name or description.",
                chunks=chunks,
                keywords=vulnerability_keywords,
                treat_missing_as_inferred=True,
            )
        )

    flagged_issue_evidence = [
        _build_item(
            key=f"flagged_issue_{index}",
            label=f"Flagged issue {index}",
            value=issue,
            rationale="This issue is derived from the extracted profile and risk engine rules. The snippets below show the closest supporting document language.",
            chunks=chunks,
            keywords=_issue_keywords(issue, profile),
            treat_missing_as_inferred=True,
        )
        for index, issue in enumerate(assessment.flagged_issues, start=1)
    ]

    positive_signal_evidence = [
        _build_item(
            key=f"positive_signal_{index}",
            label=f"Positive signal {index}",
            value=signal,
            rationale="This positive signal is derived from the extracted profile and any successful on-chain checks.",
            chunks=chunks,
            keywords=_issue_keywords(signal, profile),
            treat_missing_as_inferred=True,
        )
        for index, signal in enumerate(assessment.positive_signals, start=1)
    ]

    return AnalysisEvidence(
        profile_claims=profile_claims,
        flagged_issue_evidence=flagged_issue_evidence,
        positive_signal_evidence=positive_signal_evidence,
    )
