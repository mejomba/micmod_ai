import uuid

from django.contrib.auth import get_user_model
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
import json

# from comments.models import Comments
from files.models import File, Image
from tools.utils import elapsed_time
from django.db.models import Q
from accounts.models import User


# from accounts.models import User

from translator import get_text as _
from django.contrib.contenttypes.fields import GenericRelation

class ExtraData(object):
    ...

class BaseManager(models.Manager):
    # is_public = False
    def __init__(self, is_public=False):
        super().__init__()
        self.is_public = is_public

    def get_queryset(self):
        if self.is_public:
            # print('================ public', self.model.objects)
            return super().get_queryset().filter(is_deleted=False).order_by('-last_update_date')
        else:
            user = get_user_model().objects.filter(pk=1)
            # return self.get_access_object(user)

            # print('================ private', self.model.objects)
        return super().get_queryset().filter(is_deleted=False)

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

    def get_access_object(self, user,q="all"):
        from workflow.models import WorkFlow
        if user.is_superuser:
            return self.model.objects.all()
        content_type = ContentType.objects.filter(model=self.model._meta.model_name, app_label=self.model._meta.app_label).first()

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
        if obj and q == 'active':
            content_type = ContentType.objects.filter(model=obj._meta.model_name, app_label=obj._meta.app_label).first()
            for item in qry:
                wf = WorkFlow.objects.filter(object_id=obj.id, content_type=content_type).order_by('id').last()
                if wf.to_user == user:
                    quotations_record_lst.append(item)
        else:
            quotations_record_lst = qry

        return quotations_record_lst



class NoUserBaseModel(models.Model):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.extra_data = ExtraData()
    created_date = models.DateTimeField(_('create_date'), auto_now_add=True)
    last_update_date = models.DateTimeField(_('last_update_date'), auto_now=True)

    is_deleted = models.BooleanField(default=False, verbose_name=_('is_deleted'))

    # object_uid = models.UUIDField(verbose_name=_("object_uid"), default=uuid.uuid4, unique=True)

    auto_complete = False
    is_public = False

    workflows = GenericRelation('workflow.Workflow',related_query_name="parent_object_wf")
    notifications = GenericRelation('notifications.Messages',related_query_name="parent_object_no")

    objects = BaseManager()



    def __str__(self):
        if self.auto_complete:
            return getattr(self, self.auto_complete)
        return super().__str__()

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
                image_input_name = f'{input_prefix}_{i+1}'
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
                image_input_name = f'{related_name}-{form_idx}-image_{i+1}'
            alt_input_name = f''
            images = request.FILES.getlist(image_input_name)
            alt = request.POST.get(alt_input_name)

            if alt:
                try:
                    alt = alt.split('-')
                    if len(alt) < len(images):
                        alt.extend([''] * (len(images) - len(alt)))
                except Exception as e:
                    print('error: ',  e.__traceback__.tb_lineno, e)
                    alt = [''] * len(images)
            else:
                alt = [''] * len(images)

            for idx, image in enumerate(images):
                image_model.objects.create(path=image, content_object=obj, group=i+1, alt=alt[idx])

    """***NEW***"""

    def save_comment(self, request, idx=None):
        from comments.models import Comments
        title = request.POST.get('comment_title')
        comment_input_name = f'comment_{idx}' if idx is not None else 'comment_'
        content = request.POST.get(comment_input_name)
        contenttype = ContentType.objects.get_for_model(self._meta.model)
        #
        # comment_input_name = f'{input_prefix}_{idx+1}'
        # comments = request.POST.get(comment_input_name)
        #
        # for idx, comment in enumerate(comments):
        #     comment_model.objects.create(title=title,
        #                                  content=content,
        #                                  contenttype=contenttype,
        #                                  object_id=self.pk,
        #                                  content_object=comment,
        #                                  )

        comment = Comments.objects.create(comment_title=title,
                                comment_content=content,
                                contenttype=contenttype,
                                object_id=self.pk,
                                )

        comment.save_user(request)

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

        addition.save_user(request=request)

    """***NEW***"""
    def compare(self, obj=None, excluded_keys=None):
        if excluded_keys is None:
            excluded_keys = list()
        excluded_keys.extend(['created_date', 'last_update_date', '_state'])
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
                    print('TypeError: ',  e.__traceback__.tb_lineno, e)
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

    def save_log(self, request, obj, old=None, action=None):
        content_type = ContentType.objects.filter(app_label=obj._meta.app_label,
                                                  model=obj._meta.model_name
                                                  ).first()

        if old:
            diff = self.compare(old)
        else:
            diff = self.compare()

        obj_s = json.dumps(diff, default=str)
        obj_struct = json.loads(obj_s)

        from changelog.models import ChangeLog
        if obj_struct['fields']:
            ch = ChangeLog.objects.create(content_type=content_type,
                                          object_id=obj.id,
                                          diff_json=obj_struct,
                                          action=action
                                          )
            ch.save_user(request)

    @staticmethod
    def attach_image_file(obj, form=None):
        """attach image and file field to obj if exist"""
        content_type = ContentType.objects.filter(app_label=obj._meta.app_label,
                                                  model=obj._meta.model_name,
                                                  ).first()
        if form is None or (form.image_groups and form.file_groups):
            images = list(Image.objects.filter(content_type=content_type, object_id=obj.id))
            files = list(File.objects.filter(content_type=content_type, object_id=obj.id))
            obj.images = images
            obj.files = files
        elif form.image_groups:
            images = list(Image.objects.filter(content_type=content_type, object_id=obj.id))
            obj.images = images
        elif form.file_groups:
            files = list(File.objects.filter(content_type=content_type, object_id=obj.id))
            obj.files = files
        return obj


class AbsBaseModel(NoUserBaseModel):
    creator_user = models.ForeignKey(User, on_delete=models.DO_NOTHING, null=True, blank=True, related_name='%(app_label)s_creator_%(model_name)s',
                                     verbose_name=_('creator_user'), )
    editor_user = models.ForeignKey(User, on_delete=models.DO_NOTHING, null=True, blank=True, related_name='%(app_label)s_updator_%(model_name)s',
                                    verbose_name=_('updator_user'))

    def save_user(self, request):
        try:
            if self.creator_user:
                self.editor_user = request.user
            else:
                self.creator_user = request.user
                self.editor_user = request.user
            self.save()
        except Exception as e:
            print('error: ',  e.__traceback__.tb_lineno, e)

    class Meta:
        abstract = True


class BaseModel(AbsBaseModel):
    code = models.CharField(_('code'), max_length=30, null=True, blank=True)
    title = models.CharField(max_length=50, blank=True, null=True, verbose_name=_('m-title'))
    group = models.IntegerField(_('group'), default=1)

    class Meta:
        abstract = True


class BaseContentType(AbsBaseModel):
    contenttype = models.ForeignKey(ContentType, on_delete=models.DO_NOTHING)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('contenttype', 'object_id')

    as_table = 'templates/core/partial/table.html'
    as_list = 'templates/core/partial/list.html'

    class Meta:
        abstract = True

