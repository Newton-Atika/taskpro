from django import forms

from .models import Task, TaskDocument


# ============================================================
# TASK FORM
# ============================================================

class TaskForm(forms.ModelForm):

    class Meta:

        model = Task

        fields = [
            "title",
            "category",
            "description",
            "deadline",
            "budget",
        ]

        widgets = {

            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder":
                        "e.g. Develop a Python dashboard"
                }
            ),

            "category": forms.Select(
                attrs={
                    "class": "form-select"
                }
            ),

            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 6,
                    "placeholder":
                        "Describe exactly what you need done..."
                }
            ),

            "deadline": forms.DateTimeInput(
                attrs={
                    "class": "form-control",
                    "type": "datetime-local"
                }
            ),

            "budget": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Optional",
                    "min": "0",
                    "step": "0.01"
                }
            ),
        }


# ============================================================
# TASK DOCUMENT FORM
# ============================================================

class TaskDocumentForm(forms.ModelForm):

    class Meta:

        model = TaskDocument

        fields = [
            "file",
            "description",
        ]

        widgets = {

            "file": forms.ClearableFileInput(
                attrs={
                    "class": "form-control"
                }
            ),

            "description": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder":
                        "Briefly describe this document (optional)"
                }
            ),
        }
