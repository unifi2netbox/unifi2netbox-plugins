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
# Choice-field value wrapper
# ---------------------------------------------------------------------------

class _ChoiceValue(str):
    """str subclass that exposes .value and .label for pynetbox API compatibility.

    Django ORM returns choice field values as plain strings (e.g. "1000base-t").
    pynetbox REST responses return objects with .value and .label attributes.
    This subclass is a drop-in str replacement, so existing string comparisons
    (==, ``in``, ``startswith``) continue to work unchanged.
    """

    @property
    def value(self):
        return str(self)

    @property
    def label(self):
        return str(self)


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
        # tags: django-taggit returns a _TaggableManager (not directly iterable).
        # pynetbox returns a plain list of tag objects — match that behaviour.
        if name == "tags":
            try:
                return list(instance.tags.all())
            except Exception:
                return []
        value = getattr(instance, name)
        # Normalise ContentType FK accessors to "app_label.model_name" strings
        # so callers can do:  if obj.assigned_object_type == "dcim.interface"
        # (pynetbox returns strings; Django returns ContentType instances)
        if name in _OrmObject._CONTENT_TYPE_FIELDS:
            if value is not None and not isinstance(value, str):
                try:
                    # ContentType has app_label + model attributes
                    return _ChoiceValue(f"{value.app_label}.{value.model}")
                except AttributeError:
                    return _ChoiceValue(str(value))
        # Wrap plain strings in _ChoiceValue so callers can use .value / .label
        # (pynetbox returns objects with those attrs; Django returns plain strings).
        if isinstance(value, str):
            return _ChoiceValue(value)
        return value

    # Fields whose "name" accessor is a GenericForeignKey; the real DB column
    # that stores the ContentType FK is ``<name>_id``.  When callers set these
    # with a "app_label.model" string (pynetbox REST payload style) we
    # transparently resolve it to a ContentType instance so Django is happy.
    _CONTENT_TYPE_FIELDS = frozenset({"assigned_object_type", "scope_type", "termination_type"})

    # FK fields where callers pass an integer PK using the *field name* (without
    # the ``_id`` suffix).  Django requires either ``field_id = int`` or
    # ``field = <model_instance>``; assigning an int to the bare FK name raises
    # ValueError.  We rewrite these automatically.
    _INT_FK_FIELDS = frozenset({"primary_ip4", "primary_ip6"})

    def __setattr__(self, name: str, value):
        if name == "_instance":
            object.__setattr__(self, name, value)
            return
        instance = object.__getattribute__(self, "_instance")
        # tags: django-taggit uses .set() on the manager; plain assignment is
        # not supported.  Accept a list of Tag PKs or Tag instances (pynetbox
        # passes PKs after reading tag IDs via __getattr__).
        if name == "tags":
            try:
                instance.tags.set(value or [])
            except Exception as exc:
                logger.debug("ORM: could not set tags on %r: %s", instance, exc)
            return
        if name == "custom_fields":
            # Merge into custom_field_data
            existing = getattr(instance, "custom_field_data", {}) or {}
            if isinstance(value, dict):
                existing.update(value)
                instance.custom_field_data = existing
            return
        if name in _OrmObject._CONTENT_TYPE_FIELDS and isinstance(value, str) and "." in value:
            # Convert "app_label.model_name" string → ContentType instance
            try:
                from django.contrib.contenttypes.models import ContentType
                app_label, model_name = value.split(".", 1)
                value = ContentType.objects.get(app_label=app_label, model=model_name)
            except (ValueError, LookupError):
                pass  # fall through and let Django handle/reject it
        if name in _OrmObject._INT_FK_FIELDS and isinstance(value, int):
            # Rewrite bare FK name to attname (primary_ip4 → primary_ip4_id)
            # so Django stores the PK directly without trying to resolve the
            # related instance.
            setattr(instance, f"{name}_id", value)
            return
        setattr(instance, name, value)

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def save(self, update_fields=None):
        instance = object.__getattribute__(self, "_instance")
        # Call snapshot() before saving existing objects so NetBox change log
        # records the pre-change state (prechange_data) correctly.
        if instance.pk and hasattr(instance, 'snapshot'):
            try:
                instance.snapshot()
            except Exception as exc:
                logger.debug("snapshot() failed on %r (non-fatal): %s", instance, exc)
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
                    translated["prefix__net_contains_or_equals"] = str(value)
                except Exception:
                    translated["prefix__contains"] = str(value)
            elif key in _OrmObject._CONTENT_TYPE_FIELDS and isinstance(value, str) and "." in value:
                # Convert "app_label.model_name" string → ContentType instance.
                # Covers scope_type, assigned_object_type, termination_type.
                try:
                    from django.contrib.contenttypes.models import ContentType
                    app_label, model_name = str(value).split(".", 1)
                    ct = ContentType.objects.get(app_label=app_label, model=model_name)
                    translated[key] = ct
                except (ValueError, LookupError):
                    pass  # silently ignore unresolvable content-type strings
            elif key == "scope_id":
                translated["scope_id"] = value
            else:
                # Pass through; _id suffix fields work natively in Django ORM
                translated[key] = value
        return translated

    def get(self, *args, **kwargs) -> "_OrmObject | None":
        # Accept a single positional PK argument (pynetbox API compat):
        #   nb.dcim.cables.get(42)  →  Cable.objects.get(pk=42)
        if args:
            pk = args[0]
            try:
                return _wrap(self._qs().get(pk=pk))
            except self._model.DoesNotExist:
                return None
            except Exception as exc:
                logger.debug("ORM .get(pk=%s) error for %s: %s", pk, self._model.__name__, exc)
                return None
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

    @staticmethod
    def _fk_fields(model) -> set[str]:
        """
        Return the set of ForeignKey field *names* (without the ``_id`` suffix)
        on *model*.  Used to rewrite ``{'manufacturer': 5}`` →
        ``{'manufacturer_id': 5}`` so Django never tries to resolve the
        related instance during construction or validation.
        """
        try:
            from django.db.models import ForeignKey
            return {
                f.name
                for f in model._meta.get_fields()
                if isinstance(f, ForeignKey)
            }
        except Exception:
            return set()

    def create(self, payload: dict | None = None, **kwargs) -> "_OrmObject | None":
        """
        Create a new instance from a flat payload dict.

        Handles:
        * ``xxx`` (FK name) with integer value → stored as ``xxx_id`` so Django
          never attempts to resolve the related object during construction
        * ``content_types`` → ManyToMany (set after save)
        * ``scope_type`` / ``assigned_object_type`` string → ContentType lookup
        * ``custom_fields`` → stored in custom_field_data
        * ``a_terminations`` / ``b_terminations`` (Cable) → creates CableTermination
          rows after the Cable is saved (pynetbox REST API format:
          ``[{"object_type": "dcim.interface", "object_id": <id>}]``)

        We intentionally skip ``model.full_clean()`` because NetBox model
        validators (e.g. ``_clean_custom_fields``) run against the full
        NetBox runtime context and may raise ``ValidationError`` for
        valid data when called on an unsaved instance outside a request
        cycle.  The REST API uses DRF serialiser validation, not
        ``full_clean()``, so we match that behaviour here.
        """
        if payload is None:
            payload = kwargs
        elif kwargs:
            payload = {**payload, **kwargs}
        m2m: dict[str, list] = {}
        direct: dict[str, Any] = {}
        custom_fields: dict[str, Any] = {}
        # Cable terminations: {"A": [...], "B": [...]}
        cable_terminations: dict[str, list] = {}

        fk_names = self._fk_fields(self._model)

        for key, value in payload.items():
            if key == "content_types":
                # ManyToMany: list of "app_label.model" strings
                m2m["content_types"] = value
            elif key == "custom_fields" and isinstance(value, dict):
                custom_fields = value
            elif key in _OrmObject._CONTENT_TYPE_FIELDS and isinstance(value, str) and "." in value:
                # Convert "app_label.model_name" → ContentType instance.
                # Covers scope_type, assigned_object_type, termination_type.
                try:
                    from django.contrib.contenttypes.models import ContentType
                    app_label, model_name = value.split(".", 1)
                    ct = ContentType.objects.get(app_label=app_label, model=model_name)
                    direct[key] = ct
                except (ValueError, LookupError):
                    pass  # skip unresolvable content-type strings
            elif key == "a_terminations" and isinstance(value, list):
                # Cable A-end terminations — handled after save
                cable_terminations["A"] = value
            elif key == "b_terminations" and isinstance(value, list):
                # Cable B-end terminations — handled after save
                cable_terminations["B"] = value
            elif key in fk_names and isinstance(value, int):
                # Rewrite FK name to attname so Django stores the PK directly
                # without trying to resolve the related instance.
                direct[f"{key}_id"] = value
            else:
                direct[key] = value

        if custom_fields:
            direct["custom_field_data"] = custom_fields

        try:
            instance = self._model(**direct)
            # Skip full_clean(): NetBox model validators require a fully
            # initialised request context and may reject valid payloads on
            # unsaved instances.  Django's save() enforces DB constraints
            # (NOT NULL, UNIQUE) at the database level instead.
            instance.save()
        except Exception as exc:
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
                    except (ValueError, LookupError) as exc:
                        logger.debug("M2M ContentType add skipped for %r: %s", item, exc)
                else:
                    try:
                        field.add(item)
                    except Exception as exc:
                        logger.debug("M2M field.add skipped for %r: %s", item, exc)

        # Create CableTermination rows for Cable a_terminations / b_terminations.
        # Each entry is {"object_type": "dcim.interface", "object_id": <int>}.
        if cable_terminations:
            try:
                from django.contrib.contenttypes.models import ContentType
                from dcim.models import CableTermination
                for cable_end, terminations in cable_terminations.items():
                    for term in terminations:
                        obj_type_str = term.get("object_type", "")
                        obj_id = term.get("object_id")
                        if not obj_type_str or obj_id is None:
                            continue
                        try:
                            app_label, model_name = obj_type_str.split(".", 1)
                            ct = ContentType.objects.get(app_label=app_label, model=model_name)
                            CableTermination.objects.create(
                                cable=instance,
                                cable_end=cable_end,
                                termination_type=ct,
                                termination_id=obj_id,
                            )
                        except Exception as exc:
                            logger.warning(
                                "ORM: could not create CableTermination "
                                "(cable=%s end=%s type=%s id=%s): %s",
                                instance.pk, cable_end, obj_type_str, obj_id, exc,
                            )
            except ImportError:
                logger.debug("ORM: CableTermination not available — skipping terminations")

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
