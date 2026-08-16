from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import CustomUser


class RegisterForm(UserCreationForm):

    class Meta:
        model = CustomUser

        fields = (
            "full_name",
            "email",
            "phone_number",
            "password1",
            "password2",
            "accepted_terms",
        )

    def clean_accepted_terms(self):
        accepted = self.cleaned_data.get("accepted_terms")

        if not accepted:
            raise forms.ValidationError(
                "You must accept the Terms and Conditions."
            )

        return accepted