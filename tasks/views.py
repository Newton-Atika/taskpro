from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.http import (
    JsonResponse,
    HttpResponse,
    Http404,
)
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.urls import reverse
from urllib.parse import quote
from .notification_helpers import notify_user
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model
from urllib.parse import quote
from pathlib import Path
import mimetypes
import requests
from .models import PushSubscription

from .push_notifications import send_push_notification

from decimal import Decimal, InvalidOperation
import requests
import hashlib
import hmac
import json
import uuid

from accounts.models import CustomUser

from .forms import TaskForm, TaskDocumentForm
from .models import (
    Task,
    TaskDocument,
    TaskDeliverable,
    Notification,
)

User = get_user_model()

# ============================================================
# WEB PUSH — GET PUBLIC VAPID KEY
# ============================================================

@login_required
def vapid_public_key(request):

    return JsonResponse(
        {
            "publicKey": (
                settings.WEBPUSH_VAPID_PUBLIC_KEY
            )
        }
    )


# ============================================================
# WEB PUSH — SAVE BROWSER SUBSCRIPTION
# ============================================================

@login_required
@require_POST
def save_push_subscription(request):

    try:

        data = json.loads(
            request.body.decode("utf-8")
        )

    except (
        ValueError,
        UnicodeDecodeError,
    ):

        return JsonResponse(
            {
                "success": False,
                "message": "Invalid JSON."
            },
            status=400
        )

    endpoint = data.get(
        "endpoint"
    )

    keys = data.get(
        "keys",
        {}
    )

    p256dh = keys.get(
        "p256dh"
    )

    auth = keys.get(
        "auth"
    )

    if not endpoint or not p256dh or not auth:

        return JsonResponse(
            {
                "success": False,
                "message": "Invalid push subscription."
            },
            status=400
        )

    PushSubscription.objects.update_or_create(

        endpoint=endpoint,

        defaults={
            "user": request.user,
            "p256dh": p256dh,
            "auth": auth,
        }
    )

    return JsonResponse(
        {
            "success": True,
            "message": "Push subscription saved."
        }
    )


# ============================================================
# WEB PUSH — REMOVE SUBSCRIPTION
# ============================================================

@login_required
@require_POST
def remove_push_subscription(request):

    endpoint = None

    try:

        data = json.loads(
            request.body.decode("utf-8")
        )

        endpoint = data.get(
            "endpoint"
        )

    except (
        ValueError,
        UnicodeDecodeError,
    ):

        pass

    if endpoint:

        PushSubscription.objects.filter(
            user=request.user,
            endpoint=endpoint
        ).delete()

    return JsonResponse(
        {
            "success": True
        }
    )


def create_task_notification(
    task,
    title,
    message,
    notification_type="info",
    recipients=None,
):
    """
    Create a notification for one or more users.
    """

    if recipients is None:

        recipients = []

    # Remove duplicate users
    unique_users = {}

    for user in recipients:

        if user and user.is_active:

            unique_users[user.id] = user

    notifications = []

    for user in unique_users.values():

        notifications.append(
            Notification(
                user=user,
                task=task,
                title=title,
                message=message,
                notification_type=notification_type,
            )
        )

    if notifications:

        Notification.objects.bulk_create(
            notifications
        )


def notify_task_parties(
    task,
    title,
    message,
    notification_type="info",
    include_customer=True,
    include_staff=True,
    include_admin=True,
):
    """
    Notify customer, assigned staff and administrators.
    """

    recipients = []

    # ------------------------------------------------
    # CUSTOMER
    # ------------------------------------------------

    if include_customer and task.customer:

        recipients.append(
            task.customer
        )

    # ------------------------------------------------
    # ASSIGNED STAFF
    # ------------------------------------------------

    if (
        include_staff
        and task.assigned_staff
    ):

        recipients.append(
            task.assigned_staff
        )

    # ------------------------------------------------
    # SUPERUSERS / ADMINS
    # ------------------------------------------------

    if include_admin:

        admins = CustomUser.objects.filter(
            is_superuser=True,
            is_active=True,
        )

        recipients.extend(
            admins
        )

    create_task_notification(
        task=task,
        title=title,
        message=message,
        notification_type=notification_type,
        recipients=recipients,
    )


# ============================================================
# PAYSTACK CONFIGURATION
# ============================================================

PAYSTACK_INITIALIZE_URL = (
    f"{settings.PAYSTACK_BASE_URL}/transaction/initialize"
)

PAYSTACK_VERIFY_URL = (
    f"{settings.PAYSTACK_BASE_URL}/transaction/verify/"
)


# ============================================================
# PAYSTACK CONFIGURATION
# ============================================================

PAYSTACK_INITIALIZE_URL = (
    "https://api.paystack.co/transaction/initialize"
)

PAYSTACK_VERIFY_URL = (
    "https://api.paystack.co/transaction/verify/"
)


# ============================================================
# SUBMIT TASK
# ============================================================

@login_required
def submit_task(request):

    if request.method == "POST":

        task_form = TaskForm(request.POST)

        document_form = TaskDocumentForm(
            request.POST,
            request.FILES,
            prefix="document"
        )

        if task_form.is_valid() and document_form.is_valid():

            task = task_form.save(commit=False)

            task.customer = request.user

            # New tasks start as SUBMITTED
            task.status = "submitted"

            task.save()

            notify_user(

                user=request.user,

                title="Task Submitted",

                message=(
                    f"Your task #{task.id} "
                    f"'{task.title}' has been submitted successfully."
                ),

                task=task,
            )

            # ------------------------------------------------
            # Save initial document if uploaded
            # ------------------------------------------------

            if document_form.cleaned_data.get("file"):

                document = document_form.save(
                    commit=False
                )

                document.task = task
                document.uploaded_by = request.user

                document.save()

            messages.success(
                request,
                "Your task has been submitted successfully."
            )

            return redirect(
                "task_detail",
                task_id=task.id
            )

    else:

        task_form = TaskForm()

        document_form = TaskDocumentForm(
            prefix="document"
        )

    return render(
        request,
        "tasks/submit_task.html",
        {
            "form": task_form,
            "document_form": document_form,
        }
    )

# ============================================================
# EDIT TASK — CUSTOMER
# ============================================================

@login_required
def edit_task(request, task_id):

    # --------------------------------------------------------
    # GET TASK
    #
    # Only the customer who created the task can edit it.
    # --------------------------------------------------------

    task = get_object_or_404(
        Task,
        id=task_id,
        customer=request.user
    )

    # --------------------------------------------------------
    # LOCK EDITING
    #
    # Customer cannot edit if:
    #
    # 1. Quote has been accepted
    # OR
    # 2. Task has been assigned to staff
    # --------------------------------------------------------

    if (
        task.quoted_amount_accepted
        or task.assigned_staff
    ):

        messages.error(
            request,
            "This task can no longer be edited because "
            "the quote has been accepted or the task "
            "has already been assigned."
        )

        return redirect(
            "task_detail",
            task_id=task.id
        )

    # --------------------------------------------------------
    # POST — SAVE TASK CHANGES
    # --------------------------------------------------------

    if request.method == "POST":

        form = TaskForm(
            request.POST,
            instance=task
        )

        if form.is_valid():

            form.save()

            messages.success(
                request,
                "Your task has been updated successfully."
            )

            return redirect(
                "task_detail",
                task_id=task.id
            )

    # --------------------------------------------------------
    # GET — SHOW EXISTING INFORMATION
    # --------------------------------------------------------

    else:

        form = TaskForm(
            instance=task
        )

    # --------------------------------------------------------
    # GET DOCUMENTS
    # --------------------------------------------------------

    documents = task.documents.all().order_by(
        "-uploaded_at"
    )

    # --------------------------------------------------------
    # RENDER PAGE
    # --------------------------------------------------------

    return render(
        request,
        "tasks/edit_task.html",
        {
            "form": form,
            "task": task,
            "documents": documents,
        }
    )



