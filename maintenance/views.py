from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from .models import MaintenanceRequest
from equipment.models import Equipment
from .workflow import (
    WorkflowEngine, PermissionChecker, WorkflowException, 
    InvalidTransitionError, PermissionError as WorkflowPermissionError,
    MissingDataError, get_available_actions, get_workflow_state
)
from django.utils import timezone
from datetime import date
import calendar as _calendar
from django.db import transaction
from django.urls import reverse



def kanban_board(request):
    # If the user is not authenticated, send them to the landing page
    # with a `next` parameter so they can login and return here.
    if not request.user.is_authenticated:
        return redirect(reverse('home') + f"?next={request.path}")

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


@login_required
@require_http_methods(["GET"])
def kanban_data(request):
    """
    API: Return Kanban data grouped by status.
    """
    qs = MaintenanceRequest.objects.select_related(
        'equipment', 'assigned_team', 'assigned_technician', 'created_by'
    ).order_by('-created_at')

    grouped = {'New': [], 'In Progress': [], 'Repaired': [], 'Scrap': []}

    for r in qs:
        card = {
            'id': r.id,
            'subject': r.subject,
            'equipment': r.equipment.name if r.equipment else None,
            'assigned_technician': None,
            'scheduled_date': r.scheduled_date.isoformat() if r.scheduled_date else None,
            'is_overdue': r.is_overdue,
            'status': r.status,
        }
        if r.assigned_technician:
            card['assigned_technician'] = {
                'id': r.assigned_technician.id,
                'name': r.assigned_technician.get_full_name() or r.assigned_technician.username,
                'avatar': (r.assigned_technician.username[:1].upper())
            }

        if r.status in grouped:
            grouped[r.status].append(card)
        else:
            grouped['New'].append(card)

    return JsonResponse({
        'success': True,
        'data': grouped,
        'user_role': PermissionChecker.get_user_role(request.user)
    }, status=200)


@login_required
@require_http_methods(["POST"])
def kanban_move(request):
    """
    API: Move a card to a new status (called by drag-and-drop).
    Expects JSON body: { id: <int>, new_status: <str>, duration: <float, optional> }
    """
    import json

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    request_id = payload.get('id')
    new_status = payload.get('new_status')
    duration = payload.get('duration')

    if not request_id or not new_status:
        return JsonResponse({'success': False, 'error': 'Missing id or new_status'}, status=400)

    try:
        mr = MaintenanceRequest.objects.select_related('assigned_technician', 'assigned_team').get(id=request_id)
    except MaintenanceRequest.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Request not found'}, status=404)

    if mr.status == new_status:
        return JsonResponse({'success': True, 'message': 'No change', 'status': mr.status}, status=200)

    try:
        if new_status == 'In Progress':
            result = WorkflowEngine.start_work(mr, request.user)
            return JsonResponse({'success': True, 'message': result['message'], 'status': result['status']}, status=200)

        if new_status == 'Repaired':
            if duration is None:
                return JsonResponse({'success': False, 'error': 'Duration required to complete work', 'error_type': 'workflow'}, status=400)
            result = WorkflowEngine.complete_work(mr, duration, request.user)
            return JsonResponse({'success': True, 'message': result['message'], 'status': result['status'], 'duration': result['duration']}, status=200)

        if new_status == 'Scrap':
            with transaction.atomic():
                result = WorkflowEngine.scrap_request(mr, request.user)
                # Scrap automation: mark equipment as scrapped
                if result['status'] == 'Scrap':
                    mr.equipment.mark_scrapped()
            return JsonResponse({'success': True, 'message': result['message'], 'status': result['status']}, status=200)

        return JsonResponse({'success': False, 'error': f'Unsupported status change to {new_status}'}, status=400)

    except WorkflowPermissionError as e:
        return JsonResponse({'success': False, 'error': str(e), 'error_type': 'permission'}, status=403)
    except (InvalidTransitionError, MissingDataError) as e:
        return JsonResponse({'success': False, 'error': str(e), 'error_type': 'workflow'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e), 'error_type': 'unknown'}, status=500)


