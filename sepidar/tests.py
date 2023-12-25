import datetime
import os
import time

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dason.settings")

import django
django.setup()

from sepidar.models import Dl,Item

if __name__ == '__main__':
    t = datetime.datetime.now()
    items = Item.get_items('cap',2355)
    k = len(items)
    d = (datetime.datetime.now()-t).microseconds
    print(f'{k}-{d}')
    for item in items:
        print(item.__dict__)