# ============================================================
# EDIT TASK DOCUMENT — CUSTOMER
# ============================================================

@login_required
def edit_task_document(
    request,
    task_id,
    document_id
):

    # --------------------------------------------------------
    # GET TASK
    #
    # Only the task owner can edit the document.
    # --------------------------------------------------------

    task = get_object_or_404(
        Task,
        id=task_id,
        customer=request.user
    )

    # --------------------------------------------------------
    # LOCK EDITING
    #
    # Cannot edit after:
    #
    # 1. Quote acceptance
    # 2. Staff assignment
    # --------------------------------------------------------

    if (
        task.quoted_amount_accepted
        or task.assigned_staff
    ):

        messages.error(
            request,
            "Documents can no longer be edited because "
            "the quote has been accepted or the task "
            "has already been assigned."
        )

        return redirect(
            "task_detail",
            task_id=task.id
        )

    # --------------------------------------------------------
    # GET DOCUMENT
    #
    # Important: document must belong to this task.
    # --------------------------------------------------------

    document = get_object_or_404(
        TaskDocument,
        id=document_id,
        task=task
    )

    # --------------------------------------------------------
    # POST — UPDATE DOCUMENT
    # --------------------------------------------------------

    if request.method == "POST":

        form = TaskDocumentForm(
            request.POST,
            request.FILES,
            instance=document
        )

        if form.is_valid():

            updated_document = form.save(
                commit=False
            )

            # Keep original uploader if already set.
            if not updated_document.uploaded_by:

                updated_document.uploaded_by = (
                    request.user
                )

            updated_document.save()

            messages.success(
                request,
                "Document updated successfully."
            )

            return redirect(
                "edit_task",
                task_id=task.id
            )

    # --------------------------------------------------------
    # GET — SHOW EXISTING DOCUMENT
    # --------------------------------------------------------

    else:

        form = TaskDocumentForm(
            instance=document
        )

    # --------------------------------------------------------
    # RENDER PAGE
    # --------------------------------------------------------

    return render(
        request,
        "tasks/edit_task_document.html",
        {
            "task": task,
            "document": document,
            "form": form,
        }
    )


# ============================================================
# DELETE TASK DOCUMENT — CUSTOMER
# ============================================================

@login_required
def delete_task_document(
    request,
    task_id,
    document_id
):

    # --------------------------------------------------------
    # GET TASK
    # --------------------------------------------------------

    task = get_object_or_404(
        Task,
        id=task_id,
        customer=request.user
    )

    # --------------------------------------------------------
    # LOCK EDITING
    # --------------------------------------------------------

    if (
        task.quoted_amount_accepted
        or task.assigned_staff
    ):

        messages.error(
            request,
            "Documents can no longer be deleted because "
            "the quote has been accepted or the task "
            "has already been assigned."
        )

        return redirect(
            "task_detail",
            task_id=task.id
        )

    # --------------------------------------------------------
    # GET DOCUMENT
    # --------------------------------------------------------

    document = get_object_or_404(
        TaskDocument,
        id=document_id,
        task=task
    )

    # --------------------------------------------------------
    # ONLY ALLOW POST
    # --------------------------------------------------------

    if request.method == "POST":

        document.delete()

        messages.success(
            request,
            "Document deleted successfully."
        )

    return redirect(
        "edit_task",
        task_id=task.id
    )

# ============================================================
# MY TASKS — CUSTOMER
# ============================================================

@login_required
def my_tasks(request):

    tasks = Task.objects.filter(
        customer=request.user
    ).order_by("-created_at")

    return render(
        request,
        "tasks/my_tasks.html",
        {
            "tasks": tasks,
        }
    )


# ============================================================
# STAFF DASHBOARD
# ============================================================

@login_required
def staff_dashboard(request):

    if not request.user.is_staff:

        messages.error(
            request,
            "You do not have permission to access the staff dashboard."
        )

        return redirect("home")

    tasks = Task.objects.filter(
        assigned_staff=request.user
    ).order_by("-created_at")

    in_progress_count = tasks.filter(
        status="in_progress"
    ).count()

    completed_count = tasks.filter(
        status__in=[
            "completed",
            "delivered",
        ]
    ).count()

    pending_count = tasks.filter(
        status__in=[
            "assigned",
            "in_progress",
            "reviewing",
        ]
    ).count()

    return render(
        request,
        "tasks/staff_dashboard.html",
        {
            "tasks": tasks,
            "in_progress_count": in_progress_count,
            "completed_count": completed_count,
            "pending_count": pending_count,
        }
    )


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@login_required
def admin_dashboard(request):

    # --------------------------------------------------------
    # ONLY ADMIN / SUPERUSER
    # --------------------------------------------------------

    if not request.user.is_superuser:

        messages.error(
            request,
            "Only an administrator can access the admin dashboard."
        )

        return redirect("home")

    # --------------------------------------------------------
    # ALL TASKS
    # --------------------------------------------------------

    tasks = (
        Task.objects
        .select_related(
            "customer",
            "assigned_staff",
        )
        .prefetch_related(
            "deliverables",
            "documents",
        )
        .order_by("-created_at")
    )

    # --------------------------------------------------------
    # STAFF AVAILABLE FOR ASSIGNMENT
    # --------------------------------------------------------

    staff_members = (
        CustomUser.objects
        .filter(
            is_staff=True,
            is_active=True,
        )
        .order_by("full_name")
    )

    # --------------------------------------------------------
    # STATUS COUNTS
    # --------------------------------------------------------

    total_count = tasks.count()

    submitted_count = tasks.filter(
        status="submitted"
    ).count()

    assigned_count = tasks.filter(
        status="assigned"
    ).count()

    in_progress_count = tasks.filter(
        status="in_progress"
    ).count()

    reviewing_count = tasks.filter(
        status="reviewing"
    ).count()

    delivered_count = tasks.filter(
        status="delivered"
    ).count()

    completed_count = tasks.filter(
        status="completed"
    ).count()

    cancelled_count = tasks.filter(
        status="cancelled"
    ).count()

    # --------------------------------------------------------
    # UNASSIGNED
    # --------------------------------------------------------

    unassigned_count = tasks.filter(
        assigned_staff__isnull=True
    ).count()

    # --------------------------------------------------------
    # PAYMENT COUNTS
    # --------------------------------------------------------

    unpaid_count = tasks.filter(
        payment_status__in=[
            "pending",
            "requested",
        ]
    ).count()

    paid_count = tasks.filter(
        payment_status="paid"
    ).count()

    failed_payment_count = tasks.filter(
        payment_status="failed"
    ).count()

    refunded_count = tasks.filter(
        payment_status="refunded"
    ).count()

    # --------------------------------------------------------
    # CONTEXT
    # --------------------------------------------------------

    context = {

        "tasks": tasks,

        "staff_members": staff_members,

        "total_count": total_count,

        "submitted_count": submitted_count,

        "assigned_count": assigned_count,

        "in_progress_count": in_progress_count,

        "reviewing_count": reviewing_count,

        "delivered_count": delivered_count,

        "completed_count": completed_count,

        "cancelled_count": cancelled_count,

        "unassigned_count": unassigned_count,

        "unpaid_count": unpaid_count,

        "paid_count": paid_count,

        "failed_payment_count": failed_payment_count,

        "refunded_count": refunded_count,
    }

    return render(
        request,
        "tasks/admin_dashboard.html",
        context
    )


# ============================================================
# ASSIGN TASK — ADMIN
# ============================================================

