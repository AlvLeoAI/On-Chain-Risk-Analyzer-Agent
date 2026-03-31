import uuid

import requests
import streamlit as st


DEFAULT_TIMEOUT = 240
STATUS_TIMEOUT = 4


def get_session_id() -> str:
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    return st.session_state.session_id


def set_session_id(session_id: str) -> str:
    st.session_state.session_id = session_id
    return session_id


def create_new_session_id() -> str:
    return set_session_id(str(uuid.uuid4()))


def _format_error(resp, exc: Exception) -> dict:
    detail = None
    status_code = getattr(resp, "status_code", None)
    try:
        if resp is not None:
            data = resp.json()
            if isinstance(data, dict):
                detail = data.get("detail")
            elif isinstance(data, str):
                detail = data
    except Exception:
        detail = None

    if status_code == 404:
        return {"error": detail or "The requested item could not be found."}
    if status_code and status_code >= 500:
        return {"error": detail or "The backend hit an internal error while processing this request."}
    if detail:
        return {"error": detail}
    return {"error": f"Request failed: {str(exc)}"}


def get_backend_status(api_url: str) -> dict:
    resp = None
    try:
        resp = requests.get(
            f"{api_url}/health",
            timeout=STATUS_TIMEOUT,
        )
        data = resp.json()
        db_status = data.get("database", {}) if isinstance(data, dict) else {}
        db_connected = db_status.get("connected", True)
        api_healthy = data.get("status") == "healthy"

        if resp.ok and api_healthy and db_connected:
            return {
                "ok": True,
                "label": "Connected",
                "detail": data.get("service", "backend ready"),
            }

        return {
            "ok": False,
            "label": "Degraded",
            "detail": db_status.get("detail") or data.get("service", "backend not ready"),
        }
    except requests.exceptions.ConnectionError:
        return {
            "ok": False,
            "label": "Unavailable",
            "detail": "The backend could not be reached.",
        }
    except requests.exceptions.Timeout:
        return {
            "ok": False,
            "label": "Slow / unavailable",
            "detail": "The backend did not answer in time.",
        }
    except requests.exceptions.RequestException as exc:
        error = _format_error(resp, exc)
        return {
            "ok": False,
            "label": "Error",
            "detail": error["error"],
        }


def analyze_protocol(documents: list[str], api_url: str, session_id: str | None = None) -> dict:
    session_id = session_id or create_new_session_id()

    resp = None
    try:
        resp = requests.post(
            f"{api_url}/api/v1/analyze",
            json={"session_id": session_id, "documents": documents},
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        return {"error": "Could not connect to backend. Is it running?"}
    except requests.exceptions.Timeout:
        return {"error": "Request timed out. Try again."}
    except requests.exceptions.RequestException as exc:
        return _format_error(resp, exc)


def chat_with_agent(
    documents: list[str],
    message: str,
    api_url: str,
    session_id: str | None = None,
) -> dict:
    session_id = session_id or get_session_id()

    resp = None
    try:
        resp = requests.post(
            f"{api_url}/api/v1/chat",
            json={
                "session_id": session_id,
                "documents": documents,
                "message": message,
            },
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        return {"error": "Could not connect to backend. Is it running?"}
    except requests.exceptions.Timeout:
        return {"error": "Request timed out. Try again."}
    except requests.exceptions.RequestException as exc:
        return _format_error(resp, exc)


def fetch_pdf_report(session_id: str, api_url: str) -> bytes | None:
    try:
        resp = requests.get(
            f"{api_url}/api/v1/report/{session_id}",
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.content
    except Exception:
        return None


def fetch_analysis_history(api_url: str, limit: int = 20) -> dict:
    resp = None
    try:
        resp = requests.get(
            f"{api_url}/api/v1/history",
            params={"limit": limit},
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        return {"error": "Could not connect to backend. Is it running?"}
    except requests.exceptions.Timeout:
        return {"error": "Request timed out. Try again."}
    except requests.exceptions.RequestException as exc:
        return _format_error(resp, exc)


def fetch_analysis_detail(session_id: str, api_url: str) -> dict:
    resp = None
    try:
        resp = requests.get(
            f"{api_url}/api/v1/history/{session_id}",
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        return {"error": "Could not connect to backend. Is it running?"}
    except requests.exceptions.Timeout:
        return {"error": "Request timed out. Try again."}
    except requests.exceptions.RequestException as exc:
        return _format_error(resp, exc)
