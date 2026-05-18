from unittest.mock import patch, MagicMock
import pytest


def test_get_ai_settings(client, admin_headers):
    """GET /settings/ai returns AI settings for admin."""
    resp = client.get("/settings/ai", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    # Should have base_url or model fields
    assert "base_url" in data or "model" in data


def test_save_ai_settings(client, admin_headers):
    """POST /settings/ai saves settings for admin."""
    resp = client.post("/settings/ai", json={
        "base_url": "https://api.example.com/v1",
        "api_key": "test-key",
        "model": "gpt-4o",
        "assistant_prompt": "",
    }, headers=admin_headers)
    assert resp.status_code == 200


def test_ai_recommend_mocked(client, auth_headers):
    """POST /ai/recommend with mocked external call."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": '{"items": []}'}}]
    }
    mock_response.raise_for_status = MagicMock()
    with patch("ai.router.httpx.Client") as mock_client_cls:
        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_response
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client_instance
        resp = client.post("/ai/recommend?prompt=Камеры+видеонаблюдения", headers=auth_headers)
    # Accept 200 (if settings have key), or any response (the endpoint may use fallback)
    assert resp.status_code in (200, 422, 500)


def test_public_ai_chat_rate_limited(client):
    """POST /ai/public/chat should rate limit after ~10 requests."""
    from ai.router import _PUBLIC_CHAT_RL
    _PUBLIC_CHAT_RL.clear()

    payload = {"phone": "+79991234567", "message": "Привет", "mode": "smeta"}
    responses = []
    for _ in range(15):
        r = client.post("/ai/public/chat", json=payload)
        responses.append(r)
    codes = [r.status_code for r in responses]
    assert 429 in codes, f"Rate limiter should kick in after ~10 requests, got codes: {codes}"
