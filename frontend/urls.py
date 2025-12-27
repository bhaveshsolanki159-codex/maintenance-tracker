from django.urls import path
from . import views

urlpatterns = [
    path("maintenance/", views.maintenance_dashboard, name="frontend-maintenance-dashboard"),
]
