from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from workflow.models import FlowAdminGroup

from django.conf import settings
import json


class Command(BaseCommand):
    help = 'initial FlowAdmin object from json file'

    def handle(self, *args, **kwargs):
        config_dir = settings.BASE_DIR / 'dason/config_json/flow_admin_group.json'
        print(f'use config file from  <{config_dir}>')
        with open(config_dir, 'r', encoding='utf-8') as jf:
            data = json.load(jf)
            for d in data.values():
                group_name = d['group_name']
                group_rel = Group.objects.filter(name=d['group_rel']).first()
                group_child = Group.objects.filter(name__in=d['group_child'])
                if FlowAdminGroup.objects.filter(group_name=group_name).exists():
                    continue
                obj = FlowAdminGroup.objects.create(group_name=group_name, group_rel=group_rel)
                obj.save()
                for g in group_child:
                    obj.group_child.add(g)
                print(f'create object  <{obj}>')
            print('Done')
