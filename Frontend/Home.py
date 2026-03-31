import os
from datetime import datetime

import streamlit as st

from utils.api import (
    analyze_protocol,
    chat_with_agent,
    create_new_session_id,
    fetch_analysis_detail,
    fetch_analysis_history,
    fetch_pdf_report,
    get_backend_status,
    get_session_id,
    set_session_id,
)
from utils.document_processor import (
    DocumentProcessingError,
    extract_text_from_pdf,
    extract_text_from_url,
)


DEFAULT_BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
WORKSPACE_MODES = ("Analyzer", "History")


st.set_page_config(
    page_title="On-Chain Due Diligence Workstation",
    page_icon="🛡️",
    layout="wide",
)


def initialize_state():
    st.session_state.setdefault("analysis_result", None)
    st.session_state.setdefault("documents", [])
    st.session_state.setdefault("chat_history", [])
    st.session_state.setdefault("workspace_mode", WORKSPACE_MODES[0])
    st.session_state.setdefault("workspace_mode_selector", st.session_state.workspace_mode)
    st.session_state.setdefault("pending_workspace_mode", None)
    st.session_state.setdefault("loaded_from_history", False)
    st.session_state.setdefault("last_assessed_signature", None)
    st.session_state.setdefault("history_open_error", None)


def reset_workspace():
    st.session_state.clear()
    st.rerun()


def apply_pending_workspace_mode():
    pending_mode = st.session_state.pop("pending_workspace_mode", None)
    if pending_mode in WORKSPACE_MODES:
        st.session_state.workspace_mode = pending_mode
        st.session_state.workspace_mode_selector = pending_mode
    elif st.session_state.workspace_mode_selector not in WORKSPACE_MODES:
        st.session_state.workspace_mode_selector = st.session_state.workspace_mode


def sync_workspace_mode():
    st.session_state.workspace_mode = st.session_state.workspace_mode_selector
    if st.session_state.workspace_mode != "History":
        st.session_state.history_open_error = None


def request_workspace_mode(mode: str):
    if mode in WORKSPACE_MODES:
        st.session_state.pending_workspace_mode = mode


def hydrate_saved_session(detail: dict):
    session_id = detail.get("session_id")
    if not session_id:
        raise ValueError("The saved session payload did not include a session ID.")

    set_session_id(session_id)
    st.session_state.analysis_result = detail
    st.session_state.chat_history = detail.get("chat_history", [])
    st.session_state.documents = []
    st.session_state.loaded_from_history = True
    st.session_state.last_assessed_signature = None


def open_saved_session(session_id: str, backend_url: str):
    try:
        detail = fetch_analysis_detail(session_id, backend_url)
        if "error" in detail:
            st.session_state.history_open_error = detail["error"]
            st.rerun()

        hydrate_saved_session(detail)
        st.session_state.history_open_error = None
        request_workspace_mode("Analyzer")
        st.rerun()
    except Exception:
        st.session_state.history_open_error = (
            "The saved session could not be reopened. Refresh History and try again."
        )
        st.rerun()


def format_timestamp(value: str | None) -> str:
    if not value:
        return "Unknown time"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return value


def infer_source_type(name: str) -> str:
    lowered = (name or "").lower()
    if lowered.endswith(".pdf") or "pdf" in lowered:
        return "PDF"
    if lowered.startswith("url ") or lowered.startswith("http"):
        return "URL"
    return "Text"


def document_signature() -> tuple:
    return tuple(
        (doc.get("name", ""), len(doc.get("text", "")))
        for doc in st.session_state.documents
    )


def document_summary() -> dict:
    documents = st.session_state.documents
    counts = {"Text": 0, "PDF": 0, "URL": 0}
    total_chars = 0
    for doc in documents:
        counts[infer_source_type(doc.get("name", ""))] += 1
        total_chars += len(doc.get("text", ""))
    return {
        "count": len(documents),
        "total_chars": total_chars,
        "counts": counts,
    }


def short_session_id() -> str:
    session_id = get_session_id()
    return session_id[:8] if session_id else "Not set"


def preview_text(text: str, limit: int = 160) -> str:
    collapsed = " ".join((text or "").split())
    if len(collapsed) <= limit:
        return collapsed or "No preview available."
    return collapsed[:limit].rstrip() + "..."


def current_stage() -> int:
    if st.session_state.loaded_from_history and st.session_state.analysis_result:
        return 5
    if st.session_state.analysis_result:
        return 4
    if st.session_state.documents:
        return 3
    return 1


