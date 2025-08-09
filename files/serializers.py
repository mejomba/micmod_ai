from .models import File, Image
from core.serializers import CustomFieldModelSerializer


class GenericFileSerializer(CustomFieldModelSerializer):

    class Meta:
        model = File
        fields = '__all__'


class GenericImageSerializer(CustomFieldModelSerializer):

    class Meta:
        model = Image
        fields = '__all__'
