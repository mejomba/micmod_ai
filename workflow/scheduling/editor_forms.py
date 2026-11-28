"""Bounded draft editor forms. All identifiers are scoped to a policy version."""
from datetime import date
import math
from django import forms
from django.core.exceptions import ValidationError
from .configuration import normalize_condition
from .engine import SchedulingError
from .models import (WorkflowSchedulePolicy, WorkflowCalendar, WorkflowCalendarException,
    WorkflowStageTiming, WorkflowTimingRule, WorkflowScheduleTransition)

LABELS = {
    'name': ('عنوان', 'Name'), 'description': ('توضیحات', 'Description'),
    'code': ('شناسه تقویم', 'Calendar code'), 'timezone': ('منطقه زمانی', 'Timezone'),
    'working_weekdays': ('روزهای کاری هفته', 'Working weekdays'),
    'date': ('تاریخ میلادی', 'Gregorian date'), 'is_working_day': ('روز کاری است', 'Working day'),
    'is_active': ('فعال', 'Active'), 'default_duration': ('مدت استاندارد (روز)', 'Standard duration (days)'),
    'calendar': ('تقویم', 'Calendar'), 'remaining_time_strategy': ('روش محاسبه باقی‌مانده', 'Remaining time'),
    'overdue_duration': ('مدت اضافه در تأخیر (روز)', 'Overdue extension (days)'),
    'stage': ('مرحله', 'Stage'), 'stage_timing': ('مرحله', 'Stage'),
    'condition_json': ('شرط', 'Condition'), 'priority': ('اولویت', 'Priority'),
    'operation': ('اثر قانون', 'Effect'), 'duration': ('مدت (روز)', 'Duration (days)'),
    'duration_field': ('متغیر مدت', 'Duration field'), 'effect_calendar': ('تقویم اثر', 'Effect calendar'),
    'source': ('مبدأ مسیر', 'Source'), 'target': ('مقصد مسیر', 'Target'),
    'route_mode': ('نوع مسیر', 'Route mode'), 'effective_from': ('زمان اعتبار نسخه', 'Effective from'),
    'document_id': ('شناسه سند واقعی', 'Real document ID'),
}
FIELD_NAMES = {'has_price_inquiry': 'استعلام قیمت دارد', 'production_lead_time': 'زمان تولید',
               'shipment_type': 'روش حمل مؤثر', 'gio_weight_kg': 'وزن مؤثر GIO (kg)'}
OPS = [('set_duration','تعیین مدت','Set duration'), ('add_duration','افزایش مدت','Add duration'),
       ('add_field_duration','افزودن مقدار متغیر','Add field duration'),
       ('set_calendar','تغییر تقویم','Set calendar'), ('skip_stage','صرف‌نظر از مرحله در پیش‌بینی','Skip forecast stage')]
MODES = [('MARK_INCOMPLETE','ناقص','Mark incomplete'), ('BLOCK_FORECAST','مسدود','Block forecast'),
         ('USE_DEFAULT','مقدار پیش‌فرض','Use default'), ('USE_SCENARIOS','سناریوها','Use scenarios')]


def label_field(key, field, fa):
    return FIELD_NAMES.get(key, field.label) if fa else field.label


def stage_choices(binding, fa):
    # Labels are supplied by the operational registry when available; keys remain stable.
    from order.scheduling_rules import ORDER_STAGES, PACKING_STAGES
    labels = {w + '.' + key: label for w, rows in [('order', ORDER_STAGES), ('packing', PACKING_STAGES)]
              for key, label, _ in rows}
    return [(s, labels.get(s, s) + ' (' + s + ')' if fa else s) for s in sorted(binding.stages)]


def style(form, fa):
    for name, field in form.fields.items():
        if name in LABELS:
            field.label = LABELS[name][0 if fa else 1]
        widget = field.widget
        if isinstance(widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
            continue
        if not widget.is_hidden:
            widget.attrs['class'] = 'form-select form-select-sm' if isinstance(widget, forms.Select) else 'form-control form-control-sm'
    return form


class CalendarForm(forms.ModelForm):
    working_weekdays = forms.TypedMultipleChoiceField(coerce=int, widget=forms.CheckboxSelectMultiple)
    class Meta:
        model = WorkflowCalendar
        fields = ('name', 'code', 'timezone', 'working_weekdays', 'is_active')

    def __init__(self, *args, fa=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['working_weekdays'].choices = list(enumerate(
            ('دوشنبه','سه‌شنبه','چهارشنبه','پنجشنبه','جمعه','شنبه','یکشنبه') if fa else
            ('Mon','Tue','Wed','Thu','Fri','Sat','Sun')))


class ExceptionForm(forms.ModelForm):
    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))
    class Meta:
        model = WorkflowCalendarException
        fields = ('calendar', 'date', 'is_working_day', 'description')


