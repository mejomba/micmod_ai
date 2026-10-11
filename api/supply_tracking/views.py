from rest_framework import permissions, status
from urllib.parse import urlencode
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import SupplyTrackingService, normalize_phone


DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


class MobileInputMixin:
    def get_mobile(self, request):
        mobile = normalize_phone(request.query_params.get("mobile"))
        if not mobile:
            return None
        return mobile


class SupplyTrackingListView(MobileInputMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        mobile = self.get_mobile(request)
        if not mobile:
            return Response(
                {"detail": "mobile query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            page = max(int(request.query_params.get("page", 1)), 1)
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = int(request.query_params.get("page_size", DEFAULT_PAGE_SIZE))
        except (TypeError, ValueError):
            page_size = DEFAULT_PAGE_SIZE
        page_size = min(max(page_size, 1), MAX_PAGE_SIZE)

        offset = (page - 1) * page_size
        payload = SupplyTrackingService(mobile).list_summaries(
            offset=offset,
            limit=page_size,
        )

        def page_url(target_page):
            if target_page < 1:
                return None
            params = request.query_params.copy()
            params["page"] = target_page
            params["page_size"] = page_size
            return request.build_absolute_uri(
                f"{request.path}?{urlencode(params, doseq=True)}"
            )

        count = payload["count"]
        has_next = offset + page_size < count
        response_data = {
            "count": count,
            "next": page_url(page + 1) if has_next else None,
            "previous": page_url(page - 1) if page > 1 else None,
            "results": payload["results"],
        }
        return Response(response_data)


class SupplyTrackingDetailView(MobileInputMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, tracking_id):
        mobile = self.get_mobile(request)
        if not mobile:
            return Response(
                {"detail": "mobile query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = SupplyTrackingService(mobile).get_detail(tracking_id)
        if data is None:
            return Response(
                {"detail": "tracking item not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(data)
