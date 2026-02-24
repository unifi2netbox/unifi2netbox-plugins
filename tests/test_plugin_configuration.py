import os

from netbox_unifi2netbox.configuration import (
    plugin_settings_to_env,
    resolve_secret_value,
    validate_plugin_settings,
)


def test_resolve_secret_from_env(monkeypatch):
    monkeypatch.setenv("UNIFI_TEST_KEY", "secret-value")
    assert resolve_secret_value("env:UNIFI_TEST_KEY") == "secret-value"


def test_plugin_settings_to_env_maps_core_values(monkeypatch):
    monkeypatch.setenv("NB_TEST_TOKEN", "nb-token")
    settings = {
        "unifi_urls": ["https://unifi.example.com/integration/v1"],
        "unifi_api_key": "abc123",
        "netbox_url": "https://netbox.example.com",
        "netbox_token": "env:NB_TEST_TOKEN",
        "netbox_import_tenant": "Example Tenant",
        "netbox_roles": {"WIRELESS": "Wireless AP"},
        "unifi_site_mappings": {"Default": "HQ"},
        "sync_interfaces": True,
    }

    env = plugin_settings_to_env(settings)
    assert env["UNIFI_URLS"] == '["https://unifi.example.com/integration/v1"]'
    assert env["NETBOX_URL"] == "https://netbox.example.com"
    assert env["NETBOX_TOKEN"] == "nb-token"
    assert env["NETBOX_ROLES"] == '{"WIRELESS": "Wireless AP"}'
    assert env["UNIFI_SITE_MAPPINGS"] == '{"Default": "HQ"}'
    assert env["SYNC_INTERVAL"] == "0"


def test_validate_plugin_settings_reports_missing_values():
    errors = validate_plugin_settings({})
    assert any("unifi_urls" in msg for msg in errors)
    assert any("netbox_url" in msg for msg in errors)
    assert any("netbox_token" in msg for msg in errors)
    assert any("netbox_roles" in msg for msg in errors)
