from django import forms

from .models import AIAuditorSettings


class AIAuditorSettingsForm(forms.ModelForm):
    class Meta:
        model = AIAuditorSettings
        fields = [
            "auto_fix_enabled",
            "auto_test_generation",
            "excluded_apps",
            "analysis_schedule",
            "email_notifications",
            "critical_threshold",
        ]
        widgets = {
            "excluded_apps": forms.Textarea(attrs={"rows": 3}),
        }
