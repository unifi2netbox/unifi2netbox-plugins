# Troubleshooting

## Plugin not visible in menu

Check:

- `PLUGINS = ["netbox_unifi_sync"]`
- Migrations applied:

```bash
python manage.py showmigrations netbox_unifi_sync
```

## Sync runs but devices are skipped

Most common cause: missing site mapping.

Validate UniFi site names vs NetBox site names and add mapping rows.

## Connection error to `netbox:8080` or `http://localhost`

This only occurs with plugin version 0.1.x which used HTTP self-calls to NetBox. Since v0.2.0 the plugin uses the Django ORM directly — no internal HTTP call is needed. Upgrade to the latest version:

```bash
pip install --upgrade netbox-unifi-sync
python manage.py migrate
# restart netbox + netbox-worker
```

## PyPI publish fails with trusted publisher

Check exact publisher tuple in PyPI:

- owner/repo/workflow/environment must match GitHub claims exactly.

## PyPI publish fails with filename reuse

Bump version and publish new artifacts.

Reference: [docs/troubleshooting.md](https://github.com/unifi2netbox/netbox-unifi-sync/blob/main/docs/troubleshooting.md)
