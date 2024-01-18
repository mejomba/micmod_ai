from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render, redirect, reverse
from django.contrib import messages

from translator import get_text as _

from ajax_datatable.views import AjaxDatatableView

from sepidar.models import Dl

from django.views import View
from django.views.generic import ListView
from .forms import *
import time
from tlg.task import add_new_order_receiver


from django.contrib.auth import get_user_model

User = get_user_model()


class IMEIListRegCreateView(LoginRequiredMixin, View):
    template_name = 'IMEI/IMEI_list_reg_create.html'

    def get(self, request):
        add_new_order_receiver.delay()
        context = {}
        context['heading'] = _("create")
        context['pageview'] = _("imei_list_reg")
        context['form'] = IMEIListRegFrm(initial={'action': '1'})
        context['form'] = IMEIListRegFrm(initial={'action': '1'})

        return render(request, self.template_name, context)

    def post(self, request):
        form = IMEIListRegFrm(request.POST, request.FILES)
        if form.is_valid():
            file = request.FILES.get('source_file')
            action = request.POST.get('action')
            user = User.objects.filter(username=request.user.username).first()
            obj = form.save(commit=True)
            obj.editor_user = user
            if not obj.creator_user:
                obj.creator_user = user
            obj.save()
            messages.success(request, _('آیتم با موفقیت ایجاد شد'))
            IMEIListRegDetail.create_from_excel(file, action, obj.id)
            if 'create' in request.POST:
                return redirect(reverse('IMEI:imei_list_reg.view', args=[obj.id]))
            elif 'create-continue' in request.POST:
                return redirect(reverse('IMEI:imei_list_reg.create'))
        else:
            messages.error(request, _('خطایی رخ داده است'))
            context = {}
            context['heading'] = _("create")
            context['pageview'] = _("imei_list_reg")
            context['form'] = IMEIListRegFrm(request.POST, request.FILES, initial={'action': '1'})
            return render(request, self.template_name, context)


class IMEIListRegView(LoginRequiredMixin, View):
    template_name = 'IMEI/IMEI_list_reg.html'

    def get(self, request,id=-1):
        greeting = {}
        greeting['heading'] = _("create")
        greeting['pageview'] = _("imei_list_reg")
        obj = IMEIListReg.objects.filter(id=id).first()
        greeting['form'] = IMEIListRegFrm(instance=obj, initial={'action': '1'})
        if obj:
            obj.created_date = datetime2jalali(obj.created_date).strftime('%y/%m/%d-%H:%M')
            obj.last_update_date = datetime2jalali(obj.last_update_date).strftime('%y/%m/%d-%H:%M')
            greeting['data'] = obj

            return render(request, self.template_name, greeting)
        else:
            return redirect(reverse('IMEI:imei_list_reg.create'))

    def post(self, request, id=-1):
        file = request.FILES.get('source_file')
        action = request.POST.get('action')

        s = time.time()
        IMEIListRegDetail.create_from_excel(file, action, id)
        obj = IMEIListReg.objects.filter(id=id).first()

        if request.method == "POST":
            form = IMEIListRegFrm(request.POST, request.FILES, instance=obj)
            if form.is_valid():
                user = User.objects.filter(username=request.user.username).first()
                obj = form.save(commit=True)
                obj.editor_user = user
                if not obj.creator_user:
                    obj.creator_user = user
                obj.save()
                url = reverse('IMEI:imei_list_reg.view', args=[obj.id])
                messages.success(request, 'با موفقیت به روز شد')
                return redirect(url)
            if "deleteCustomer" in request.POST:
                id = request.POST['id']
                obj = IMEIListReg.objects.filter(id=id).first()
                obj.delete()
                return HttpResponse()
            if obj:
                url = reverse('IMEI:imei_list_reg.view', args=[obj.id])
            else:
                messages.info(request, _('آیتم با مشخصات خواسته شده پیدا نشد. میتوانید یکی ایجاد کنید.'))
                url = reverse('IMEI:imei_list_reg.create')
            return redirect(url)


