from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class IsSiteOwner(BasePermission):
    """Lets through the site's owner alone: everyone else gets a 403.

    Guards the owner's two exclusive features, the Telegram bot and the user
    panel; see apps.users.plans. Not to be confused with
    core.permissions.IsOwner, which is about who owns a record.
    """

    message = "این بخش فقط برای مالک سایت است."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.is_site_owner)


class HasAccount(BasePermission):
    """Lets in anyone signed in to a real account; a guest gets a 403.

    For what only makes sense with a password and more than one browser, such
    as the list of signed-in devices.
    """

    message = "این بخش برای حساب مهمان نیست. اول یک حساب بساز."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and not user.is_guest)
