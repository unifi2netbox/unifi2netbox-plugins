# netbox_unifi_sync

> [!WARNING]
> We are aware that there are issues in the codebase.
> This is a hobby project maintained in spare time.
> Fixes and improvements are implemented when time allows.
> Do not deploy in production without proper validation.

`netbox_unifi_sync` is a NetBox 4.2+ plugin that runs UniFi -> NetBox sync jobs inside NetBox workers.

---

> [!IMPORTANT]
> NetBox should be treated as the Source of Truth.
> Objects created or managed by this plugin should not be manually modified unless you understand how future sync runs will affect them.

---

## Visual Overview

![netbox-unifi-sync overview](docs/assets/netbox-unifi-sync-overview.svg)

```mermaid
flowchart LR
    U["UniFi Controller(s)"] --> P["netbox_unifi_sync plugin<br/>NetBox Jobs (RQ)"]
    P --> N["NetBox DCIM/IPAM/Wireless"]
    A["Plugin UI<br/>Settings/Controllers/Mappings"] --> P
```

---

## Architecture & Internal Flow

### Runtime Execution Flow

```mermaid
flowchart TD
    A[Scheduled Job / Manual Trigger] --> B[NetBox RQ Worker]
    B --> C[Load Plugin Settings]
    C --> D[Authenticate to UniFi]
    D --> E[Fetch Data from UniFi API]
    E --> F[Normalize / Map Data]
    F --> G[Create / Update NetBox Objects]
    G --> H[Write Audit Log]
```

---

### Detailed Sync Pipeline

```mermaid
flowchart LR
    U[UniFi API] --> V[Devices]
    U --> W[VLANs]
    U --> X[WLANs]
    U --> Y[DHCP Scopes]

    V --> M1[Device Mapping]
    W --> M2[VLAN Mapping]
    X --> M3[Wireless Mapping]
    Y --> M4[IP Range Mapping]

    M1 --> NB[NetBox ORM]
    M2 --> NB
    M3 --> NB
    M4 --> NB

    NB --> DB[(NetBox Database)]
```

---

### Object Lifecycle Logic

```mermaid
flowchart TD
    A[UniFi Object] --> B{Exists in NetBox?}
    B -- Yes --> C[Update Object]
    B -- No --> D[Create Object]
    C --> E[Mark as Synced]
    D --> E
    E --> F{Cleanup Enabled?}
    F -- Yes --> G[Remove Stale Objects]
    F -- No --> H[Keep Orphaned Objects]
```

---

### Authentication Flow

```mermaid
flowchart LR
    A[Plugin Settings] --> B{Auth Mode}
    B -- API Key --> C[Attach Authorization Header]
    B -- Username/Password --> D[Session Login]
    D --> E[Optional MFA]
    C --> F[Authenticated API Session]
    E --> F
    F --> G[Execute Requests]
```

---

### Error Handling & Retry Logic

```mermaid
flowchart TD
    A[API Request] --> B{Success?}
    B -- Yes --> C[Process Response]
    B -- No --> D{Retry < Max Attempts?}
    D -- Yes --> E[Backoff + Retry]
    D -- No --> F[Log Error]
    F --> G[Mark Job Failed]
```

---

## Features

- Device sync (devices, interfaces, VLANs, prefixes, WLANs, uplink relations, IP assignments)
- DHCP scope sync to NetBox IP Ranges
- UniFi auth via API key or legacy login (username/password + optional MFA)
- Manual and scheduled sync jobs
- Runtime settings stored in plugin models (`Settings`, `Controllers`, `Site mappings`)

> [!NOTE]
> Sync is strictly one-way: UniFi -> NetBox.
> No configuration is ever pushed back to UniFi.

---

## Quick Start

### 1. Install

```bash
pip install netbox-unifi-sync
```

PyPI project page:
https://pypi.org/project/netbox-unifi-sync/

For `netbox-docker`, add the package to `local_requirements.txt` before build:

```bash
echo "netbox-unifi-sync" >> local_requirements.txt
```

> [!IMPORTANT]
> The plugin must be installed in the same environment as both NetBox and the worker container.
> Otherwise scheduled jobs will fail.

---

### 2. Enable plugin in NetBox

```python
PLUGINS = ["netbox_unifi_sync"]

PLUGINS_CONFIG = {
    "netbox_unifi_sync": {}
}
```

---

### 3. Apply migrations

```bash
python manage.py migrate
```

> [!CAUTION]
> Skipping migrations will result in database errors and plugin initialization failure.

---

### 4. Configure in UI

Go to:

Plugins -> UniFi Sync

Configure:

1. Settings (`tenant_name`, `netbox_roles`, defaults)
2. Controllers (URL, auth mode, credentials)
3. Site mappings (if UniFi/NetBox site names differ)

> [!TIP]
> Use a dedicated read-only API account in UniFi for synchronization.
> This limits impact if credentials are exposed.

---

### 5. Run first sync

UI:
Plugins -> UniFi Sync -> Sync Dashboard -> Run now

CLI:

```bash
python manage.py netbox_unifi_sync_run --dry-run --json
python manage.py netbox_unifi_sync_run
python manage.py netbox_unifi_sync_run --cleanup
```

> [!IMPORTANT]
> Always run the first execution with --dry-run to verify intended changes before writing to NetBox.

> [!CAUTION]
> The --cleanup flag removes objects in NetBox that no longer exist in UniFi.
> Review carefully before using in production.

---

## Credentials

Set credentials only in:

Plugins -> UniFi Sync -> Controllers

> [!WARNING]
> Never store UniFi credentials in PLUGINS_CONFIG.
> Configuration files may end up in version control or logs.

---

## Scheduled Jobs

The plugin supports NetBox Scheduled Jobs.

Recommended intervals:

- Small environments: every 30–60 minutes
- Larger environments: every 2–4 hours

> [!NOTE]
> High sync frequency increases load on both the UniFi controller and NetBox worker processes.

---

## Security Notes

- SSL verification defaults to true
- Secrets are redacted in run history and audit logs
- Timeouts, retries, and backoff are configurable

> [!IMPORTANT]
> If disabling SSL verification for testing, restrict access to the controller network.
> Never disable SSL verification in production environments.

---

## Documentation

- [Server install guide](docs/server-install.md)
- [NetBox plugin mode](docs/netbox-plugin.md)
- [Configuration reference](docs/configuration.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Release and PyPI publish](docs/release.md)
- [netbox-docker setup](deploy/netbox-docker/README.md)
- [Wiki source pages](wiki/Home.md)
- [GitHub Wiki](https://github.com/unifi2netbox/netbox-unifi-sync/wiki)

---

## Maintainer: Release to PyPI

1. Bump version in:
   - pyproject.toml (`[project].version`)
   - netbox_unifi_sync/version.py (`__version__`)
2. Configure PyPI Trusted Publisher (OIDC) for this repository/workflow.
3. Create and push tag `vX.Y.Z`:
   - `git tag -a vX.Y.Z -m "Release vX.Y.Z"`
   - `git push origin vX.Y.Z`
4. `release.yml` creates GitHub Release.
5. `publish-python-package.yml` publishes package to PyPI when release is published.

> [!CAUTION]
> Version mismatch between pyproject.toml and version.py will break the release pipeline.
