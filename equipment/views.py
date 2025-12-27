from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .models import Equipment
from maintenance.models import MaintenanceRequest


@login_required
@require_http_methods(["GET"])
def equipment_detail(request, equipment_id):
    """
    Display equipment detail page with Smart Button.
    Shows open request count (New + In Progress).
    """
    equipment = get_object_or_404(Equipment, id=equipment_id)
    open_count = equipment.get_open_request_count()
    
    context = {
        'equipment': equipment,
        'open_count': open_count,
    }
    return render(request, 'equipment/detail.html', context)


@login_required
@require_http_methods(["GET"])
def equipment_maintenance_list(request, equipment_id):
    """
    Show all maintenance requests for a specific equipment.
    Filtered list view for Smart Button action.
    """
    equipment = get_object_or_404(Equipment, id=equipment_id)
    requests = MaintenanceRequest.objects.filter(equipment=equipment).select_related(
        'assigned_technician', 'assigned_team'
    ).order_by('-created_at')
    
    context = {
        'equipment': equipment,
        'requests': requests,
    }
    return render(request, 'equipment/maintenance_list.html', context)
