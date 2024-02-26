import uuid

from django.contrib.auth import get_user_model
from django.db import models, router
from django.contrib.contenttypes.models import ContentType
import json
import importlib
from django import forms
from django.db.models.deletion import Collector
from django.db.models.sql.constants import GET_ITERATOR_CHUNK_SIZE
from django.forms import fields_for_model

# from _core.forms import CustomBaseModelForm
from _core.middleware import get_request
# from _files.models import File
from tools.utils import elapsed_time
from django.db.models import Q
# from _account.models import User
from collections import Counter, defaultdict
from functools import partial, reduce
from itertools import chain
from operator import attrgetter, or_

from django.db import IntegrityError, connections, models, transaction
from django.db.models import query_utils, signals, sql


# from accounts.models import User

from translator import get_text as _
from tools.utils import show_error
from django.contrib.contenttypes.fields import GenericRelation
from django.db.models.sql.query import Query


class CustomCollector(Collector):

    def delete(self):
        # sort instance collections
        for model, instances in self.data.items():

            self.data[model] = sorted(instances, key=attrgetter("pk"))

        # if possible, bring the models in an order suitable for databases that
        # don't support transactions or cannot defer constraint checks until the
        # end of a transaction.
        self.sort()
        # number of objects deleted for each model label
        deleted_counter = Counter()

        # Optimize for the case with a single obj and no dependencies
        if len(self.data) == 1 and len(instances) == 1:
            instance = list(instances)[0]
            if self.can_fast_delete(instance):
                if not getattr(instance,'safe_delete', None):
                    with transaction.mark_for_rollback_on_error(self.using):
                        count = sql.DeleteQuery(model).delete_batch(
                            [instance.pk], self.using
                        )
                    setattr(instance, model._meta.pk.attname, None)
                    return count, {model._meta.label: count}
                else:
                    instance.is_deleted = True
                    return 1, {model._meta.label: 1}

        with transaction.atomic(using=self.using, savepoint=False):
            # send pre_delete signals
            for model, obj in self.instances_with_model():
                if not model._meta.auto_created:
                    signals.pre_delete.send(
                        sender=model,
                        instance=obj,
                        using=self.using,
                        origin=self.origin,
                    )

            # fast deletes
            for qs in self.fast_deletes:
                if not getattr(model,'safe_delete', None):
                    count = qs._raw_delete(using=self.using)
                else:
                    try:
                        count = qs.update(is_deleted=True)
                    except Exception as e:
                        show_error(e, __file__)
                if count:
                    deleted_counter[qs.model._meta.label] += count

            # update fields
            for (field, value), instances_list in self.field_updates.items():
                updates = []
                objs = []
                for instances in instances_list:
                    if (
                            isinstance(instances, models.QuerySet)
                            and instances._result_cache is None
                    ):
                        updates.append(instances)
                    else:
                        objs.extend(instances)
                if updates:
                    combined_updates = reduce(or_, updates)
                    combined_updates.update(**{field.name: value})
                if objs:
                    model = objs[0].__class__
                    query = sql.UpdateQuery(model)
                    query.update_batch(
                        list({obj.pk for obj in objs}), {field.name: value}, self.using
                    )

            # reverse instance collections
            for instances in self.data.values():
                instances.reverse()

            # delete instances
            for model, instances in self.data.items():
                if not getattr(model,'safe_delete', None):
                    query = sql.DeleteQuery(model)
                    pk_list = [obj.pk for obj in instances]
                    count = query.delete_batch(pk_list, self.using)
                else:
                    query = sql.UpdateQuery(model)
                    pk_list = [obj.pk for obj in instances]
                    count = query.update_batch(pk_list,{"is_deleted": True}, self.using)
                    # count = self.delete_batch(instances)
                if count:
                    deleted_counter[model._meta.label] += count

                if not model._meta.auto_created:
                    for obj in instances:
                        signals.post_delete.send(
                            sender=model,
                            instance=obj,
                            using=self.using,
                            origin=self.origin,
                        )

        for model, instances in self.data.items():
            if not getattr(model,'safe_delete', None):
                for instance in instances:
                    setattr(instance, model._meta.pk.attname, None)
        return sum(deleted_counter.values()), dict(deleted_counter)

    @staticmethod
    def delete_batch(query, pk_list):
        """
        Set up and execute delete queries for all the objects in pk_list.

        More than one physical query may be executed if there are a
        lot of values in pk_list.
        """
        # number of objects deleted
        # num_deleted = 0
        # for instance in instances:
        #     try:
        #         instance.is_deleted = True
        #         instance.save()
        #         num_deleted += 1
        #     except Exception as e:
        #         err_log(e,__file__)
        # return num_deleted

        num_deleted = 0
        field = model.get_meta().pk
        for offset in range(0, len(pk_list), GET_ITERATOR_CHUNK_SIZE):
            model.clear_where()
            self.add_filter(
                f"{field.attname}__in",
                pk_list[offset: offset + GET_ITERATOR_CHUNK_SIZE],
            )
            num_deleted += self.up
        return num_deleted


