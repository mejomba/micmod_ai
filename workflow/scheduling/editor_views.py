"""Portal scheduling settings. All writes use the parent policy row lock."""
from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import get_language
from django.views.decorators.http import require_http_methods, require_POST

from .configuration import normalize_condition
from .engine import SchedulingError
from .registry import registry
from .scheduler import compile_policy, publish_configured_policy
from .policies import clone_policy
from .models import (WorkflowSchedulePolicy, WorkflowCalendar, WorkflowCalendarException,
                     WorkflowStageTiming, WorkflowTimingRule, WorkflowScheduleTransition)
from .editor_forms import (CalendarForm, ExceptionForm, StageForm, RuleForm, TransitionForm,
                           PolicyForm, UnknownForm, label_field, style, condition_summary, effect_summary)

VIEW = 'workflow.view_workflowschedulepolicy'
RESOURCES = {
    'calendar': (WorkflowCalendar, CalendarForm, 'policy'),
    'exception': (WorkflowCalendarException, ExceptionForm, 'calendar__policy'),
    'stage': (WorkflowStageTiming, StageForm, 'policy'),
    'rule': (WorkflowTimingRule, RuleForm, 'stage_timing__policy'),
    'transition': (WorkflowScheduleTransition, TransitionForm, 'policy'),
}


def _fa(request):
    from order.forecast_presentation import is_farsi
    return is_farsi(request)


def _require(request, perm):
    if not request.user.is_active or not request.user.has_perm(perm):
        raise PermissionDenied


def _policy(request, pk, lock=False):
    _require(request, VIEW)
    qs = WorkflowSchedulePolicy.objects.select_for_update() if lock else WorkflowSchedulePolicy.objects.all()
    return get_object_or_404(qs, pk=pk)


def _draft(policy):
    if policy.status != 'draft':
        raise PermissionDenied('Published policies are read-only. Clone to edit.')


def _permit(user, model, action):
    return user.has_perm('workflow.%s_%s' % (action, model._meta.model_name))


def _resources(policy, kind):
    model, _, lookup = RESOURCES[kind]
    return model.objects.filter(**{lookup:policy}).order_by('pk')


def _error(exc):
    return '; '.join(exc.messages) if isinstance(exc,ValidationError) else str(exc)


@login_required
@require_http_methods(['GET'])
def index(request):
    _require(request, VIEW)
    from django.core.paginator import Paginator
    qs = WorkflowSchedulePolicy.objects.order_by('workflow_key','code','-version')
    workflow = request.GET.get('workflow')
    if workflow:
        qs = qs.filter(workflow_key=workflow)
    return render(request,'workflow/scheduling/index.html', {'page':Paginator(qs,30).get_page(request.GET.get('page')),
        'workflows': WorkflowSchedulePolicy.objects.order_by('workflow_key').values_list('workflow_key',flat=True).distinct(),
        'selected':workflow, 'fa':_fa(request)})


def _detail(request, policy, **extra):
    binding = registry.by_key(policy.workflow_key)
    sections = []
    fa = _fa(request)
    for kind, (model, _, _) in RESOURCES.items():
        qs = _resources(policy,kind)
        if kind == 'stage':
            qs = qs.select_related('calendar')
        if kind == 'rule':
            qs = qs.select_related('stage_timing')
        if kind == 'exception':
            qs = qs.select_related('calendar')
        rows = list(qs)
        for item in rows:
            if kind in ('rule','transition'):
                item.display_condition = condition_summary(item.condition_json,binding,fa)
            if kind == 'rule':
                item.display_effect = effect_summary(item.effect_json,binding,fa)
        sections.append({'kind':kind,'rows':rows,'add':policy.status=='draft' and _permit(request.user,model,'add'),
                         'edit':policy.status=='draft' and _permit(request.user,model,'change'),
                         'delete':policy.status=='draft' and _permit(request.user,model,'delete')})
    from .policies import select_policy
    eligible = select_policy(policy.workflow_key,policy.code)
    can_refresh = bool(eligible and eligible.pk==policy.pk and policy.code=='central-arrival'
        and policy.workflow_key in ('order','packing') and request.user.has_perm('workflow.publish_schedule_policy'))
    return render(request,'workflow/scheduling/detail.html',dict(policy=policy,sections=sections,fa=fa,can_refresh=can_refresh,
        can_edit=policy.status=='draft' and request.user.has_perm('workflow.change_workflowschedulepolicy'),
        can_publish=policy.status=='draft' and request.user.has_perm('workflow.publish_schedule_policy'),
        can_clone=request.user.has_perm('workflow.add_workflowschedulepolicy'),
        versions=WorkflowSchedulePolicy.objects.filter(workflow_key=policy.workflow_key,code=policy.code).order_by('-version'),
        **extra))