def workspace_state_label(backend_status: dict) -> tuple[str, str]:
    if not backend_status.get("ok"):
        return (
            "Backend unavailable",
            "The workstation can still collect sources, but new assessments and history reloads are unavailable.",
        )

    current_signature = document_signature()
    if st.session_state.loaded_from_history and st.session_state.analysis_result:
        if st.session_state.documents:
            return (
                "Saved session loaded",
                "You have loaded new sources on top of a saved session. Run Assessment to replace the current findings.",
            )
        return (
            "Saved session loaded",
            "Review the saved findings, inspect evidence, or continue asking follow-up questions.",
        )

    if st.session_state.analysis_result:
        if st.session_state.last_assessed_signature != current_signature:
            return (
                "Sources changed",
                "The loaded sources differ from the last assessment. Run Assessment again to refresh the result.",
            )
        return (
            "Assessment ready",
            "The latest assessment is loaded. Review evidence, continue in chat, or revisit it later from History.",
        )

    if st.session_state.documents:
        return (
            "Ready to assess",
            "Your sources are loaded. Review them, then run the assessment when the intake looks complete.",
        )

    return (
        "Waiting for sources",
        "Start by loading a whitepaper, audit PDF, docs URL, or raw text excerpt.",
    )


def render_status_cards(backend_status: dict):
    summary = document_summary()
    state_title, state_detail = workspace_state_label(backend_status)
    cards = st.columns(4)

    with cards[0]:
        with st.container(border=True):
            st.caption("Backend")
            st.markdown(f"**{backend_status.get('label', 'Unknown')}**")
            st.caption(backend_status.get("detail", ""))

    with cards[1]:
        with st.container(border=True):
            st.caption("Workspace")
            st.markdown(f"**{state_title}**")
            st.caption(state_detail)

    with cards[2]:
        with st.container(border=True):
            st.caption("Loaded Sources")
            st.markdown(f"**{summary['count']} source(s)**")
            st.caption(f"{summary['total_chars']:,} total characters")

    with cards[3]:
        with st.container(border=True):
            st.caption("Session")
            st.markdown(f"**{short_session_id()}**")
            if st.session_state.analysis_result:
                st.caption("Results save automatically to History.")
            else:
                st.caption("A new session is created when you run an assessment.")


def render_workflow_strip():
    steps = [
        ("Load sources", "Paste text, upload PDFs, or fetch docs URLs."),
        ("Review intake", "Check that the source set is complete and useful."),
        ("Run assessment", "Create the structured profile, score, and findings."),
        ("Verify evidence", "Inspect source-backed claims before trusting the result."),
        ("Revisit later", "Reload saved sessions from History and continue the investigation."),
    ]
    active = current_stage()
    columns = st.columns(len(steps))
    for index, (title, description) in enumerate(steps, start=1):
        with columns[index - 1]:
            with st.container(border=True):
                st.caption(f"Step {index}")
                st.markdown(f"**{title}**")
                st.caption(description)
                if index == active:
                    st.caption("Current")
                elif index < active:
                    st.caption("Completed")
                else:
                    st.caption("Next")


def render_section_intro(title: str, detail: str | None = None):
    st.markdown(f"### {title}")
    if detail:
        st.caption(detail)


def render_loaded_documents():
    summary = document_summary()
    with st.container(border=True):
        render_section_intro(
            "Loaded Sources",
            "Review the active source set before rerunning the assessment.",
        )

        if not st.session_state.documents:
            st.markdown("**No sources loaded yet**")
            st.write(
                "Add at least one source before running an assessment. The most useful starting points are "
                "a whitepaper, an audit PDF, the main docs site, or a project README."
            )
            st.caption("Suggested first pass: one whitepaper, one audit report, and one docs URL.")
            return

        metrics = st.columns(3, gap="small", vertical_alignment="top")
        metrics[0].metric("Sources", summary["count"])
        metrics[1].metric("Total Text", f"{summary['total_chars']:,}")
        metrics[2].metric(
            "Source Mix",
            f"{summary['counts']['Text']} text / {summary['counts']['PDF']} pdf / {summary['counts']['URL']} url",
        )

        st.divider()

        for index, doc in enumerate(st.session_state.documents, start=1):
            with st.container(border=True):
                text_col, action_col = st.columns([4, 1], gap="small", vertical_alignment="top")
                source_type = infer_source_type(doc.get("name", ""))
                text_col.markdown(f"**{index}. {doc['name']}**")
                text_col.caption(f"{source_type} source • {len(doc.get('text', '')):,} characters")
                text_col.write(preview_text(doc.get("text", "")))

                if action_col.button("Remove", key=f"del_{index}"):
                    st.session_state.documents.pop(index - 1)
                    st.rerun()


