from django.urls import path

from apps.telegrambot.views import TelegramLinkView, TelegramWebhookView

app_name = "telegrambot"

urlpatterns = [
    path("link/", TelegramLinkView.as_view(), name="link"),
    path("webhook/", TelegramWebhookView.as_view(), name="webhook"),
]
