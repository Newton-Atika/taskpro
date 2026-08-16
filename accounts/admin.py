from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):

    model = CustomUser

    list_display = (
        "email",
        "full_name",
        "phone_number",
        "is_staff",
        "is_assigned",
        "accepted_terms",
    )

    list_filter = (
        "is_staff",
        "is_assigned",
        "accepted_terms",
        "is_active",
    )

    search_fields = (
        "email",
        "full_name",
        "phone_number",
        "id_number",
        "kra_pin",
    )

    ordering = ("email",)

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "email",
                    "password",
                )
            },
        ),

        (
            "Personal Information",
            {
                "fields": (
                    "full_name",
                    "phone_number",
                    "legal_name",
                    "id_number",
                    "kra_pin",
                )
            },
        ),

        (
            "Workload Staff Settings",
            {
                "fields": (
                    "is_staff",
                    "is_assigned",
                )
            },
        ),

        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),

        (
            "Terms",
            {
                "fields": (
                    "accepted_terms",
                )
            },
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "full_name",
                    "phone_number",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_assigned",
                ),
            },
        ),
    )