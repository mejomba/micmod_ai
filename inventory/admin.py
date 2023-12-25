from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from .models import Receipt, ReceiptDetail
from files.models import Image, File


class Image1Admin(GenericTabularInline):
    model = Image
    fields = ['path', 'alt']


class Image2Admin(GenericTabularInline):
    model = Image
    fields = ['path', 'alt']


class Filee1Admin(GenericTabularInline):
    model = File
    fields = ['path']


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    inlines = [Image1Admin]


@admin.register(ReceiptDetail)
class ReceiptAdmin(admin.ModelAdmin):
    inlines = [Image1Admin, Image2Admin, Filee1Admin]
