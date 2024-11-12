from tokenize import Comment

from ajax_datatable import AjaxDatatableView
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views import View
from django.views.generic import ListView

from rest_framework import viewsets

from comments.forms import CommentsForm
from comments.models import Comments
from core.views import BaseView


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


class CommentListView(ListView):
    model = Comments
    template_name = 'list.html'


class CommentView(BaseView):
    model = Comments
    form_class = CommentsForm
    template_name = 'update.html'
    success_message = 'بروز شد'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['app_name'] = self.request.resolver_match.app_name
        return context

    def get_success_url(self):
        path = reverse('comments:comment.update', kwargs={'pk': self.object.pk})
        return path


class CommentListDatatableView(AjaxDatatableView):
    model = Comments
    title = 'sku_list'
    length_menu = [[20, 50, 100, -1], [20, 50, 100, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    not_search_values_separator = '|'
    render_row_details_template_name = 'sku_list_detail.html'
    from translator import get_text as _
    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'id', 'visible': True, 'title': _('شناسه'), "orderable": True},
        {'name': 'comment_title', 'visible': True, 'title': _('title'), 'className': 'py-1'},
        {'name': 'comment_content', 'title': _('متن'), 'visible': True, 'searchable': True, },
        {'name': 'customer', 'visible': True, 'title': _('customer'), 'className': 'py-1 ', 'lookup_field': '__title__icontains'},
        {'name': 'sku', 'visible': True, 'title': _('sku'), 'className': 'py-1', 'lookup_field': '__sku__icontains'},
    ]

    def customize_row(self, row, obj):
        row['comment_content'] = '<a class="fw-bold" href="%s">%s</a>' % (
            reverse('comments:comment.update', args=(obj.id,)),
            obj.comment_content if obj.comment_content else '_'
        )