from typing import Any

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class IsOwner(BasePermission):
    """Object-level check that the requesting user owns the record.

    This is a second line of defence only. The primary guarantee is that every
    viewset filters its queryset by `owner=request.user`, so a record belonging
    to someone else is never reachable in the first place.
    """

    message = "شما به این رکورد دسترسی ندارید."

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        return getattr(obj, "owner_id", None) == request.user.id
