import importlib
import uuid

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.forms import generic_inlineformset_factory
from django.core import serializers
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
import json

from django.forms import fields_for_model
from django.utils import timezone

# from comments.models import Comments
# from files.models import File, Image
from tools.utils import elapsed_time, to_jalali_date
from django.db.models import Q
from accounts.models import User
from tools.utils import c_get as c_get
from workflow.models import WorkFlow

# from accounts.models import User

from translator import get_text as _
from django.contrib.contenttypes.fields import GenericRelation
from django.apps import apps


from tools import utils
from django.db.models.query import QuerySet

class ExtraData(object):
    ...


class QuerysetManager(QuerySet):
    def update(self, **kwargs):
        super(QuerysetManager, self).update(**kwargs)


class BaseManager(models.Manager):
    # is_public = False
    def __init__(self, is_public=False):
        super().__init__()
        self.is_public = is_public

    def get_for_update(self):
        return QuerysetManager(self.model, using=self._db)

    def full_queryset(self, *args, **kwargs):
        qs = self._queryset_class(model=self.model, using=self._db, hints=self._hints)
        return qs.filter(*args, **kwargs)

    def get_query_set(self):
        ...

    def get_queryset(self):
        qs = super().get_queryset().filter(is_deleted=False)
        # qs = qs.extra(select={"work_flow_status": f"select max(id) from workflow_workflow where object_id=id and content_type_id={self.model.content_type().id} group by object_id,content_type_id"})
        if self.is_public:
            # print('================ public', self.model.objects)
            return qs.order_by('-last_update_date')
        else:
            user = get_user_model().objects.filter(pk=1)
            # return self.get_access_object(user)

            # print('================ private', self.model.objects)
        return qs.order_by('-last_update_date')

    # def get_target_user_from_group(group, level=1):
    #     from workflow.models import FlowAdminGroup
    #     from django.contrib.auth import get_user_model
    #     print('group: ', group)
    #     qs = get_user_model().objects.filter(pk=-1)
    #     if level > 1:
    #         qs |= group.user_set.all()
    #         print(qs)
    #     for g in FlowAdminGroup.objects.filter(group_rel=group):
    #         for gc in g.group_child.all():
    #             qs |= BaseManager.get_target_user_from_group(gc, level + 1)
    #     print('qs before return ', qs)
    #     return qs

    # from tools.utils import get_target_users
    # from accounts.models import User
    # x = User.objects.get(username='u2')
    # get_target_users(x)

    # @staticmethod
    # def get_target_users(user):
    #     from django.contrib.auth import get_user_model
    #     user_qs = get_user_model().objects.filter(id=user.id)
    #     for main_user_group in user.groups.all():
    #         user_qs |= BaseManager.get_target_user_from_group(main_user_group)
    #     print('user_list  > ', user_qs)
    #     return user_qs
    #
    # @staticmethod
    # def get_target_wf(user):
    #     from workflow.models import WorkFlow
    #     user_list = BaseManager.get_target_users(user)
    #     wf = WorkFlow.objects.filter(id=-1)
    #     for user in user_list:
    #         wf |= WorkFlow.objects.filter(
    #             Q(creator_user=user) |
    #             Q(editor_user=user) |
    #             Q(from_user=user) |
    #             Q(to_user=user)
    #         )
    #     return wf

    def get_access_object(self, user, q="all", *args, **kwargs):
        import time
        from workflow.models import WorkFlow
        if user.is_superuser or self.is_public:
            return self.model.objects.all()
        content_type = ContentType.objects.filter(model=self.model._meta.model_name,
                                                  app_label=self.model._meta.app_label).first()

        # wfs = BaseManager.get_target_wf(user)
        wfs = user.get_target_wf()
        object_id_from_flow = wfs.filter(content_type=content_type).values_list('object_id', flat=True)

        # user_list = user.get_target_users(user)
        user_list = user.get_target_users()
        objects_from_user = self.model.objects.filter(
            Q(creator_user__in=user_list) |
            Q(editor_user__in=user_list)
        )
        objects_from_flow = self.model.objects.filter(pk__in=object_id_from_flow)

        qry = objects_from_user | objects_from_flow
        quotations_record_lst = []
        obj = qry.first()
        # user_team = user.team.all()
        if obj and q == 'active':
            content_type = ContentType.objects.filter(model=obj._meta.model_name, app_label=obj._meta.app_label).first()
            for item in qry:
                wf = WorkFlow.objects.filter(object_id=item.id, content_type=content_type).order_by('id').last()
                if wf and (wf.to_user == user):
                    quotations_record_lst.append(item)
        else:
            quotations_record_lst = qry

        if kwargs.get('quotation') and q == 'active':
            return [x for x in quotations_record_lst if not x.sepidar_number and not x.cancel]
        else:
            return [x for x in quotations_record_lst if x]

        return quotations_record_lst


