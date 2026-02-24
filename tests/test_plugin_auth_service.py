from netbox_unifi2netbox.services.auth import UnifiAuthError, UnifiAuthSettings


def test_auth_settings_validation_api_key_mode_requires_key():
    settings = UnifiAuthSettings(
        auth_mode="api_key",
        api_key="",
        api_key_header="X-API-KEY",
        username="",
        password="",
        mfa_secret="",
    )
    try:
        settings.validate()
        assert False, "Expected UnifiAuthError for missing API key"
    except UnifiAuthError as exc:
        assert "api_key" in str(exc)


def test_auth_settings_validation_login_mode_requires_username_password():
    settings = UnifiAuthSettings(
        auth_mode="login",
        api_key="",
        api_key_header="X-API-KEY",
        username="admin",
        password="",
        mfa_secret="",
    )
    try:
        settings.validate()
        assert False, "Expected UnifiAuthError for missing password"
    except UnifiAuthError as exc:
        assert "username and password" in str(exc)


def test_build_client_uses_login_fields(monkeypatch):
    calls = {}

    class DummyUnifi:
        def __init__(self, **kwargs):
            calls.update(kwargs)

    monkeypatch.setattr("netbox_unifi2netbox.services.auth.Unifi", DummyUnifi)
    settings = UnifiAuthSettings(
        auth_mode="login",
        api_key="",
        api_key_header="X-API-KEY",
        username="admin",
        password="secret",
        mfa_secret="mfa",
    )
    settings.build_client(base_url="https://unifi.local")
    assert calls["base_url"] == "https://unifi.local"
    assert calls["username"] == "admin"
    assert calls["password"] == "secret"
    assert calls["mfa_secret"] == "mfa"
    assert "api_key" not in calls


def test_build_client_disables_fallback_in_api_key_mode(monkeypatch):
    calls = {}

    class DummyUnifi:
        def __init__(self, **kwargs):
            calls.update(kwargs)

    monkeypatch.setattr("netbox_unifi2netbox.services.auth.Unifi", DummyUnifi)
    settings = UnifiAuthSettings(
        auth_mode="api_key",
        api_key="abc123",
        api_key_header="X-API-KEY",
        username="admin",
        password="secret",
        mfa_secret="",
    )
    settings.build_client(base_url="https://unifi.local")
    assert calls["api_key"] == "abc123"
    assert calls["allow_login_fallback"] is False
    assert "username" not in calls
