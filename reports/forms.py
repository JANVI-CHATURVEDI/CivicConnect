
from django import forms
from django.contrib.auth.models import User
from .models import Report


class ReportForm(forms.ModelForm):

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
        ]

        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "latitude": forms.HiddenInput(),
            "longitude": forms.HiddenInput(),
        }


class RegistrationForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={"placeholder": "Enter your password"}
        )
    )

    confirm_password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={"placeholder": "Confirm your password"}
        )
    )

    class Meta:
        model = User
        fields = ["username", "email", "password"]

    def clean(self):
        cleaned_data = super().clean()

        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords do not match.")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)

        user.set_password(self.cleaned_data["password"])

        if commit:
            user.save()

            from .models import UserProfile
            UserProfile.objects.create(
                user=user,
                role="citizen"
            )

        return user