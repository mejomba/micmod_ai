from django.urls import path
from . import editor_views as views

app_name = 'scheduling'
urlpatterns = [
    path('',views.index,name='index'),
    path('history/<str:kind>/<int:document_id>/',views.history,name='history'),
    path('<int:pk>/',views.detail,name='detail'),
    path('<int:pk>/clone/',views.clone,name='clone'),
    path('<int:pk>/publish/',views.publish,name='publish'),
    path('<int:pk>/refresh-open/',views.refresh_open,name='refresh_open'),
    path('<int:pk>/preview/',views.preview,name='preview'),
    path('<int:pk>/edit/<str:kind>/',views.edit,name='add'),
    path('<int:pk>/edit/<str:kind>/<int:row_id>/',views.edit,name='edit'),
    path('<int:pk>/remove/<str:kind>/<int:row_id>/',views.remove,name='remove'),
]