class IMEIListRegShowView(LoginRequiredMixin, ListView):
    template_name = 'IMEI/IMEI_list.html'
    model = IMEIListReg
    context_object_name = 'imei_list'


class IMEIINTSWCreatReg(LoginRequiredMixin, View):
    template_name = 'IMEI/IMEI_ntsw_reg_create.html'

    def get(self, request):
        context = {}
        context['heading'] = _("create")
        context['pageview'] = _("imei_list_reg")
        context['form'] = IMEIINTSWRegForm(initial={'action': '1'})

        return render(request, self.template_name, context)

    def post(self, request):
        form = IMEIINTSWRegForm(request.POST, request.FILES)
        if form.is_valid():
            file = request.FILES.get('source_file')
            action = request.POST.get('action')
            user = User.objects.filter(username=request.user.username).first()
            obj = form.save(commit=True)
            obj.editor_user = user
            if not obj.creator_user:
                obj.creator_user = user
            obj.save()

            s = time.time()
            IMEINTSWRegDetail.create_from_excel(file, action, obj.id)
            messages.success(request, 'با موفقیت ایجاد شد')
            if 'create' in request.POST:
                return redirect(reverse('IMEI:imei_ntsw_reg.view', args=[obj.id]))
            if 'create-continue' in request.POST:
                return redirect(reverse('IMEI:imei_ntsw_reg.create'))
        else:
            context = {}
            context['heading'] = _("create")
            context['pageview'] = _("imei_list_reg")
            context['form'] = IMEIINTSWRegForm(request.POST, request.FILES, initial={'action': '1'})
            return render(request, self.template_name, context)


class IMEIINTSWReg(LoginRequiredMixin, View):
    template_name = 'IMEI/IMEI_intsw_reg.html'

    def get(self, request, id=-1):
        obj = IMEINTSWReg.objects.filter(id=id).first()
        form = IMEIINTSWRegForm(instance=obj, initial={'action': '1'})
        context = {}
        context['heading'] = _("create")
        context['pageview'] = _("imei_intsw_reg")
        context['form'] = form
        if obj:
            obj.created_date = datetime2jalali(obj.created_date).strftime('%y/%m/%d-%H:%M')
            obj.last_update_date = datetime2jalali(obj.last_update_date).strftime('%y/%m/%d-%H:%M')
        context['data'] = obj
        return render(request, self.template_name, context)

    def post(self, request, id=-1):
        file = request.FILES.get('source_file')
        action = request.POST.get('action')

        import time
        s = time.time()
        IMEINTSWRegDetail.create_from_excel(file, action, id)

        obj = IMEINTSWReg.objects.filter(id=id).first()
        if request.method == "POST":
            form = IMEIINTSWRegForm(request.POST, request.FILES, instance=obj)
            if form.is_valid():
                user = User.objects.filter(username=request.user.username).first()
                obj = form.save(commit=True)
                obj.editor_user = user
                if not obj.creator_user:
                    obj.creator_user = user
                obj.save()
                messages.success(request, 'با موفقیت بروز شد')
                url = reverse('IMEI:imei_ntsw_reg.view', args=[obj.id])
                return redirect(url)
            if "deleteCustomer" in request.POST:
                id = request.POST['id']
                obj = IMEIListReg.objects.filter(id=id).first()
                obj.delete()
                return HttpResponse()
            if obj:
                url = reverse('IMEI:imei_ntsw_reg.view', args=[obj.id])
            else:
                url = reverse('IMEI:imei_ntsw_reg.create')
            return redirect(url)


class IMEIINTSWRegShowView(LoginRequiredMixin, ListView):
    template_name = 'IMEI/IMEI_intsw_list.html'
    model = IMEINTSWReg
    context_object_name = 'imei_intsw_list'