class StageForm(forms.ModelForm):
    stage = forms.ChoiceField()
    class Meta:
        model = WorkflowStageTiming
        fields = ('stage', 'default_duration', 'calendar', 'remaining_time_strategy',
                  'overdue_duration', 'is_active')

    def __init__(self, *args, policy, binding, fa=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['stage'].choices = stage_choices(binding, fa)
        self.fields['calendar'].queryset = policy.calendars.order_by('code')
        if self.instance.pk:
            self.initial['stage'] = self.instance.workflow_key + '.' + self.instance.stage_key
        self.policy = policy

    def clean(self):
        data = super().clean()
        if data.get('stage'):
            self.instance.workflow_key, self.instance.stage_key = data['stage'].split('.', 1)
            if self.policy.stage_timings.filter(workflow_key=self.instance.workflow_key,
                stage_key=self.instance.stage_key).exclude(pk=self.instance.pk).exists():
                self.add_error('stage', 'Stage already exists.')
        return data


class ConditionForm(forms.ModelForm):
    def _update_errors(self, errors):
        # Model.clean() can report errors on computed model fields that are
        # deliberately absent from this editor (e.g. effect_json, target_stage).
        # Django would otherwise raise ValueError from add_error().
        if hasattr(errors, 'error_dict'):
            mapped = {}
            for key, items in errors.error_dict.items():
                mapped.setdefault(key if key in self.fields else '__all__', []).extend(items)
            errors = ValidationError(mapped)
        return super()._update_errors(errors)

    condition_json = forms.JSONField(required=False, widget=forms.HiddenInput)

    def clean_condition_json(self):
        raw = self.cleaned_data['condition_json']
        raw = {} if raw is None else raw
        try:
            normalize_condition(raw, self.binding)
        except (SchedulingError, ValueError, TypeError, KeyError) as exc:
            raise ValidationError(str(exc)) from exc
        return raw


class RuleForm(ConditionForm):
    operation = forms.ChoiceField()
    duration = forms.IntegerField(min_value=0, max_value=36600, required=False)
    duration_field = forms.ChoiceField(required=False)
    effect_calendar = forms.ChoiceField(required=False)

    class Meta:
        model = WorkflowTimingRule
        fields = ('stage_timing', 'name', 'description', 'condition_json', 'priority', 'is_active')

    def __init__(self, *args, policy, binding, fa=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.binding = binding
        self.fields['stage_timing'].queryset = policy.stage_timings.order_by('workflow_key','stage_key')
        self.fields['stage_timing'].label_from_instance = lambda obj: obj.workflow_key + '.' + obj.stage_key
        self.fields['operation'].choices = [(op, f if fa else e) for op, f, e in OPS]
        self.fields['duration_field'].choices = [('', '—')] + [(key,label_field(key,field,fa)) for key,field in binding.fields.items() if field.kind == 'number']
        self.fields['effect_calendar'].choices = [('', '—')] + list(policy.calendars.values_list('code','name'))
        effect = self.instance.effect_json or {}
        self.initial.update(operation=effect.get('operation','set_duration'),
                            duration=effect.get('value'), duration_field=effect.get('field'),
                            effect_calendar=effect.get('calendar'))

    def clean(self):
        data = super().clean()
        op = data.get('operation')
        effect = {'operation': op}
        if op in ('set_duration', 'add_duration'):
            if data.get('duration') is None:
                self.add_error('duration','Required for this operation.')
            else:
                effect['value'] = data['duration']
        if op == 'add_field_duration':
            if not data.get('duration_field'):
                self.add_error('duration_field','Required for this operation.')
            else:
                effect['field'] = data['duration_field']
        if op == 'set_calendar' and not data.get('effect_calendar'):
            self.add_error('effect_calendar','Required for this operation.')
        if op != 'skip_stage' and data.get('effect_calendar'):
            effect['calendar'] = data['effect_calendar']
        self.instance.effect_json = effect
        return data


class TransitionForm(ConditionForm):
    source = forms.ChoiceField()
    target = forms.ChoiceField()
    class Meta:
        model = WorkflowScheduleTransition
        fields = ('source','target','condition_json','priority','is_active')

    def __init__(self, *args, policy, binding, fa=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.binding = binding
        choices = stage_choices(binding, fa)
        self.fields['source'].choices = choices
        self.fields['target'].choices = choices
        if self.instance.pk:
            self.initial.update(source=self.instance.source_workflow + '.' + self.instance.source_stage,
                                target=self.instance.target_workflow + '.' + self.instance.target_stage)

    def clean(self):
        data = super().clean()
        if data.get('source') and data.get('target'):
            self.instance.source_workflow, self.instance.source_stage = data['source'].split('.',1)
            self.instance.target_workflow, self.instance.target_stage = data['target'].split('.',1)
        return data


class PolicyForm(forms.ModelForm):
    class Meta:
        model = WorkflowSchedulePolicy
        fields = ('name','description','route_mode')


def parse_value(raw, spec):
    if spec.kind == 'number':
        value = float(raw)
        if not math.isfinite(value):
            raise ValueError('Invalid number')
        if value.is_integer():
            value = int(value)
    elif spec.kind == 'boolean':
        if raw not in ('true','false'):
            raise ValueError('Use true or false')
        value = raw == 'true'
    elif spec.kind == 'date':
        value = date.fromisoformat(raw)
    else:
        value = raw
    if not spec.accepts(value):
        raise ValueError('Invalid choice')
    return value.isoformat() if isinstance(value,date) else value


class UnknownForm(forms.Form):
    def __init__(self, *args, policy, binding, fa=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.binding = binding
        for key, spec in binding.fields.items():
            old = policy.unknown_policies.get(key, {})
            title = label_field(key,spec,fa)
            values = old.get('values', [old['value']] if 'value' in old else [])
            self.fields['mode_' + key] = forms.ChoiceField(label=title, choices=[(m,f if fa else e) for m,f,e in MODES],
                initial=old.get('mode','MARK_INCOMPLETE'))
            self.fields['value_' + key] = forms.CharField(label=title + (' — مقدار / مقادیر' if fa else ' — value(s)'),
                required=False, max_length=1000, initial=', '.join(str(v).lower() if isinstance(v,bool) else str(v) for v in values),
                help_text='سناریوها با کاما جدا شوند؛ true/false برای بولین' if fa else 'Comma-separated scenarios; true/false for boolean.')

    def clean(self):
        data = super().clean()
        config = {}
        for key,spec in self.binding.fields.items():
            mode = data.get('mode_' + key)
            if not mode:
                continue
            entry = {'mode':mode}
            if mode in ('USE_DEFAULT','USE_SCENARIOS'):
                try:
                    raw = data.get('value_' + key,'')
                    values = [parse_value(v.strip(),spec) for v in raw.split(',') if v.strip()]
                    if mode == 'USE_DEFAULT' and len(values) != 1 or mode == 'USE_SCENARIOS' and not 1 <= len(values) <= 16:
                        raise ValueError('Invalid number of values')
                    entry['value' if mode == 'USE_DEFAULT' else 'values'] = values[0] if mode == 'USE_DEFAULT' else values
                except (ValueError,OverflowError):
                    self.add_error('value_' + key,'Invalid value or count.')
            config[key] = entry
        self.config = config
        return data

def condition_summary(node, binding, fa):
    if not node:
        return 'همیشه' if fa else 'Always'
    if not isinstance(node, dict):
        return 'شرط نامعتبر' if fa else 'Invalid condition'
    if 'and' in node or 'or' in node:
        key = 'and' if 'and' in node else 'or'
        join = (' و ' if key == 'and' else ' یا ') if fa else (' AND ' if key == 'and' else ' OR ')
        return '(' + join.join(condition_summary(c,binding,fa) for c in node[key]) + ')'
    if 'not' in node:
        return ('نه ' if fa else 'NOT ') + '(' + condition_summary(node['not'],binding,fa) + ')'
    key = node.get('field','?')
    field = binding.fields.get(key)
    title = label_field(key,field,fa) if field else key
    operators = {'eq':'=', 'ne':'≠', 'gt':'>', 'gte':'≥', 'lt':'<', 'lte':'≤',
                 'in':'در مجموعه' if fa else 'in', 'not_in':'خارج مجموعه' if fa else 'not in',
                 'is_null':'نامشخص' if fa else 'is unknown', 'is_not_null':'مشخص' if fa else 'is known'}
    op = node.get('operator','?')
    if op in ('is_null','is_not_null'):
        return title + ' ' + operators[op]
    value = node.get('value')
    def value_label(v):
        if v is None:
            return 'نامشخص' if fa else 'Unknown'
        if isinstance(v,bool):
            return ('بله' if v else 'خیر') if fa else ('Yes' if v else 'No')
        if fa and key == 'shipment_type':
            return {'air':'هوایی','sea':'دریایی','road':'زمینی','rail':'ریلی'}.get(v,str(v))
        return str(v)
    value = ', '.join(value_label(v) for v in value) if isinstance(value,list) else value_label(value)
    return title + ' ' + operators.get(op,op) + ' ' + value


def effect_summary(effect, binding, fa):
    op = effect.get('operation','?')
    title = next((f if fa else e for key,f,e in OPS if key==op),op)
    parts = [title]
    if 'value' in effect:
        parts.append(str(effect['value']) + (' روز' if fa else ' days'))
    if 'field' in effect:
        key=effect['field']
        field=binding.fields.get(key)
        parts.append(label_field(key,field,fa) if field else key)
    if effect.get('calendar'):
        parts.append(str(effect['calendar']))
    return ' · '.join(parts)
