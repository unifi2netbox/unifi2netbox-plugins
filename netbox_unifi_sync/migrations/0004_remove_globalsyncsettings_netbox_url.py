"""
Remove the ``netbox_url`` field that was added in migration 0003.

The sync worker previously needed a self-referential HTTP URL to call the
NetBox REST API via pynetbox.  The plugin now uses the Django ORM directly
(``unifi2netbox.services.sync.netbox_orm``), so no internal URL is required.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_unifi_sync", "0003_globalsyncsettings_netbox_url"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="globalsyncsettings",
            name="netbox_url",
        ),
    ]
