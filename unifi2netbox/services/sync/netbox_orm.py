"""
Django ORM adapter that mimics the pynetbox API surface.

Instead of making HTTP REST calls to NetBox, this adapter routes all
``nb.dcim.*``, ``nb.ipam.*``, ``nb.wireless.*``, ``nb.extras.*`` and
``nb.tenancy.*`` calls directly to Django model managers.  The plugin
already runs inside the Django / NetBox process, so ORM access is both
faster and architecturally correct.

Usage inside sync_engine.py (drop-in replacement for
``pynetbox.api(url, token=token, threading=True)``):

    from .sync.netbox_orm import build_netbox_orm_client
    nb = build_netbox_orm_client()

The returned object exposes the same attribute chain that sync_engine.py
already uses::

    nb.dcim.devices.get(serial="abc")
    nb.ipam.prefixes.filter(prefix="10.0.0.0/24")
    nb.extras.custom_fields.create({"name": "unifi_mac", ...})
    nb_obj.save()
    nb_obj.delete()
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Thin wrapper around a Django model instance
# ---------------------------------------------------------------------------

class _OrmObject:
    """
    Wraps a Django model instance and exposes it with attribute-style access,
    matching the pynetbox record interface (obj.id, obj.name, obj.save(), …).

    ``custom_fields`` are stored as a dict on the Django instance via
    NetBox's ``local_context_data`` / ``custom_field_data`` mechanism.
    """

    def __init__(self, instance):
        object.__setattr__(self, "_instance", instance)

    # ------------------------------------------------------------------
    # Attribute delegation
    # ------------------------------------------------------------------

    def __getattr__(self, name: str):
        instance = object.__getattribute__(self, "_instance")
        # Expose custom_field_data as 'custom_fields' (pynetbox naming)
        if name == "custom_fields":
            return getattr(instance, "custom_field_data", {}) or {}
        # FK fields: return the related object directly (already an ORM obj)
        return getattr(instance, name)

    def __setattr__(self, name: str, value):
        if name == "_instance":
            object.__setattr__(self, name, value)
            return
        instance = object.__getattribute__(self, "_instance")
        if name == "custom_fields":
            # Merge into custom_field_data
            existing = getattr(instance, "custom_field_data", {}) or {}
            if isinstance(value, dict):
                existing.update(value)
                instance.custom_field_data = existing
            return
        setattr(instance, name, value)

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def save(self, update_fields=None):
        instance = object.__getattribute__(self, "_instance")
        if update_fields:
            instance.save(update_fields=update_fields)
        else:
            instance.save()

    def delete(self):
        instance = object.__getattribute__(self, "_instance")
        instance.delete()

    # ------------------------------------------------------------------
    # Representation
    # ------------------------------------------------------------------

    def __repr__(self):
        instance = object.__getattribute__(self, "_instance")
        return f"<_OrmObject {instance!r}>"

    def __bool__(self):
        return True

    def __eq__(self, other):
        if isinstance(other, _OrmObject):
            return (
                object.__getattribute__(self, "_instance")
                == object.__getattribute__(other, "_instance")
            )
        return NotImplemented


# ---------------------------------------------------------------------------
# Endpoint: wraps a Django model manager with get/filter/all/create
# ---------------------------------------------------------------------------

def _wrap(instance_or_none):
    """Return an _OrmObject or None."""
    if instance_or_none is None:
        return None
    if isinstance(instance_or_none, _OrmObject):
        return instance_or_none
    return _OrmObject(instance_or_none)


def _wrap_many(queryset):
    """Return a list of _OrmObject wrappers from a queryset / iterable."""
    return [_OrmObject(obj) for obj in queryset]


class _Endpoint:
    """
    Mimics a pynetbox endpoint (e.g. ``nb.dcim.devices``).

    Supported methods:

    * ``.get(**kwargs)``   — return one object or None; raises ValueError for multiple
    * ``.filter(**kwargs)``— return list of matching objects
    * ``.all()``           — return all objects
    * ``.create(payload)`` — create and return a new object
    """

    def __init__(self, model, *, extra_filter: dict | None = None):
        self._model = model
        self._extra = extra_filter or {}

    def _qs(self):
        return self._model.objects.filter(**self._extra)

    def _translate_kwargs(self, kwargs: dict) -> dict:
        """
        pynetbox uses ``xxx_id`` kwargs to filter by FK primary key.
        Django ORM expresses the same as ``xxx_id=…`` which already works,
        but pynetbox also uses ``vrf_id`` while Django stores it as
        ``vrf_id`` on the model — so most cases are already compatible.

        We also handle ``contains`` for prefix queries (custom lookup).
        """
        translated: dict[str, Any] = {}
        for key, value in kwargs.items():
            # ``contains`` is a custom prefix lookup used in ipam
            if key == "contains":
                try:
                    from netaddr import IPAddress, IPNetwork
                    translated["prefix__net_contains_or_equals"] = str(value)
                except Exception:
                    translated["prefix__contains"] = str(value)
            elif key == "scope_type":
                # pynetbox passes scope_type as string like "dcim.site";
                # Django uses a ContentType FK.
                try:
                    from django.contrib.contenttypes.models import ContentType
                    app_label, model_name = str(value).split(".", 1)
                    ct = ContentType.objects.get(app_label=app_label, model=model_name)
                    translated["scope_type"] = ct
                except Exception:
                    pass  # silently ignore unsupported scope filters
            elif key == "scope_id":
                translated["scope_id"] = value
            else:
                # Pass through; _id suffix fields work natively in Django ORM
                translated[key] = value
        return translated

    def get(self, **kwargs) -> "_OrmObject | None":
        qs = self._qs()
        translated = self._translate_kwargs(kwargs)
        try:
            matches = list(qs.filter(**translated))
        except Exception as exc:
            logger.debug("ORM .get() filter error for %s %s: %s", self._model.__name__, kwargs, exc)
            return None
        if not matches:
            return None
        if len(matches) > 1:
            raise ValueError(
                f"Multiple {self._model.__name__} objects returned for {kwargs}"
            )
        return _wrap(matches[0])

    def filter(self, **kwargs) -> list["_OrmObject"]:
        qs = self._qs()
        translated = self._translate_kwargs(kwargs)
        try:
            return _wrap_many(qs.filter(**translated))
        except Exception as exc:
            logger.debug("ORM .filter() error for %s %s: %s", self._model.__name__, kwargs, exc)
            return []

    def all(self) -> list["_OrmObject"]:
        try:
            return _wrap_many(self._qs())
        except Exception as exc:
            logger.debug("ORM .all() error for %s: %s", self._model.__name__, exc)
            return []

    def create(self, payload: dict) -> "_OrmObject | None":
        """
        Create a new instance from a flat payload dict.

        Handles:
        * ``xxx_id`` → FK field (pass as-is, Django handles it)
        * ``content_types`` → ManyToMany (set after save)
        * ``scope_type`` string → ContentType lookup
        * ``custom_fields`` → stored in custom_field_data
        """
        m2m: dict[str, list] = {}
        direct: dict[str, Any] = {}
        custom_fields: dict[str, Any] = {}

        for key, value in payload.items():
            if key == "content_types":
                # ManyToMany: list of "app_label.model" strings
                m2m["content_types"] = value
            elif key == "custom_fields" and isinstance(value, dict):
                custom_fields = value
            elif key == "scope_type" and isinstance(value, str):
                try:
                    from django.contrib.contenttypes.models import ContentType
                    app_label, model_name = value.split(".", 1)
                    ct = ContentType.objects.get(app_label=app_label, model=model_name)
                    direct["scope_type"] = ct
                except Exception:
                    pass  # skip unsupported scope_type
            else:
                direct[key] = value

        if custom_fields:
            direct["custom_field_data"] = custom_fields

        try:
            instance = self._model(**direct)
            instance.full_clean()
            instance.save()
        except Exception as exc:
            # Re-raise as a generic RuntimeError so callers that catch
            # pynetbox.core.query.RequestError will need updating, but at
            # least we avoid importing pynetbox here.
            raise RuntimeError(
                f"ORM create failed for {self._model.__name__}: {exc}"
            ) from exc

        # Handle ManyToMany fields after save
        for field_name, values in m2m.items():
            field = getattr(instance, field_name)
            for item in (values or []):
                if isinstance(item, str) and "." in item:
                    try:
                        from django.contrib.contenttypes.models import ContentType
                        app_label, model_name = item.split(".", 1)
                        ct = ContentType.objects.get(app_label=app_label, model=model_name)
                        field.add(ct)
                    except Exception:
                        pass
                else:
                    try:
                        field.add(item)
                    except Exception:
                        pass

        return _wrap(instance)


# ---------------------------------------------------------------------------
# Namespace: groups multiple endpoints (e.g. nb.dcim, nb.ipam)
# ---------------------------------------------------------------------------

class _Namespace:
    """Lazily resolves endpoint names to _Endpoint instances."""

    def __init__(self, endpoints: dict[str, "_Endpoint | type"]):
        self._endpoints: dict[str, "_Endpoint"] = {}
        for name, model_or_endpoint in endpoints.items():
            if isinstance(model_or_endpoint, _Endpoint):
                self._endpoints[name] = model_or_endpoint
            else:
                self._endpoints[name] = _Endpoint(model_or_endpoint)

    def __getattr__(self, name: str) -> "_Endpoint":
        endpoints = object.__getattribute__(self, "_endpoints")
        if name in endpoints:
            return endpoints[name]
        raise AttributeError(
            f"Endpoint '{name}' not found in namespace. "
            "Available: " + ", ".join(endpoints)
        )


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------

def build_netbox_orm_client():
    """
    Return a drop-in replacement for ``pynetbox.api(url, token=token)``.

    Lazily imports NetBox/Django models so this module is safe to import
    at package load time (before Django is fully configured).
    """
    # Import NetBox models lazily to avoid import-time Django setup errors
    from dcim.models import (
        Cable,
        ConsolePortTemplate,
        Device,
        DeviceRole,
        DeviceType,
        Interface,
        InterfaceTemplate,
        Manufacturer,
        PowerPortTemplate,
        Site,
    )
    from extras.models import CustomField, Tag
    from ipam.models import IPAddress, IPRange, Prefix, VLAN, VLANGroup, VRF
    from tenancy.models import Tenant
    from wireless.models import WirelessLAN, WirelessLANGroup

    client = type("NetBoxOrmClient", (), {})()

    client.dcim = _Namespace({
        "manufacturers": Manufacturer,
        "sites": Site,
        "device_roles": DeviceRole,
        "device_types": DeviceType,
        "devices": Device,
        "interfaces": Interface,
        "cables": Cable,
        "interface_templates": InterfaceTemplate,
        "console_port_templates": ConsolePortTemplate,
        "power_port_templates": PowerPortTemplate,
    })

    client.ipam = _Namespace({
        "prefixes": Prefix,
        "vlans": VLAN,
        "vlan_groups": VLANGroup,
        "ip_addresses": IPAddress,
        "ip_ranges": IPRange,
        "vrfs": VRF,
    })

    client.wireless = _Namespace({
        "wireless_lan_groups": WirelessLANGroup,
        "wireless_lans": WirelessLAN,
    })

    client.extras = _Namespace({
        "custom_fields": CustomField,
        "tags": Tag,
    })

    client.tenancy = _Namespace({
        "tenants": Tenant,
    })

    # Compatibility shim: pynetbox allows setting http_session, ignore it
    client.http_session = None

    return client
