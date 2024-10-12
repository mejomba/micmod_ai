import importlib

from django.shortcuts import render
from rest_framework import status, permissions
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import GenericAPIView, ListAPIView
from rest_framework.viewsets import ModelViewSet

from api.serializers import TelBotUserRegisterSerializer, GeneralSerializer, CustomerSerializer
from core.views import JsonTemplateResponseMixin
from extra_data.models import Customer
from tools.utils import show_error


# Create your views here.


class TelBotRegisterUserAPI(APIView):
    # permission_classes = [permissions.AllowAny]
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['post']

    def post(self, request):
        serializer_ = TelBotUserRegisterSerializer(data=request.data)
        serializer_.is_valid(raise_exception=True)
        serializer_.save()
        print(serializer_.data.get('status'))

        if serializer_.data.get('status') == 400:
            return Response(serializer_.data, status=status.HTTP_400_BAD_REQUEST)
        elif serializer_.data.get('status') == 404:
            return Response(serializer_.data, status=status.HTTP_404_NOT_FOUND)

        return Response(serializer_.data, status=status.HTTP_201_CREATED)


class CustomerListAPI(ListAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer

    def list(self, request, *args, **kwargs):
        if limit_ := self.request.GET.get('limit'):
            self.pagination_class.default_limit = limit_
        else:
            self.pagination_class = None
        return super().list(request, *args, **kwargs)


class AjaxCall(APIView):
    # permission_classes = [permissions.IsAuthenticated]
    permission_classes = [permissions.AllowAny]
    http_method_names = ['get']
    app = None
    model = None
    fields = None

    @staticmethod
    def get_model_class(app, model):
        from django.apps import apps
        try:
            target_model = apps.get_model(app, model)
        except Exception as e:
            print(show_error(e, __file__))
            target_model = None
        if not target_model:
            model_names = apps.get_models(model)
            for model_class in model_names:
                if model.lower() == model_class.__name__.lower():
                    target_model = model_class
        return target_model

    def get_serializer_class(self):
        GeneralSerializer.Meta.model = self.get_model_class(self.app, self.model)
        GeneralSerializer.Meta.fields = '__all__' if self.fields is None else self.fields
        return GeneralSerializer

    def get(self, request, app: str, model: str):
        self.app = app
        self.model = model
        params = dict(map(lambda x: x, request.GET.items()))
        print(params)

        serializer = self.get_serializer_class()

        target_model = self.get_model_class(app, model)
        if target_model:
            try:
                qs = target_model.objects.filter(**params)
                serializer_ = serializer(instance=qs, many=True)
                return Response(serializer_.data)
            except Exception as e:
                show_error(e, __file__)
                pass
        return Response({'detail': 'error'}, status.HTTP_400_BAD_REQUEST)


class AjaxInquiryResult(JsonTemplateResponseMixin, AjaxCall):
    fields = [
        'sku',
        'price_inquiry_file',
        'supplier',
        'price',
        'local_price',
        'description',
        'xxx',
        'active',
        'rial_final_price',
        'weight',
        'free_rmb_rate_new_order',
    ]