def render_action_center(backend_status: dict) -> bool:
    summary = document_summary()
    state_title, state_detail = workspace_state_label(backend_status)
    can_run = backend_status.get("ok") and summary["count"] > 0

    with st.container(border=True):
        render_section_intro(
            "Action Center",
            "Review workspace readiness, then launch the next assessment run.",
        )
        st.markdown(f"**{state_title}**")
        st.write(state_detail)

        if summary["count"] == 0:
            st.caption("Load at least one source to enable the assessment run.")
        else:
            st.caption(
                f"Assessment queue: {summary['count']} source(s) / {summary['total_chars']:,} characters."
            )

        if st.session_state.analysis_result and st.session_state.last_assessed_signature != document_signature():
            st.warning("Your source set changed after the last run. The current result is out of date until you rerun.")

        run_label = "Run Assessment"
        if summary["count"]:
            run_label = f"Run Assessment on {summary['count']} Source(s)"

        clicked = st.button(
            run_label,
            type="primary",
            use_container_width=True,
            disabled=not can_run,
            help=None if can_run else "Connect the backend and load at least one source first.",
        )

        st.caption("Results are saved automatically and become available in History.")
        return clicked


def render_result_empty_state(backend_status: dict):
    summary = document_summary()
    if not backend_status.get("ok"):
        st.warning("The backend is unavailable. You can still stage sources, but assessment and history features are paused.")
    elif summary["count"] == 0:
        st.write(
            "Nothing has been assessed yet. Load a source set, review the intake, and then run the assessment "
            "to generate a profile, score, evidence panel, and follow-up chat context."
        )
    else:
        st.write(
            "Your sources are ready. Run Assessment to generate a structured profile, deterministic score, "
            "evidence-backed findings, and a saved session for later review."
        )


def render_evidence_items(items: list[dict], empty_message: str):
    if not items:
        st.info(empty_message)
        return

    for item in items:
        with st.container(border=True):
            cols = st.columns([3, 1])
            cols[0].markdown(f"**{item.get('label', 'Evidence')}**")
            cols[1].markdown(f"`{item.get('status', 'unknown')}`")
            if item.get("value") not in (None, ""):
                st.caption(f"Value: {item['value']}")
            st.write(item.get("rationale", ""))

            snippets = item.get("snippets", [])
            if snippets:
                for snippet in snippets:
                    st.code(snippet, language="text")
            else:
                st.caption("No directly matched source snippet was found in the stored document chunks.")


