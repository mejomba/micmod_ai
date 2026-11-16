"""Full-featured quotation v2 views.

Important: reuse the *actual* quotation form, nested inquiry formset and
workflow implementation. The deprecated v2 pricing-only editor cannot replace
the production quotation workflow.
"""
from django.urls import Resolver404, resolve, reverse_lazy
from urllib.parse import urlsplit
from django.http import HttpResponseRedirect

from .forms import QuotationForm
from inquiry.forms import InquiryResultForm
from django.conf import settings
from .quotation_v2_full_forms import (
    QuotationItemFormV2, QuotationItemFormsetV2,
)
from .views import QuotationsView


class QuotationsV2FullView(QuotationsView):
    template_name = "micmod-base/quotation/v2/full.html"
    form_class = QuotationForm
    formset_form = QuotationItemFormV2
    form_struct = {
        "form": QuotationForm,
        "childes": [
            {
                "form": QuotationItemFormsetV2,
                "childes": [{"form": InquiryResultForm}],
            },
        ],
    }
    # Preserve QuotationsView.flow_config and all workflow branching, as well
    # as existing nested InquiryResultFormset behavior in BaseQIFormsetV2.
    def get_success_url(self):
        return reverse_lazy(
            "micmod_base:quotation.v2", kwargs={"pk": self.object.pk}
        )

    def post(self, request, *args, **kwargs):
        # Use the production workflow/post handler, including duplication,
        # inquiry and Sepidar operations. Keep legacy redirects inside v2.
        response = super().post(request, *args, **kwargs)
        if getattr(response, "status_code", None) in (301, 302):
            target = response.get("Location", "")
            try:
                match = resolve(urlsplit(target).path)
                if match.view_name == "micmod_base:quotations.view":
                    return HttpResponseRedirect(
                        reverse_lazy("micmod_base:quotation.v2", kwargs={"pk": match.kwargs["pk"]})
                    )
            except (ValueError, Resolver404):
                pass
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["v2_full_editor"] = True
        context["v2_tax_rate"] = getattr(settings, "TAX_VALUE", 10)
        return context
