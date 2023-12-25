from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import serializers

from inquiry.models import PriceInquiryResult
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