def render_analysis_dashboard(result: dict, backend_url: str, debug_mode: bool = False):
    with st.container(border=True):
        render_section_intro(
            "Assessment Workspace",
            "Review findings, inspect evidence, and continue the investigation from one place.",
        )

        if not result:
            render_result_empty_state(get_backend_status(backend_url))
            return

        if "error" in result:
            st.error(result["error"])
            st.caption("Review the backend status, inspect your sources, and rerun the assessment when ready.")
            return

        session_id = result.get("session_id")
        profile = result.get("extracted_profile", {})
        assessment = result.get("risk_assessment", {})
        evidence = result.get("evidence", {})
        missing_fields = result.get("missing_fields", [])
        created_at = format_timestamp(result.get("created_at"))

        st.divider()
        col_title, col_meta, col_download = st.columns([3, 2, 1], gap="small", vertical_alignment="top")
        with col_title:
            st.subheader("Assessment Results")
        with col_meta:
            st.caption(f"Session: `{session_id}`")
            st.caption(f"Saved: {created_at}")
        with col_download:
            pdf_data = fetch_pdf_report(session_id, backend_url) if session_id else None
            if pdf_data:
                st.download_button(
                    label="Download PDF",
                    data=pdf_data,
                    file_name=f"Security_Report_{session_id[:8]}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            else:
                st.caption("PDF unavailable")

        if st.session_state.loaded_from_history and not st.session_state.documents:
            st.info("This result was loaded from History. You can review evidence immediately or ask follow-up questions using the saved backend context.")
        else:
            st.success("Assessment is ready. Verify the evidence before acting on any finding, then continue in chat if you need deeper answers.")

        metric_cols = st.columns(4, gap="small", vertical_alignment="top")
        metric_cols[0].metric("Risk Score", f"{assessment.get('risk_score', 0)}/100")
        metric_cols[1].metric("Risk Level", assessment.get("overall_risk_level", "Unknown"))
        metric_cols[2].metric("Project Name", profile.get("project_name", "Unknown"))
        metric_cols[3].metric("Chain", profile.get("chain", "Unknown"))

        summary_tab, evidence_tab, chat_tab = st.tabs(["Summary", "Evidence", "Chat"])

        with summary_tab:
            c1, c2 = st.columns([1, 1], gap="large", vertical_alignment="top")

            with c1:
                st.subheader("Project Fundamentals")
                with st.container(border=True):
                    st.markdown(f"**Category:** {profile.get('category', 'Unknown')}")
                    st.markdown(f"**Audit Status:** {profile.get('audit_status', 'Unknown')}")
                    st.markdown(f"**Open Source:** {profile.get('is_open_source', 'Unknown')}")
                    st.markdown(f"**Admin Key Controlled:** {profile.get('admin_key_controlled', 'Unknown')}")
                    st.markdown(f"**Token Ticker:** {profile.get('token_ticker', 'Unknown')}")

                    if profile.get("summary"):
                        st.markdown("**Summary:**")
                        st.info(profile["summary"])

                    if profile.get("tokenomics"):
                        st.markdown("**Tokenomics:**")
                        st.json(profile["tokenomics"])

            with c2:
                st.subheader("Risk Assessment")
                with st.container(border=True):
                    st.markdown(f"**Recommended Action:** {assessment.get('recommended_action', '')}")

                    st.markdown("**Positive Signals**")
                    for signal in assessment.get("positive_signals", []) or ["None identified."]:
                        prefix = "- " if signal != "None identified." else ""
                        st.markdown(f"{prefix}{signal}")

                    st.markdown("**Flagged Issues**")
                    for issue in assessment.get("flagged_issues", []) or ["None identified."]:
                        prefix = "- " if issue != "None identified." else ""
                        st.markdown(f"{prefix}{issue}")

            vulnerabilities = profile.get("identified_vulnerabilities", [])
            if vulnerabilities:
                st.subheader("Identified Vulnerabilities")
                for vulnerability in vulnerabilities:
                    with st.expander(f"{vulnerability.get('severity', 'Unknown')} Risk: {vulnerability.get('name', 'Unknown')}"):
                        st.write(f"**Mitigated:** {vulnerability.get('mitigated', 'Unknown')}")
                        st.write(f"**Description:** {vulnerability.get('description', 'No description.')}")

            if missing_fields:
                st.warning(
                    "The system could not confidently extract: "
                    + ", ".join(missing_fields)
                )

        with evidence_tab:
            st.subheader("Evidence Panel")
            st.caption("Use explicit snippets first. Treat inferred claims as prompts for additional verification.")
            st.caption("Evidence status: `explicit` = direct snippet match, `inferred` = rule-backed without a direct match, `missing` = not supported.")
            evidence_tabs = st.tabs(["Profile Claims", "Flagged Issues", "Positive Signals"])

            with evidence_tabs[0]:
                render_evidence_items(
                    evidence.get("profile_claims", []),
                    "No profile-level evidence is available yet.",
                )
            with evidence_tabs[1]:
                render_evidence_items(
                    evidence.get("flagged_issue_evidence", []),
                    "No flagged issue evidence is available for this assessment.",
                )
            with evidence_tabs[2]:
                render_evidence_items(
                    evidence.get("positive_signal_evidence", []),
                    "No positive signal evidence is available for this assessment.",
                )

        with chat_tab:
            st.subheader("Follow-Up Chat")
            st.caption("Ask pointed questions about the current protocol review. The assistant will use the saved session context when available.")

            for message in st.session_state.chat_history:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            prompt = st.chat_input("Ask a question about the protocol...", key=f"chat_input_{session_id}")
            if prompt:
                st.session_state.chat_history.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)

                with st.chat_message("assistant"):
                    with st.spinner("Searching stored findings and source context..."):
                        documents = [doc["text"] for doc in st.session_state.documents]
                        chat_result = chat_with_agent(documents, prompt, backend_url, session_id=session_id)
                        if "error" in chat_result:
                            response = chat_result["error"]
                            st.error(response)
                        else:
                            response = chat_result.get("response", "No response received.")
                            st.markdown(response)
                        st.session_state.chat_history.append({"role": "assistant", "content": response})

        if debug_mode:
            st.divider()
            with st.expander("Raw API Response", expanded=False):
                st.json(result)


