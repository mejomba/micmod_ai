from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from core.models import BaseModel


class ChangeLog(BaseModel):
    ACTION = ((1, 'create'), (2, 'update'), (3, 'delete'))
    content_type = models.ForeignKey(ContentType, on_delete=models.DO_NOTHING)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    action = models.SmallIntegerField(choices=ACTION, null=True, blank=True)
    diff_json = models.JSONField(null=True, blank=True)

    # old_json = models.JSONField(null=True, blank=True)
    # new_json = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f'{self.content_type.app_label}.{self.content_type.model}.{self.object_id}'

    @classmethod
    def get_last_log(cls, obj):
        try:
            print(cls.objects.filter(object_id=obj.id).order_by('id').last().id)
        except Exception:
            pass
        return cls.objects.filter(object_id=obj.id).order_by('id').last()

    @classmethod
    def log(cls, obj):
        pass

    @classmethod
    def get_log(cls, obj):
        try:
            content_type = ContentType.objects.filter(model=obj._meta.model_name, app_label=obj._meta.app_label).first()
            return cls.objects.filter(object_id=obj.id, content_type=content_type).order_by('pk')
        except Exception as e:
            print('error: ', __file__, e.__traceback__.tb_lineno, e)
        return None
        # qs = cls.objects.filter(object_id=obj.id).order_by('pk')
        # res = []
        # for idx in range(len(qs)):
        #     if idx < len(qs) - 1:
        #         res.append((qs[idx], qs[idx+1]))
        # return res

    def compare(self, obj, excluded_keys=None):
        if excluded_keys is None:
            excluded_keys = list()
        excluded_keys.extend(['created_date', 'last_update_date'])
        return self._compare(self, obj, excluded_keys)

    def _compare(self, log_obj, new_obj, excluded_keys):
        log, new = log_obj.__dict__.get('diff_json').get('fields'), new_obj.__dict__
        print('log: ', log)
        print("new: ", new)
        diff = {'fields': {}}
        for k, v in new.items():
            if k in excluded_keys:
                continue
            try:
                if v != log[k][1]:
                    diff['fields'].update({k: [log[k][1], v]})
            except KeyError as e:
                print('key error: ', e)
            except IndexError as e:
                print('index error: ', e)
                diff['fields'].update({k: [log[k], v]})
            except TypeError as e:
                print('type error: ', e)

            print('*'*33)
            print(diff)

        return diff