class BaseModelAuto:
    __fields = None
    base_fields = []
    excluded_fields = []
    form_structures = []
    form_class = None
    safe_delete = True
    excluded_keys = list()
    template_name_list = ''
    WorkFlowForms = None
    extra_prefix = ''
    form_crispy = False
    form_label = 'on-border'
    css_class = 'row row-cols5'
    field_groups = []

    def get_workflow_forms(self):
        if not self.WorkFlowForms:
            from workflow.models import WorkFlow
            self.__class__.WorkFlowForms = generic_inlineformset_factory(WorkFlow, extra=1, can_delete=False)
        self.workflows_forms = self.WorkFlowForms(instance=self)
        return self.workflows_forms

    def __init__(self, *args, **kwargs):
        self.active_form_structure_index = 0
        self.serialized_ = None
        self.workflows_forms = None
        self.excluded_fields += ['created_date', 'last_update_date', 'is_deleted', 'creator_user', 'editor_user']

    @property
    def serialized(self):
        return json.loads(serializers.serialize('json', [self]))

    def get_base_fields(self):
        if self.base_fields:
            return self.base_fields
        else:
            self.base_fields = [field.name for field in self._meta.fields if field.editable and not field.primary_key]
            self.base_fields = list(set(self.base_fields)
                                    - set(self.excluded_fields)
                                    - {'creator_user', 'editor_user', 'group', 'is_deleted'}
                                    )
            self.base_fields.sort()
            return self.base_fields

    def get_fields(self, fields=None):
        if fields is None:
            fields = []
        if not self.__fields:
            self.__fields = fields_for_model(self.__class__, self.get_base_fields())
        result = dict()
        for field in fields:
            result[field] = self.__fields.get(field)
        return result

    def get_form(self, *args, **kwargs):
        return self.get_form_class()(model=self.__class__, fields=None, *args, **kwargs)

    def get_form_class(self, *args, **kwargs):
        if self.form_class:
            return self.form_class
        else:
            self.form_class = importlib.import_module(f'core.forms').CustomBaseModelFormAuto  # (model=cls, *args, **kwargs)
            return self.form_class

    def get_view_forms(self, request, *args, **kwargs):
        form_structure = self.get_form_structure(self.active_form_structure_index)
        if request.META['REQUEST_METHOD'] == 'POST':
            kwargs['data'] = request.POST
        else:
            data = request.GET
            for key, value in data.items():
                if getattr(self, key, 'NUN') != 'NUN':
                    setattr(self, key, value)
        kwargs['instance'] = self
        self.kwargs = kwargs
        self.args = args
        forms = self.__get_view_forms(form_structure, request, *args, **kwargs)
        if forms:
            return forms[0]

    def __get_view_forms(self, form_structure, request, *args, **kwargs):
        forms = list()
        method = request.META['REQUEST_METHOD']
        instance = kwargs.get("instance")
        prefix = kwargs.get("prefix")
        # get child forms based form_structure
        for item in form_structure:
            form = None
            extra_prefix = (item.get("form") or item.get("model") or '').replace('.', "_")
            relation_field = item.get("rel")
            kwargs['prefix'] = f"{prefix + '_' if prefix else ''}{extra_prefix}"
            # get form based form_structure
            if item.get("form"):
                app_label, form_name = item.get("form").split(".")
                form_module = importlib.import_module(f'{app_label}.forms')
                form = getattr(form_module, form_name, None)
                model = getattr(form, "._meta", None)
            elif item.get('model'):
                if instance and item.get("model") == "this":
                    model = instance._meta.model
                else:
                    app_label, model_name = item.get("model").split(".")
                    model_module = importlib.import_module(f'{app_label}.models')
                    model = getattr(model_module, model_name, None)
                if not instance:
                    instance = model()
                form = instance.get_form_class()
            form.form_structure = form_structure
            # update instance data of form
            if method == "GET" and getattr(form, "_meta", None):
                if relation_field:
                    form_instance = model.objects.filter(**{relation_field: instance}).first() or model()
                else:
                    form_instance = instance or model() if model else None
                if form_instance and item.get("clone"):
                    for key in item.get("clone"):
                        value = getattr(instance, key, None)
                        if value and getattr(form_instance, key, None):
                            setattr(form_instance, key, value)
                kwargs['instance'] = form_instance
                form = form(model=model, fields=item.get("fields"), *args, **kwargs)
                form.instance.pre_process_on_get_method()
            elif method == "POST":
                if relation_field:
                    kwargs['data']._mutable = True
                    kwargs['data'][f"{kwargs['prefix']}-{relation_field}"] = str(instance.pk)
                    kwargs['data']._mutable = False
                    kwargs['instance'] = model.objects.filter(**{relation_field: instance}).first()
                form = form(model=model, fields=item.get("fields"), *args, **kwargs)
                form.is_valid()
                form.instance.pre_process_on_post_method()
            form.instance.extra_data.request = request
            if relation_field:
                form.change_hidden([relation_field])
            if item.get("forms"):
                form.forms = self.__get_view_forms(item.get("forms"), request, *args, **kwargs)
            forms.append(form)

        return forms

    def pre_process_on_get_method(self, data=None):
        ...

    def pre_process_on_post_method(self, data=None):
        ...

    def get_form_structure(self, index=0):
        if self.form_structures:
            return self.form_structures[index]
        else:
            return [
                {"model": "this", "form": None,
                 "fields": {"enabled": ["__all__"], "disabled": [], "hidden": []},
                 "field_groups": [],
                 "forms": []}
            ]