@login_required
def assign_task(request, task_id):

    # Only superusers/admins can assign tasks
    if not request.user.is_superuser:

        messages.error(
            request,
            "Only an administrator can assign tasks."
        )

        return redirect(
            "task_detail",
            task_id=task_id
        )

    task = get_object_or_404(
        Task,
        id=task_id
    )

    if request.method == "POST":

        staff_id = request.POST.get(
            "assigned_staff"
        )

        if not staff_id:

            messages.error(
                request,
                "Please select a staff member."
            )

            return redirect(
                "task_detail",
                task_id=task.id
            )

        staff = get_object_or_404(
            CustomUser,
            id=staff_id,
            is_staff=True
        )

        # ------------------------------------------------
        # ASSIGN STAFF
        # ------------------------------------------------

        task.assigned_staff = staff

        # ------------------------------------------------
        # IMPORTANT
        # Assignment changes status to ASSIGNED
        # ------------------------------------------------

        task.status = "assigned"

        task.save()
        notify_task_parties(
            task=task,

            title="Task assigned",

            message=(
                f"Task #{task.id} — {task.title} "
                f"has been assigned to "
                f"{staff.full_name}."
            ),

            notification_type="info",

            include_customer=True,
            include_staff=True,
            include_admin=True,
        )

        messages.success(
            request,
            f"Task assigned to {staff.full_name}."
        )

        return redirect(
            "task_detail",
            task_id=task.id
        )

    return redirect(
        "task_detail",
        task_id=task.id
    )


# ============================================================
# STAFF — START TASK
# ============================================================

@login_required
def start_task(request, task_id):

    task = get_object_or_404(
        Task,
        id=task_id
    )

    # Only staff can start work
    if not request.user.is_staff:

        messages.error(
            request,
            "Only staff members can start tasks."
        )

        return redirect(
            "task_detail",
            task_id=task.id
        )

    # Only the assigned staff member can start
    if task.assigned_staff != request.user:

        messages.error(
            request,
            "This task is not assigned to you."
        )

        return redirect(
            "task_detail",
            task_id=task.id
        )

    # ------------------------------------------------
    # A task that is already assigned OR is still
    # marked submitted can be started if staff has
    # already been assigned.
    #
    # This handles existing tasks where the staff
    # member was assigned but the status remained
    # "submitted".
    # ------------------------------------------------

    if task.status not in ["submitted", "assigned"]:

        messages.error(
            request,
            "This task cannot be started at its current stage."
        )

        return redirect(
            "task_detail",
            task_id=task.id
        )

    if request.method != "POST":

        messages.error(
            request,
            "Invalid request."
        )

        return redirect(
            "task_detail",
            task_id=task.id
        )

    # ------------------------------------------------
    # START WORK
    # ------------------------------------------------

    task.status = "in_progress"

    task.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    notify_task_parties(
        task=task,

        title="Task started",

        message=(
            f"Task #{task.id} — {task.title} "
            "has been started by the assigned staff member."
        ),

        notification_type="info",

        include_customer=True,
        include_staff=False,
        include_admin=True,
    )

    messages.success(
        request,
        "Task started. You can now begin working on it."
    )

    return redirect(
        "task_detail",
        task_id=task.id
    )

# ============================================================
# CLOUDINARY DOWNLOAD HELPERS
# ============================================================

def _get_file_filename(file_field, default_name="download"):
    """
    Safely determine a filename from a Cloudinary file.
    """

    if not file_field:
        return default_name

    # --------------------------------------------------------
    # Try original filename
    # --------------------------------------------------------

    for attribute in [
        "filename",
        "original_filename",
        "name",
    ]:

        value = getattr(
            file_field,
            attribute,
            None
        )

        if value:

            value = str(value)

            if value:

                return Path(
                    value
                ).name

    # --------------------------------------------------------
    # Try Cloudinary public_id
    # --------------------------------------------------------

    public_id = getattr(
        file_field,
        "public_id",
        None
    )

    file_format = getattr(
        file_field,
        "format",
        None
    )

    if public_id:

        name = str(
            public_id
        ).split("/")[-1]

        if file_format:

            file_format = str(
                file_format
            ).lower()

            if not name.lower().endswith(
                "." + file_format
            ):

                name = (
                    f"{name}."
                    f"{file_format}"
                )

        return name

    # --------------------------------------------------------
    # Final fallback
    # --------------------------------------------------------

    try:

        value = str(
            file_field
        )

        if value:

            value = value.split("/")[-1]

            return value

    except Exception:

        pass

    return default_name


import cloudinary

# ============================================================
# DOWNLOAD CLOUDINARY FILE
# ============================================================

def _download_cloudinary_file(
    request,
    file_field,
    filename,
):
    """
    Download a Cloudinary file through Django.

    Handles Cloudinary raw resources by generating a signed
    authenticated URL rather than relying on the public URL.
    """

    if not file_field:
        raise Http404(
            "The requested file does not exist."
        )

    try:
        public_id = getattr(
            file_field,
            "public_id",
            None,
        )

        resource_type = getattr(
            file_field,
            "resource_type",
            "raw",
        )

        delivery_type = getattr(
            file_field,
            "type",
            "upload",
        )

        if not public_id:
            raise Http404(
                "The stored file does not have a valid Cloudinary ID."
            )

    except Exception as exc:

        raise Http404(
            "Unable to access the stored file."
        ) from exc

    # --------------------------------------------------------
    # GENERATE AUTHENTICATED CLOUDINARY URL
    # --------------------------------------------------------

    try:

        import cloudinary.utils

        file_url, options = cloudinary.utils.cloudinary_url(
            public_id,
            resource_type=resource_type,
            type=delivery_type,
            secure=True,
            sign_url=True,
        )

    except Exception as exc:

        raise Http404(
            "Unable to generate the file download URL."
        ) from exc

    if not file_url:

        raise Http404(
            "Unable to generate the file download URL."
        )

    # --------------------------------------------------------
    # DOWNLOAD FROM CLOUDINARY
    # --------------------------------------------------------

    try:

        cloudinary_response = requests.get(
            file_url,
            timeout=60,
            allow_redirects=True,
        )

    except requests.RequestException as exc:

        raise Http404(
            "Unable to retrieve the file from storage."
        ) from exc

    # --------------------------------------------------------
    # CHECK RESPONSE
    # --------------------------------------------------------

    if cloudinary_response.status_code != 200:

        raise Http404(
            "The file could not be retrieved from storage."
        )

    # --------------------------------------------------------
    # CONTENT TYPE
    # --------------------------------------------------------

    content_type = (
        cloudinary_response.headers.get(
            "Content-Type"
        )
        or mimetypes.guess_type(
            filename
        )[0]
        or "application/octet-stream"
    )

    # --------------------------------------------------------
    # RESPONSE
    # --------------------------------------------------------

    response = HttpResponse(
        cloudinary_response.content,
        content_type=content_type,
    )

    # --------------------------------------------------------
    # FORCE DOWNLOAD
    # --------------------------------------------------------

    response[
        "Content-Disposition"
    ] = (
        f'attachment; filename="{filename}"'
    )

    # --------------------------------------------------------
    # CACHE / SECURITY
    # --------------------------------------------------------

    response[
        "Cache-Control"
    ] = (
        "private, no-store, max-age=0"
    )

    return response

# ============================================================
# DOWNLOAD TASK DOCUMENT
# ============================================================