@login_required
@require_http_methods(['GET'])
def detail(request,pk):
    return _detail(request,_policy(request,pk))


@login_required
@require_POST
def clone(request,pk):
    policy = _policy(request,pk)
    draft = clone_policy(policy.pk,user=request.user)
    return redirect('scheduling:detail',pk=draft.pk)


@login_required
@require_http_methods(['GET','POST'])
def edit(request,pk,kind,row_id=None):
    if kind not in (*RESOURCES,'policy','unknown'):
        raise Http404
    with transaction.atomic():
        policy = _policy(request,pk,lock=True)
        _draft(policy)
        binding = registry.by_key(policy.workflow_key)
        fa = _fa(request)
        data = request.POST if request.method == 'POST' else None
        if kind == 'unknown':
            _require(request,'workflow.change_workflowschedulepolicy')
            form = UnknownForm(data,policy=policy,binding=binding,fa=fa)
        elif kind == 'policy':
            _require(request,'workflow.change_workflowschedulepolicy')
            form = PolicyForm(data,instance=policy)
        else:
            model, cls, parent = RESOURCES[kind]
            _require(request,'workflow.%s_%s' % ('change' if row_id else 'add',model._meta.model_name))
            obj = get_object_or_404(_resources(policy,kind),pk=row_id) if row_id else model()
            if parent == 'policy':
                obj.policy = policy
            kwargs = {'policy':policy,'binding':binding,'fa':fa} if kind in ('stage','rule','transition') else {'fa':fa} if kind=='calendar' else {}
            form = cls(data,instance=obj,**kwargs)
            if kind=='exception':
                form.fields['calendar'].queryset = policy.calendars.order_by('code')
        style(form,fa)
        if request.method == 'POST' and form.is_valid():
            try:
                with transaction.atomic():
                    if kind=='unknown':
                        policy.unknown_policies = form.config
                        policy.full_clean()
                        policy.save(update_fields=['unknown_policies'])
                    else:
                        obj = form.save(commit=False)
                        obj.full_clean()
                        obj.save()
                return redirect('scheduling:detail',pk=pk)
            except (IntegrityError,ValidationError) as exc:
                form.add_error(None, _error(exc) if isinstance(exc,ValidationError) else 'Duplicate or invalid configuration.')
        meta = [{'key':key,'label':label_field(key,spec,fa),'kind':spec.kind,'choices':list(spec.choices)}
                for key,spec in binding.fields.items()]
        return render(request,'workflow/scheduling/edit.html', {'policy':policy,'kind':kind,'form':form,'fa':fa,
            'field_metadata':meta,'condition_editor':kind in ('rule','transition')})


@login_required
@require_POST
@transaction.atomic
def remove(request,pk,kind,row_id):
    if kind not in RESOURCES:
        raise Http404
    policy = _policy(request,pk,lock=True)
    _draft(policy)
    model = RESOURCES[kind][0]
    _require(request,'workflow.delete_' + model._meta.model_name)
    obj = get_object_or_404(_resources(policy,kind),pk=row_id)
    try:
        with transaction.atomic():
            obj.delete()
    except IntegrityError:
        return _detail(request,policy,error='This configuration is referenced and cannot be deleted.')
    return redirect('scheduling:detail',pk=pk)


