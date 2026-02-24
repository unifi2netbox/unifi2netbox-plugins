import main


def test_extract_asset_tag_default_pattern(monkeypatch):
    monkeypatch.delenv("UNIFI_ASSET_TAG_PATTERNS", raising=False)
    monkeypatch.setenv("UNIFI_ASSET_TAG_ENABLED", "true")
    assert main.extract_asset_tag("IT-AULA-AP02-ID3006") == "ID3006"


def test_extract_asset_tag_custom_pattern_list(monkeypatch):
    monkeypatch.setenv("UNIFI_ASSET_TAG_ENABLED", "true")
    monkeypatch.setenv("UNIFI_ASSET_TAG_PATTERNS", '["ASSET[: -]?(\\\\d+)$", "T-([A-Z0-9]+)$"]')
    assert main.extract_asset_tag("Branch-ASSET-9842") == "9842"
    assert main.extract_asset_tag("EDGE-T-AB12") == "AB12"


def test_extract_asset_tag_disabled(monkeypatch):
    monkeypatch.setenv("UNIFI_ASSET_TAG_ENABLED", "false")
    monkeypatch.setenv("UNIFI_ASSET_TAG_PATTERNS", '["(ID\\\\d+)$"]')
    assert main.extract_asset_tag("SW-ID1234") is None


def test_extract_asset_tag_no_capture_group(monkeypatch):
    monkeypatch.setenv("UNIFI_ASSET_TAG_ENABLED", "true")
    monkeypatch.setenv("UNIFI_ASSET_TAG_PATTERNS", "[A-Z]{3}-[0-9]{4}$")
    assert main.extract_asset_tag("foo-ABC-1234") == "ABC-1234"