@login_required
def download_task_document(request, document_id):

    document = get_object_or_404(
        TaskDocument,
        pk=document_id
    )

    task = document.task

    # --------------------------------------------------------
    # ACCESS CONTROL
    # --------------------------------------------------------

    if not (
        request.user.is_superuser
        or request.user.is_staff
        or task.customer == request.user
        or task.assigned_staff == request.user
    ):
        raise Http404(
            "You do not have permission to access this file."
        )

    # --------------------------------------------------------
    # CHECK FILE
    # --------------------------------------------------------

    if not document.file:
        raise Http404(
            "This document has no file."
        )

    # --------------------------------------------------------
    # GET CLOUDINARY URL
    # --------------------------------------------------------

    try:
        file_url = document.file.url
    except Exception as exc:
        raise Http404(
            "Unable to obtain the Cloudinary file URL."
        ) from exc

    if not file_url:
        raise Http404(
            "Cloudinary did not provide a file URL."
        )

    # --------------------------------------------------------
    # DOWNLOAD FROM CLOUDINARY
    # --------------------------------------------------------

    try:

        cloudinary_response = requests.get(
            file_url,
            timeout=60,
            allow_redirects=True
        )

    except requests.RequestException as exc:

        raise Http404(
            "Unable to retrieve the file from Cloudinary."
        ) from exc

    # --------------------------------------------------------
    # CHECK CLOUDINARY RESPONSE
    # --------------------------------------------------------

    if cloudinary_response.status_code != 200:

        raise Http404(
            f"Cloudinary returned HTTP "
            f"{cloudinary_response.status_code}."
        )

    # --------------------------------------------------------
    # DETERMINE FILENAME
    # --------------------------------------------------------

    filename = _get_file_filename(
        document.file,
        default_name=f"task_{task.id}_document"
    )

    # Make sure PDF extension is retained
    if (
        not Path(filename).suffix
        and cloudinary_response.headers.get("Content-Type")
    ):

        content_type = (
            cloudinary_response
            .headers
            .get("Content-Type")
            .split(";")[0]
            .strip()
        )

        extension = mimetypes.guess_extension(
            content_type
        )

        if extension:
            filename += extension

    # --------------------------------------------------------
    # RESPONSE
    # --------------------------------------------------------

    response = HttpResponse(
        cloudinary_response.content,
        content_type=(
            cloudinary_response
            .headers
            .get(
                "Content-Type",
                "application/octet-stream"
            )
        )
    )

    response["Content-Disposition"] = (
        f'attachment; filename="{filename}"'
    )

    response["Cache-Control"] = (
        "private, no-store, max-age=0"
    )

    return response


# ============================================================
# DOWNLOAD DELIVERABLE
# ============================================================

@login_required
def download_deliverable(request, deliverable_id):

    deliverable = get_object_or_404(
        TaskDeliverable,
        pk=deliverable_id
    )

    task = deliverable.task

    # --------------------------------------------------------
    # ACCESS CONTROL
    # --------------------------------------------------------

    if not (
        request.user.is_superuser
        or request.user.is_staff
        or task.customer == request.user
        or task.assigned_staff == request.user
    ):
        raise Http404(
            "You do not have permission to access this file."
        )

    # --------------------------------------------------------
    # CHECK FILE
    # --------------------------------------------------------

    if not deliverable.file:
        raise Http404(
            "This deliverable has no file."
        )

    # --------------------------------------------------------
    # CUSTOMER CANNOT DOWNLOAD UNAPPROVED DELIVERABLE
    # --------------------------------------------------------

    if (
        task.customer == request.user
        and not deliverable.approved
    ):
        raise Http404(
            "This deliverable has not been released."
        )

    # --------------------------------------------------------
    # CLOUDINARY URL
    # --------------------------------------------------------

    try:
        file_url = deliverable.file.url
    except Exception as exc:
        raise Http404(
            "Unable to obtain the Cloudinary file URL."
        ) from exc

    if not file_url:
        raise Http404(
            "Cloudinary did not provide a file URL."
        )

    # --------------------------------------------------------
    # DOWNLOAD FROM CLOUDINARY
    # --------------------------------------------------------

    try:

        cloudinary_response = requests.get(
            file_url,
            timeout=60,
            allow_redirects=True
        )

    except requests.RequestException as exc:

        raise Http404(
            "Unable to retrieve the file from Cloudinary."
        ) from exc

    if cloudinary_response.status_code != 200:

        raise Http404(
            f"Cloudinary returned HTTP "
            f"{cloudinary_response.status_code}."
        )

    # --------------------------------------------------------
    # FILENAME
    # --------------------------------------------------------

    filename = _get_file_filename(
        deliverable.file,
        default_name=f"task_{task.id}_deliverable"
    )

    if (
        not Path(filename).suffix
        and cloudinary_response.headers.get("Content-Type")
    ):

        content_type = (
            cloudinary_response
            .headers
            .get("Content-Type")
            .split(";")[0]
            .strip()
        )

        extension = mimetypes.guess_extension(
            content_type
        )

        if extension:
            filename += extension

    # --------------------------------------------------------
    # RESPONSE
    # --------------------------------------------------------

    response = HttpResponse(
        cloudinary_response.content,
        content_type=(
            cloudinary_response
            .headers
            .get(
                "Content-Type",
                "application/octet-stream"
            )
        )
    )

    response["Content-Disposition"] = (
        f'attachment; filename="{filename}"'
    )

    response["Cache-Control"] = (
        "private, no-store, max-age=0"
    )

    return response

    # ========================================================
    # CUSTOMER SECURITY
    # ========================================================

    if (
        is_customer
        and not deliverable.approved
    ):

        messages.error(
            request,
            "This deliverable has not yet been released."
        )

        return redirect(
            "task_detail",
            task_id=task.id
        )

    # ========================================================
    # GET CLOUDINARY URL
    # ========================================================

    try:

        file_url = deliverable.file.url

    except Exception:

        file_url = None

    if not file_url:

        messages.error(
            request,
            "The stored file could not be found."
        )

        return redirect(
            "task_detail",
            task_id=task.id
        )

    # ========================================================
    # REDIRECT DIRECTLY TO CLOUDINARY
    # ========================================================

    return redirect(file_url)
@login_required
def task_detail(request, task_id):

    task = get_object_or_404(
        Task.objects.select_related(
            "customer",
            "assigned_staff",
        ),
        id=task_id
    )

    # ========================================================
    # ACCESS CONTROL
    # ========================================================

    is_customer = (
        task.customer == request.user
    )

    is_assigned_staff = (
        task.assigned_staff == request.user
    )

    is_admin = (
        request.user.is_superuser
    )

    is_staff = (
        request.user.is_staff
    )

    if not (
        is_customer
        or is_assigned_staff
        or is_staff
        or is_admin
    ):

        messages.error(
            request,
            "You do not have permission to view this task."
        )

        return redirect(
            "home"
        )

    # ========================================================
    # CUSTOMER DOCUMENTS
    # ========================================================

    documents = (
        task.documents
        .select_related(
            "uploaded_by"
        )
        .order_by(
            "-uploaded_at"
        )
    )

    # ========================================================
    # STAFF DELIVERABLES
    # ========================================================

    deliverables = (
        task.deliverables
        .select_related(
            "submitted_by",
            "approved_by",
        )
        .order_by(
            "-submitted_at"
        )
    )

    # ========================================================
    # ADD DISPLAY FILENAMES
    # ========================================================

    for document in documents:

        document.download_filename = (
            _get_file_filename(
                document.file,
                default_name=(
                    f"task_{task.id}_document"
                )
            )
        )

    for deliverable in deliverables:

        deliverable.download_filename = (
            _get_file_filename(
                deliverable.file,
                default_name=(
                    f"task_{task.id}_deliverable"
                )
            )
        )

    # ========================================================
    # CONTEXT
    # ========================================================

    context = {

        "task": task,

        "documents": documents,

        "deliverables": deliverables,

        "is_customer": is_customer,

        "is_assigned_staff": is_assigned_staff,

        "is_staff": is_staff,

        "is_admin": is_admin,

    }

    return render(
        request,
        "tasks/task_detail.html",
        context
    )


# ============================================================
# ADDITIONAL CUSTOMER DOCUMENT
# ============================================================

