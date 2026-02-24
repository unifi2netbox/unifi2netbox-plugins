"""Tests for UniFi DHCP pool parsing and NetBox IP range sync."""

from __future__ import annotations

import ipaddress
from types import SimpleNamespace

import main


class FakeNetworkConfEndpoint:
    def __init__(self, configs):
        self._configs = configs

    def all(self):
        return list(self._configs)


class FakeSiteObj:
    def __init__(self, configs, site_id="site-1"):
        self.id = site_id
        self._id = site_id
        self.network_conf = FakeNetworkConfEndpoint(configs)


class FakeIPRangeObject:
    def __init__(self, payload):
        self.start_address = payload.get("start_address")
        self.end_address = payload.get("end_address")
        self.description = payload.get("description", "")
        self.saved = False

    def save(self):
        self.saved = True


class FakeIPRangeEndpoint:
    def __init__(self):
        self.items = {}
        self.create_calls = []

    def get(self, **kwargs):
        key = (kwargs.get("start_address"), kwargs.get("end_address"))
        return self.items.get(key)

    def create(self, payload):
        self.create_calls.append(dict(payload))
        obj = FakeIPRangeObject(payload)
        key = (payload.get("start_address"), payload.get("end_address"))
        self.items[key] = obj
        return obj


class FakeNetBox:
    def __init__(self):
        self.ipam = SimpleNamespace(ip_ranges=FakeIPRangeEndpoint())


def test_extract_dhcp_pools_prefers_explicit_legacy_range(monkeypatch):
    """When integration lacks start/stop, legacy explicit range should win."""
    integration_networks = [
        {
            "name": "LAN",
            "dhcpdEnabled": True,
            "subnet": "10.0.0.0/24",
            "gateway": "10.0.0.1",
        }
    ]
    legacy_networks = [
        {
            "name": "LAN",
            "dhcpd_enabled": True,
            "ip_subnet": "10.0.0.0/24",
            "gateway_ip": "10.0.0.1",
            "dhcpd_start": "10.0.0.50",
            "dhcpd_stop": "10.0.0.150",
        }
    ]

    monkeypatch.setattr(
        main.ipam_helpers,
        "_fetch_legacy_networkconf",
        lambda _unifi, _site_obj: legacy_networks,
    )

    site = FakeSiteObj(integration_networks, site_id="site-explicit")
    pools = main.extract_dhcp_pools_from_unifi(site, unifi=object())

    assert len(pools) == 1
    assert str(pools[0]["network"]) == "10.0.0.0/24"
    assert str(pools[0]["start"]) == "10.0.0.50"
    assert str(pools[0]["end"]) == "10.0.0.150"


def test_extract_dhcp_pools_derives_default_host_range():
    """If start/stop is missing, derive a safe host range from subnet."""
    configs = [
        {
            "name": "Guest",
            "dhcpd_enabled": True,
            "ip_subnet": "192.168.10.0/24",
            "gateway_ip": "192.168.10.1",
        }
    ]

    site = FakeSiteObj(configs, site_id="site-derived")
    pools = main.extract_dhcp_pools_from_unifi(site)

    assert len(pools) == 1
    assert str(pools[0]["start"]) == "192.168.10.2"
    assert str(pools[0]["end"]) == "192.168.10.254"


def test_sync_site_dhcp_ip_ranges_is_idempotent():
    nb = FakeNetBox()
    tenant = SimpleNamespace(id=42)
    site = SimpleNamespace(name="HQ")
    pools = [
        {
            "name": "LAN",
            "network": ipaddress.ip_network("10.88.0.0/24"),
            "start": ipaddress.ip_address("10.88.0.50"),
            "end": ipaddress.ip_address("10.88.0.200"),
        }
    ]

    main.sync_site_dhcp_ip_ranges(nb, site, tenant, pools)
    main.sync_site_dhcp_ip_ranges(nb, site, tenant, pools)

    assert len(nb.ipam.ip_ranges.create_calls) == 1
    payload = nb.ipam.ip_ranges.create_calls[0]
    assert payload["start_address"] == "10.88.0.50/24"
    assert payload["end_address"] == "10.88.0.200/24"
    assert payload["description"] == "UniFi DHCP: LAN"
