from django.urls import reverse

from .models import Notification

from .push_notifications import send_push_notification


def notify_user(
    user,
    title,
    message,
    task=None,
):

    notification = Notification.objects.create(

        user=user,

        task=task,

        title=title,

        message=message,
    )

    if task:

        url = reverse(
            "task_detail",
            kwargs={
                "task_id": task.id
            }
        )

    else:

        url = "/"

    send_push_notification(

        user=user,

        title=title,

        message=message,

        url=url,
    )

    return notification