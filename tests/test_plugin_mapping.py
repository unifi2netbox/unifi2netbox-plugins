from netbox_unifi2netbox.services.mapping import merge_tags, resolve_site_name


def test_resolve_site_name_with_mapping():
    mapping = {"UniFi-HQ": "NetBox-HQ"}
    assert resolve_site_name("UniFi-HQ", mapping, default_site_name="Fallback") == "NetBox-HQ"


def test_resolve_site_name_without_mapping_uses_source():
    assert resolve_site_name("UniFi-Branch", {}, default_site_name="Fallback") == "UniFi-Branch"


def test_merge_tags_append_dedupes_case_insensitive():
    merged = merge_tags(["wireless", "AP"], ["ap", "unifi"], strategy="append")
    assert merged == ["wireless", "AP", "unifi"]


def test_merge_tags_replace():
    assert merge_tags(["old"], ["new", "tag"], strategy="replace") == ["new", "tag"]


def test_merge_tags_none():
    assert merge_tags(["keep"], ["ignored"], strategy="none") == ["keep"]
