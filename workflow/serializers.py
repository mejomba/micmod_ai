from rest_framework import serializers

from .models import WorkFlow


class WorkflowSerializer(serializers.ModelSerializer):

    class Meta:
        model = WorkFlow
        fields = '__all__'
