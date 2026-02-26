# Troubleshooting

## Quick Triage

1. Check `Plugins -> UniFi Sync -> Runs` for the latest run status/error.
2. Check worker logs:
   - Docker: `docker compose logs -f netbox-worker`
3. Validate plugin setup:
   - `Settings` has `tenant_name` and `netbox_roles`
   - At least one enabled controller has valid auth config
   - Site mappings exist where names differ

## Common Issues

### `HTTPConnectionPool(host='netbox', port=8080)` error

This error indicates an outdated plugin version (0.1.3 or earlier) that used a hardcoded Docker-only fallback URL. It does not work on standard server installs.

Upgrade to fix:

```bash
pip install --upgrade netbox-unifi-sync
python manage.py migrate
# restart netbox + netbox-worker
```

### `could not be found` for `http://localhost/api/...` or `http://127.0.0.1/api/...`

The sync worker auto-detects the internal NetBox URL. If it resolves to the wrong host or port:

1. Go to **Plugins → UniFi Sync → Settings**
2. Set **NetBox URL** to the internal API base, e.g. `http://127.0.0.1:8000`
3. Save and re-run

Or set `NETBOX_URL=http://127.0.0.1:8000` in the NetBox worker environment.

This is most common on Debian/venv installs where gunicorn listens on port 8000.

Requires plugin version 0.1.8 or later.

### Connection timeout / connection refused

Check:

- controller URL in `Controllers`
- network reachability from NetBox worker container/host
- TLS/SSL settings (`verify_ssl`)
- `request_timeout` value

### Authentication failed (`401`/`403`)

For `api_key` mode:

- verify `api_key_ref` in the controller row contains a valid local UniFi Integration API key
- verify header (`api_key_header`)
- do not place UniFi credentials in `PLUGINS_CONFIG`

For `login` mode:

- verify `username_ref` and `password_ref`
- verify optional `mfa_secret_ref` when required

### Plugin page errors / namespace errors

Check:

- plugin enabled in NetBox config:
  - `PLUGINS = ["netbox_unifi_sync"]`
- plugin package installed in both `netbox` and `netbox-worker`
- migrations applied

Useful checks:

```bash
python manage.py showmigrations netbox_unifi_sync
python manage.py check
```

### No devices created

Check in order:

1. Controller test connection passes
2. `tenant_name` + `netbox_roles` are configured
3. Site mappings are correct
4. Run detail does not contain skipped site mapping warnings

### Prefix exists but DHCP range missing

Check:

- DHCP is enabled on UniFi network
- `dhcp_auto_discover` enabled
- DHCP range sync enabled (internal `SYNC_DHCP_RANGES=true`)

### Expected prefixes not created

Check:

- prefix sync enabled (internal `SYNC_PREFIXES=true`)
- network has valid subnet/CIDR in UniFi data
- run detail for per-site errors

### Worker not processing jobs

Check:

- `netbox-worker` container/service is running
- RQ queues active (`high`, `default`, `low`)
- no startup install failure for plugin package

## Debug Commands

```bash
# Dry-run from NetBox runtime
python manage.py netbox_unifi_sync_run --dry-run --json

# Cleanup run
python manage.py netbox_unifi_sync_run --cleanup

# Migration state
python manage.py showmigrations netbox_unifi_sync
```

## When opening an issue

Include:

- NetBox version
- plugin version
- deployment mode (venv or netbox-docker)
- relevant run error from `Runs` detail
- worker log excerpt

Do not include credentials, tokens, cookies, or private secrets.