@login_required
@require_http_methods(["GET"])
def get_equipment_details(request):
    """
    API endpoint that returns auto-fill data for a selected equipment.
    
    Query Parameters:
    - equipment_id: ID of the equipment
    
    Returns:
    {
        "success": bool,
        "data": {
            "department": str,
            "maintenance_team": {
                "id": int,
                "name": str,
                "member_count": int
            },
            "default_technician": {
                "id": int,
                "username": str,
                "first_name": str,
                "last_name": str
            } | null,
            "is_scrapped": bool,
            "warranty_status": str
        },
        "error": str | null
    }
    """
    equipment_id = request.GET.get('equipment_id')
    
    # Validation: equipment_id is required
    if not equipment_id:
        return JsonResponse({
            'success': False,
            'error': 'Equipment ID is required'
        }, status=400)
    
    try:
        equipment = get_object_or_404(Equipment, id=equipment_id)
    except Equipment.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Equipment not found'
        }, status=404)
    
    # Business Rule: Block if equipment is scrapped
    if equipment.is_scrapped:
        return JsonResponse({
            'success': False,
            'error': 'Equipment is marked as scrapped and cannot be maintained',
            'data': {
                'is_scrapped': True
            }
        }, status=422)
    
    # Build response data
    response_data = {
        'success': True,
        'data': {
            'department': equipment.department,
            'is_scrapped': equipment.is_scrapped,
            'warranty_status': 'Under Warranty' if equipment.is_under_warranty else 'Out of Warranty',
        },
        'error': None
    }
    
    # Auto-fill maintenance team
    if equipment.default_maintenance_team:
        response_data['data']['maintenance_team'] = {
            'id': equipment.default_maintenance_team.id,
            'name': equipment.default_maintenance_team.name,
            'member_count': equipment.default_maintenance_team.member_count
        }
    else:
        response_data['data']['maintenance_team'] = None
    
    # Auto-fill default technician
    if equipment.default_technician:
        response_data['data']['default_technician'] = {
            'id': equipment.default_technician.id,
            'username': equipment.default_technician.username,
            'first_name': equipment.default_technician.first_name,
            'last_name': equipment.default_technician.last_name
        }
    else:
        response_data['data']['default_technician'] = None
    
    return JsonResponse(response_data, status=200)


@login_required
@require_http_methods(["GET"])
def calendar_data(request):
    """
    API: Return preventive maintenance requests for a given month/year.
    Query parameters: year, month (integers). Defaults to current month.
    Returns: { success: True, events: [ { id, date, subject, equipment, assigned_technician } ] }
    """
    try:
        today = timezone.localdate()
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
    except Exception:
        return JsonResponse({'success': False, 'error': 'Invalid year or month'}, status=400)

    # build month range
    try:
        first_day = date(year, month, 1)
        last_day = date(year, month, _calendar.monthrange(year, month)[1])
    except Exception:
        return JsonResponse({'success': False, 'error': 'Invalid month/year range'}, status=400)

    qs = MaintenanceRequest.objects.select_related('equipment', 'assigned_technician').filter(
        request_type='Preventive',
        scheduled_date__isnull=False,
        scheduled_date__range=(first_day, last_day),
        equipment__is_scrapped=False
    ).order_by('scheduled_date')

    events = []
    for r in qs:
        events.append({
            'id': r.id,
            'date': r.scheduled_date.isoformat(),
            'subject': r.subject,
            'equipment': r.equipment.name if r.equipment else None,
            'assigned_technician': r.assigned_technician.get_full_name() if r.assigned_technician else None,
            'status': r.status,
        })

    return JsonResponse({'success': True, 'events': events}, status=200)