@login_required
def add_task_document(request, task_id):

    task = get_object_or_404(
        Task,
        id=task_id
    )

    # Only customer can add documents
    if task.customer != request.user:

        messages.error(
            request,
            "You do not have permission to add documents to this task."
        )

        return redirect(
            "task_detail",
            task_id=task.id
        )

    if request.method == "POST":

        form = TaskDocumentForm(
            request.POST,
            request.FILES
        )

        if form.is_valid():

            document = form.save(
                commit=False
            )

            document.task = task
            document.uploaded_by = request.user

            document.save()

            messages.success(
                request,
                "Your additional document has been uploaded successfully."
            )

            return redirect(
                "task_detail",
                task_id=task.id
            )

    else:

        form = TaskDocumentForm()

    return render(
        request,
        "tasks/add_document.html",
        {
            "task": task,
            "form": form,
        }
    )


# ============================================================
# STAFF — ADD DELIVERABLE
# ============================================================

@login_required
def add_deliverable(request, task_id):

    task = get_object_or_404(
        Task,
        id=task_id
    )

    # ------------------------------------------------
    # Only staff can submit
    # ------------------------------------------------

    if not request.user.is_staff:

        messages.error(
            request,
            "You do not have permission to submit deliverables."
        )

        return redirect(
            "task_detail",
            task_id=task.id
        )

    # ------------------------------------------------
    # Only assigned staff can submit
    # ------------------------------------------------

    if task.assigned_staff != request.user:

        messages.error(
            request,
            "This task is not assigned to you."
        )

        return redirect(
            "task_detail",
            task_id=task.id
        )

    # ------------------------------------------------
    # Staff must START task first
    # ------------------------------------------------

    if task.status != "in_progress":


        messages.error(
            request,
            "You can only submit a deliverable after starting the task."
        )

        return redirect(
            "task_detail",
            task_id=task.id
        )

    # ------------------------------------------------
    # Submit deliverable
    # ------------------------------------------------

    if request.method == "POST":

        # Get ALL uploaded files
        files = request.FILES.getlist(
            "files"
        )

        comment = request.POST.get(
            "comment",
            ""
        ).strip()

        # ------------------------------------------------
        # Require at least one file OR a comment
        # ------------------------------------------------

        if not files and not comment:

            messages.error(
                request,
                "Please provide at least one file or a comment."
            )

            return redirect(
                "add_deliverable",
                task_id=task.id
            )

        # ------------------------------------------------
        # Create a deliverable record for each file
        # ------------------------------------------------

        if files:

            for file in files:

                TaskDeliverable.objects.create(

                    task=task,

                    file=file,

                    comment=comment,

                    submitted_by=request.user
                )

        else:

            # ------------------------------------------------
            # Allow comment-only submission
            # ------------------------------------------------

            TaskDeliverable.objects.create(

                task=task,

                file=None,

                comment=comment,

                submitted_by=request.user
            )

        # ------------------------------------------------
        # Send to ADMIN REVIEW
        # ------------------------------------------------

        task.status = "reviewing"

        notify_task_parties(
            task=task,
            title="Deliverable submitted for review",
            message=(
                f"Task #{task.id} — {task.title} has a new deliverable "
                "submitted by the assigned staff member and is waiting "
                "for administrator review."
            ),
            notification_type="warning",
            include_customer=True,
            include_staff=False,
            include_admin=True,
        )

        task.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        notify_task_parties(
            task=task,
            title="Deliverable submitted for review",
            message=(
                f"Task #{task.id} — {task.title} has a deliverable "
                "submitted by the assigned staff member and is now "
                "awaiting administrator review."
            ),
            notification_type="info",
            include_customer=True,
            include_staff=False,
            include_admin=True,
        )

        messages.success(
            request,
            "Deliverable submitted successfully and sent for admin review."
        )

        return redirect(
            "task_detail",
            task_id=task.id
        )

    # ------------------------------------------------
    # Display form
    # ------------------------------------------------

    return render(
        request,
        "tasks/add_deliverable.html",
        {
            "task": task,
        }
    )


# ============================================================
# ADMIN — APPROVE DELIVERABLE
# ============================================================

@login_required
def approve_deliverable(
    request,
    task_id,
    deliverable_id
):

    # Only superusers can approve
    if not request.user.is_superuser:

        messages.error(
            request,
            "Only an administrator can approve deliverables."
        )

        return redirect(
            "task_detail",
            task_id=task_id
        )

    task = get_object_or_404(
        Task,
        id=task_id
    )

    deliverable = get_object_or_404(
        TaskDeliverable,
        id=deliverable_id,
        task=task
    )

    if request.method == "POST":

        deliverable.approved = True

        deliverable.approved_by = request.user

        deliverable.approved_at = timezone.now()

        deliverable.save(
            update_fields=[
                "approved",
                "approved_by",
                "approved_at",
            ]
        )

        # ------------------------------------------------
        # Release to client
        # ------------------------------------------------

        task.status = "delivered"

        task.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        notify_task_parties(
            task=task,
            title="Task delivered",
            message=(
                f"Task #{task.id} — {task.title} has been approved "
                "and delivered to the customer."
            ),
            notification_type="success",
            include_customer=True,
            include_staff=True,
            include_admin=False,
        )

        messages.success(
            request,
            "Deliverable approved and released to the client."
        )

    return redirect(
        "task_detail",
        task_id=task.id
    )


# ============================================================
# CUSTOMER — CONFIRM COMPLETION
# ============================================================

@login_required
def confirm_task_completion(request, task_id):

    task = get_object_or_404(
        Task,
        id=task_id,
        customer=request.user
    )

    # Customer can only confirm DELIVERED task
    if task.status != "delivered":

        messages.error(
            request,
            "This task is not ready for completion confirmation."
        )

        return redirect(
            "task_detail",
            task_id=task.id
        )

    if request.method == "POST":

        task.status = "completed"

        task.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        notify_task_parties(
            task=task,
            title="Task completed",
            message=(
                f"Task #{task.id} — {task.title} has been confirmed "
                "as completed by the customer."
            ),
            notification_type="success",
            include_customer=False,
            include_staff=True,
            include_admin=True,
        )

        messages.success(
            request,
            "Thank you. The task has been marked as completed."
        )

    return redirect(
        "task_detail",
        task_id=task.id
    )


# ============================================================
# ADMIN — ACCEPT CUSTOMER BUDGET
# ============================================================

@login_required
def accept_customer_budget(request, task_id):

    # --------------------------------------------------------
    # ADMIN ONLY
    # --------------------------------------------------------

    if not request.user.is_superuser:

        messages.error(
            request,
            "Only an administrator can accept the customer budget."
        )

        return redirect(
            "task_detail",
            task_id=task_id
        )

    task = get_object_or_404(
        Task,
        id=task_id
    )

    if request.method != "POST":

        return redirect(
            "task_detail",
            task_id=task.id
        )

    # --------------------------------------------------------
    # CUSTOMER MUST HAVE PROVIDED A BUDGET
    # --------------------------------------------------------

    if not task.budget:

        messages.error(
            request,
            "This task does not have a customer budget."
        )

        return redirect(
            "task_detail",
            task_id=task.id
        )

    # --------------------------------------------------------
    # ACCEPT CUSTOMER BUDGET
    # --------------------------------------------------------

    task.quoted_amount = task.budget

    task.quoted_amount_accepted = False

    task.payment_status = "requested"

    task.save(
        update_fields=[
            "quoted_amount",
            "quoted_amount_accepted",
            "payment_status",
            "updated_at",
        ]
    )

    # --------------------------------------------------------
    # NOTIFY CUSTOMER
    # --------------------------------------------------------

    notify_task_parties(
        task=task,
        title="Task amount accepted",
        message=(
            f"The customer budget for task #{task.id} — {task.title} "
            f"has been accepted at KES {task.quoted_amount:,.2f}. "
            "The customer can now proceed to payment."
        ),
        notification_type="success",
        include_customer=True,
        include_staff=False,
        include_admin=False,
    )

    messages.success(
        request,
        "Customer amount accepted and payment requested."
    )

    return redirect(
        "task_detail",
        task_id=task.id
    )


