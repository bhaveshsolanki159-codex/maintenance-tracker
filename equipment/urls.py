from django.urls import path
from . import views

app_name = 'equipment'

urlpatterns = [
    path('<int:equipment_id>/', views.equipment_detail, name='detail'),
    path('<int:equipment_id>/maintenance/', views.equipment_maintenance_list, name='maintenance_list'),
]