@login_required
@require_http_methods(["GET"])
def calendar_page(request):
    """Render calendar HTML page."""
    return render(request, 'maintenance/calendar.html')


@login_required
@require_http_methods(["GET", "POST"])
def create_maintenance_request(request):
    """
    Display and handle creation of maintenance requests.
    GET: Show form with equipment dropdown
    POST: Create new maintenance request
    """
    if request.method == 'POST':
        subject = request.POST.get('subject')
        request_type = request.POST.get('request_type')
        equipment_id = request.POST.get('equipment')
        assigned_technician_id = request.POST.get('assigned_technician')
        scheduled_date = request.POST.get('scheduled_date')
        due_date = request.POST.get('due_date')
        duration = request.POST.get('duration')
        
        # Validation
        if not subject:
            return render(request, 'maintenance/create_request.html', {
                'error': 'Subject is required',
                'equipments': Equipment.objects.filter(is_scrapped=False)
            })
        
        if not equipment_id:
            return render(request, 'maintenance/create_request.html', {
                'error': 'Equipment is required',
                'equipments': Equipment.objects.filter(is_scrapped=False)
            })
        
        try:
            equipment = Equipment.objects.get(id=equipment_id)
        except Equipment.DoesNotExist:
            return render(request, 'maintenance/create_request.html', {
                'error': 'Selected equipment does not exist',
                'equipments': Equipment.objects.filter(is_scrapped=False)
            })
        
        # Block scrapped equipment
        if equipment.is_scrapped:
            return render(request, 'maintenance/create_request.html', {
                'error': 'Cannot create requests for scrapped equipment',
                'equipments': Equipment.objects.filter(is_scrapped=False)
            })
        
        # Create maintenance request
        maintenance_request = MaintenanceRequest(
            subject=subject,
            request_type=request_type or 'Corrective',
            equipment=equipment,
            created_by=request.user,
            scheduled_date=scheduled_date or None,
            due_date=due_date or None,
            duration=float(duration) if duration else None,
        )
        
        # Assign technician if provided
        if assigned_technician_id:
            try:
                technician = Equipment.objects.get(id=assigned_technician_id).default_technician
                maintenance_request.assigned_technician = technician
            except:
                pass
        
        maintenance_request.save()
        
        return redirect('maintenance:kanban')
    
    # GET request: Show form
    equipments = Equipment.objects.filter(is_scrapped=False)
    context = {
        'equipments': equipments
    }
    
    return render(request, 'maintenance/create_request.html', context)

# ============================================================================
# PHASE 5: WORKFLOW TRANSITION ENDPOINTS
# ============================================================================
# These endpoints enforce strict workflow rules and role-based permissions.

