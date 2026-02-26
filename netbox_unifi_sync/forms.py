from __future__ import annotations

import re

from django import forms
from dcim.models import Site

from .models import GlobalSyncSettings, SiteMapping, UnifiController
from .services.orchestrator import discover_unifi_site_names


# ---------------------------------------------------------------------------
# Custom field helpers
# ---------------------------------------------------------------------------

class _CommaSeparatedField(forms.CharField):
    """
    Text input that stores a comma-separated list of strings.
    Shown in the UI as a single text input (e.g. "tag1, tag2, tag3").
    """

    def to_python(self, value):
        raw = super().to_python(value) or ""
        return [item.strip() for item in raw.split(",") if item.strip()]

    def prepare_value(self, value):
        if isinstance(value, list):
            return ", ".join(str(item) for item in value)
        return value or ""


class _OnePerLineField(forms.CharField):
    """
    Textarea where each non-empty line is one entry in a list.
    Used for regex patterns, DHCP ranges, etc.
    """

    def to_python(self, value):
        raw = super().to_python(value) or ""
        return [line.strip() for line in raw.splitlines() if line.strip()]

    def prepare_value(self, value):
        if isinstance(value, list):
            return "\n".join(str(item) for item in value)
        return value or ""


class _KeyValueField(forms.CharField):
    """
    Textarea where each non-empty line is ``KEY = Value``.
    Stores and returns a dict.  Keys are uppercased automatically.

    Example input::

        WIRELESS = Wireless AP
        SWITCH = Switch
        ROUTER = Router
    """

    def to_python(self, value):
        raw = super().to_python(value) or ""
        result: dict[str, str] = {}
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                raise forms.ValidationError(
                    f"Invalid line (expected 'KEY = Value'): {line!r}"
                )
            key, _, val = line.partition("=")
            key = key.strip().upper()
            val = val.strip()
            if key and val:
                result[key] = val
        return result

    def prepare_value(self, value):
        if isinstance(value, dict):
            return "\n".join(f"{k} = {v}" for k, v in value.items())
        return value or ""


# ---------------------------------------------------------------------------
# NetBox 4.x device status choices
# ---------------------------------------------------------------------------

# NetBox 4.x DeviceStatusChoices (dcim/choices.py) — value passed directly
# to the sync engine via NETBOX_DEVICE_STATUS env var.
_DEVICE_STATUS_CHOICES = [
    ("offline", "Offline"),
    ("active", "Active"),
    ("planned", "Planned"),
    ("staged", "Staged"),
    ("failed", "Failed"),
    ("inventory", "Inventory"),
    ("decommissioning", "Decommissioning"),
]


# ---------------------------------------------------------------------------
# Main settings form
# ---------------------------------------------------------------------------

