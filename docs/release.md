# Release and PyPI Publish

This plugin is published as:

- package name: `netbox-unifi-sync`
- install command: `pip install netbox-unifi-sync`
- project URL: <https://pypi.org/project/netbox-unifi-sync/>

## One-Time Setup

1. Create project on PyPI:
   - `netbox-unifi-sync`
2. Configure **PyPI Trusted Publisher** (GitHub OIDC) with:
   - **PyPI Project Name**: `netbox-unifi-sync`
   - **Owner**: `unifi2netbox`
   - **Repository name**: `netbox_unifi_sync`
   - **Workflow name**: `publish-python-package.yml`
   - **Environment name**: `pypi`
3. In GitHub repository settings, create environment:
   - `pypi`

Read more: GitHub Actions OpenID Connect support  
https://docs.github.com/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect

## Versioning Rules

Keep versions aligned in both files:

- `pyproject.toml` -> `[project].version`
- `netbox_unifi_sync/version.py` -> `__version__`

Tag must match version exactly: `vX.Y.Z`.

## Automated Publish Flow

Configured workflows:

- `release.yml`:
  - runs on push of tags matching `v*`
  - creates GitHub Release
- `publish-python-package.yml`:
  - runs on `release: published` (or manual dispatch)
  - uses environment `pypi`
  - uses GitHub OIDC (`id-token: write`)
  - builds package (`sdist` + `wheel`)
  - runs `twine check`
  - publishes to PyPI without API token secret

## Recommended Release Commands

```bash
git add pyproject.toml netbox_unifi_sync/version.py
git commit -m "Release vX.Y.Z"
git push origin main
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
```

## Manual Publish (fallback)

```bash
python -m pip install --upgrade build twine
python -m build
twine check dist/*
twine upload dist/*
```

Use (only for fallback without OIDC):

- username: `__token__`
- password: `<your PyPI API token>`

## Verification

After publish:

```bash
python -m pip index versions netbox-unifi-sync
pip install netbox-unifi-sync
```