@login_required
@require_http_methods(["POST"])
def assign_technician(request):
    """
    API: Assign a technician to a maintenance request.
    
    POST Parameters:
    - request_id: ID of the maintenance request
    - technician_id: ID of the user to assign
    
    Returns: JSON with success status and message
    
    Rules:
    - Only managers or team members can assign
    - Technician must belong to request's maintenance team
    - Request must have assigned_team set
    """
    request_id = request.POST.get('request_id')
    technician_id = request.POST.get('technician_id')
    
    if not request_id or not technician_id:
        return JsonResponse({
            'success': False,
            'error': 'Missing request_id or technician_id'
        }, status=400)
    
    try:
        maintenance_request = MaintenanceRequest.objects.get(id=request_id)
        technician = get_object_or_404(User, id=technician_id)
    except MaintenanceRequest.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Request not found'
        }, status=404)
    
    try:
        result = WorkflowEngine.assign_technician(maintenance_request, technician, request.user)
        return JsonResponse({
            'success': True,
            'message': result['message'],
            'technician': result['technician']
        }, status=200)
    except WorkflowPermissionError as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'error_type': 'permission'
        }, status=403)
    except (MissingDataError, ValidationError) as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'error_type': 'validation'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'error_type': 'unknown'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def start_work(request):
    """
    API: Start work on a maintenance request (New -> In Progress).
    
    POST Parameters:
    - request_id: ID of the maintenance request
    
    Returns: JSON with success status and new status
    
    Rules:
    - Only assigned technician or manager can start
    - Request must be in 'New' status
    - Request must have a technician assigned
    """
    request_id = request.POST.get('request_id')
    
    if not request_id:
        return JsonResponse({
            'success': False,
            'error': 'request_id is required'
        }, status=400)
    
    try:
        maintenance_request = MaintenanceRequest.objects.get(id=request_id)
    except MaintenanceRequest.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Request not found'
        }, status=404)
    
    try:
        result = WorkflowEngine.start_work(maintenance_request, request.user)
        return JsonResponse({
            'success': True,
            'message': result['message'],
            'status': result['status']
        }, status=200)
    except WorkflowPermissionError as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'error_type': 'permission'
        }, status=403)
    except (InvalidTransitionError, MissingDataError) as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'error_type': 'workflow'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'error_type': 'unknown'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def complete_work(request):
    """
    API: Complete work on a maintenance request (In Progress -> Repaired).
    
    POST Parameters:
    - request_id: ID of the maintenance request
    - duration_hours: Hours spent on work (required, must be > 0)
    
    Returns: JSON with success status, new status, and recorded duration
    
    Rules:
    - Only assigned technician or manager can complete
    - Request must be in 'In Progress' status
    - Duration is mandatory and must be positive
    """
    request_id = request.POST.get('request_id')
    duration_hours = request.POST.get('duration_hours')
    
    if not request_id:
        return JsonResponse({
            'success': False,
            'error': 'request_id is required'
        }, status=400)
    
    try:
        maintenance_request = MaintenanceRequest.objects.get(id=request_id)
    except MaintenanceRequest.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Request not found'
        }, status=404)
    
    try:
        result = WorkflowEngine.complete_work(maintenance_request, duration_hours, request.user)
        return JsonResponse({
            'success': True,
            'message': result['message'],
            'status': result['status'],
            'duration': result['duration']
        }, status=200)
    except WorkflowPermissionError as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'error_type': 'permission'
        }, status=403)
    except (InvalidTransitionError, MissingDataError) as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'error_type': 'workflow'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'error_type': 'unknown'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def scrap_request(request):
    """
    API: Mark a maintenance request as scrapped (terminal state).
    
    POST Parameters:
    - request_id: ID of the maintenance request
    
    Returns: JSON with success status and new status
    
    Rules:
    - Only managers can scrap requests
    - Can scrap from any status except 'Scrap'
    - Scrap is a terminal state (cannot transition out)
    """
    request_id = request.POST.get('request_id')
    
    if not request_id:
        return JsonResponse({
            'success': False,
            'error': 'request_id is required'
        }, status=400)
    
    try:
        maintenance_request = MaintenanceRequest.objects.get(id=request_id)
    except MaintenanceRequest.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Request not found'
        }, status=404)
    
    try:
        result = WorkflowEngine.scrap_request(maintenance_request, request.user)
        return JsonResponse({
            'success': True,
            'message': result['message'],
            'status': result['status']
        }, status=200)
    except WorkflowPermissionError as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'error_type': 'permission'
        }, status=403)
    except InvalidTransitionError as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'error_type': 'workflow'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'error_type': 'unknown'
        }, status=500)


@login_required
@require_http_methods(["GET"])
def get_request_actions(request):
    """
    API: Get available workflow actions for current user on a request.
    
    Query Parameters:
    - request_id: ID of the maintenance request
    
    Returns: JSON with available actions and current state
    
    Used by frontend to show/hide buttons based on user role and request status.
    """
    request_id = request.GET.get('request_id')
    
    if not request_id:
        return JsonResponse({
            'success': False,
            'error': 'request_id is required'
        }, status=400)
    
    try:
        maintenance_request = MaintenanceRequest.objects.get(id=request_id)
    except MaintenanceRequest.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Request not found'
        }, status=404)
    
    actions = get_available_actions(maintenance_request, request.user)
    state = get_workflow_state(maintenance_request)
    
    return JsonResponse({
        'success': True,
        'actions': actions,
        'state': state,
        'user_role': PermissionChecker.get_user_role(request.user)
    }, status=200)


