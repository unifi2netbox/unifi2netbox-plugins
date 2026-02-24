import types

from netbox_unifi_sync.services.runtime import (
    group_runtimes_by_auth,
    redact_runtime,
    to_controller_runtime,
)


def test_to_controller_runtime_resolves_secret_refs(monkeypatch):
    monkeypatch.setenv("UNIFI_TEST_API_KEY", "abc123")
    controller = types.SimpleNamespace(
        name="ctrl1",
        base_url="https://unifi.local",
        auth_mode="api_key",
        api_key_ref="env:UNIFI_TEST_API_KEY",
        api_key_header="X-API-KEY",
        username_ref="",
        password_ref="",
        mfa_secret_ref="",
        verify_ssl=True,
        request_timeout=None,
        http_retries=None,
        retry_backoff_base=None,
        retry_backoff_max=None,
    )

    cfg = to_controller_runtime(controller, {"request_timeout": 15, "http_retries": 3, "retry_backoff_base": 1.0, "retry_backoff_max": 30.0, "verify_ssl_default": True})

    assert cfg.api_key == "abc123"
    assert cfg.request_timeout == 15
    assert cfg.http_retries == 3


def test_group_runtimes_by_auth_is_deterministic(monkeypatch):
    monkeypatch.setenv("UNIFI_KEY_1", "same")

    c1 = types.SimpleNamespace(
        name="a",
        base_url="https://a",
        auth_mode="api_key",
        api_key_ref="env:UNIFI_KEY_1",
        api_key_header="X-API-KEY",
        username_ref="",
        password_ref="",
        mfa_secret_ref="",
        verify_ssl=True,
        request_timeout=None,
        http_retries=None,
        retry_backoff_base=None,
        retry_backoff_max=None,
    )
    c2 = types.SimpleNamespace(**{**c1.__dict__, "name": "b", "base_url": "https://b"})

    defaults = {"request_timeout": 15, "http_retries": 3, "retry_backoff_base": 1.0, "retry_backoff_max": 30.0, "verify_ssl_default": True}
    grouped = group_runtimes_by_auth([to_controller_runtime(c1, defaults), to_controller_runtime(c2, defaults)])
    assert len(grouped) == 1


def test_redact_runtime_masks_secrets(monkeypatch):
    monkeypatch.setenv("UNIFI_TEST_API_KEY", "sensitive")
    controller = types.SimpleNamespace(
        name="ctrl1",
        base_url="https://unifi.local",
        auth_mode="api_key",
        api_key_ref="env:UNIFI_TEST_API_KEY",
        api_key_header="X-API-KEY",
        username_ref="",
        password_ref="",
        mfa_secret_ref="",
        verify_ssl=True,
        request_timeout=None,
        http_retries=None,
        retry_backoff_base=None,
        retry_backoff_max=None,
    )
    defaults = {"request_timeout": 15, "http_retries": 3, "retry_backoff_base": 1.0, "retry_backoff_max": 30.0, "verify_ssl_default": True}
    masked = redact_runtime(to_controller_runtime(controller, defaults))
    assert masked["api_key"] == "***"
