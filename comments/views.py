from tokenize import Comment

from django.http import JsonResponse
from django.shortcuts import render
from django.views import View

from rest_framework import viewsets

from comments.models import Comments


# Create your views here.
#
# class CommentViewSet(viewsets.ModelViewSet):
#     queryset = Comment.objects.all()
#     serializer_class =


class CommentSeenView(View):
    def post(self, request, *args, **kwargs):
        ...


class CommentDeleteView(View):
    def post(self, request, *args, **kwargs):
        comment = Comments.objects.get(pk=request.POST.get('pk'))
        if comment.creator_user == request.user:
            comment.is_deleted = True
            comment.save()
            return JsonResponse({"status": "success"}, status=200)
        else:
            return JsonResponse({"status": "fail"}, status=400)


