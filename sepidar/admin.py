from django.contrib import admin
from .models import Dl,Device,APILogs
# Register your models here.

admin.site.register([Dl,Device,APILogs])