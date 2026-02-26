from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_unifi_sync", "0002_asset_tag_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="globalsyncsettings",
            name="netbox_url",
            field=models.CharField(
                blank=True,
                default="",
                help_text=(
                    "Internal NetBox API base URL used by the sync worker "
                    "(e.g. http://127.0.0.1:8000). Leave blank to auto-detect."
                ),
                max_length=255,
            ),
            preserve_default=False,
        ),
    ]
