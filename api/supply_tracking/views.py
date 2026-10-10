from rest_framework import permissions, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import SupplyTrackingService, normalize_phone


class SupplyTrackingPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


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

        data = SupplyTrackingService(mobile).list_summaries()
        paginator = SupplyTrackingPagination()
        page = paginator.paginate_queryset(data, request, view=self)
        return paginator.get_paginated_response(page)


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
