from django.views import generic

from changelog.models import ChangeLog


class ShowLogHistory(generic.ListView):
    model = ChangeLog
    template_name = 'changelog/changelog.html'
    context_object_name = 'logs'
    paginate_by = 20

    # Todo add some filter for log
    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        print(context['logs'][0].__dict__)
        # context['object_logs'] = self.model.get_log()
        return context