class IMEISaleCreatReg(LoginRequiredMixin, View):
    template_name = 'IMEI/IMEI_sale_reg_create.html'

    def get(self, request):
        context = {}
        context['heading'] = _("create")
        context['pageview'] = _("imei_list_reg")
        context['form'] = IMEISaleRegForm(initial={'action': '1'})

        return render(request, self.template_name, context)

    def post(self, request):
        form = IMEISaleRegForm(request.POST, request.FILES)
        file = request.FILES.get('source_file')
        action = request.POST.get('action')
        id = self.kwargs.get('id')

        submitter = request.POST.get('submitter')
        if form.is_valid():
            code = request.POST.get('customer_code')
            try:
                dl = Dl.get_dl(code)
                customer = dl[0] if dl else None
            except Exception:
                customer = None

            if not customer:
                return JsonResponse({'status': 'false',
                                     'detail': 'کد وارد شده برای مشتری معتبر نیست (در حال حاظر این مشتری در سیستم ثبت نشده است)'},
                                    status=404
                                    )
            pack_numbers = request.POST.get('pack_numbers')
            try:
                pack_numbers = pack_numbers.split('-')
            except Exception:
                pack_numbers = None

            if submitter == 'normal-submitter':
                if not pack_numbers:
                    return JsonResponse({'status': 'false',
                                         'detail': 'شماره کارتن های وارد شده در سیستم ثبت نشده است.\n پس از اصلاح مجدد ثبت کنید یا  "ثبت با هر شرایطی"  انتخاب کنید.'},
                                        status=403
                                        )

                for item in pack_numbers:
                    if not IMEIListRegDetail.objects.filter(Q(internal_box=item) | Q(main_box=item)).exists():
                        return JsonResponse({'status': 'false',
                                             'detail': 'شماره کارتن های وارد شده در سیستم ثبت نشده است.\n پس از اصلاح مجدد ثبت کنید یا "ثبت با هر شرایطی" انتخاب کنید.'},
                                            status=403
                                            )

                user = User.objects.filter(username=request.user.username).first()
                obj = form.save(commit=True)
                obj.editor_user = user
                obj.invoice_year = obj.invoice_date.year
                if not obj.creator_user:
                    obj.creator_user = user
                obj.customer_name = customer.name
                obj.save()

                import time
                s = time.time()
                # IMEISaleRegDetail.create_from_excel(file, action, id)

                packs = {}
                for pack_number in pack_numbers:
                    packs[pack_number] = IMEIListRegDetail.objects.filter(
                        Q(main_box=pack_number) | Q(internal_box=pack_number))

                messages.success(request, 'با موفقیت ایجاد شد')

                redirect_url = reverse('IMEI:imei_sale_reg.view', args=[obj.id])
                res = JsonResponse({'detail': 'ok', 'redirect_url': redirect_url}, status=201)
                return res

            elif submitter == 'force-submitter':
                user = User.objects.filter(username=request.user.username).first()
                obj = form.save(commit=True)
                obj.editor_user = user
                obj.invoice_year = obj.invoice_date.year
                obj.warning = 'این رکورد بدون در نظر گرفتن صحت شماره کارتن ثبت شده است'
                if not obj.creator_user:
                    obj.creator_user = user

                obj.customer_name = customer.name
                obj.save()

                packs = {}
                for pack_number in pack_numbers:
                    packs[pack_number] = IMEIListRegDetail.objects.filter(
                        Q(main_box=pack_number) | Q(internal_box=pack_number))

                messages.success(request, 'با موفقیت ایجاد شد')

                redirect_url = reverse('IMEI:imei_sale_reg.view', args=[obj.id])
                res = JsonResponse({'detail': 'ok', 'redirect_url': redirect_url}, status=201)
                return res

        else:
            res = JsonResponse({'detail': _('check fields, some fields with star is required')}, status=400)
            return res


