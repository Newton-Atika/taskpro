import json

from django.conf import settings

from pywebpush import webpush, WebPushException

from .models import PushSubscription


def send_push_notification(
    user,
    title,
    message,
    url="/",
):

    subscriptions = PushSubscription.objects.filter(
        user=user
    )

    payload = json.dumps(
        {
            "title": title,
            "message": message,
            "url": url,
        }
    )

    for subscription in subscriptions:

        subscription_info = {
            "endpoint": subscription.endpoint,
            "keys": {
                "p256dh": subscription.p256dh,
                "auth": subscription.auth,
            },
        }

        try:

            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=(
                    settings.WEBPUSH_VAPID_PRIVATE_KEY
                ),
                vapid_claims=(
                    settings.WEBPUSH_VAPID_CLAIMS
                ),
                ttl=86400,
            )

        except WebPushException as error:

            response = getattr(
                error,
                "response",
                None
            )

            if response is not None:

                if response.status_code in [
                    404,
                    410,
                ]:

                    subscription.delete()

            print(
                f"Web push failed for {user}: {error}"
            )

        except Exception as error:

            print(
                f"Unexpected web push error for {user}: {error}"
            )