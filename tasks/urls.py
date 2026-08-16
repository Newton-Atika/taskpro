from django.urls import path

from . import views


urlpatterns = [

    # ============================================================
    # CUSTOMER
    # ============================================================

    path(
        "submit/",
        views.submit_task,
        name="submit_task"
    ),

    path(
        "my-tasks/",
        views.my_tasks,
        name="my_tasks"
    ),


    # ============================================================
    # STAFF
    # ============================================================

    path(
        "staff/",
        views.staff_dashboard,
        name="staff_dashboard"
    ),

    path(
        "<int:task_id>/start/",
        views.start_task,
        name="start_task"
    ),

    path(
        "<int:task_id>/deliverable/add/",
        views.add_deliverable,
        name="add_deliverable"
    ),


    # ============================================================
    # DOCUMENTS
    # ============================================================

    path(
        "<int:task_id>/document/add/",
        views.add_task_document,
        name="add_task_document"
    ),


    # ============================================================
    # DOCUMENT DOWNLOAD
    # ============================================================

    path(
        "documents/<int:document_id>/download/",
        views.download_task_document,
        name="download_task_document"
    ),


    # ============================================================
    # DELIVERABLE DOWNLOAD
    # ============================================================

    path(
        "deliverables/<int:deliverable_id>/download/",
        views.download_deliverable,
        name="download_deliverable"
    ),


    # ============================================================
    # ADMIN
    # ============================================================

    path(
        "admin-dashboard/",
        views.admin_dashboard,
        name="admin_dashboard"
    ),

    path(
        "<int:task_id>/assign/",
        views.assign_task,
        name="assign_task"
    ),

    path(
        "<int:task_id>/accept-budget/",
        views.accept_customer_budget,
        name="accept_customer_budget"
    ),

    path(
        "<int:task_id>/propose-amount/",
        views.propose_amount,
        name="propose_amount"
    ),

    path(
        "<int:task_id>/deliverable/<int:deliverable_id>/approve/",
        views.approve_deliverable,
        name="approve_deliverable"
    ),


    # ============================================================
    # CUSTOMER — QUOTE ACCEPTANCE
    # ============================================================

    path(
        "<int:task_id>/accept-amount/",
        views.accept_quoted_amount,
        name="accept_quoted_amount"
    ),


    # ============================================================
    # PAYMENTS
    # ============================================================

    path(
        "<int:task_id>/payment/",
        views.payment_page,
        name="payment_page"
    ),

    path(
        "<int:task_id>/payment/initialize/",
        views.initialize_payment,
        name="initialize_payment"
    ),

    path(
        "<int:task_id>/payment/success/",
        views.payment_success,
        name="payment_success"
    ),

    path(
        "payment/webhook/",
        views.paystack_webhook,
        name="paystack_webhook"
    ),


    # ============================================================
    # CUSTOMER — COMPLETION
    # ============================================================

    path(
        "<int:task_id>/confirm/",
        views.confirm_task_completion,
        name="confirm_task_completion"
    ),


    # ============================================================
    # NOTIFICATIONS
    # ============================================================

    path(
        "notifications/",
        views.notifications_api,
        name="notifications_api"
    ),

    path(
        "notifications/<int:notification_id>/read/",
        views.mark_notification_read,
        name="mark_notification_read"
    ),

    path(
        "notifications/read-all/",
        views.mark_all_notifications_read,
        name="mark_all_notifications_read"
    ),

    path(
        "notifications/push/vapid-key/",
        views.vapid_public_key,
        name="vapid_public_key"
    ),

    path(
        "notifications/push/subscribe/",
        views.save_push_subscription,
        name="save_push_subscription"
    ),

    path(
        "notifications/push/unsubscribe/",
        views.remove_push_subscription,
        name="remove_push_subscription"
    ),


    # ============================================================
    # TASK DETAIL
    # ============================================================

    path(
        "<int:task_id>/",
        views.task_detail,
        name="task_detail"
    ),
]
