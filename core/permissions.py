from rest_framework.permissions import BasePermission

from accounts.templatetags.accounts_tag import has_groups


class HasGroupPermission(BasePermission):

    required_groups = ''

    def has_permission(self, request, view):
        if not self.required_groups:
            return False
        return has_groups(request.user, self.required_groups)


class HasShopPermission(HasGroupPermission):
    required_groups = 'shop'
