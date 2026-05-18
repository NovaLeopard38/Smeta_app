def test_tts_without_credentials_returns_4xx(client):
    """POST /voice/tts without Tinkoff credentials should return 400, not 500."""
    res = client.post(
        "/voice/tts",
        json={
            "text": "test",
            "voice": "",
            "sample_rate": 8000,
            "encoding": "MPEG_AUDIO",
        },
    )
    # Should be 400 (keys not configured) not 500 (unhandled exception)
    assert res.status_code == 400
