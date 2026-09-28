from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.ideas.attachment_views import (
    AttachmentFileView,
    AttachmentThumbnailView,
    AttachmentViewSet,
)
from apps.ideas.views import CategoryViewSet, IdeaViewSet, TagViewSet, TrashViewSet

app_name = "ideas"

router = DefaultRouter()
router.register("ideas", IdeaViewSet, basename="idea")
router.register("categories", CategoryViewSet, basename="category")
router.register("tags", TagViewSet, basename="tag")
router.register("attachments", AttachmentViewSet, basename="attachment")
router.register("trash", TrashViewSet, basename="trash")

urlpatterns = [
    *router.urls,
    path(
        "attachments/<int:pk>/file/",
        AttachmentFileView.as_view(),
        name="attachment-file",
    ),
    path(
        "attachments/<int:pk>/thumbnail/",
        AttachmentThumbnailView.as_view(),
        name="attachment-thumbnail",
    ),
]
