from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import serializers
from extra_data.models import Customer, CustomerExpert, CustomerGrade, CustomerGroup, CustomerFields, Senf, SubSenf, \
    IntroductionMethod, Introducer, Marketer, Province

from inquiry.models import PriceInquiryResult
from micmod_base.base import Currency
from micmod_base.models import SaleType, Month
from sepidar.models import Dl

from translator import get_text as _


class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = get_user_model()
        fields = ['id', 'email', 'phone', 'first_name', 'last_name', 'is_active', 'is_staff', 'is_superuser']


class TelBotUserRegisterSerializer(serializers.Serializer):
    telegram_code = serializers.CharField(max_length=100)
    sepidar_code = serializers.CharField(max_length=100)
    phone = serializers.CharField(max_length=11)
    message = serializers.CharField(max_length=255, read_only=True)
    status = serializers.IntegerField(read_only=True)

    def create(self, validated_data):
        telegram_code = validated_data.get('telegram_code')
        sepidar_code = validated_data.get('sepidar_code')
        phone = validated_data.get('phone')

        if get_user_model().objects.filter(Q(telegram_code=telegram_code) | Q(sepidar_code=sepidar_code) | Q(phone=phone)).exists():
            return {"telegram_code": None,
                    "sepidar_code": None,
                    "phone": None,
                    "message": _(f"telegram account or sepidar code or phone exist"),
                    "status": 400,
                    }
        else:
            sepidar_user = Dl.get_dl(validated_data['sepidar_code'])

            new_user = None
            if sepidar_user:
                password = get_user_model().objects.make_random_password()
                try:
                    new_user = get_user_model().objects.create_user(
                        username=sepidar_code,
                        phone=phone,
                        telegram_code=telegram_code,
                        sepidar_code=sepidar_code,
                        first_name=sepidar_user[0].name,
                        is_active=False,
                        is_customer=True
                    )
                    new_user.set_password(password)
                    new_user.save(update_fields=['password'])
                except Exception as e:
                    print('error: ', __file__, e.__traceback__.tb_lineno, e)
            else:
                return {"telegram_code": None,
                        "sepidar_code": None,
                        "phone": None,
                        "message": _("invalid sepidar code"),
                        "status": 404,
                        }
            if new_user:
                return {"telegram_code": new_user.telegram_code,
                        "sepidar_code": new_user.sepidar_code,
                        "phone": new_user.phone,
                        "message": _("user create"),
                        "status": 201
                        }
            else:
                return {"telegram_code": None,
                        "sepidar_code": None,
                        "phone": None,
                        "message": _("error: user creation fail"),
                        "status": 400
                        }


class GeneralSerializer(serializers.ModelSerializer):
    xxx = serializers.CharField(source='currency_type', read_only=True)

    class Meta:
        model = None
        # fields = '__all__'
        # fields = ['pk', 'supplier', 'price', 'local_price', 'description']


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = '__all__'


class MonthSerializer(serializers.ModelSerializer):
    class Meta:
        model = Month
        fields = '__all__'


class CustomerGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerGroup
        fields = ['title', 'sepidar_id', 'sepidar_group_id']


class CustomerLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Province
        fields = ['title', 'location_id', 'sepidar_location_id']


class SenfSerializer(serializers.ModelSerializer):
    class Meta:
        model = Senf
        fields = ['id', 'title']


class SubSenfSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubSenf
        fields = ['id', 'title']


class IntroductionMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntroductionMethod
        fields = ['id', 'title']


class IntroducerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Introducer
        fields = ['id', 'title']


class MarketerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Marketer
        fields = ['id', 'title']


class CustomerSaleTypeSerializer(serializers.ModelSerializer):
    month = MonthSerializer(read_only=True)
    currency = CurrencySerializer(read_only=True)

    class Meta:
        model = SaleType
        fields = ['id',  'number', 'title', 'month', 'currency', 'extra_percentage', ]


class CustomerFieldSerializer(serializers.ModelSerializer):

    class Meta:
        model = CustomerFields
        fields = ['id', 'title', 'icon']


class CustomerSerializer(serializers.ModelSerializer):
    customer_group = CustomerGroupSerializer(read_only=True)
    province = CustomerLocationSerializer(read_only=True)
    location = CustomerLocationSerializer(read_only=True)
    senf = SenfSerializer(read_only=True)  # serializers.PrimaryKeyRelatedField(many=True)
    sub_senf = SubSenfSerializer(read_only=True)
    introduction_method = IntroductionMethodSerializer(read_only=True)
    introducer = IntroducerSerializer(read_only=True)
    marketer = MarketerSerializer(read_only=True)
    customer_sale_type = CustomerSaleTypeSerializer(read_only=True)
    customer_field = CustomerFieldSerializer(many=True, read_only=True)
    class Meta:
        model = Customer
        fields = ['id', 'sepidar_dl_id', 'sepidar_dl_code', 'sepidar_party_id', 'title', 'type', 'national_code',
                  'name', 'last_name', 'email', 'website', 'phone', 'credit_with_doc', 'customer_group', 'province',
                  'location', 'address', 'senf', 'sub_senf', 'introduction_method', 'introducer', 'revival_date',
                  'z_no', 'z_safte', 'z_cheque_s', 'z_cheque_ns', 'z_max_credit_rafi', 'extra_credit', 'i_type1_target',
                  'marketer', 'cheque_to_delivery', 'customer_sale_type', 'official_name', 'customer_grade',
                  'description', 'lat', 'long', 'customer_field', 'active', 'guid', 'meet_in_person', 'black_list',
                  ]