@login_required
@require_http_methods(["GET"])
def request_detail(request, request_id):
    """
    View: Display detailed information about a maintenance request.
    
    Shows:
    - Request details (equipment, type, status, etc.)
    - Available actions based on user role
    - Workflow state and history
    - Form to execute allowed actions
    """
    try:
        maintenance_request = MaintenanceRequest.objects.get(id=request_id)
    except MaintenanceRequest.DoesNotExist:
        return render(request, 'maintenance/request_not_found.html', {
            'error': 'Request not found'
        }, status=404)
    
    actions = get_available_actions(maintenance_request, request.user)
    state = get_workflow_state(maintenance_request)
    user_role = PermissionChecker.get_user_role(request.user)
    
    context = {
        'request': maintenance_request,
        'actions': actions,
        'state': state,
        'user_role': user_role,
        'available_technicians': (
            maintenance_request.assigned_team.members.all()
            if maintenance_request.assigned_team else []
        )
    }
    
    return render(request, 'maintenance/request_detail.html', context)


# ============================================================================
# PHASE 9: REPORTS & ANALYTICS
# ============================================================================

@login_required
@require_http_methods(["GET"])
def report_team_requests(request):
    """
    Report: Requests per Maintenance Team
    
    Shows aggregated request count grouped by team.
    Optional filters: date range, status.
    Manager access only.
    """
    from django.db.models import Count
    
    # Permission check - managers only
    if not PermissionChecker.is_manager(request.user):
        return render(request, 'maintenance/report_403.html', {
            'message': 'Reports are available to managers only.'
        }, status=403)
    
    # Get filter parameters
    status_filter = request.GET.get('status')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    # Base queryset
    qs = MaintenanceRequest.objects.select_related('assigned_team').filter(
        equipment__is_scrapped=False
    )
    
    # Apply status filter
    if status_filter and status_filter != '':
        qs = qs.filter(status=status_filter)
    
    # Apply date range filter
    if date_from:
        try:
            from datetime import datetime
            start = datetime.fromisoformat(date_from).date()
            qs = qs.filter(created_at__date__gte=start)
        except:
            pass
    
    if date_to:
        try:
            from datetime import datetime
            end = datetime.fromisoformat(date_to).date()
            qs = qs.filter(created_at__date__lte=end)
        except:
            pass
    
    # Aggregate by team
    team_data = qs.values('assigned_team__name').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Format for JSON response
    teams = []
    total = 0
    for item in team_data:
        team_name = item['assigned_team__name'] or 'Unassigned'
        count = item['count']
        teams.append({
            'name': team_name,
            'count': count
        })
        total += count
    
    # Handle request type (JSON or HTML)
    if request.GET.get('format') == 'json':
        return JsonResponse({
            'success': True,
            'data': teams,
            'total': total
        })
    
    context = {
        'teams': teams,
        'total': total,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'statuses': [s[0] for s in MaintenanceRequest.STATUS_CHOICES],
    }
    
    return render(request, 'maintenance/report_team_requests.html', context)


