"""Smoke tests for WebApp API integration."""

import pytest
from fastapi.testclient import TestClient

from backend.apps.admin_api.main import create_app


class TestWebAppSmoke:
    """Smoke tests for WebApp API endpoints availability."""

    def test_app_starts_with_webapp_router(self):
        """Test that FastAPI app starts successfully with WebApp router mounted."""
        app = create_app()
        assert app is not None
        
        # Check that WebApp router is mounted
        routes = [route.path for route in app.routes]
        assert "/api/webapp/me" in routes or any("/api/webapp" in route for route in routes)

    def test_root_endpoint_includes_webapp(self):
        """Test that root endpoint advertises webapp_api."""
        app = create_app()
        client = TestClient(app)
        
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "webapp_api" in data
        assert data["webapp_api"] == "/api/webapp"

    def test_webapp_endpoints_exist(self):
        """Test that WebApp endpoints are registered (not testing auth)."""
        app = create_app()
        routes = [route.path for route in app.routes]
        
        # Check that key WebApp endpoints exist
        expected_paths = [
            "/api/webapp/me",
            "/api/webapp/slots",
            "/api/webapp/booking",
            "/api/webapp/cancel",
        ]
        
        for expected_path in expected_paths:
            # Check if exact path or path with prefix exists
            assert any(
                expected_path in route for route in routes
            ), f"Expected endpoint {expected_path} not found in routes"
