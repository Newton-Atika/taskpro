from django.conf import settings
from django.db import models
from accounts.models import CustomUser
from cloudinary.models import CloudinaryField

class Task(models.Model):
    
    CATEGORY_CHOICES = [
        ("programming", "Programming & IT"),
        ("data_analysis", "Data Analysis"),
        ("writing", "Writing & Research"),
        ("design", "Graphic Design"),
        ("presentation", "Presentations"),
        ("excel", "Excel & Spreadsheets"),
        ("gis", "GIS & Mapping"),
        ("business", "Business Services"),
        ("academic", "Academic Support"),
        ("other", "Other"),
    ]

    STATUS_CHOICES = [
        ("submitted", "Submitted"),
        ("quoted", "Quote Sent"),
        ("accepted", "Quote Accepted"),
        ("paid", "Paid"),
        ("assigned", "Assigned"),
        ("in_progress", "In Progress"),
        ("reviewing", "Under Review"),
        ("delivered", "Delivered"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    PAYMENT_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("requested", "Payment Requested"),
        ("paid", "Paid"),
        ("failed", "Payment Failed"),
        ("refunded", "Refunded"),
    ]

    # =====================================================
    # CUSTOMER
    # =====================================================

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tasks"
    )

    # =====================================================
    # TASK INFORMATION
    # =====================================================

    title = models.CharField(
        max_length=255
    )

    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES
    )

    description = models.TextField()

    deadline = models.DateTimeField()

    # =====================================================
    # CUSTOMER BUDGET
    # =====================================================

    budget = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True
    )

    # =====================================================
    # FINAL WORKLOAD QUOTE
    # =====================================================

    quoted_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True
    )

    # =====================================================
    # PAYMENT
    # =====================================================

    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default="pending"
    )

    payment_reference = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    paid_at = models.DateTimeField(
        blank=True,
        null=True
    )

    quoted_amount_accepted = models.BooleanField(
        default=False
    )

    quoted_amount_accepted_at = models.DateTimeField(
        null=True,
        blank=True
    )

    # =====================================================
    # TASK STATUS
    # =====================================================

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="submitted"
    )

    # =====================================================
    # STAFF ASSIGNMENT
    # =====================================================

    assigned_staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tasks",
        limit_choices_to={"is_staff": True},
    )

    # =====================================================
    # TIMESTAMPS
    # =====================================================

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return self.title


# =========================================================
# CUSTOMER DOCUMENTS
# =========================================================

class TaskDocument(models.Model):

    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="documents"
    )

    file = CloudinaryField(
        "file",
        resource_type="auto"
    )

    description = models.CharField(
        max_length=255,
        blank=True
    )

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_task_documents"
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        if self.file:
            return str(self.file)
        return f"Document - {self.task.title}"


# =========================================================
# STAFF DELIVERABLES
# =========================================================

class TaskDeliverable(models.Model):

    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="deliverables"
    )

    file = CloudinaryField(
        "file",
        resource_type="auto",
        blank=True,
        null=True
    )

    comment = models.TextField(
        blank=True
    )

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_deliverables"
    )

    submitted_at = models.DateTimeField(
        auto_now_add=True
    )

    # ADMIN APPROVAL
    approved = models.BooleanField(
        default=False
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_deliverables"
    )

    approved_at = models.DateTimeField(
        null=True,
        blank=True
    )

    def __str__(self):
        return f"Deliverable - {self.task.title}"


# ============================================================
# NOTIFICATIONS
# ============================================================

class Notification(models.Model):

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="notifications"
    )

    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications"
    )

    title = models.CharField(
        max_length=255
    )

    message = models.TextField()

    notification_type = models.CharField(
        max_length=50,
        default="info"
    )

    is_read = models.BooleanField(
        default=False
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:

        ordering = ["-created_at"]

    def __str__(self):

        return f"{self.user} - {self.title}"



class PushSubscription(models.Model):

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="push_subscriptions"
    )

    endpoint = models.TextField(
        unique=True
    )

    p256dh = models.TextField()

    auth = models.TextField()

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"Push subscription - {self.user}"
