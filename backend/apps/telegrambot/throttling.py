from rest_framework.throttling import AnonRateThrottle


class WebhookRateThrottle(AnonRateThrottle):
    """Caps how fast the webhook will accept updates.

    The endpoint is unauthenticated by necessity -- Telegram has no session --
    so the secret header is what keeps strangers out and this is what keeps a
    flood, from Telegram or anyone else, from occupying every worker.
    """

    scope = "telegram_webhook"
