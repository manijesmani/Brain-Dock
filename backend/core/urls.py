from django.urls import path

from core.views import HealthView, SiteView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("site/", SiteView.as_view(), name="site"),
]