@login_required
@require_http_methods(["GET"])
def report_equipment_requests(request):
    """
    Report: Requests per Equipment
    
    Shows aggregated request count grouped by equipment.
    Highlights high-maintenance assets.
    Optional filters: department, status, date range.
    Manager access only.
    """
    from django.db.models import Count
    
    # Permission check - managers only
    if not PermissionChecker.is_manager(request.user):
        return render(request, 'maintenance/report_403.html', {
            'message': 'Reports are available to managers only.'
        }, status=403)
    
    # Get filter parameters
    department_filter = request.GET.get('department')
    status_filter = request.GET.get('status')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    # Base queryset (exclude scrapped equipment)
    qs = MaintenanceRequest.objects.select_related('equipment').filter(
        equipment__is_scrapped=False
    )
    
    # Apply department filter
    if department_filter and department_filter != '':
        qs = qs.filter(equipment__department=department_filter)
    
    # Apply status filter
    if status_filter and status_filter != '':
        qs = qs.filter(status=status_filter)
    
    # Apply date range filter
    if date_from:
        try:
            from datetime import datetime
            start = datetime.fromisoformat(date_from).date()
            qs = qs.filter(created_at__date__gte=start)
        except:
            pass
    
    if date_to:
        try:
            from datetime import datetime
            end = datetime.fromisoformat(date_to).date()
            qs = qs.filter(created_at__date__lte=end)
        except:
            pass
    
    # Aggregate by equipment (top 20)
    equipment_data = qs.values('equipment__name', 'equipment__id').annotate(
        count=Count('id')
    ).order_by('-count')[:20]
    
    # Format for JSON response
    equipment_list = []
    total = 0
    for item in equipment_data:
        equipment_list.append({
            'id': item['equipment__id'],
            'name': item['equipment__name'],
            'count': item['count']
        })
        total += item['count']
    
    # Get unique departments for filter dropdown
    departments = Equipment.objects.filter(
        is_scrapped=False
    ).values_list('department', flat=True).distinct().order_by('department')
    
    # Handle request type (JSON or HTML)
    if request.GET.get('format') == 'json':
        return JsonResponse({
            'success': True,
            'data': equipment_list,
            'total': total
        })
    
    context = {
        'equipment_list': equipment_list,
        'total': total,
        'department_filter': department_filter,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'departments': list(departments),
        'statuses': [s[0] for s in MaintenanceRequest.STATUS_CHOICES],
    }
    
    return render(request, 'maintenance/report_equipment_requests.html', context)


@login_required
@require_http_methods(["GET"])
def report_department_requests(request):
    """
    Report: Requests per Department
    
    Shows aggregated request count grouped by department.
    Manager access only.
    """
    from django.db.models import Count
    
    # Permission check - managers only
    if not PermissionChecker.is_manager(request.user):
        return render(request, 'maintenance/report_403.html', {
            'message': 'Reports are available to managers only.'
        }, status=403)
    
    # Get filter parameters
    status_filter = request.GET.get('status')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    # Base queryset
    qs = MaintenanceRequest.objects.select_related('equipment').filter(
        equipment__is_scrapped=False
    )
    
    # Apply status filter
    if status_filter and status_filter != '':
        qs = qs.filter(status=status_filter)
    
    # Apply date range filter
    if date_from:
        try:
            from datetime import datetime
            start = datetime.fromisoformat(date_from).date()
            qs = qs.filter(created_at__date__gte=start)
        except:
            pass
    
    if date_to:
        try:
            from datetime import datetime
            end = datetime.fromisoformat(date_to).date()
            qs = qs.filter(created_at__date__lte=end)
        except:
            pass
    
    # Aggregate by department
    dept_data = qs.values('equipment__department').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Format for JSON response
    departments = []
    total = 0
    for item in dept_data:
        dept_name = item['equipment__department'] or 'Unknown'
        count = item['count']
        departments.append({
            'name': dept_name,
            'count': count
        })
        total += count
    
    # Handle request type (JSON or HTML)
    if request.GET.get('format') == 'json':
        return JsonResponse({
            'success': True,
            'data': departments,
            'total': total
        })
    
    context = {
        'departments': departments,
        'total': total,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'statuses': [s[0] for s in MaintenanceRequest.STATUS_CHOICES],
    }
    
    return render(request, 'maintenance/report_department_requests.html', context)