def add_document(name: str, text: str):
    st.session_state.documents.append({"name": name, "text": text})


def process_pdf_uploads(uploaded_files) -> tuple[int, list[tuple[str, str]]]:
    added_count = 0
    failures: list[tuple[str, str]] = []

    for uploaded_file in uploaded_files:
        with st.spinner(f"Extracting {uploaded_file.name}..."):
            try:
                extracted = extract_text_from_pdf(uploaded_file.read())
                add_document(uploaded_file.name, extracted)
                added_count += 1
            except DocumentProcessingError as exc:
                failures.append((uploaded_file.name, str(exc)))
            except Exception:
                failures.append(
                    (
                        uploaded_file.name,
                        "This PDF could not be processed right now. Try again or paste the relevant text manually.",
                    )
                )

    return added_count, failures


def render_source_intake():
    with st.container(border=True):
        render_section_intro(
            "Source Intake",
            "Collect the protocol materials you want to assess. Strongest results usually come from combining docs, whitepapers, and at least one audit.",
        )

        tab_text, tab_pdf, tab_url = st.tabs(["Paste Text", "Upload PDF", "Fetch URL"])

        with tab_text:
            text_name = st.text_input("Document name", placeholder="e.g. Whitepaper", key="text_name")
            text_input = st.text_area(
                "Paste content here",
                height=200,
                placeholder="Paste unstructured text here...",
            )
            if st.button("Add text source", key="btn_text"):
                if text_input.strip():
                    name = text_name if text_name else f"Text Source {len(st.session_state.documents) + 1}"
                    add_document(name, text_input)
                    st.success(f"Added '{name}'.")
                else:
                    st.warning("Paste some text before adding a source.")

        with tab_pdf:
            uploaded_files = st.file_uploader("Upload PDF documents", type="pdf", accept_multiple_files=True)
            if st.button("Extract PDF source(s)", key="btn_pdf"):
                if uploaded_files:
                    added_count, failures = process_pdf_uploads(uploaded_files)
                    if added_count:
                        st.success(f"Added {added_count} PDF source(s).")
                    for file_name, message in failures:
                        st.error(f"{file_name}: {message}")
                else:
                    st.warning("Upload at least one PDF first.")

        with tab_url:
            url_name = st.text_input("Document name", placeholder="e.g. GitHub README", key="url_name")
            url_input = st.text_input("Enter URL", key="url_input")
            if st.button("Fetch URL source", key="btn_url"):
                if url_input:
                    with st.spinner("Fetching content..."):
                        try:
                            extracted = extract_text_from_url(url_input)
                            name = url_name if url_name else f"URL Source {len(st.session_state.documents) + 1}"
                            add_document(name, extracted)
                            st.success(f"Added '{name}'.")
                        except DocumentProcessingError:
                            st.error("The URL could not be processed. Check the URL and try again.")
                else:
                    st.warning("Enter a URL before fetching.")


def render_analyzer_workspace(backend_url: str, backend_status: dict, debug_mode: bool):
    st.title("On-Chain Due Diligence Workstation")
    st.caption("Daily protocol review with multi-source intake, evidence-backed findings, follow-up chat, and saved sessions.")

    render_status_cards(backend_status)
    st.divider()
    render_workflow_strip()

    top_left, top_right = st.columns([2, 1], gap="large", vertical_alignment="top")
    with top_left:
        render_source_intake()

    with top_right:
        run_clicked = render_action_center(backend_status)

    if run_clicked:
        session_id = create_new_session_id()
        st.session_state.chat_history = []
        st.session_state.loaded_from_history = False
        with st.spinner("Running assessment across the current source set..."):
            documents = [doc["text"] for doc in st.session_state.documents]
            result = analyze_protocol(documents, backend_url, session_id=session_id)
            st.session_state.analysis_result = result
            if "error" not in result:
                st.session_state.last_assessed_signature = document_signature()
        st.rerun()

    intake_col, results_col = st.columns([1, 1], gap="large", vertical_alignment="top")
    with intake_col:
        render_loaded_documents()
    with results_col:
        render_analysis_dashboard(st.session_state.analysis_result, backend_url, debug_mode)