class IMEISaleRegView(LoginRequiredMixin, View):
    template_name = 'IMEI/IMEI_sale_reg.html'

    def get(self, request, id=-1):
        obj = IMEISaleReg.objects.filter(id=id).first()
        form = IMEISaleRegForm(instance=obj, initial={'action': '1'})
        context = {}
        context['heading'] = _("create")
        context['pageview'] = _("imei_intsw_reg")
        context['form'] = form
        if obj:
            obj.created_date = datetime2jalali(obj.created_date).strftime('%y/%m/%d-%H:%M')
            obj.last_update_date = datetime2jalali(obj.last_update_date).strftime('%y/%m/%d-%H:%M')
        context['data'] = obj
        return render(request, self.template_name, context)

    def post(self, request, id=-1):
        current_obj = IMEISaleReg.objects.filter(pk=id).first()
        form = IMEISaleRegForm(request.POST, request.FILES, instance=current_obj)
        file = request.FILES.get('source_file')
        action = request.POST.get('action')
        id = self.kwargs.get('id')

        if form.is_valid():
            submitter = request.POST.get('submitter')
            code = request.POST.get('customer_code')
            try:
                dl = Dl.get_dl(code)
                customer = dl[0] if dl else None
            except Exception as e:
                print(e)
                customer = None

            if not customer:
                return JsonResponse({'status': 'false',
                                     'detail': 'کد وارد شده برای مشتری معتبر نیست (در حال حاظر این مشتری در سیستم ثبت نشده است)'},
                                    status=404
                                    )
            pack_numbers = request.POST.get('pack_numbers')
            try:
                pack_numbers = pack_numbers.split('-')
            except Exception:
                pack_numbers = None
            if submitter == 'normal-submitter':
                if not pack_numbers:
                    return JsonResponse({'status': 'false',
                                         'detail': 'شماره کارتن های وارد شده در سیستم ثبت نشده است.\n پس از اصلاح مجدد ثبت کنید یا  "ثبت با هر شرایطی"  انتخاب کنید.'},
                                        status=403
                                        )

                for item in pack_numbers:
                    if not IMEIListRegDetail.objects.filter(Q(internal_box=item) | Q(main_box=item)).exists():
                        return JsonResponse({'status': 'false',
                                             'detail': 'شماره کارتن های وارد شده در سیستم ثبت نشده است.\n پس از اصلاح مجدد ثبت کنید یا "ثبت با هر شرایطی" انتخاب کنید.'},
                                            status=403
                                            )

                user = User.objects.filter(username=request.user.username).first()
                obj = form.save(commit=True)
                obj.editor_user = user
                obj.invoice_year = obj.invoice_date.year
                if not obj.creator_user:
                    obj.creator_user = user
                obj.customer_name = customer.name
                obj.save()

                IMEISaleRegDetail.create_from_excel(file, action, id)

                packs = {}
                for pack_number in pack_numbers:
                    packs[pack_number] = IMEIListRegDetail.objects.filter(
                        Q(main_box=pack_number) | Q(internal_box=pack_number))

                messages.success(request, 'با موفقیت بروز شد')

                redirect_url = reverse('IMEI:imei_sale_reg.view', args=[obj.id])
                res = JsonResponse({'detail': 'ok', 'redirect_url': redirect_url}, status=201)
                return res

            elif submitter == 'force-submitter':
                user = User.objects.filter(username=request.user.username).first()
                obj = form.save(commit=True)
                obj.editor_user = user
                obj.invoice_year = obj.invoice_date.year
                obj.warning = 'این رکورد بدون در نظر گرفتن صحت شماره کارتن ثبت شده است'
                if not obj.creator_user:
                    obj.creator_user = user
                obj.customer_name = customer.name
                obj.save()

                IMEISaleRegDetail.create_from_excel(file, action, id)

                packs = {}
                for pack_number in pack_numbers:
                    packs[pack_number] = IMEIListRegDetail.objects.filter(
                        Q(main_box=pack_number) | Q(internal_box=pack_number))

                messages.success(request, 'با موفقیت بروز شد')

                redirect_url = reverse('IMEI:imei_sale_reg.view', args=[obj.id])
                res = JsonResponse({'detail': 'ok', 'redirect_url': redirect_url}, status=201)
                return res

        else:
            res = JsonResponse({'detail': _('check fields, some fields with star is required')}, status=400)
            return res


class IMEISaleRegShowView(LoginRequiredMixin, ListView):
    template_name = 'IMEI/IMEI_sale_list.html'
    model = IMEISaleReg
    context_object_name = 'imei_sale_list'


