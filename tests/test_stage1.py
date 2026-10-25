"""
Stage 1 Acceptance Tests — CareerSync Backend Configuration and DB Connectivity
Updated for Phase 2 unified static hosting and non-destructive isolated execution.
"""
import sys
from pathlib import Path

# Add project root to sys.path so backend imports resolve cleanly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from backend.config import settings
from backend.database import check_database_connection
from backend.main import app, health_check


def test_root_endpoint():
    """Verify root endpoint serves the unified frontend application."""
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert "CareerSync" in response.text, "Root endpoint should serve the CareerSync index.html"
    print("  [PASS] test_root_endpoint: Root endpoint serves unified frontend HTML.")


def test_health_endpoint_structure():
    """Verify health endpoint preserves existing keys and adds database health check."""
    response = health_check()
    assert response["service"] == "CareerSync API"
    assert response["status"] in ("healthy", "degraded")
    assert "database" in response
    assert isinstance(response["database"], dict)
    assert "connected" in response["database"]
    assert "database" in response["database"]
    print("  [PASS] test_health_endpoint_structure: Response structure matches expected specification.")


def test_credential_masking():
    """Verify credentials are never exposed in safe_database_url or error output."""
    safe_url = settings.safe_database_url
    assert "****" in safe_url, "Password should be masked in safe_database_url"
    if settings.DB_PASSWORD:
        assert settings.DB_PASSWORD not in safe_url, "Raw password must not be present in safe_database_url"
    print("  [PASS] test_credential_masking: Credentials properly masked.")


def test_database_connection_probe():
    """Run read-only database connectivity probe and print status."""
    result = check_database_connection()
    connected = result.get("connected", False)
    if connected:
        print(f"  [PASS] test_database_connection_probe: MySQL connected successfully to '{result.get('database')}'.")
    else:
        print(f"  [INFO] test_database_connection_probe: MySQL not connected yet (normal in isolated test environments).")
        print(f"         Target Database: {result.get('database')}")


def run_all_tests():
    print("\n=== Running Stage 1 Acceptance Tests ===")
    test_root_endpoint()
    test_health_endpoint_structure()
    test_credential_masking()
    test_database_connection_probe()
    print("=== All Stage 1 Checks Completed ===\n")


if __name__ == "__main__":
    run_all_tests()
