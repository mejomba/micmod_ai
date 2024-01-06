from django.http import JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from tools.utils import is_ajax

# Create your views here.
from .models import Messages, ReadStatus

def notification_menu_list(request, template="notifications/partials/notification_messages_list.html"):
    context = dict()
    context['notifications'] = Messages.get_unread_messages(request.user)
    context["unread_count"] = Messages.get_unread_messages(request.user, ReadStatus.Unread).count()
    if request.method == "POST":
        if is_ajax(request):
            html = render_to_string(template, context,request=request)
            return JsonResponse({'html': html, 'unread_count': context["unread_count"]})
    return render(request, template, context=context,)
