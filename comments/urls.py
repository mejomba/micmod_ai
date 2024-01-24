from django.urls import path

from comments.views import CommentSeenView

urlpatterns = [
    path('ajax/comment_seen/', CommentSeenView.as_view(), name='comment_seen')
    # 'app_label/model_name/content_type_id/object_id'
    # 'comments/comments/qi_ctt/qi_id'
]