class ExtraData(object):
    ...


class BaseManager(models.Manager):
    # is_public = False
    def __init__(self):
        super().__init__()

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class NoUserBaseModel(models.Model):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.extra_data = ExtraData()

    auto_complete = False
    is_public = False
    excluded_keys = list()
    template_name_list = ''
    # form_class = CustomBaseModelForm
    created_date = models.DateTimeField(_('create_date'), auto_now_add=True)
    last_update_date = models.DateTimeField(_('last_update_date'), auto_now=True)

    is_deleted = models.BooleanField(default=False, verbose_name=_('is_deleted'))
    safe_delete = True

    comments = GenericRelation('_comments.Like', related_query_name="parent_object")
    likes = GenericRelation('_comments.Comment', related_query_name="parent_object")
    files = GenericRelation('_files.File', related_query_name="parent_object")
    file_groups = GenericRelation('_files.FileGroup', related_query_name="parent_object")
    notifications = GenericRelation('_notifications.Messages', related_query_name="parent_object")
    workflows = GenericRelation('_workflows.WorkFlow', related_query_name="parent_object")
    change_logs = GenericRelation('_change_logs.ChangeLog', related_query_name="parent_object")



    objects = BaseManager()

    form_structure = None
    form = None
    base_fields = None
    _fields = None

    def delete(self, using=None, keep_parents=False):
        if self.pk is None:
            raise ValueError(
                "%s object can't be deleted because its %s attribute is set "
                "to None." % (self._meta.object_name, self._meta.pk.attname)
            )
        using = using or router.db_for_write(self.__class__, instance=self)
        collector = CustomCollector(using=using, origin=self)
        collector.collect([self], keep_parents=keep_parents)

        return collector.delete()

    @classmethod
    def get_base_fields(cls):
        if cls.base_fields:
            return cls.base_fields
        else:
            cls.base_fields = [field.name for field in cls._meta.fields if field.editable and not field.primary_key ]
            return cls.base_fields
    @classmethod
    def get_fields(cls, fields=None):
        if not cls._fields:
            cls._fields = fields_for_model(cls, cls.get_base_fields())
        result = dict()
        for field in fields:
            result[field] = cls._fields.get(field)
        return result

    @classmethod
    def get_form(cls, *args, **kwargs):
        if cls.form:
            return cls.form
        else:
            cls.form = importlib.import_module(f'_core.forms').CustomBaseModelForm #(model=cls, *args, **kwargs)
            return cls.form

    def get_view_forms(self, request, *args, **kwargs):
        form_structure = self.get_form_structure()
        if request.META['REQUEST_METHOD'] == 'POST':
            kwargs['data'] = request.POST
        else:
            data = request.GET
            for key, value in data.items():
                if getattr(self, key, None):
                    setattr(self, key, value)
        kwargs['instance'] = self
        form = self._get_view_forms(form_structure, request, *args, **kwargs)
        if form:
            return form[0]

    @staticmethod
    def _get_view_forms(form_structure, request, *args, **kwargs):
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
                if form and getattr(form,"._meta"):
                    model = form._meta.model
            elif item.get('model'):
                if instance and item.get("model") == "this":
                    model = instance._meta.model
                else:
                    app_label, model_name = item.get("model").split(".")
                    model_module = importlib.import_module(f'{app_label}.models')
                    model = getattr(model_module, model_name, None)
                form = model.get_form()
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
            elif method == "POST":
                if relation_field:
                    kwargs['data']._mutable = True
                    kwargs['data'][f"{kwargs['prefix']}-{relation_field}"] = str(instance.pk)
                    kwargs['data']._mutable = False
                    kwargs['instance'] = model.objects.filter(**{relation_field:instance}).first()
                form = form(model=model, fields=item.get("fields"), *args, **kwargs)
            form.instance.extra_data.request = request
            if relation_field:
                form.change_hidden([relation_field])
            if item.get("forms"):
                form.forms = NoUserBaseModel._get_view_forms(item.get("forms"), request, *args, **kwargs)
            forms.append(form)

        return forms

    def pre_process_on_get_method(self, data=None):
        ...

    def pre_process_on_post_method(self, data=None):
        ...

    @classmethod
    def get_form_structure(cls):
        if cls.form_structure:
            return cls.form_structure
        else:
            return [
                {"model": "this",}
            ]