class IMEIErrCreatReg(LoginRequiredMixin, View):
    template_name = 'IMEI/IMEI_err_reg_create.html'

    def get(self, request):
        context = {}
        context['heading'] = _("create")
        context['pageview'] = _("imei_list_reg")
        context['form'] = IMEIErrRegForm(initial={'action': '1'})

        return render(request, self.template_name, context)

    def post(self, request):
        form = IMEIErrRegForm(request.POST, request.FILES)
        if form.is_valid():
            user = User.objects.filter(username=request.user.username).first()
            obj = form.save(commit=True)
            obj.editor_user = user
            if not obj.creator_user:
                obj.creator_user = user
            obj.save()
            messages.success(request, _('آیتم با موفقیت ایجاد شد'))

            if 'create' in request.POST:
                return redirect(reverse('IMEI:imei_err_reg.view', args=[obj.id]))
            elif 'create-continue' in request.POST:
                return redirect(reverse('IMEI:imei_err_reg.create'))
        else:
            context = {}
            context['heading'] = _("create")
            context['pageview'] = _("imei_list_reg")
            context['form'] = IMEIErrRegForm(request.POST, request.FILES)
            return render(request, self.template_name, context)


class IMEIErrRegView(LoginRequiredMixin, View):
    template_name = 'IMEI/IMEI_err_reg.html'

    def get(self, request, id=-1):
        obj = IMEIErrReg.objects.filter(id=id).first()
        form = IMEIErrRegForm(instance=obj, initial={'action': '1'})
        context = {}
        context['heading'] = _("create")
        context['pageview'] = _("imei_err_reg")
        context['form'] = form
        if obj:
            obj.created_date = datetime2jalali(obj.created_date).strftime('%y/%m/%d-%H:%M')
            obj.last_update_date = datetime2jalali(obj.last_update_date).strftime('%y/%m/%d-%H:%M')
        context['data'] = obj
        return render(request, self.template_name, context)

    def post(self, request, id=-1):
        obj = IMEIErrReg.objects.filter(id=id).first()
        if request.method == "POST":
            form = IMEIErrRegForm(request.POST, request.FILES, instance=obj)
            if form.is_valid():
                user = User.objects.filter(username=request.user.username).first()
                obj = form.save(commit=True)
                obj.editor_user = user
                if not obj.creator_user:
                    obj.creator_user = user
                obj.save()
                messages.success(request, _('با موفقیت ثبت شد.'))
                url = reverse('IMEI:imei_err_reg.view', args=[obj.id])
                return redirect(url)
            if "deleteCustomer" in request.POST:
                id = request.POST['id']
                obj = IMEIListReg.objects.filter(id=id).first()
                obj.delete()
                return HttpResponse()
            if obj:
                url = reverse('IMEI:imei_err_reg.view', args=[obj.id])
                messages.success(request, _('آیتم با موفقیت ایجاد شد'))
            else:
                url = reverse('IMEI:imei_err_reg.create')
            return HttpResponseRedirect(url)


class IMEIErrRegShowView(LoginRequiredMixin, ListView):
    template_name = 'IMEI/IMEI_err_list.html'
    model = IMEIErrReg
    context_object_name = 'imei_err_list'


class IMEIAllListShowView(LoginRequiredMixin, ListView):
    model = IMEIListReg
    template_name = 'IMEI/imei_all_list.html'
    context_object_name = 'imei_list'
    paginate_by = 5000

    # def dispatch(self, request, *args, **kwargs):
    #     x = super().dispatch(request, *args, **kwargs)
    #     print('dispatch')
    #     return ExportExcel.get(request, model=self.model, *args, **kwargs)
    #     return x
    #     pass

    def get(self, request, *args, **kwargs):
        print('get all')
        super().get(request, *args, **kwargs)
        context = dict()
        # context['model_name'] = self.model._meta.model_name
        context['model_name'] = IMEIAllSearch._meta.model_name
        context['app_label'] = 'IMEI'
        context['header'] = "id IMEI packing register_date main_box internal_box status code invoice_code customer_code customer_name"
        param = self.request.GET.get('q', 'submit').strip('/')

        return render(request, self.template_name, context)


