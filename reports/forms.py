
from django import forms
<<<<<<< HEAD
=======
from django.contrib.auth.forms import UserCreationForm
>>>>>>> origin/main
from django.contrib.auth.models import User
from .models import Report


class ReportForm(forms.ModelForm):
<<<<<<< HEAD
=======
    other_issue = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Describe your issue",
    )

    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
    )
>>>>>>> origin/main

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
            "latitude": forms.HiddenInput(),
            "longitude": forms.HiddenInput(),
        }

<<<<<<< HEAD

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
=======
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
>>>>>>> origin/main