# """
#     only one of form or model must be assigned
#     rel must be assigned in child form and formsets
#     model may assign as this
#     form_structure = [
#         {"form":"app_label.form_name",
#          "model":"app_label.model_name",
#          "fields":{"enabled":["f1","f2",...], disabled:["__all__"], hidden:["f1",...]},
#          "forms":[list of forms],
#          "formsets":[
#               {"form":"app_label.form_name",
#                "model":"app_label.model_name",
#                "fields":{"enabled":["f1","f2",...], disabled:["__all__"], hidden:["f1",...]},
#                "clone":["f1",...],
#                "rel":"f1",
#                "is_formset":True,"max_record":None, "min_record":0, "extra_record":1,
#                "forms":[list of forms],
#                "formsets":[list of formsets],
#               }
#              ],
#          }
#     ]
# """

    def __str__(self):
        if self.auto_complete:
            return getattr(self, self.auto_complete)
        return super().__str__()

    class Meta:
        abstract = True
        ordering = ['-created_date']


    @property
    def elapsed_time(self):
        return elapsed_time(self.created_date)

    def save_file(self, request, file_groups, file_model, obj, form_idx=0, *args, **kwargs):
        input_prefix = kwargs.get('input_prefix')
        fk = kwargs.get('fk')

        for i in range(file_groups):
            if input_prefix:
                file_input_name = f'{input_prefix}_{i+1}'
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
                file_input_name = f'{related_name}-{form_idx}-file_{i+1}'
            files = request.FILES.getlist(file_input_name)

            for file in files:
                file_model.objects.create(path=file, content_object=obj, group=i+1)


    def compare(self, old_obj=None, excluded_keys=None):
        if excluded_keys is None:
            excluded_keys = list()
        excluded_keys.extend(['created_date', 'last_update_date','editor_user', '_state', 'extra_data'])

        diff = {'fields': dict()}
        new, old = self.__dict__, old_obj.__dict__ if old_obj else dict()
        for k, v in new.items():
            if k in excluded_keys:
                continue
            if v != old.get(k):
                diff['fields'][k] = v
        return diff

    def save_log(self):
        if self._meta.app_label == '_change_logs':
            return
        if self.pk:
            obj = self._meta.model.objects.filter(pk=self.pk).first()
            action = 2
        else:
            obj = None
            action = 1
        diff = self.compare(obj)
        obj_s = json.dumps(diff, default=str)
        obj_struct = json.loads(obj_s)
        if obj_struct['fields']:
            creator_user = self.extra_data.request.user if getattr(self.extra_data,'request', None) else None
            return {'diff_json': obj_struct, 'action': action, 'creator_user': creator_user}
        else:
            return None

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        change_log = self.save_log()
        super().save(force_insert=force_insert, force_update=force_update, using=using, update_fields=update_fields)
        if change_log:
            self.change_logs.create(**change_log)


    @staticmethod
    def attach_image_file(obj, form=None):
        """attach image and file field to obj if exist"""
        content_type = ContentType.objects.filter(app_label=obj._meta.app_label,
                                                  model=obj._meta.model_name,
                                                  ).first()
        if form is None or (form.image_groups and form.file_groups):
            # images = list(Image.objects.filter(content_type=content_type, object_id=obj.id))
            files = list(File.objects.filter(content_type=content_type, object_id=obj.id))
            # obj.images = images
            obj.files = files
        elif form.image_groups:
            ...
            # images = list(Image.objects.filter(content_type=content_type, object_id=obj.id))
            # obj.images = images
        elif form.file_groups:
            files = list(File.objects.filter(content_type=content_type, object_id=obj.id))
            obj.files = files
        return obj


class AbsBaseModel(NoUserBaseModel):
    creator_user = models.ForeignKey('_account.User', on_delete=models.DO_NOTHING, null=True, blank=True, related_name='%(app_label)s_creator_%(model_name)s',
                                     verbose_name=_('creator_user'), )
    editor_user = models.ForeignKey('_account.User', on_delete=models.DO_NOTHING, null=True, blank=True, related_name='%(app_label)s_updator_%(model_name)s',
                                    verbose_name=_('updator_user'))

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        self.save_user()
        super().save(force_insert=force_insert, force_update=force_update, using=using, update_fields=update_fields)

    def save_user(self, user=None, commit=False):
        try:
            if not user and getattr(self.extra_data, 'request', None):
                user = self.extra_data.request.user
            if self.creator_user:
                self.editor_user = user
            else:
                self.creator_user = user
                self.editor_user = user
            if commit:
                self.save()
        except Exception as e:
            err_log(e,__file__)

    class Meta:
        abstract = True


class BaseModel(AbsBaseModel):
    code = models.CharField(_('code'), max_length=30, null=True, blank=True)
    title = models.CharField(max_length=50, blank=True, null=True, verbose_name=_('m-title'))
    group = models.IntegerField(_('group'), default=1)

    class Meta:
        abstract = True
