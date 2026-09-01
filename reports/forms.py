from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Report
from .constants import STATES


class ReportForm(forms.ModelForm):
    other_issue = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Describe your issue",
    )

    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
    )

    state = forms.ChoiceField(choices=[("", "— Select State —")] + STATES)

    class Meta:
        model = Report
        fields = [
            "title",
            "description",
            "category",
            "priority",
            "image",
            "latitude",
            "longitude",
            "address",
            "state",
        ]
        widgets = {
            "latitude": forms.HiddenInput(),
            "longitude": forms.HiddenInput(),
        }

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get("category")
        other_issue = cleaned_data.get("other_issue", "").strip()
        description = cleaned_data.get("description", "").strip()

        if category == "other" and not description and not other_issue:
            self.add_error(
                "description",
                "Please describe the issue, or use the box under 'Other Issue'.",
            )

        return cleaned_data


class SignupForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class CreateAdminForm(UserCreationForm):
    email = forms.EmailField(required=True)
    role = forms.ChoiceField(choices=[("admin", "State Admin"), ("superadmin", "Super Admin")])
    state = forms.ChoiceField(choices=[("", "— Select State —")] + STATES, required=False)

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("role") == "admin" and not cleaned_data.get("state"):
            self.add_error("state", "Select a state for a State Admin.")
        return cleaned_data
