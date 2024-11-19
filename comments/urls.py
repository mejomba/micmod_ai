from django.urls import path

from comments.views import CommentSeenView, CommentDeleteView, CommentListView, CommentListDatatableView, CommentView

app_name = 'comments'
urlpatterns = [
    path('ajax/comment_seen/', CommentSeenView.as_view(), name='comment_seen'),
    path('ajax/comment_delete/', CommentDeleteView.as_view(), name='comment_delete'),
    path('list/', CommentListView.as_view(), name='comment.list'),
    path('list_datatable/', CommentListDatatableView.as_view(), name='comment.list.datatable'),
    path('view/', CommentView.as_view(), name='comment.view'),
    path('view/<int:pk>/', CommentView.as_view(), name='comment.update')
    # 'app_label/model_name/content_type_id/object_id'
    # 'comments/comments/qi_ctt/qi_id'
]
