import pytest

pytestmark = pytest.mark.django_db


def login(client):
    return client.post(
        "/api/v1/auth/token/",
        {
            "username": "fictional.staff",
            "password": "Fictional-test-password-42!",
        },
    )


def test_current_user_requires_authentication(client):
    assert client.get("/api/v1/auth/me/").status_code == 401


def test_login_and_current_user(client, user):
    response = login(client)
    assert response.status_code == 200
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    response = client.get("/api/v1/auth/me/")
    assert response.status_code == 200
    assert response.data["id"] == user.pk
    assert "password" not in response.data


def test_refresh_rotates_and_revokes_old_token(client, user):
    original = login(client).data["refresh"]
    response = client.post("/api/v1/auth/token/refresh/", {"refresh": original})
    assert response.status_code == 200
    assert response.data["refresh"] != original
    assert client.post("/api/v1/auth/token/refresh/", {"refresh": original}).status_code == 401
    assert (
        client.post(
            "/api/v1/auth/token/refresh/",
            {"refresh": response.data["refresh"]},
        ).status_code
        == 200
    )


def test_logout_revokes_refresh(client, user):
    refresh = login(client).data["refresh"]
    assert client.post("/api/v1/auth/logout/", {"refresh": refresh}).status_code == 200
    assert client.post("/api/v1/auth/token/refresh/", {"refresh": refresh}).status_code == 401


def test_inactive_user_cannot_login(client, user):
    user.is_active = False
    user.save()
    assert login(client).status_code == 401


def test_bad_credentials(client, user):
    assert (
        client.post(
            "/api/v1/auth/token/",
            {
                "username": user.username,
                "password": "wrong",
            },
        ).status_code
        == 401
    )


def test_invalid_bearer_token(client):
    client.credentials(HTTP_AUTHORIZATION="Bearer invalid")
    assert client.get("/api/v1/auth/me/").status_code == 401


def test_login_is_throttled(client):
    for _ in range(30):
        assert client.post("/api/v1/auth/token/", {}).status_code == 400
    assert client.post("/api/v1/auth/token/", {}).status_code == 429
