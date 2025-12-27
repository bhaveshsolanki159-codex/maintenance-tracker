from django.shortcuts import render
from maintenance.models import MaintenanceRequest


def maintenance_dashboard(request):
    requests = MaintenanceRequest.objects.select_related("equipment", "team", "assigned_technician")
    return render(request, "frontend/maintenance_dashboard.html", {"requests": requests})
