# Release and PyPI

Package:

- Name: `netbox-unifi-sync`
- Install: `pip install netbox-unifi-sync`

## Trusted Publisher (PyPI + GitHub OIDC)

PyPI publisher must match exactly:

- PyPI Project Name: `netbox-unifi-sync`
- Owner: `unifi2netbox`
- Repository: `netbox-unifi-sync`
- Workflow: `publish-python-package.yml`
- Environment: `pypi`

## Release flow

1. Bump version in:
   - `pyproject.toml`
   - `netbox_unifi_sync/version.py`
2. Commit + push `main`
3. Create and push tag `vX.Y.Z`
4. `release.yml` creates GitHub release
5. `publish-python-package.yml` publishes to PyPI

Note:
- If publish does not start automatically from the release event, run `Publish Python Package` manually (`workflow_dispatch`).

## Common failure

If upload says filename already used/deleted, publish a new version (e.g. `0.1.2` -> `0.1.3`).

Reference: [docs/release.md](https://github.com/unifi2netbox/netbox-unifi-sync/blob/main/docs/release.md)