# ============================================================
# ADMIN — PROPOSE NEW AMOUNT
# ============================================================

@login_required
def propose_amount(request, task_id):

    # --------------------------------------------------------
    # ADMIN ONLY
    # --------------------------------------------------------

    if not request.user.is_superuser:

        messages.error(
            request,
            "Only an administrator can propose a new amount."
        )

        return redirect(
            "task_detail",
            task_id=task_id
        )

    task = get_object_or_404(
        Task,
        id=task_id
    )

    if request.method != "POST":

        return redirect(
            "task_detail",
            task_id=task.id
        )

    # --------------------------------------------------------
    # GET PROPOSED AMOUNT
    # --------------------------------------------------------

    amount = request.POST.get(
        "quoted_amount"
    )

    # --------------------------------------------------------
    # VALIDATE AMOUNT
    # --------------------------------------------------------

    try:

        amount = Decimal(
            amount
        )

    except (
        TypeError,
        ValueError,
        InvalidOperation
    ):

        messages.error(
            request,
            "Please enter a valid amount."
        )

        return redirect(
            "task_detail",
            task_id=task.id
        )

    if amount <= 0:

        messages.error(
            request,
            "The proposed amount must be greater than zero."
        )

        return redirect(
            "task_detail",
            task_id=task.id
        )

    # --------------------------------------------------------
    # SAVE QUOTE
    # --------------------------------------------------------

    task.quoted_amount = amount

    # New quote must be accepted by customer
    task.quoted_amount_accepted = False

    task.quoted_amount_accepted_at = None

    # Payment is now being requested
    task.payment_status = "requested"

    # IMPORTANT:
    # The task has now moved from SUBMITTED to QUOTE SENT
    task.status = "quoted"

    task.save(
        update_fields=[
            "quoted_amount",
            "quoted_amount_accepted",
            "quoted_amount_accepted_at",
            "payment_status",
            "status",
            "updated_at",
        ]
    )

    # --------------------------------------------------------
    # NOTIFY CUSTOMER
    # --------------------------------------------------------

    notify_task_parties(
        task=task,
        title="New amount proposed",
        message=(
            f"A new amount of KES {task.quoted_amount:,.2f} "
            f"has been proposed for task #{task.id} — {task.title}. "
            "Please review and accept the amount before payment."
        ),
        notification_type="warning",
        include_customer=True,
        include_staff=False,
        include_admin=False,
    )

    # --------------------------------------------------------
    # SUCCESS MESSAGE
    # --------------------------------------------------------

    messages.success(
        request,
        f"New amount of KES {task.quoted_amount:,.2f} "
        "proposed and customer notified."
    )

    return redirect(
        "task_detail",
        task_id=task.id
    )

# ============================================================
# CUSTOMER — ACCEPT QUOTED AMOUNT
# ============================================================

@login_required
def accept_quoted_amount(request, task_id):

    task = get_object_or_404(
        Task,
        id=task_id,
        customer=request.user
    )

    # --------------------------------------------------------
    # ONLY POST
    # --------------------------------------------------------

    if request.method != "POST":

        return redirect(
            "task_detail",
            task_id=task.id
        )

    # --------------------------------------------------------
    # MUST HAVE QUOTED AMOUNT
    # --------------------------------------------------------

    if not task.quoted_amount:

        messages.error(
            request,
            "There is no quoted amount to accept."
        )

        return redirect(
            "task_detail",
            task_id=task.id
        )

    # --------------------------------------------------------
    # ACCEPT QUOTE
    # --------------------------------------------------------

    task.quoted_amount_accepted = True

    task.quoted_amount_accepted_at = timezone.now()

    # IMPORTANT:
    # Quote has now been accepted by customer
    task.status = "accepted"

    task.save(
        update_fields=[
            "quoted_amount_accepted",
            "quoted_amount_accepted_at",
            "status",
            "updated_at",
        ]
    )

    notify_task_parties(
        task=task,
        title="Quote accepted",
        message=(
            f"Task #{task.id} — {task.title} has been accepted "
            "by the customer. Payment is now available."
        ),
        notification_type="success",
        include_customer=False,
        include_staff=True,
        include_admin=True,
    )

    # --------------------------------------------------------
    # PAYMENT NOW AVAILABLE
    # --------------------------------------------------------

    messages.success(
        request,
        "Amount accepted. You can now proceed to payment."
    )

    return redirect(
        "payment_page",
        task_id=task.id
    )
# ============================================================
# CUSTOMER — PAYMENT PAGE
# ============================================================

@login_required
def payment_page(request, task_id):

    task = get_object_or_404(
        Task,
        id=task_id,
        customer=request.user
    )

    # --------------------------------------------------------
    # MUST HAVE A QUOTED AMOUNT
    # --------------------------------------------------------

    if not task.quoted_amount:

        messages.error(
            request,
            "There is no quoted amount available for this task."
        )

        return redirect(
            "task_detail",
            task_id=task.id
        )

    # --------------------------------------------------------
    # CUSTOMER MUST ACCEPT THE QUOTE FIRST
    # --------------------------------------------------------

    if not task.quoted_amount_accepted:

        messages.error(
            request,
            "Please accept the quoted amount before making payment."
        )

        return redirect(
            "task_detail",
            task_id=task.id
        )

    # --------------------------------------------------------
    # ALREADY PAID
    # --------------------------------------------------------

    if task.payment_status == "paid":

        messages.info(
            request,
            "This task has already been paid for."
        )

        return redirect(
            "task_detail",
            task_id=task.id
        )

    # --------------------------------------------------------
    # DISPLAY PAYMENT PAGE
    # --------------------------------------------------------

    return render(
        request,
        "tasks/payment.html",
        {
            "task": task,
        }
    )


# ============================================================
# CUSTOMER — INITIALIZE PAYSTACK PAYMENT
# ============================================================