def render_history_error_panel(error_message: str):
    with st.container(border=True):
        st.warning("Saved analyses are temporarily unavailable.")
        st.write(error_message)
        st.caption("You can keep using Analyzer while the backend history path recovers.")
        action_cols = st.columns(2)
        if action_cols[0].button("Retry History", use_container_width=True):
            st.session_state.history_open_error = None
            st.rerun()
        if action_cols[1].button("Go to Analyzer", use_container_width=True):
            request_workspace_mode("Analyzer")
            st.rerun()


def render_history_workspace(backend_url: str, backend_status: dict):
    st.title("Saved Analyses")
    st.caption("Reload prior protocol reviews, compare recent work, and continue from saved backend state.")

    if st.session_state.history_open_error:
        with st.container(border=True):
            st.warning("The selected saved session could not be opened.")
            st.write(st.session_state.history_open_error)

    render_status_cards(backend_status)
    st.divider()

    top_cols = st.columns([3, 1])
    search_query = top_cols[0].text_input("Search saved analyses", placeholder="Filter by project name or chain")
    if top_cols[1].button("Refresh", use_container_width=True):
        st.session_state.history_open_error = None
        st.rerun()

    if not backend_status.get("ok"):
        render_history_error_panel("The backend is not reachable, so saved sessions cannot be loaded right now.")
        return

    history = fetch_analysis_history(backend_url, limit=30)
    if "error" in history:
        render_history_error_panel(history["error"])
        return

    items = history.get("items", [])
    if search_query:
        needle = search_query.lower().strip()
        items = [
            item for item in items
            if needle in item.get("project_name", "").lower()
            or needle in item.get("chain", "").lower()
            or needle in item.get("category", "").lower()
        ]

    if not items:
        with st.container(border=True):
            st.markdown("**No saved analyses available**")
            st.write(
                "Saved assessments appear here after you run an analysis from the Analyzer workspace. "
                "Use History to revisit evidence, reopen a session, and continue your investigation."
            )
        return

    metrics = st.columns(3)
    metrics[0].metric("Saved Sessions", len(items))
    metrics[1].metric(
        "High / Critical",
        sum(1 for item in items if item.get("overall_risk_level") in {"High", "Critical"}),
    )
    metrics[2].metric("Most Recent", format_timestamp(items[0].get("created_at")))

    for item in items:
        with st.container(border=True):
            header_col, meta_col, action_col = st.columns([3, 2, 1])
            header_col.markdown(f"**{item.get('project_name', 'Unknown Project')}**")
            header_col.caption(f"Session `{item.get('session_id', '')[:8]}`")
            header_col.write(item.get("recommended_action", ""))

            meta_col.caption(f"{item.get('chain', 'Unknown')} • {item.get('category', 'Unknown')}")
            meta_col.markdown(
                f"Risk: `{item.get('overall_risk_level', 'Unknown')}` ({item.get('risk_score', 0)}/100)"
            )
            meta_col.caption(f"Saved {format_timestamp(item.get('created_at'))}")

            if action_col.button("Open", key=f"load_{item.get('session_id')}", use_container_width=True):
                open_saved_session(item["session_id"], backend_url)


initialize_state()
apply_pending_workspace_mode()

with st.sidebar:
    st.header("Workspace")
    st.radio(
        "Mode",
        WORKSPACE_MODES,
        key="workspace_mode_selector",
        on_change=sync_workspace_mode,
    )

    st.divider()
    st.header("Connection")
    backend_url = st.text_input(
        "Backend URL",
        value=DEFAULT_BACKEND_URL,
        help="Point this to your local API or a deployed FastAPI instance.",
    )
    backend_status = get_backend_status(backend_url)
    if backend_status.get("ok"):
        st.success(f"Backend: {backend_status['label']}")
    else:
        st.error(f"Backend: {backend_status['label']}")
    st.caption(backend_status.get("detail", ""))

    st.divider()
    st.header("Current Session")
    st.caption(f"Session `{short_session_id()}`")
    st.caption(f"Sources loaded: {document_summary()['count']}")
    debug_mode = st.checkbox("Show debug data", value=False)

    st.divider()
    if st.button("Reset workspace", use_container_width=True):
        reset_workspace()


if st.session_state.workspace_mode == "Analyzer":
    render_analyzer_workspace(backend_url, backend_status, debug_mode)
else:
    render_history_workspace(backend_url, backend_status)
