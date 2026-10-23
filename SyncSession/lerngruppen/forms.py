from django import forms

from .models import LearningGroup


class GroupCreateForm(forms.ModelForm):
    class Meta:
        model = LearningGroup
        fields = ("name",)
        labels = {"name": "Gruppenname"}
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "z. B. Mathe 2"}),
        }


class InviteSettingsForm(forms.ModelForm):
    class Meta:
        model = LearningGroup
        fields = ("members_can_invite",)