def imei_related_on_box(request, id, box_number):
    if request.method == 'GET':
        context = {}
        obj = IMEISaleReg.objects.filter(id=id).first()
        IMEI_box_sell = IMEISaleRegDetail.objects.values_list('IMEI', flat=True)
        box_imei = IMEIListRegDetail.objects.filter(Q(internal_box=box_number) | Q(main_box=box_number)).filter(
            IMEI__in=IMEI_box_sell)
        form = IMEISaleRegForm(instance=obj, initial={'action': '1'})
        for field_name in form.fields:
            form.fields[field_name].disabled = True

        context['heading'] = _("create")
        context['pageview'] = _("imei_intsw_reg")
        context['box_number'] = box_number
        context['form'] = form
        context['box_imei'] = box_imei

        if obj:
            obj.created_date = datetime2jalali(obj.created_date).strftime('%y/%m/%d-%H:%M')
            obj.last_update_date = datetime2jalali(obj.last_update_date).strftime('%y/%m/%d-%H:%M')
        context['data'] = obj
        return render(request, 'IMEI/IMEI_sale_reg_box.html', context)


class TestAjaxDatatableView(AjaxDatatableView):
    model = IMEIAllSearch
    title = 'all_imei'
    initial_order = [["IMEI", "asc"], ]
    length_menu = [[25, 50, 100, -1], [25, 50, 100, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'imei_all_search_detail.html'

    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'IMEI', 'visible': True, 'className': 'py-1 border', },
        {'name': 'packing', 'visible': True, 'className': 'py-1 border'},
        {'name': 'main_box', 'visible': True, 'title': 'باکس اصلی', 'className': 'py-1 border'},
        {'name': 'internal_box', 'visible': True, 'title': 'باکس داخلی', 'className': 'py-1 border'},
        {'name': 'status', 'visible': True, 'title': 'وضعیت', 'className': 'py-1 border'},
        {'name': 'code', 'visible': True, 'title': 'کد', 'className': 'py-1 border'},
        {'name': 'invoice_code', 'visible': True, 'className': 'py-1 border'},
        {'name': 'customer_code', 'visible': True, 'className': 'py-1 border'},
        {'name': 'customer_name', 'visible': True, 'className': 'py-1 border', 'title': 'نام مشتری'},
        {'name': 'register_date', 'visible': True, 'className': 'py-1 border', 'title': 'تاریخ ثبت(میلادی)'},
        {'name': 'jalali_register_date', 'visible': True, 'searchable': False, 'orderable': False,
         'title': 'تاریخ ثبت(شمسی)', 'className': 'py-1 border'},
        # all invisible field must be end of config
        {'name': 'id', 'visible': True, },
    ]

    def get_initial_queryset(self, request=None):
        param = self.request.POST.get('q', 'submit').strip('/')
        qs = self.model.get_all(param)
        return qs

    # def render_row_details(self, pk, request=None):
    #     return super().render_row_details(pk, request)

        # print(html)
        # return html
        # pass


class ImeiRegDatatableView(AjaxDatatableView):
    model = IMEIListReg
    title = 'imei_reg'
    # initial_order = [["row", "asc"], ]
    length_menu = [[25, 50, 100, -1], [25, 50, 100, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'

    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'row', 'visible': True, 'title': 'row', 'className': 'py-1 border', },
        {'name': 'IMEI', 'visible': True, 'title': 'IMEI', 'className': 'py-1 border'},
        {'name': 'main_box', 'visible': True, 'title': 'main box', 'className': 'py-1 border'},
        {'name': 'internal_box', 'visible': True, 'title': 'internal box', 'className': 'py-1 border'},
        {'name': 'version', 'visible': True, 'title': 'version', 'className': 'py-1 border'},
        # all invisible field must be end of config
    ]

    def get_initial_queryset(self, request=None):
        obj = IMEIListReg.objects.filter(id=self.kwargs.get('id')).first()
        qs = self.model.get_related(obj)
        return qs


def icon(request):
    return render(request, 'components/icons/icons-feather.html')
