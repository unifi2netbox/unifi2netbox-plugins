# Installation

## Option A: Install from PyPI

```bash
pip install netbox-unifi-sync
```

PyPI: <https://pypi.org/project/netbox-unifi-sync/>

Enable plugin in NetBox `configuration.py`:

```python
PLUGINS = ["netbox_unifi_sync"]

PLUGINS_CONFIG = {
    "netbox_unifi_sync": {}
}
```

Run migrations:

```bash
python manage.py migrate
```

## Option B: netbox-docker (local validation)

```bash
git clone https://github.com/unifi2netbox/netbox-unifi-sync.git
cd netbox-unifi-sync
git clone -b release https://github.com/netbox-community/netbox-docker.git .netbox-docker
cp deploy/netbox-docker/configuration/plugins.py .netbox-docker/configuration/plugins.py
echo "netbox-unifi-sync" >> .netbox-docker/local_requirements.txt
```

Build and start:

```bash
cd .netbox-docker
docker compose build netbox netbox-worker
docker compose up -d
docker compose exec netbox /opt/netbox/netbox/manage.py migrate
```

For editable dev mode instead, use `deploy/netbox-docker/docker-compose.override.yml`.