@login_required
@require_POST
def publish(request,pk):
    policy = _policy(request,pk)
    _require(request,'workflow.publish_schedule_policy')
    _draft(policy)
    try:
        effective = forms.DateTimeField(required=False).clean(request.POST.get('effective_from') or None)
        publish_configured_policy(pk,user=request.user,effective_from=effective)
    except (ValidationError,SchedulingError,ValueError,TypeError) as exc:
        return _detail(request,policy,error=_error(exc))
    return redirect('scheduling:detail',pk=pk)


@login_required
@require_POST
def preview(request,pk):
    policy = _policy(request,pk)
    _require(request,'workflow.view_workflowforecast')
    from order.models import Order,Packing
    from order.scheduling_adapters import forecast_order_arrival,forecast_packing_arrival
    try:
        document_id = forms.IntegerField(min_value=1).clean(request.POST.get('document_id'))
        if policy.workflow_key == 'order':
            _require(request,'order.view_order')
            instance = get_object_or_404(Order.objects.get_access_object(request.user,lst=False),pk=document_id)
            if request.user.base_group=='mac' and instance.buy_operator!='mac' and instance.pay_operator!='mac':
                raise PermissionDenied
            result = forecast_order_arrival(instance,policy=policy)
        elif policy.workflow_key == 'packing':
            _require(request,'order.view_packing')
            instance = get_object_or_404(Packing.objects,pk=document_id)
            if not instance.user_can_view_workflow(request.user):
                raise PermissionDenied
            result = forecast_packing_arrival(instance,policy=policy)
        else:
            raise ValidationError('No real-document preview adapter registered.')
    except (ValidationError,SchedulingError,ValueError,TypeError) as exc:
        return _detail(request,policy,error=_error(exc))
    return _detail(request,policy,preview_result=result,preview_id=document_id)

 
@login_required
@require_http_methods(['GET'])
def history(request,kind,document_id):
    _require(request,'workflow.view_workflowforecast')
    from order.models import Order,Packing
    from order.forecast_presentation import revision_summary
    from .models import WorkflowForecast
    from django.contrib.contenttypes.models import ContentType
    from django.core.paginator import Paginator
    from order.scheduling_rules import TARGET
    if kind == 'order':
        _require(request,'order.view_order')
        instance = get_object_or_404(Order.objects.get_access_object(request.user,lst=False),pk=document_id)
        if request.user.base_group=='mac' and instance.buy_operator!='mac' and instance.pay_operator!='mac':
            raise PermissionDenied
    elif kind == 'packing':
        _require(request,'order.view_packing')
        instance = get_object_or_404(Packing.objects,pk=document_id)
        if not instance.user_can_view_workflow(request.user):
            raise PermissionDenied
    else:
        raise Http404
    qs = WorkflowForecast.objects.filter(content_type=ContentType.objects.get_for_model(instance),
        object_id=document_id,target_stage=TARGET,target_event='exit').order_by('-revision')
    page = Paginator(qs,25).get_page(request.GET.get('page'))
    fa = _fa(request)
    selected = None
    if request.GET.get('revision'):
        revision = forms.IntegerField(min_value=1)
        try:
            number = revision.clean(request.GET['revision'])
        except ValidationError as exc:
            raise Http404 from exc
        selected = get_object_or_404(qs,revision=number)
    from order.forecast_presentation import panel_context
    selected_panel = panel_context(instance,kind,request.user,fa,revision=selected) if selected else None
    return render(request,'order/scheduling/history.html',dict(page=page,
        rows=[revision_summary(r,fa) for r in page],fa=fa,kind=kind,document_id=document_id,selected_panel=selected_panel))


@login_required
@require_POST
def refresh_open(request,pk):
    policy = _policy(request,pk)
    _require(request,'workflow.publish_schedule_policy')
    from .policies import select_policy
    from order.scheduling_queue import enqueue_sweep
    from order.scheduling_rules import POLICY_CODE
    effective = select_policy(policy.workflow_key,policy.code)
    if policy.code != POLICY_CODE or policy.workflow_key not in ('order','packing') or not effective or effective.pk != pk:
        raise PermissionDenied('Only the latest currently effective operational policy may be applied.')
    count = enqueue_sweep('policy_upgrade',latest_policy=True,workflow_key=policy.workflow_key)
    return _detail(request,policy,refresh_count=count)
