from netbox_unifi_sync.services.audit import sanitize_error


def test_sanitize_error_masks_token_and_password():
    text = "Authorization: Bearer supersecret password=admin123"
    cleaned = sanitize_error(text)
    assert "supersecret" not in cleaned
    assert "admin123" not in cleaned