@login_required
def initialize_payment(request, task_id):

    task = get_object_or_404(
        Task,
        id=task_id,
        customer=request.user
    )

    # --------------------------------------------------------
    # ONLY POST
    # --------------------------------------------------------

    if request.method != "POST":

        return redirect(
            "payment_page",
            task_id=task.id
        )

    # --------------------------------------------------------
    # MUST HAVE QUOTED AMOUNT
    # --------------------------------------------------------

    if not task.quoted_amount:

        messages.error(
            request,
            "This task does not have a valid quoted amount."
        )

        return redirect(
            "task_detail",
            task_id=task.id
        )

    # --------------------------------------------------------
    # MUST HAVE ACCEPTED QUOTE
    # --------------------------------------------------------

    if not task.quoted_amount_accepted:

        messages.error(
            request,
            "You must accept the quote before making payment."
        )

        return redirect(
            "task_detail",
            task_id=task.id
        )

    # --------------------------------------------------------
    # ALREADY PAID
    # --------------------------------------------------------

    if task.payment_status == "paid":

        messages.info(
            request,
            "This task has already been paid for."
        )

        return redirect(
            "task_detail",
            task_id=task.id
        )

    # --------------------------------------------------------
    # CUSTOMER EMAIL
    # --------------------------------------------------------

    customer_email = getattr(
        request.user,
        "email",
        None
    )

    if not customer_email:

        messages.error(
            request,
            "Your account does not have an email address. "
            "Please update your account before making payment."
        )

        return redirect(
            "task_detail",
            task_id=task.id
        )

    # --------------------------------------------------------
    # AMOUNT
    #
    # Paystack expects the amount in the currency subunit.
    #
    # Example:
    #
    # KES 1,500.00
    #
    # becomes:
    #
    # 150000
    # --------------------------------------------------------

    amount = int(
        (
            Decimal(str(task.quoted_amount))
            * Decimal("100")
        ).quantize(
            Decimal("1")
        )
    )

    if amount <= 0:

        messages.error(
            request,
            "The payment amount must be greater than zero."
        )

        return redirect(
            "payment_page",
            task_id=task.id
        )

    # --------------------------------------------------------
    # UNIQUE PAYMENT REFERENCE
    # --------------------------------------------------------

    reference = (
        f"WL-TASK-{task.id}-"
        f"{uuid.uuid4().hex[:16].upper()}"
    )

    # --------------------------------------------------------
    # CALLBACK URL
    #
    # Paystack will redirect the customer here after payment.
    # --------------------------------------------------------

    callback_url = request.build_absolute_uri(
        reverse(
            "payment_success",
            kwargs={
                "task_id": task.id
            }
        )
    )

    # --------------------------------------------------------
    # PAYSTACK HEADERS
    # --------------------------------------------------------

    headers = {

        "Authorization": (
            f"Bearer {settings.PAYSTACK_SECRET_KEY}"
        ),

        "Content-Type": "application/json",
    }

    # --------------------------------------------------------
    # PAYSTACK PAYMENT DATA
    # --------------------------------------------------------

    payload = {

        "email": customer_email,

        "amount": amount,

        "currency": "KES",

        "reference": reference,

        "callback_url": callback_url,

        "metadata": {

            "task_id": task.id,

            "customer_id": request.user.id,

            "task_title": task.title,
        },
    }

    # --------------------------------------------------------
    # INITIALIZE PAYMENT
    # --------------------------------------------------------

    try:

        response = requests.post(

            PAYSTACK_INITIALIZE_URL,

            json=payload,

            headers=headers,

            timeout=30,
        )

        response_data = response.json()

    except requests.RequestException:

        messages.error(

            request,

            "Unable to connect to Paystack. "
            "Please try again."
        )

        return redirect(

            "payment_page",

            task_id=task.id
        )

    except ValueError:

        messages.error(

            request,

            "Paystack returned an invalid response."
        )

        return redirect(

            "payment_page",

            task_id=task.id
        )

    # --------------------------------------------------------
    # CHECK INITIALIZATION RESPONSE
    # --------------------------------------------------------

    if not response.ok or not response_data.get("status"):

        error_message = response_data.get(

            "message",

            "Unable to initialize payment."
        )

        messages.error(

            request,

            f"Paystack payment initialization failed: "
            f"{error_message}"
        )

        return redirect(

            "payment_page",

            task_id=task.id
        )

    # --------------------------------------------------------
    # GET AUTHORIZATION URL
    # --------------------------------------------------------

    authorization_url = (
        response_data
        .get("data", {})
        .get("authorization_url")
    )

    if not authorization_url:

        messages.error(

            request,

            "Paystack did not return a payment URL."
        )

        return redirect(

            "payment_page",

            task_id=task.id
        )

    # --------------------------------------------------------
    # SAVE PAYMENT REFERENCE
    # --------------------------------------------------------

    task.payment_reference = reference

    task.payment_status = "requested"

    task.save(

        update_fields=[

            "payment_reference",

            "payment_status",

            "updated_at",
        ]
    )

    notify_task_parties(
        task=task,
        title="Payment initiated",
        message=(
            f"Payment of KES {task.quoted_amount:,.2f} for task "
            f"#{task.id} — {task.title} has been initiated."
        ),
        notification_type="info",
        include_customer=False,
        include_staff=True,
        include_admin=True,
    )

    # --------------------------------------------------------
    # SEND CUSTOMER TO PAYSTACK
    # --------------------------------------------------------

    return redirect(
        authorization_url
    )


# ============================================================
# CUSTOMER — PAYSTACK PAYMENT SUCCESS / CALLBACK
# ============================================================

@login_required
def payment_success(request, task_id):

    task = get_object_or_404(
        Task,
        id=task_id,
        customer=request.user
    )

    # --------------------------------------------------------
    # GET REFERENCE FROM PAYSTACK
    # --------------------------------------------------------

    reference = request.GET.get(
        "reference"
    )

    if not reference:

        messages.error(
            request,
            "No payment reference was returned by Paystack."
        )

        return redirect(
            "payment_page",
            task_id=task.id
        )

    # --------------------------------------------------------
    # MAKE SURE REFERENCE BELONGS TO THIS TASK
    # --------------------------------------------------------

    if (
        task.payment_reference
        and task.payment_reference != reference
    ):

        messages.error(
            request,
            "The payment reference does not match this task."
        )

        return redirect(
            "payment_page",
            task_id=task.id
        )

    # --------------------------------------------------------
    # VERIFY PAYMENT WITH PAYSTACK
    # --------------------------------------------------------

    verify_url = (
        PAYSTACK_VERIFY_URL
        + quote(
            reference,
            safe=""
        )
    )

    headers = {

        "Authorization": (
            f"Bearer {settings.PAYSTACK_SECRET_KEY}"
        ),

        "Content-Type": "application/json",
    }

    try:

        response = requests.get(

            verify_url,

            headers=headers,

            timeout=30,
        )

        response_data = response.json()

    except requests.RequestException:

        messages.error(

            request,

            "Unable to verify payment with Paystack. "
            "Please try again."
        )

        return redirect(

            "payment_page",

            task_id=task.id
        )

    except ValueError:

        messages.error(

            request,

            "Paystack returned an invalid verification response."
        )

        return redirect(

            "payment_page",

            task_id=task.id
        )

    # --------------------------------------------------------
    # VERIFY PAYSTACK RESPONSE
    # --------------------------------------------------------

    if not response.ok or not response_data.get("status"):

        messages.error(

            request,

            "Paystack could not verify this transaction."
        )

        return redirect(

            "payment_page",

            task_id=task.id
        )

    transaction = response_data.get(
        "data",
        {}
    )

    # --------------------------------------------------------
    # VERIFY TRANSACTION STATUS
    # --------------------------------------------------------

    if transaction.get("status") != "success":

        task.payment_status = "failed"

        task.save(

            update_fields=[

                "payment_status",

                "updated_at",
            ]
        )

        notify_task_parties(
            task=task,
            title="Payment failed",
            message=(
                f"Payment for task #{task.id} — {task.title} "
                "was not successful. Please review the payment status."
            ),
            notification_type="danger",
            include_customer=True,
            include_staff=True,
            include_admin=True,
        )

        messages.error(

            request,

            "The payment was not successful."
        )

        return redirect(

            "payment_page",

            task_id=task.id
        )

    # --------------------------------------------------------
    # VERIFY REFERENCE
    # --------------------------------------------------------

    returned_reference = transaction.get(
        "reference"
    )

    if returned_reference != reference:

        messages.error(

            request,

            "Payment reference verification failed."
        )

        return redirect(

            "payment_page",

            task_id=task.id
        )

    # --------------------------------------------------------
    # VERIFY CURRENCY
    # --------------------------------------------------------

    if transaction.get("currency") != "KES":

        messages.error(

            request,

            "The payment currency does not match the task currency."
        )

        return redirect(

            "payment_page",

            task_id=task.id
        )

    # --------------------------------------------------------
    # VERIFY AMOUNT
    # --------------------------------------------------------

    expected_amount = int(

        (
            Decimal(str(task.quoted_amount))
            * Decimal("100")
        ).quantize(
            Decimal("1")
        )
    )

    paid_amount = int(

        transaction.get(
            "amount",
            0
        )
    )

    if paid_amount != expected_amount:

        messages.error(

            request,

            "The payment amount does not match the "
            "quoted task amount."
        )

        return redirect(

            "payment_page",

            task_id=task.id
        )

    # --------------------------------------------------------
    # ALREADY PAID
    # --------------------------------------------------------

    if task.payment_status == "paid":

        messages.info(

            request,

            "This payment has already been recorded."
        )

        return redirect(

            "task_detail",

            task_id=task.id
        )

    # --------------------------------------------------------
    # MARK TASK AS PAID
    # --------------------------------------------------------

    task.payment_status = "paid"

    task.payment_reference = returned_reference

    task.paid_at = timezone.now()

    # --------------------------------------------------------
    # MOVE TASK TO PAID STAGE
    # --------------------------------------------------------

    if task.status in [
        "accepted",
        "quoted",
    ]:

        task.status = "paid"

        task.save(

            update_fields=[

                "payment_status",

                "payment_reference",

                "paid_at",

                "status",

                "updated_at",
            ]
        )

    else:

        task.save(

            update_fields=[

                "payment_status",

                "payment_reference",

                "paid_at",

                "updated_at",
            ]
        )

    # --------------------------------------------------------
    # NOTIFY CUSTOMER
    # --------------------------------------------------------

    notify_task_parties(
        task=task,
        title="Payment successful",
        message=(
            f"Payment of KES {task.quoted_amount:,.2f} for task "
            f"#{task.id} — {task.title} was received successfully. "
            "The task is now marked as paid."
        ),
        notification_type="success",
        include_customer=True,
        include_staff=True,
        include_admin=True,
    )

    # --------------------------------------------------------
    # SUCCESS
    # --------------------------------------------------------

    messages.success(

        request,

        "Payment successful! "
        "Your task has been marked as paid."
    )

    return redirect(

        "task_detail",

        task_id=task.id
    )