class GlobalSyncSettingsForm(forms.ModelForm):
    # --- friendly replacements for JSON fields ----------------------------

    # default_tags: stored as JSON list → shown as comma-separated text
    default_tags_text = _CommaSeparatedField(
        required=False,
        label="Default tags",
        help_text='Tags added to every synced device, separated by commas (e.g. "unifi, wifi").',
        widget=forms.TextInput(attrs={"placeholder": "unifi, wifi, managed"}),
    )

    # asset_tag_patterns: stored as JSON list → shown as one regex per line
    asset_tag_patterns_text = _OnePerLineField(
        required=False,
        label="Asset tag patterns",
        help_text=(
            "One regular expression per line.  "
            "First match wins; use a capture group for the extracted value.  "
            r"Example: [-_]?(A?ID\d+)$"
        ),
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": r"[-_]?(A?ID\d+)$"}),
    )

    # netbox_roles: stored as JSON dict → shown as KEY = Value lines
    netbox_roles_text = _KeyValueField(
        required=True,
        label="NetBox role mappings",
        help_text=(
            "One mapping per line in the format  KEY = Role name.  "
            "Keys are the UniFi device role slugs (uppercased).  "
            "Example: WIRELESS = Wireless AP"
        ),
        widget=forms.Textarea(attrs={
            "rows": 8,
            "placeholder": (
                "WIRELESS = Wireless AP\n"
                "SWITCH = Switch\n"
                "ROUTER = Router\n"
                "SECURITY = Security Appliance\n"
                "PHONE = VoIP Phone\n"
                "OTHER = Network Device"
            ),
        }),
    )

    class Meta:
        model = GlobalSyncSettings
        # Exclude the raw JSON fields; we handle them via the friendly fields above.
        exclude = ("singleton_key", "updated", "default_tags", "asset_tag_patterns", "netbox_roles")
        widgets = {
            "dhcp_ranges": forms.Textarea(attrs={
                "rows": 4,
                "placeholder": "192.168.1.0/24\n10.0.0.0/8",
            }),
            "netbox_device_status": forms.Select(choices=_DEVICE_STATUS_CHOICES),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get("instance")
        if instance:
            self.fields["default_tags_text"].initial = (
                self.fields["default_tags_text"].prepare_value(instance.default_tags)
            )
            patterns = instance.asset_tag_patterns or [r"[-_]?(A?ID\d+)$"]
            self.fields["asset_tag_patterns_text"].initial = (
                self.fields["asset_tag_patterns_text"].prepare_value(patterns)
            )
            self.fields["netbox_roles_text"].initial = (
                self.fields["netbox_roles_text"].prepare_value(instance.netbox_roles)
            )

    def clean(self):
        cleaned = super().clean()

        # --- default_tags ---
        tags = cleaned.get("default_tags_text") or []
        cleaned["default_tags"] = [str(t).strip() for t in tags if str(t).strip()]

        # --- asset_tag_patterns: validate each line as a regex ---
        patterns = cleaned.get("asset_tag_patterns_text") or []
        validated_patterns = []
        for idx, pat in enumerate(patterns):
            pat = str(pat).strip()
            if not pat:
                continue
            try:
                re.compile(pat)
            except re.error as exc:
                self.add_error(
                    "asset_tag_patterns_text",
                    f"Line {idx + 1} is not a valid regular expression: {exc}",
                )
                break
            validated_patterns.append(pat)
        cleaned["asset_tag_patterns"] = validated_patterns

        # --- netbox_roles ---
        roles = cleaned.get("netbox_roles_text")
        if not roles:
            self.add_error("netbox_roles_text", "At least one role mapping is required.")
        else:
            cleaned["netbox_roles"] = {
                str(k).strip().upper(): str(v).strip()
                for k, v in roles.items()
                if str(k).strip() and str(v).strip()
            }

        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.default_tags = self.cleaned_data.get("default_tags", [])
        instance.asset_tag_patterns = self.cleaned_data.get("asset_tag_patterns", [])
        instance.netbox_roles = self.cleaned_data.get("netbox_roles", {})
        if commit:
            instance.save()
        return instance


class UnifiControllerForm(forms.ModelForm):
    class Meta:
        model = UnifiController
        fields = (
            "name",
            "base_url",
            "enabled",
            "auth_mode",
            "api_key_ref",
            "api_key_header",
            "username_ref",
            "password_ref",
            "mfa_secret_ref",
            "verify_ssl",
            "request_timeout",
            "http_retries",
            "retry_backoff_base",
            "retry_backoff_max",
            "notes",
        )
        widgets = {
            "api_key_ref": forms.PasswordInput(render_value=True),
            "password_ref": forms.PasswordInput(render_value=True),
            "mfa_secret_ref": forms.PasswordInput(render_value=True),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        direct_secret_help = "Paste the credential value directly in this field."
        self.fields["api_key_ref"].help_text = direct_secret_help
        self.fields["username_ref"].help_text = direct_secret_help
        self.fields["password_ref"].help_text = direct_secret_help
        self.fields["mfa_secret_ref"].help_text = direct_secret_help


class SiteMappingForm(forms.ModelForm):
    unifi_site = forms.CharField()
    netbox_site = forms.CharField()

    class Meta:
        model = SiteMapping
        fields = ("controller", "unifi_site", "netbox_site", "enabled")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        discovered_unifi_sites = set(discover_unifi_site_names())
        discovered_unifi_sites.update(
            SiteMapping.objects.values_list("unifi_site", flat=True)
        )
        current_unifi = str(getattr(self.instance, "unifi_site", "") or "").strip()
        if current_unifi:
            discovered_unifi_sites.add(current_unifi)

        unifi_choices = [("", "Select UniFi site")]
        unifi_choices.extend((name, name) for name in sorted(discovered_unifi_sites, key=str.casefold) if name)
        self.fields["unifi_site"].widget = forms.Select(choices=unifi_choices)

        netbox_site_names = set(Site.objects.order_by("name").values_list("name", flat=True))
        netbox_site_names.update(SiteMapping.objects.values_list("netbox_site", flat=True))
        current_netbox = str(getattr(self.instance, "netbox_site", "") or "").strip()
        if current_netbox:
            netbox_site_names.add(current_netbox)

        netbox_choices = [("", "Select NetBox site")]
        netbox_choices.extend((name, name) for name in sorted(netbox_site_names, key=str.casefold) if name)
        self.fields["netbox_site"].widget = forms.Select(choices=netbox_choices)


class RunActionForm(forms.Form):
    dry_run = forms.BooleanField(required=False)
    cleanup = forms.BooleanField(required=False)


class RunFilterForm(forms.Form):
    status = forms.ChoiceField(
        required=False,
        choices=[("", "Any"), ("pending", "Pending"), ("running", "Running"), ("dry_run", "Dry run"), ("success", "Success"), ("failed", "Failed")],
    )
    q = forms.CharField(required=False)
    limit = forms.IntegerField(required=False, min_value=1, max_value=500, initial=100)
