from django.shortcuts import render
from .models import MaintenanceRequest

def kanban_board(request):
    new_requests = MaintenanceRequest.objects.filter(status="New")
    in_progress_requests = MaintenanceRequest.objects.filter(status="In Progress")
    repaired_requests = MaintenanceRequest.objects.filter(status="Repaired")
    scrap_requests = MaintenanceRequest.objects.filter(status="Scrap")

    columns = [
        ("New", new_requests),
        ("In Progress", in_progress_requests),
        ("Repaired", repaired_requests),
        ("Scrap", scrap_requests),
    ]

    context = {
        "columns": columns
    }

    return render(request, "maintenance/kanban.html", context)
