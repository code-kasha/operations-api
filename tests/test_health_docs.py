from unittest.mock import patch

import pytest
from django.db.utils import OperationalError


@pytest.mark.django_db
def test_health(client):
    response = client.get("/health/")
    assert response.status_code == 200
    assert response.data == {"status": "ok"}


def test_health_hides_database_errors(client):
    with patch("config.views.connection.cursor", side_effect=OperationalError("private detail")):
        response = client.get("/health/")
    assert response.status_code == 503
    assert response.data == {"status": "unavailable"}


@pytest.mark.parametrize("path", ["/api/schema/", "/api/docs/", "/api/redoc/", "/admin/login/"])
def test_documentation_and_admin_available(client, path):
    assert client.get(path).status_code == 200
