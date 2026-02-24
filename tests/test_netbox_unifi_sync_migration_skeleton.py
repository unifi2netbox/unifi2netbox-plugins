from pathlib import Path


def test_migration_file_exists():
    migration = Path("netbox_unifi_sync/migrations/0001_initial.py")
    assert migration.exists(), "Expected initial migration for netbox_unifi_sync"
