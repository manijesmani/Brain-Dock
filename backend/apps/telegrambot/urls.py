from django.urls import path

from apps.telegrambot.views import TelegramLinkView

app_name = "telegrambot"

urlpatterns = [
    path("link/", TelegramLinkView.as_view(), name="link"),
]
