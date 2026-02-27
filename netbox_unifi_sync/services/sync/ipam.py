"""DHCP/IPAM helpers and UniFi static-IP writeback logic."""

from __future__ import annotations

import ipaddress
import logging
import os
import subprocess  # nosec B404
import threading

from .runtime_config import _parse_env_list, _unifi_verify_ssl

logger = logging.getLogger(__name__)

_dhcp_ranges_cache = None
_dhcp_ranges_lock = threading.Lock()
_assigned_static_ips = set()
_assigned_static_ips_lock = threading.Lock()
_exhausted_static_prefixes = set()  # Prefix IDs exhausted for static selection in current sync run
_exhausted_static_prefixes_lock = threading.Lock()
_static_prefix_locks = {}
_static_prefix_locks_lock = threading.Lock()
_unifi_dhcp_ranges = {}  # site_id -> list of IPv4Network
_unifi_dhcp_ranges_lock = threading.Lock()
_unifi_network_info = {}  # site_id -> list of dicts: {network, gateway, dns}
_unifi_network_info_lock = threading.Lock()


def _get_static_prefix_lock(prefix_key) -> threading.Lock:
    with _static_prefix_locks_lock:
        lock = _static_prefix_locks.get(prefix_key)
        if lock is None:
            lock = threading.Lock()
            _static_prefix_locks[prefix_key] = lock
    return lock


def _parse_env_dhcp_ranges():
    """Parse DHCP_RANGES env var into a list of ipaddress.IPv4Network objects. Cached."""
    global _dhcp_ranges_cache
    with _dhcp_ranges_lock:
        if _dhcp_ranges_cache is not None:
            return _dhcp_ranges_cache

    raw_ranges = _parse_env_list("DHCP_RANGES")
    if not raw_ranges:
        with _dhcp_ranges_lock:
            _dhcp_ranges_cache = []
        return []

    networks = []
    for r in raw_ranges:
        r = r.strip()
        try:
            networks.append(ipaddress.ip_network(r, strict=False))
        except ValueError:
            logger.warning(f"Invalid DHCP range '{r}' in DHCP_RANGES. Skipping.")

    with _dhcp_ranges_lock:
        _dhcp_ranges_cache = networks
    logger.debug(f"Parsed {len(networks)} env DHCP ranges: {[str(n) for n in networks]}")
    return networks


