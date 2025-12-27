from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from maintenance.models import MaintenanceRequest
from equipment.models import Equipment
from django.utils import timezone


@login_required(login_url='login')
def maintenance_dashboard(request):
    """Enhanced maintenance dashboard with user-specific statistics."""
    user = request.user
    is_manager = user.groups.filter(name='manager_group').exists()
    is_technician = user.groups.filter(name='technician_group').exists()
    
    # Get all requests with related objects
    all_requests = MaintenanceRequest.objects.select_related(
        "equipment", "team", "assigned_technician", "created_by"
    )
    
    # Filter based on user role
    if is_technician and not is_manager:
        # Technician: see only their assigned requests
        user_requests = all_requests.filter(assigned_technician=user)
    elif user.is_superuser or is_manager:
        # Manager: see all requests
        user_requests = all_requests
    else:
        # Regular user: see only requests they created
        user_requests = all_requests.filter(created_by=user)
    
    # Statistics
    stats = {
        'total_requests': user_requests.count(),
        'new_requests': user_requests.filter(status='New').count(),
        'in_progress': user_requests.filter(status='In Progress').count(),
        'repaired': user_requests.filter(status='Repaired').count(),
        'overdue': user_requests.filter(
            status__in=['New', 'In Progress'],
            scheduled_date__lt=timezone.now().date()
        ).count(),
    }
    
    # Get recent requests
    recent_requests = user_requests.order_by('-created_at')[:5]
    
    # Manager-specific stats
    if is_manager or user.is_superuser:
        stats['total_equipment'] = Equipment.objects.count()
        stats['under_maintenance'] = Equipment.objects.filter(
            maintenancerequest__status='In Progress'
        ).distinct().count()
        stats['preventive_upcoming'] = MaintenanceRequest.objects.filter(
            request_type='Preventive',
            status='New',
            scheduled_date__gte=timezone.now().date(),
            scheduled_date__lte=timezone.now().date() + timezone.timedelta(days=30)
        ).count()
    
    context = {
        'requests': user_requests[:20],  # Show latest 20
        'recent_requests': recent_requests,
        'stats': stats,
        'is_manager': is_manager,
        'is_technician': is_technician,
    }
    
    return render(request, "frontend/maintenance_dashboard.html", context)
