from django.http import Http404


class SuperUserAccessMixin:
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            raise Http404
        return super().dispatch(request, *args, **kwargs)