def _fetch_legacy_networkconf(unifi, site_obj):
    """Fetch network configs via Legacy API (has DHCP fields)."""
    site_code = (
        getattr(site_obj, "internal_reference", None)
        or getattr(site_obj, "name", None)
        or "default"
    )
    base = unifi.base_url
    if "/proxy/network/integration" in base:
        base = base.split("/proxy/network/integration")[0]
    elif "/integration/" in base:
        base = base.split("/integration/")[0]
    url = f"{base}/proxy/network/api/s/{site_code}/rest/networkconf"

    try:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        auth_headers = getattr(unifi, "integration_auth_headers", None) or {}
        headers.update(auth_headers)

        resp = unifi.session.get(
            url,
            headers=headers,
            verify=getattr(unifi, "verify_ssl", _unifi_verify_ssl()),
            timeout=unifi.request_timeout,
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and "data" in data:
                return data["data"]
            if isinstance(data, list):
                return data
        else:
            logger.debug(f"Legacy networkconf returned HTTP {resp.status_code} for site {site_code}")
    except Exception as e:
        logger.debug(f"Legacy networkconf fallback failed for site {site_code}: {e}")
    return None


def _collect_unifi_network_configs(site_obj, unifi=None) -> list[dict]:
    net_configs = []
    try:
        net_configs = list(site_obj.network_conf.all() or [])
    except Exception as e:
        logger.warning(f"Could not fetch network configs for DHCP parsing: {e}")
        net_configs = []

    # Integration API can omit DHCP fields on some records.
    # Merge legacy networkconf to avoid losing data.
    if unifi:
        legacy_configs = _fetch_legacy_networkconf(unifi, site_obj)
        if legacy_configs:
            net_configs.extend(list(legacy_configs))

    return net_configs


def _extract_subnet_from_network(net: dict) -> str | None:
    subnet = (
        net.get("ip_subnet")
        or net.get("subnet")
        or net.get("ipSubnet")
        or net.get("ipv4_subnet")
    )
    return str(subnet).strip() if subnet else None


def _extract_gateway_from_network(net: dict) -> str | None:
    gateway = net.get("gateway_ip") or net.get("gateway")
    return str(gateway).strip() if gateway else None


def _extract_dns_from_network(net: dict) -> list[str]:
    dns_servers = []
    for key in (
        "dhcpd_dns_1",
        "dhcpd_dns_2",
        "dhcpd_dns_3",
        "dhcpd_dns_4",
        "dhcpdDns1",
        "dhcpdDns2",
        "dhcpdDns3",
        "dhcpdDns4",
    ):
        val = net.get(key)
        if val and str(val).strip():
            dns_servers.append(str(val).strip())

    seen_dns = set()
    unique_dns = []
    for item in dns_servers:
        if item not in seen_dns:
            seen_dns.add(item)
            unique_dns.append(item)
    return unique_dns


def _parse_ip_in_network(value, network):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None

    try:
        candidate = ipaddress.ip_address(text)
        if candidate in network:
            return candidate
        return None
    except ValueError:
        pass

    if text.isdigit():
        try:
            offset = int(text)
            if offset < 0:
                return None
            candidate = ipaddress.ip_address(int(network.network_address) + offset)
            if candidate in network:
                return candidate
        except (ValueError, OverflowError):
            return None
    return None


def _normalize_dhcp_pool(network, gateway, start, end):
    # Only create DHCP pools for IPv4 subnets.
    if getattr(network, "version", 4) != 4:
        return None, None
    if network.num_addresses <= 2:
        return None, None

    min_host = ipaddress.ip_address(int(network.network_address) + 1)
    max_host = ipaddress.ip_address(int(network.broadcast_address) - 1)

    start_ip = start or min_host
    end_ip = end or max_host

    if int(start_ip) < int(min_host):
        start_ip = min_host
    if int(end_ip) > int(max_host):
        end_ip = max_host

    if int(start_ip) > int(end_ip):
        start_ip, end_ip = end_ip, start_ip

    if gateway and start_ip == gateway and int(start_ip) < int(end_ip):
        start_ip = ipaddress.ip_address(int(start_ip) + 1)
    elif gateway and end_ip == gateway and int(start_ip) < int(end_ip):
        end_ip = ipaddress.ip_address(int(end_ip) - 1)

    if int(start_ip) > int(end_ip):
        return None, None
    return start_ip, end_ip


def extract_dhcp_pools_from_unifi(site_obj, unifi=None) -> list[dict]:
    """
    Extract DHCP pools from UniFi network configs for a site.

    Returns dictionaries with:
      - name
      - network (IPv4Network)
      - gateway (str|None)
      - dns (list[str])
      - start (IPv4Address)
      - end (IPv4Address)
    """
    net_configs = _collect_unifi_network_configs(site_obj, unifi=unifi)
    pools_by_subnet: dict[str, dict] = {}
    network_info_by_subnet: dict[str, dict] = {}

    for net in net_configs:
        net_name = net.get("name") or net.get("purpose") or "unknown"
        dhcp_enabled = (
            net.get("dhcpd_enabled")
            or net.get("dhcpdEnabled")
            or net.get("dhcp_enabled")
            or net.get("dhcpEnabled")
            or False
        )
        if not dhcp_enabled:
            continue

        subnet = _extract_subnet_from_network(net)
        if not subnet:
            continue

        try:
            network = ipaddress.ip_network(subnet, strict=False)
        except ValueError:
            logger.warning(f"Invalid subnet '{subnet}' in UniFi network config. Skipping.")
            continue

        gateway_raw = _extract_gateway_from_network(net)
        gateway = _parse_ip_in_network(gateway_raw, network)
        dns_values = _extract_dns_from_network(net)

        start_raw = (
            net.get("dhcpd_start")
            or net.get("dhcpdStart")
            or net.get("dhcp_start")
            or net.get("dhcpStart")
            or net.get("dhcpd_start_addr")
            or net.get("dhcpdStartAddr")
        )
        end_raw = (
            net.get("dhcpd_stop")
            or net.get("dhcpdStop")
            or net.get("dhcp_stop")
            or net.get("dhcpStop")
            or net.get("dhcpd_stop_addr")
            or net.get("dhcpdStopAddr")
        )
        start_ip = _parse_ip_in_network(start_raw, network)
        end_ip = _parse_ip_in_network(end_raw, network)
        has_explicit_range = bool(start_ip and end_ip)
        start_ip, end_ip = _normalize_dhcp_pool(network, gateway, start_ip, end_ip)
        if not start_ip or not end_ip:
            logger.debug(
                "Skipping DHCP pool for network '%s' (%s): cannot derive valid start/end",
                net_name,
                subnet,
            )
            continue

        subnet_key = str(network)
        pool = {
            "name": net_name,
            "network": network,
            "gateway": str(gateway) if gateway else None,
            "dns": dns_values,
            "start": start_ip,
            "end": end_ip,
            "_has_explicit_range": has_explicit_range,
        }
        existing = pools_by_subnet.get(subnet_key)
        if existing is None:
            pools_by_subnet[subnet_key] = pool
        else:
            existing_explicit = bool(existing.get("_has_explicit_range"))
            candidate_explicit = bool(pool.get("_has_explicit_range"))
            should_replace = False
            if candidate_explicit and not existing_explicit:
                should_replace = True
            elif candidate_explicit == existing_explicit:
                if not existing.get("gateway") and pool.get("gateway"):
                    should_replace = True
                elif len(existing.get("dns", [])) < len(pool.get("dns", [])):
                    should_replace = True
            if should_replace:
                pools_by_subnet[subnet_key] = pool

        info_candidate = {
            "network": network,
            "gateway": str(gateway) if gateway else None,
            "dns": dns_values,
            "name": net_name,
            "dhcp_start": str(start_ip),
            "dhcp_end": str(end_ip),
        }
        current_info = network_info_by_subnet.get(subnet_key)
        if current_info is None or (not current_info.get("gateway") and info_candidate.get("gateway")) or len(current_info.get("dns", [])) < len(info_candidate.get("dns", [])):
            network_info_by_subnet[subnet_key] = info_candidate

    site_id = getattr(site_obj, "id", None) or getattr(site_obj, "_id", None)
    if site_id:
        with _unifi_network_info_lock:
            if network_info_by_subnet:
                _unifi_network_info[site_id] = list(network_info_by_subnet.values())
            else:
                _unifi_network_info.pop(site_id, None)

    pools = []
    for pool in pools_by_subnet.values():
        item = dict(pool)
        item.pop("_has_explicit_range", None)
        pools.append(item)
    return pools


def extract_dhcp_ranges_from_unifi(site_obj, unifi=None) -> list[ipaddress.IPv4Network]:
    """Extract DHCP subnet CIDRs from UniFi network configs for a site."""
    pools = extract_dhcp_pools_from_unifi(site_obj, unifi=unifi)
    seen = set()
    networks_result = []
    for pool in pools:
        network = pool.get("network")
        if not network:
            continue
        key = str(network)
        if key in seen:
            continue
        seen.add(key)
        networks_result.append(network)
        logger.debug(f"Found DHCP-enabled network '{pool.get('name', 'unknown')}': {key}")

    return networks_result

def get_all_dhcp_ranges() -> list[ipaddress.IPv4Network]:
    """Return merged DHCP ranges from env var + all discovered UniFi sites."""
    env_ranges = _parse_env_dhcp_ranges()
    with _unifi_dhcp_ranges_lock:
        unifi_ranges = []
        for ranges in _unifi_dhcp_ranges.values():
            unifi_ranges.extend(ranges)

    seen = set()
    merged = []
    for net in env_ranges + unifi_ranges:
        key = str(net)
        if key not in seen:
            seen.add(key)
            merged.append(net)
    return merged


def is_ip_in_dhcp_range(ip_str: str) -> bool:
    """Return True if the given IP string falls within any configured/discovered DHCP range."""
    dhcp_ranges = get_all_dhcp_ranges()
    if not dhcp_ranges:
        return False
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return any(addr in network for network in dhcp_ranges)


def _get_network_info_for_ip(ip_str: str) -> tuple[str | None, list[str]]:
    """Look up gateway and DNS servers for a given IP from cached UniFi network configs."""
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return None, []

    with _unifi_network_info_lock:
        for _site_id, info_list in _unifi_network_info.items():
            for info in info_list:
                if addr in info["network"]:
                    return info.get("gateway"), info.get("dns", [])

    env_gw = os.getenv("DEFAULT_GATEWAY", "").strip() or None
    env_dns_raw = os.getenv("DEFAULT_DNS", "").strip()
    env_dns = [d.strip() for d in env_dns_raw.split(",") if d.strip()] if env_dns_raw else []
    if env_gw or env_dns:
        logger.debug(f"Using env fallback for {ip_str}: gateway={env_gw}, dns={env_dns}")
    return env_gw, env_dns


def ping_ip(ip_str: str, count: int = 2, timeout: int = 1) -> bool:
    """Ping an IP address. Returns True if host responds (IP in use), False if not."""
    try:
        target_ip = str(ipaddress.ip_address(ip_str))
        safe_count = max(1, min(5, int(count)))
        safe_timeout = max(1, min(5, int(timeout)))
        cmd = ["ping", "-c", str(safe_count), "-W", str(safe_timeout), target_ip]
        result = subprocess.run(  # nosec B603
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=safe_count * safe_timeout + 5,
            check=False,
        )
        return result.returncode == 0
    except (ValueError, TypeError, subprocess.TimeoutExpired, Exception) as e:
        logger.debug(f"Ping to {ip_str} failed/timed out: {e}")
        return False


def find_available_static_ip(
    nb,
    prefix_obj,
    vrf,
    tenant,
    unifi_device_ips: set[str] | None = None,
    max_attempts: int = 10,
) -> str | None:
    """
    Find an available static IP in the given NetBox prefix.
    Returns IP string with mask (e.g. '192.168.1.5/24') or None.
    """
    dhcp_ranges = get_all_dhcp_ranges()
    subnet_mask = prefix_obj.prefix.split("/")[1]
    prefix_id = prefix_obj.id
    vrf_id = getattr(vrf, "id", None) if vrf is not None else None
    prefix_key = f"{prefix_obj.prefix}|vrf:{vrf_id if vrf_id is not None else 'none'}"
    unifi_ips = unifi_device_ips or set()

    with _get_static_prefix_lock(prefix_key):
        # Avoid repeated expensive checks and warning spam for the same exhausted prefix within one run.
        with _exhausted_static_prefixes_lock:
            if prefix_key in _exhausted_static_prefixes:
                logger.debug(
                    f"Static IP candidate search already exhausted for prefix {prefix_obj.prefix} in this run."
                )
                return None

        # Enumerate candidate IPs via Django ORM: all host addresses in the prefix
        # that are not already assigned in NetBox's ipam_ipaddress table.
        try:
            import ipaddress as _ipaddress
            from ipam.models import IPAddress as _IPAddress

            network = _ipaddress.ip_network(prefix_obj.prefix, strict=False)
            prefix_filter: dict = {"prefix": prefix_obj.prefix}
            if vrf_id is not None:
                prefix_filter["vrf_id"] = vrf_id

            # Collect IPs already assigned within this prefix (without mask)
            # Use __net_host_contained to scope to the prefix network
            assigned_qs = _IPAddress.objects.filter(
                address__net_host_contained=str(network)
            )
            assigned_set = set()
            for ip_obj in assigned_qs:
                try:
                    assigned_set.add(str(_ipaddress.ip_interface(str(ip_obj.address)).ip))
                except Exception:
                    pass

            # Build candidate list from host addresses (skip network/broadcast)
            candidates = []
            limit = max_attempts * 5
            for host in network.hosts():
                if len(candidates) >= limit:
                    break
                host_str = str(host)
                if host_str not in assigned_set:
                    candidates.append({"address": f"{host_str}/{network.prefixlen}"})

        except Exception as e:
            logger.error(f"Failed to enumerate available IPs for prefix {prefix_obj.prefix}: {e}")
            return None

        attempts = 0
        evaluated_candidates = 0
        skipped_dhcp = 0
        skipped_assigned = 0
        skipped_unifi = 0
        skipped_ping = 0
        for candidate in candidates:
            if attempts >= max_attempts:
                break

            candidate_addr = candidate.get("address", "")
            candidate_ip = candidate_addr.split("/")[0]

            try:
                addr = ipaddress.ip_address(candidate_ip)
            except ValueError:
                continue

            evaluated_candidates += 1

            if any(addr in net for net in dhcp_ranges):
                skipped_dhcp += 1
                continue

            with _assigned_static_ips_lock:
                if candidate_ip in _assigned_static_ips:
                    logger.debug(f"Skipping {candidate_ip} — already being assigned this run")
                    skipped_assigned += 1
                    continue

            if candidate_ip in unifi_ips:
                logger.debug(f"Skipping {candidate_ip} — already in use by a UniFi device")
                skipped_unifi += 1
                continue

            attempts += 1

            if ping_ip(candidate_ip):
                logger.warning(f"Candidate IP {candidate_ip} responds to ping — in use, skipping")
                skipped_ping += 1
                continue

            with _assigned_static_ips_lock:
                if candidate_ip in _assigned_static_ips:
                    continue
                _assigned_static_ips.add(candidate_ip)

            logger.info(f"Found available static IP: {candidate_ip}/{subnet_mask}")
            return f"{candidate_ip}/{subnet_mask}"

        with _exhausted_static_prefixes_lock:
            _exhausted_static_prefixes.add(prefix_key)

        if evaluated_candidates > 0 and attempts == 0 and skipped_dhcp == evaluated_candidates:
            logger.info(
                f"No static-IP candidates outside DHCP ranges for {prefix_obj.prefix} "
                f"(evaluated={evaluated_candidates}). Keeping DHCP assignment."
            )
        else:
            logger.warning(
                f"Could not find available static IP in {prefix_obj.prefix} "
                f"after {attempts} assignment attempts (evaluated {evaluated_candidates}, "
                f"skipped_dhcp={skipped_dhcp}, skipped_assigned={skipped_assigned}, "
                f"skipped_unifi={skipped_unifi}, skipped_ping={skipped_ping})"
            )
        return None


def set_unifi_device_static_ip(
    unifi,
    site_obj,
    device: dict,
    static_ip: str,
    subnet_mask: str = "255.255.252.0",
    gateway: str | None = None,
    dns_servers: list[str] | None = None,
) -> bool:
    """
    Set a static IP on a UniFi device via the controller API.
    For Integration API: PATCH /sites/{siteId}/devices/{deviceId}
    For Legacy API: PUT /api/s/{site}/rest/device/{id}
    """
    device_id = device.get("id") or device.get("_id")
    device_name = (
        device.get("name")
        or device.get("hostname")
        or device.get("macAddress")
        or device.get("mac")
        or device.get("id")
        or "unknown-device"
    )
    if not device_id:
        logger.warning("Cannot set static IP: missing UniFi device ID")
        return False

    site_api_id = getattr(site_obj, "api_id", None) or getattr(site_obj, "_id", None)
    if not site_api_id:
        logger.warning("Cannot set static IP: missing UniFi site API ID")
        return False

    if not gateway:
        try:
            network = ipaddress.ip_network(f"{static_ip}/{subnet_mask}", strict=False)
            gateway = str(list(network.hosts())[0])
        except Exception as e:
            gateway = static_ip.rsplit(".", 1)[0] + ".1"
            logger.debug(f"Could not compute gateway from prefix, using fallback {gateway}: {e}")

    api_style = getattr(unifi, "api_style", "legacy")
    if api_style == "integration":
        url = f"/sites/{site_api_id}/devices/{device_id}"
        ip_config = {
            "mode": "static",
            "ip": static_ip,
            "subnetMask": subnet_mask,
            "gateway": gateway,
        }
        if dns_servers:
            if len(dns_servers) >= 1:
                ip_config["preferredDns"] = dns_servers[0]
            if len(dns_servers) >= 2:
                ip_config["alternateDns"] = dns_servers[1]
        payload = {"ipConfig": ip_config}
        try:
            response = unifi.make_request(url, "PATCH", data=payload)
            if isinstance(response, dict):
                status = response.get("statusCode") or response.get("status")
                if status and int(status) >= 400:
                    logger.warning("Failed to set static IP on UniFi device via Integration API")
                    return False
            logger.info("Set static IP on UniFi device via Integration API")
            return True
        except Exception:
            logger.warning("Failed to set static IP on UniFi device via Integration API request exception")
            return False

    config_network = {
        "type": "static",
        "ip": static_ip,
        "netmask": subnet_mask,
        "gateway": gateway,
    }
    if dns_servers:
        if len(dns_servers) >= 1:
            config_network["dns1"] = dns_servers[0]
        if len(dns_servers) >= 2:
            config_network["dns2"] = dns_servers[1]
    payload = {"config_network": config_network}
    try:
        site_name = getattr(site_obj, "name", "default")
        url = f"/api/s/{site_name}/rest/device/{device_id}"
        response = unifi.make_request(url, "PUT", data=payload)
        if isinstance(response, dict):
            meta = response.get("meta", {})
            if isinstance(meta, dict) and meta.get("rc") == "ok":
                logger.info("Set static IP on UniFi device via Legacy API")
                return True
            logger.warning("Failed to set static IP on UniFi device via Legacy API")
            return False
        return False
    except Exception:
        logger.warning("Failed to set static IP on UniFi device via Legacy API request exception")
        return False
