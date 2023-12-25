from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DeleteView, View

from .models import Image, File


class DeleteSingleImage(LoginRequiredMixin, DeleteView):
    model = Image
    success_url = '/'

    def form_valid(self, form):
        try:
            self.get_object().delete()
            data = {'detail': 'ok'}
        except Exception as e:
            data = {'detail': 'err'}
        return JsonResponse(data)


class DeleteSingleFile(LoginRequiredMixin, DeleteView):
    model = File
    success_url = '/'

    def form_valid(self, form):
        try:
            self.get_object().delete()
            data = {'detail': 'ok'}
        except Exception as e:
            data = {'detail': 'err'}
        return JsonResponse(data)


class FileHandleView:
    SaveFile = None
    SaveImage = None
    obj = None

    @staticmethod
    def save_image(request, image_groups, image_model, obj, form_idx=1, *args, **kwargs):
        # print('save image')
        input_prefix = kwargs.get('input_prefix', 'image')
        for i in range(1, image_groups + 1):
            # print(f'{input_prefix}_{i}_{form_idx}')
            images = request.FILES.getlist(f'{input_prefix}_{i}_{form_idx}')
            # print(images)
            alt = request.POST.get(f'{input_prefix}_{i}_alt')
            if alt:
                try:
                    alt = alt.split('-')
                    if len(alt) < len(images):
                        alt.extend([''] * (len(images) - len(alt)))
                    # print(alt)
                except Exception as e:
                    print(e)
                    alt = [''] * len(images)
            else:
                alt = [''] * len(images)
            for idx, image in enumerate(images):
                image_model.objects.create(path=image, content_object=obj, group=i, alt=alt[idx])

    @staticmethod
    def save_files(request, file_groups, file_model, obj, form_idx=1, *args, **kwargs):
        input_prefix = kwargs.get('input_prefix', 'file')
        for i in range(1, file_groups + 1):
            files = request.FILES.getlist(f'{input_prefix}_{i}_{form_idx}')
            for file in files:
                file_model.objects.create(path=file, content_object=obj, group=i)

    @staticmethod
    def save_image2(request, image_groups, image_model, obj, form_idx=0, *args, **kwargs):
        # print('save image')
        input_prefix = kwargs.get('input_prefix')

        for i in range(image_groups):
            if input_prefix:
                # image_input_name = f'{input_prefix}_{i+1}_{form_idx+1}'
                image_input_name = f'{input_prefix}_{i+1}'
            else:
                image_input_name = f'{obj._meta.model_name}_set-{form_idx}-image_{i+1}'

            alt_input_name = f''
            images = request.FILES.getlist(image_input_name)
            alt = request.POST.get(alt_input_name)

            if alt:
                try:
                    alt = alt.split('-')
                    if len(alt) < len(images):
                        alt.extend([''] * (len(images) - len(alt)))
                except Exception as e:
                    print(e)
                    alt = [''] * len(images)
            else:
                alt = [''] * len(images)

            for idx, image in enumerate(images):
                image_model.objects.create(path=image, content_object=obj, group=i+1, alt=alt[idx])

    @staticmethod
    def save_files2(request, file_groups, file_model, obj, form_idx=0, *args, **kwargs):
        input_prefix = kwargs.get('input_prefix')

        for i in range(file_groups):
            if input_prefix:
                # file_input_name = f'{input_prefix}_{i+1}_{form_idx+1}'
                file_input_name = f'{input_prefix}_{i+1}'
            else:
                file_input_name = f'{obj._meta.model_name}_set-{form_idx}-file_{i+1}'

            files = request.FILES.getlist(file_input_name)

            for file in files:
                file_model.objects.create(path=file, content_object=obj, group=i+1)
