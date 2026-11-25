from django import template
from order.forecast_presentation import is_farsi, panel_context

register = template.Library()

@register.inclusion_tag('order/scheduling/panel.html', takes_context=True)
def arrival_forecast_panel(context, instance, kind):
    request = context.get('request')
    if request is None or not request.user.is_authenticated:
        return {'show':False}
    return panel_context(instance,kind,request.user,is_farsi(request))
