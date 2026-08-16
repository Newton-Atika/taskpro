from django import forms

from .models import CustomUser


class StaffProfileForm(forms.ModelForm):

    class Meta:

        model = CustomUser

        fields = [

            "legal_name",

            "id_number",

            "kra_pin",

        ]