# ============================================================
# PAYSTACK WEBHOOK
# ============================================================
#
# Paystack calls this endpoint directly.
#
# The customer does NOT need to be logged in.
#
# The signature is verified using the Paystack secret key.
# ============================================================

@csrf_exempt
def paystack_webhook(request):

    # --------------------------------------------------------
    # ONLY POST
    # --------------------------------------------------------

    if request.method != "POST":

        return JsonResponse(

            {
                "status": False,
                "message": "Method not allowed."
            },

            status=405
        )

    # --------------------------------------------------------
    # GET RAW BODY
    # --------------------------------------------------------

    payload = request.body

    # --------------------------------------------------------
    # GET PAYSTACK SIGNATURE
    # --------------------------------------------------------

    signature = request.headers.get(
        "x-paystack-signature"
    )

    if not signature:

        return JsonResponse(

            {
                "status": False,
                "message": "Missing signature."
            },

            status=400
        )

    # --------------------------------------------------------
    # CALCULATE EXPECTED SIGNATURE
    # --------------------------------------------------------

    expected_signature = hmac.new(

        settings.PAYSTACK_SECRET_KEY.encode(
            "utf-8"
        ),

        payload,

        hashlib.sha512
    ).hexdigest()

    # --------------------------------------------------------
    # VERIFY SIGNATURE
    # --------------------------------------------------------

    if not hmac.compare_digest(

        signature,

        expected_signature
    ):

        return JsonResponse(

            {
                "status": False,
                "message": "Invalid signature."
            },

            status=401
        )

    # --------------------------------------------------------
    # PARSE JSON
    # --------------------------------------------------------

    try:

        event = json.loads(

            payload.decode(
                "utf-8"
            )
        )

    except (
        ValueError,
        UnicodeDecodeError
    ):

        return JsonResponse(

            {
                "status": False,
                "message": "Invalid JSON."
            },

            status=400
        )

    # --------------------------------------------------------
    # ONLY PROCESS SUCCESSFUL CHARGES
    # --------------------------------------------------------

    if event.get("event") != "charge.success":

        return JsonResponse(

            {
                "status": True,
                "message": "Event received."
            },

            status=200
        )

    transaction = event.get(
        "data",
        {}
    )

    # --------------------------------------------------------
    # GET REFERENCE
    # --------------------------------------------------------

    reference = transaction.get(
        "reference"
    )

    if not reference:

        return JsonResponse(

            {
                "status": True,
                "message": "No transaction reference."
            },

            status=200
        )

    # --------------------------------------------------------
    # FIND TASK
    # --------------------------------------------------------

    task = (

        Task.objects

        .select_related(
            "customer"
        )

        .filter(
            payment_reference=reference
        )

        .first()
    )

    if not task:

        return JsonResponse(

            {
                "status": True,
                "message": (
                    "Transaction not associated with a task."
                )
            },

            status=200
        )

    # --------------------------------------------------------
    # VERIFY STATUS
    # --------------------------------------------------------

    if transaction.get("status") != "success":

        return JsonResponse(

            {
                "status": True,
                "message": (
                    "Transaction was not successful."
                )
            },

            status=200
        )

    # --------------------------------------------------------
    # VERIFY CURRENCY
    # --------------------------------------------------------

    if transaction.get("currency") != "KES":

        return JsonResponse(

            {
                "status": True,
                "message": "Currency mismatch."
            },

            status=200
        )

    # --------------------------------------------------------
    # VERIFY AMOUNT
    # --------------------------------------------------------

    expected_amount = int(

        (
            Decimal(str(task.quoted_amount))
            * Decimal("100")
        ).quantize(
            Decimal("1")
        )
    )

    webhook_amount = int(

        transaction.get(
            "amount",
            0
        )
    )

    if webhook_amount != expected_amount:

        return JsonResponse(

            {
                "status": True,
                "message": "Amount mismatch."
            },

            status=200
        )

    # --------------------------------------------------------
    # ALREADY PAID
    # --------------------------------------------------------

    if task.payment_status == "paid":

        return JsonResponse(

            {
                "status": True,
                "message": "Payment already processed."
            },

            status=200
        )

    # --------------------------------------------------------
    # MARK TASK AS PAID
    # --------------------------------------------------------

    task.payment_status = "paid"

    task.payment_reference = reference

    task.paid_at = timezone.now()

    if task.status in [
        "accepted",
        "quoted",
    ]:

        task.status = "paid"

        task.save(

            update_fields=[

                "payment_status",

                "payment_reference",

                "paid_at",

                "status",

                "updated_at",
            ]
        )

    else:

        task.save(

            update_fields=[

                "payment_status",

                "payment_reference",

                "paid_at",

                "updated_at",
            ]
        )

    # --------------------------------------------------------
    # NOTIFY CUSTOMER
    # --------------------------------------------------------

    notify_task_parties(
        task=task,
        title="Payment successful",
        message=(
            f"Payment of KES {task.quoted_amount:,.2f} for task "
            f"#{task.id} — {task.title} was received successfully. "
            "The task is now marked as paid."
        ),
        notification_type="success",
        include_customer=True,
        include_staff=True,
        include_admin=True,
    )

    return JsonResponse(

        {
            "status": True,
            "message": "Payment processed successfully."
        },

        status=200
    )



@login_required
def notifications_api(request):

    notifications = (
        Notification.objects
        .filter(
            user=request.user
        )
        .select_related("task")
        .order_by("-created_at")[:30]
    )

    unread_count = (
        Notification.objects
        .filter(
            user=request.user,
            is_read=False
        )
        .count()
    )

    data = []

    for notification in notifications:

        data.append({

            "id": notification.id,

            "title": notification.title,

            "message": notification.message,

            "type": notification.notification_type,

            "is_read": notification.is_read,

            "created_at": (
                notification.created_at
                .strftime("%d %b %Y, %H:%M")
            ),

            "task_id": (
                notification.task.id
                if notification.task
                else None
            ),
        })

    return JsonResponse({

        "success": True,

        "unread_count": unread_count,

        "notifications": data,
    })


@login_required
def mark_notification_read(
    request,
    notification_id
):

    notification = get_object_or_404(
        Notification,
        id=notification_id,
        user=request.user
    )

    notification.is_read = True

    notification.save(
        update_fields=[
            "is_read"
        ]
    )

    return JsonResponse({
        "success": True
    })

@login_required
def mark_all_notifications_read(request):

    Notification.objects.filter(
        user=request.user,
        is_read=False
    ).update(
        is_read=True
    )

    return JsonResponse({
        "success": True
    })
