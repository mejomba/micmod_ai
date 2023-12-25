from django.urls import path
from .views import DeleteSingleImage, DeleteSingleFile


app_name = 'files'

urlpatterns = [
    path('image/delete/single/<int:pk>/', DeleteSingleImage.as_view(), name='delete_single_image'),
    path('file/delete/single/<int:pk>/', DeleteSingleFile.as_view(), name='delete_single_file')
]