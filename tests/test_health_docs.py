from datetime import date
from unittest.mock import patch

import pytest
from django.db.utils import OperationalError


@pytest.mark.django_db
def test_health(client):
    response = client.get("/health/")
    assert response.status_code == 200
    assert response.data == {"status": "ok", "version": "1.0.0", "revision": "", "demo_until": None}


@pytest.mark.django_db
def test_health_reports_revision_and_demo_end(client, settings):
    settings.REVISION = "abc123"
    settings.DEMO_UNTIL = date(2026, 12, 27)
    response = client.get("/health/")
    assert (response.data["revision"], response.data["demo_until"]) == (
        "abc123",
        date(2026, 12, 27),
    )


def test_health_hides_database_errors(client):
    with patch("config.views.connection.cursor", side_effect=OperationalError("private detail")):
        response = client.get("/health/")
    assert response.status_code == 503
    assert response.data["status"] == "unavailable"
    assert "private detail" not in str(response.data)


def test_root_opens_the_api_documentation(client):
    response = client.get("/")
    assert response.status_code == 302
    assert response["Location"] == "/api/docs/"


@pytest.mark.parametrize("path", ["/api/schema/", "/api/docs/", "/api/redoc/", "/admin/login/"])
def test_documentation_and_admin_available(client, path):
    assert client.get(path).status_code == 200
