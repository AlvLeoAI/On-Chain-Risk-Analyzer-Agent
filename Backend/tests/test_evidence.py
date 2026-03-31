from app.evidence import _build_item, _top_snippets
from app.models import EvidenceStatus


# ---------------------------------------------------------------------------
# Original tests
# ---------------------------------------------------------------------------

def test_top_snippets_returns_matching_excerpt():
    chunks = [
        "The protocol is governed by a 5-of-9 multisig and has no admin key.",
        "Liquidity is locked for 12 months.",
    ]

    snippets = _top_snippets(chunks, ["multisig", "admin key"])

    assert snippets
    assert "multisig" in snippets[0].lower()


def test_build_item_marks_inferred_when_value_has_no_direct_match():
    item = _build_item(
        key="audit_status",
        label="Audit status",
        value="Unaudited",
        rationale="Fallback when no explicit audit claim is found.",
        chunks=["The documentation describes tokenomics but does not mention any auditor."],
        keywords=["unaudited"],
    )

    assert item.status == EvidenceStatus.INFERRED
    assert item.snippets == []


# ---------------------------------------------------------------------------
# New tests
# ---------------------------------------------------------------------------

def test_build_item_marks_explicit_when_keyword_in_chunk():
    """Direct keyword match in source text should produce Explicit status."""
    item = _build_item(
        key="audit_status",
        label="Audit status",
        value="Audited",
        rationale="Check audit claim.",
        chunks=["The smart contracts have been audited by CertiK in Q3 2025."],
        keywords=["audited", "certik"],
    )
    assert item.status == EvidenceStatus.EXPLICIT
    assert len(item.snippets) > 0


def test_build_item_marks_missing_when_value_is_none():
    """None value with no matching snippets should be Missing."""
    item = _build_item(
        key="admin_key",
        label="Admin key",
        value=None,
        rationale="No information provided.",
        chunks=["This document is about tokenomics only."],
        keywords=["admin key", "owner"],
    )
    assert item.status == EvidenceStatus.MISSING


def test_build_item_missing_value_with_treat_as_inferred():
    """None value with treat_missing_as_inferred should be Inferred, not Missing."""
    item = _build_item(
        key="token_ticker",
        label="Token ticker",
        value=None,
        rationale="No ticker found.",
        chunks=["No relevant content."],
        keywords=["ticker"],
        treat_missing_as_inferred=True,
    )
    assert item.status == EvidenceStatus.INFERRED


def test_build_item_empty_chunks_marks_inferred():
    """Non-null value with empty chunks should be Inferred (no snippets to match)."""
    item = _build_item(
        key="open_source",
        label="Open source",
        value="Yes",
        rationale="No documents loaded.",
        chunks=[],
        keywords=["open source", "github"],
    )
    assert item.status == EvidenceStatus.INFERRED
    assert item.snippets == []


def test_top_snippets_no_match_returns_empty():
    """Keywords that don't appear in any chunk should return empty list."""
    chunks = ["The protocol uses a standard ERC-20 token."]
    snippets = _top_snippets(chunks, ["reentrancy", "flash loan"])
    assert snippets == []


def test_top_snippets_respects_limit():
    """Should return at most `limit` snippets."""
    chunks = [
        "The project was audited by CertiK.",
        "A second audit was performed by Trail of Bits.",
        "Third audit by OpenZeppelin.",
    ]
    snippets = _top_snippets(chunks, ["audit"], limit=2)
    assert len(snippets) <= 2