class BaseFunctions():
    def log_error(self, e):
        print('error: ', e.__traceback__.tb_lineno, e)

class NoUserBaseModel(models.Model, BaseModelAuto, BaseFunctions):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.extra_data = ExtraData()

    def content_type(self):
        return ContentType.objects.get_for_model(self)

    created_date = models.DateTimeField(_('create_date'), auto_now_add=True)
    last_update_date = models.DateTimeField(_('last_update_date'), auto_now=True)

    is_deleted = models.BooleanField(default=False, verbose_name=_('is_deleted'))

    # object_uid = models.UUIDField(verbose_name=_("object_uid"), default=uuid.uuid4, unique=True)

    auto_complete = False
    insert_new = True
    absolute_url_create = None
    absolute_url_update = None
    absolute_url_delete = None
    absolute_url_view = None

    def auto_complete_func(self):
        ...

    is_public = False

    workflows = GenericRelation('workflow.Workflow', related_query_name="parent_object_wf")
    has_workflow = False
    notifications = GenericRelation('notifications.Messages', related_query_name="parent_object_no")
    change_logs = GenericRelation('changelog.ChangeLog', related_query_name="parent_object_no")
    comments = GenericRelation('comments.Comments', related_query_name="parent_object_no")
    images = GenericRelation('files.Image', related_query_name="parent_object_no")
    files = GenericRelation('files.File', related_query_name="parent_object_no")
    submit_copy = False
    objects = BaseManager()

    def get_content_type_forms(self):
        self.content_type_forms = list()
        if self.has_workflow:
            self.content_type_forms.append(self.workflows.model.form_class)

    def __str__(self):
        if self.auto_complete:
            return getattr(self, self.auto_complete)
        return super().__str__()

    def progress_from_create_date(self, total_hour=72):
        return utils.progress_value(self.created_date, timezone.now(), total_hour)

    @classmethod
    def content_type(cls):
        return ContentType.objects.get(model=cls.__name__.lower(), app_label=cls._meta.app_label.lower())

    @classmethod
    def all_workflows(cls):
        from workflow.models import WorkFlow
        # return WorkFlow.objects.filter(content_type=cls.content_type())
        cls.workflows = GenericRelation('workflow.Workflow', related_query_name="mooo")

    def set_public(self):
        self.objects.is_public = True

    def class_name(self):
        return f'{self.__class__}'

    class Meta:
        abstract = True
        ordering = ['-created_date']

    @property
    def elapsed_time(self):
        return elapsed_time(self.created_date)

    @property
    def jalali_last_update_date(self):
        return to_jalali_date(self.last_update_date)

    @property
    def formatted_last_update_date(self):
        return self.last_update_date.__format__('D:%Y %b %d')

    @staticmethod
    def save_file(request, file_groups, file_model, obj, form_idx=0, *args, **kwargs):
        """
        save file for related object (main model in `file` app)
        arg:
            request: user request
            file_groups = number of file groups
            file_model = file model ref
            obj = related object for save as contentType
            form_idx = form index for get html input name

        kwargs:
            input_prefix = for main form input name
            fk = in formset represent if parent form fk has related_name
        """
        input_prefix = kwargs.get('input_prefix')
        fk = kwargs.get('fk')

        for i in range(file_groups):
            if input_prefix:
                file_input_name = f'{input_prefix}_{i + 1}'
            else:
                # try:
                #     if fk:
                #         related_name = obj._meta.get_field(fk).related_query_name()
                #     else:
                #         related_name = f'{obj._meta.model_name}_set'
                # except Exception as e:
                #     related_name = f'{obj._meta.model_name}_set'
                #     print('error: ',  e.__traceback__.tb_lineno, e)
                related_name = fk
                file_input_name = f'{related_name}-{form_idx}-file_{i + 1}'
            files = request.FILES.getlist(file_input_name)

            for file in files:
                file_model.objects.create(path=file, content_object=obj, group=i + 1)

    @staticmethod
    def save_image(request, image_groups, image_model, obj, form_idx=0, *args, **kwargs):
        """
        save image for related object (main model in `file` app)
        arg:
            request: user request
            image_groups = number of image groups
            image_model = image model ref
            obj = related object for save as contentType
            form_idx = form index for get html input name

        kwargs:
            input_prefix = for main form input name
            fk = in formset represent if parent form fk has related_name
        """
        input_prefix = kwargs.get('input_prefix')  # main form
        fk = kwargs.get('fk')  # form foreign key has related name

        for i in range(image_groups):
            if input_prefix:
                image_input_name = f'{input_prefix}_{i + 1}'
            else:
                # try:
                #     if fk:
                #         related_name = obj._meta.get_field(fk).related_query_name()
                #     else:
                #         related_name = f'{obj._meta.model_name}_set'
                # except Exception as e:
                #     related_name = f'{obj._meta.model_name}_set'
                #     print(e)
                related_name = fk
                image_input_name = f'{related_name}-{form_idx}-image_{i + 1}'
            alt_input_name = f''
            images = request.FILES.getlist(image_input_name)
            alt = request.POST.get(alt_input_name)

            if alt:
                try:
                    alt = alt.split('-')
                    if len(alt) < len(images):
                        alt.extend([''] * (len(images) - len(alt)))
                except Exception as e:
                    print('error: ', e.__traceback__.tb_lineno, e)
                    alt = [''] * len(images)
            else:
                alt = [''] * len(images)

            for idx, image in enumerate(images):
                image_model.objects.create(path=image, content_object=obj, group=i + 1, alt=alt[idx])

    """***NEW***"""

    def save_comment(self, request, idx=None):
        from comments.models import Comments
        app_label = self._meta.app_label
        model_name = self._meta.model_name
        ctt_id = ContentType.objects.get_for_model(self._meta.model).pk
        obj_id = self.pk
        title = request.POST.get(f'{app_label}__{model_name}__{ctt_id}__{obj_id}-comment_title')
        image_prefix = f'{app_label}__{model_name}__{ctt_id}__{obj_id}-image'
        file_prefix = f'{app_label}__{model_name}__{ctt_id}__{obj_id}-file'
        comment_input_name = f'{app_label}__{model_name}__{ctt_id}__{obj_id}-comment_content'
        content = request.POST.get(comment_input_name)
        content_type = ContentType.objects.get_for_model(self._meta.model)
        if title in ['C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'P'] and not content:
            content = 'بدون توضیحات'


        if content:
            comment = Comments.objects.create(
                comment_title=title,
                comment_content=content,
                content_type=content_type,
                object_id=self.pk,
                creator_user=request.user,
                editor_user=request.user,
                # images=image,
                # files=file
            )
            comment.save_image(
                request=request,
                image_groups=1,
                image_model=comment.images.model,
                obj=comment,
                input_prefix=image_prefix,
            )
            comment.save_file(
                request=request,
                file_groups=1,
                file_model=comment.files.model,
                obj=comment,
                input_prefix=file_prefix,
            )

    """***NEW***"""

    """***NEW***"""

    def save_additions(self, request):
        from additions.models import Additions
        from micmod_base.base import Currency

        addition_title = request.POST.get('addition_title')
        addition_description = request.POST.get('addition_description')
        addition_count = request.POST.get('addition_count')
        addition_currency = request.POST.get('addition_currency')
        currency = Currency.objects.get(pk=int(addition_currency))
        contenttype = ContentType.objects.get_for_model(self._meta.model)

        addition = Additions.objects.create(addition_title=addition_title,
                                            addition_description=addition_description,
                                            addition_count=addition_count,
                                            addition_currency=currency,
                                            contenttype=contenttype,
                                            object_id=self.pk,
                                            )
        addition.extra_data.request = request
        addition.save()
        # addition.save_user(request=request)

    """***NEW***"""

    def compare(self, excluded_keys=None):
        obj = self._meta.model.objects.full_queryset().get(pk=self.pk) if self.pk else None
        if excluded_keys is None:
            excluded_keys = list()
        excluded_keys.extend(['created_date', 'last_update_date', 'editor_user',
                              '_state', 'extra_data', 'excluded_fields', 'files_', 'images_'])
        return self._compare(obj, excluded_keys)

    def _compare(self, old_obj=None, excluded_keys=None):
        diff = {'fields': {}}
        if old_obj:
            new, old = self.__dict__, old_obj.__dict__
            for k, v in new.items():
                if k in excluded_keys:
                    continue
                try:
                    if v != old[k]:
                        diff['fields'].update({k: [v, old[k]]})
                except KeyError as e:
                    print(f'key error: {k} ', e.__traceback__.tb_lineno, e)
                except TypeError as e:
                    print('TypeError: ', e.__traceback__.tb_lineno, e)
        else:
            new = self.__dict__
            old = new.copy()
            for k, v in new.items():
                if k in excluded_keys:
                    continue
                try:
                    diff['fields'].update({k: [v, old[k]]})
                except Exception as e:
                    print('error: ', e.__traceback__.tb_lineno, e)
        return diff

    def save_log(self):
        # old = self._meta.model.objects.full_queryset().get(pk=self.pk) if self.pk else None
        return self.compare()

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        action = 2 if self.pk else 1
        diff = ''
        if self._meta.app_label != 'changelog':
            diff = self.save_log()
        super().save(force_insert, force_update, using, update_fields)
        if self._meta.app_label != 'changelog':
            obj_s = json.dumps(diff, default=str)
            obj_struct = json.loads(obj_s)
            if obj_struct['fields']:
                obj = self.change_logs.create(
                                      diff_json=obj_struct,
                                      action=action)
                obj.extra_data.request = getattr(self.extra_data,'request', None)
                obj.save()

    @staticmethod
    def attach_image_file(obj, form=None):
        """attach image and file field to obj if exist"""
        # content_type = ContentType.objects.filter(app_label=obj._meta.app_label,
        #                                           model=obj._meta.model_name,
        #                                           ).first()
        if form is None or (form.image_groups and form.file_groups):
            images = obj.images#list(Image.objects.filter(content_type=content_type, object_id=obj.id))
            files = obj.files#list(File.objects.filter(content_type=content_type, object_id=obj.id))
            obj.images_ = images
            obj.files_ = files
        elif form.image_groups:
            images = obj.images#list(Image.objects.filter(content_type=content_type, object_id=obj.id))
            obj.images_ = images
        elif form.file_groups:
            files = obj.files#list(File.objects.filter(content_type=content_type, object_id=obj.id))
            obj.files_ = files
        return obj


class AbsBaseModel(NoUserBaseModel):
    creator_user = models.ForeignKey(User, on_delete=models.DO_NOTHING, null=True, blank=True,
                                     related_name='%(app_label)s_creator_%(model_name)s',
                                     verbose_name=_('creator_user'), )
    editor_user = models.ForeignKey(User, on_delete=models.DO_NOTHING, null=True, blank=True,
                                    related_name='%(app_label)s_updator_%(model_name)s',
                                    verbose_name=_('updator_user'))

    def save_user(self, request=None):
        try:
            request = request or getattr(self.extra_data,'request',None)
            if request:
                if self.creator_user:
                    self.editor_user = request.user
                else:
                    self.creator_user = request.user
                    self.editor_user = request.user
        except Exception as e:
            print('error: ', e.__traceback__.tb_lineno, e)

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        self.save_user()
        super().save(force_insert, force_update, using, update_fields)

    @classmethod
    def active(cls, user):
        return len(cls.objects.get_access_object(user, q='active')) + 1000

    class Meta:
        abstract = True


class BaseModel(AbsBaseModel):
    code = models.CharField(_('code'), max_length=30, null=True, blank=True)
    title = models.CharField(max_length=100, blank=True, null=True, verbose_name=_('m-title'))
    group = models.IntegerField(_('group'), default=1)

    class Meta:
        abstract = True


class BaseModeWF(BaseModel):
    ...
    last_work_flow = models.ForeignKey(WorkFlow, null=True, blank=True, verbose_name=_('las_work_flow'),
                                       on_delete=models.DO_NOTHING, related_name='%(app_label)s_wf_%(model_name)s')

    class Meta:
        abstract = True


class BaseContentType(AbsBaseModel, BaseModelAuto):
    content_type = models.ForeignKey(ContentType, on_delete=models.DO_NOTHING)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    def get_form(self,):
        return self.form_class

    as_table = 'templates/core/partial/table.html'
    as_list = 'templates/core/partial/list.html'

    class Meta:
        abstract = True


class BaseAbsContentType(models.Model, BaseModelAuto):
    content_type = models.ForeignKey(ContentType, on_delete=models.DO_NOTHING)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')


    as_table = 'templates/core/partial/table.html'
    as_list = 'templates/core/partial/list.html'

    class Meta:
        abstract = True
