from django.contrib import admin

from .models import (
    Task,
    TaskDocument,
    TaskDeliverable,
)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "title",
        "customer",
        "category",
        "status",
        "payment_status",
        "deadline",
        "assigned_staff",
        "created_at",
    )

    list_filter = (
        "status",
        "payment_status",
        "category",
        "assigned_staff",
    )

    search_fields = (
        "title",
        "description",
        "customer__email",
        "customer__full_name",
        "assigned_staff__email",
        "assigned_staff__full_name",
    )

    list_select_related = (
        "customer",
        "assigned_staff",
    )


@admin.register(TaskDocument)
class TaskDocumentAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "task",
        "uploaded_by",
        "uploaded_at",
    )

    list_filter = (
        "uploaded_at",
    )

    search_fields = (
        "task__title",
        "uploaded_by__email",
        "uploaded_by__full_name",
    )


@admin.register(TaskDeliverable)
class TaskDeliverableAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "task",
        "submitted_by",
        "submitted_at",
    )

    list_filter = (
        "submitted_at",
    )

    search_fields = (
        "task__title",
        "submitted_by__email",
        "submitted_by__full_name",
        "comment",
    )