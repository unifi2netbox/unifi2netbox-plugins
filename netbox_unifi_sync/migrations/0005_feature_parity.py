"""
Add fields that bring the plugin to feature-parity with the standalone
unifi2netbox CLI tool:

* default_gateway   — fallback gateway for DHCP→static IP conversion
* default_dns       — fallback DNS server(s) for DHCP→static IP conversion
* netbox_device_status — status assigned to newly created NetBox devices
* sync_prefixes     — toggle prefix sync to NetBox IPAM
* dhcp_ranges       — manual DHCP CIDR ranges (one per line)
* sync_dhcp_ranges  — toggle syncing DHCP IP ranges to IPAM
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_unifi_sync", "0004_remove_globalsyncsettings_netbox_url"),
    ]

    operations = [
        # DHCP range overrides (manual CIDRs, one per line)
        migrations.AddField(
            model_name="globalsyncsettings",
            name="dhcp_ranges",
            field=models.TextField(
                blank=True,
                default="",
                help_text=(
                    "Manual DHCP ranges in CIDR notation, one per line "
                    "(e.g. 192.168.1.0/24). Merged with auto-discovered ranges."
                ),
            ),
        ),
        # Toggle: sync DHCP IP ranges to NetBox IPAM
        migrations.AddField(
            model_name="globalsyncsettings",
            name="sync_dhcp_ranges",
            field=models.BooleanField(
                default=True,
                help_text="Sync DHCP IP ranges to NetBox IPAM.",
            ),
        ),
        # Fallback gateway for DHCP→static conversion
        migrations.AddField(
            model_name="globalsyncsettings",
            name="default_gateway",
            field=models.GenericIPAddressField(
                blank=True,
                null=True,
                protocol="IPv4",
                help_text=(
                    "Fallback gateway IP used for DHCP→static conversion "
                    "when UniFi network config lacks a gateway."
                ),
            ),
        ),
        # Fallback DNS for DHCP→static conversion
        migrations.AddField(
            model_name="globalsyncsettings",
            name="default_dns",
            field=models.CharField(
                blank=True,
                default="",
                max_length=255,
                help_text=(
                    "Fallback DNS servers, comma-separated (e.g. 8.8.8.8,8.8.4.4). "
                    "Used when UniFi network config lacks DNS information."
                ),
            ),
        ),
        # Status assigned to newly created devices
        migrations.AddField(
            model_name="globalsyncsettings",
            name="netbox_device_status",
            field=models.CharField(
                default="planned",
                max_length=32,
                help_text=(
                    "Status assigned to newly created devices in NetBox "
                    "(e.g. planned, staged, active, inventory)."
                ),
            ),
        ),
        # Toggle: sync network prefixes
        migrations.AddField(
            model_name="globalsyncsettings",
            name="sync_prefixes",
            field=models.BooleanField(
                default=True,
                help_text="Sync network prefixes from UniFi to NetBox IPAM.",
            ),
        ),
    ]
