from __future__ import annotations

import json

from django import forms
from dcim.models import Site

from .models import GlobalSyncSettings, SiteMapping, UnifiController
from .services.orchestrator import discover_unifi_site_names


class JSONTextAreaField(forms.CharField):
    def to_python(self, value):
        raw = super().to_python(value)
        raw = (raw or "").strip()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Invalid JSON: {exc}") from exc


class GlobalSyncSettingsForm(forms.ModelForm):
    default_tags_json = JSONTextAreaField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    asset_tag_patterns_json = JSONTextAreaField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    netbox_roles_json = JSONTextAreaField(required=True, widget=forms.Textarea(attrs={"rows": 5}))

    class Meta:
        model = GlobalSyncSettings
        exclude = ("singleton_key", "updated", "default_tags", "asset_tag_patterns", "netbox_roles")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["asset_tag_patterns_json"].label = "Asset Tag Patterns (JSON)"
        self.fields["asset_tag_patterns_json"].help_text = (
            'Example: ["[-_]?(A?ID\\\\d+)$", "ASSET[: -]?(\\\\d+)"]'
        )
        instance = kwargs.get("instance")
        if instance:
            self.fields["default_tags_json"].initial = json.dumps(instance.default_tags, indent=2)
            patterns = instance.asset_tag_patterns or [r"[-_]?(A?ID\d+)$"]
            self.fields["asset_tag_patterns_json"].initial = json.dumps(patterns, indent=2)
            self.fields["netbox_roles_json"].initial = json.dumps(instance.netbox_roles, indent=2)

    def clean(self):
        cleaned = super().clean()
        tags = cleaned.get("default_tags_json")
        asset_tag_patterns = cleaned.get("asset_tag_patterns_json")
        roles = cleaned.get("netbox_roles_json")

        if tags is None:
            cleaned["default_tags"] = []
        elif not isinstance(tags, list):
            self.add_error("default_tags_json", "default_tags must be a JSON list.")
        else:
            cleaned["default_tags"] = [str(item).strip() for item in tags if str(item).strip()]

        if asset_tag_patterns is None:
            cleaned["asset_tag_patterns"] = []
        elif not isinstance(asset_tag_patterns, list):
            self.add_error("asset_tag_patterns_json", "asset_tag_patterns must be a JSON list.")
        else:
            cleaned["asset_tag_patterns"] = [str(item).strip() for item in asset_tag_patterns if str(item).strip()]

        if roles is None:
            self.add_error("netbox_roles_json", "netbox_roles is required.")
        elif not isinstance(roles, dict) or not roles:
            self.add_error("netbox_roles_json", "netbox_roles must be a non-empty JSON object.")
        else:
            cleaned["netbox_roles"] = {str(k).strip().upper(): str(v).strip() for k, v in roles.items() if str(k).strip() and str(v).strip()}

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
