import pytest
from fastapi.testclient import TestClient
import main
from main import app
from app.models import ChainType, ProtocolCategory, AuditStatus

client = TestClient(app)

def test_health_check(monkeypatch):
    """Test the health check endpoint."""
    async def fake_status():
        return {
            "configured": True,
            "connected": True,
            "detail": "Database connection verified.",
        }

    monkeypatch.setattr(main, "get_database_status", fake_status)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "on-chain-analyzer",
        "database": {
            "configured": True,
            "connected": True,
            "detail": "Database connection verified.",
        },
    }


def test_health_endpoint_reports_service_name():
    """Health response should include the service identifier."""
    response = client.get("/health")
    data = response.json()
    assert data.get("service") == "on-chain-analyzer"


def test_analyze_endpoint_rejects_empty_request():
    """POST /api/v1/analyze with no documents should return 400."""
    response = client.post("/api/v1/analyze", json={"documents": []})
    assert response.status_code == 400
    assert "No documents" in response.json()["detail"]


def test_unknown_route_returns_404():
    """Requesting an undefined path should return 404."""
    response = client.get("/api/v1/nonexistent")
    assert response.status_code == 404
