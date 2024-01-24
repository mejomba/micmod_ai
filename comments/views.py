from tokenize import Comment

from django.shortcuts import render
from django.views import View

from rest_framework import viewsets


# Create your views here.
#
# class CommentViewSet(viewsets.ModelViewSet):
#     queryset = Comment.objects.all()
#     serializer_class =


class CommentSeenView(View):
    def post(self, request, *args, **kwargs):
        ...
