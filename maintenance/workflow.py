"""
PHASE 5: WORKFLOW LOGIC - State Machine & Business Rules Engine

This module implements strict, realistic workflow rules that govern how
Maintenance Requests move through their lifecycle. All state transitions
are validated server-side and impossible to bypass.

Architecture:
- WorkflowException: Custom exception for workflow violations
- WorkflowEngine: Centralized state machine and transition logic
- PermissionChecker: Role-based access control (User, Technician, Manager)
- Helper functions: Simplified API for common transitions
"""

from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from datetime import date
from .models import MaintenanceRequest
from teams.models import MaintenanceTeam


# ============================================================================
# CUSTOM EXCEPTIONS
# ============================================================================

class WorkflowException(Exception):
    """Base exception for all workflow violations."""
    pass


class InvalidTransitionError(WorkflowException):
    """Raised when attempting an invalid status transition."""
    pass


class PermissionError(WorkflowException):
    """Raised when user lacks required role/permission."""
    pass


class MissingDataError(WorkflowException):
    """Raised when required data is missing for a transition."""
    pass


# ============================================================================
# ROLE DEFINITION & PERMISSION SYSTEM
# ============================================================================

class UserRole:
    """Enumeration of user roles in the workflow system."""
    USER = 'user'  # Can create requests, view own requests
    TECHNICIAN = 'technician'  # Can assign themselves, execute work
    MANAGER = 'manager'  # Full control, can override, create preventive requests


class PermissionChecker:
    """
    Validates user roles and permissions.
    
    Rules:
    - Users are in 'maintenance_teams' (ManyToMany)
    - Technicians are users who belong to a maintenance team
    - Managers are identified by Django group membership or is_staff flag
    
    In production, this would check Django Groups. For now:
    - is_staff = Manager
    - In maintenance_teams = Technician
    - Otherwise = User
    """
    
    @staticmethod
    def get_user_role(user):
        """
        Determine the highest role for a user.
        
        Returns one of: USER, TECHNICIAN, MANAGER
        """
        if user.is_staff or user.is_superuser:
            return UserRole.MANAGER
        
        # Check if user belongs to any maintenance team
        if user.maintenance_teams.exists():
            return UserRole.TECHNICIAN
        
        return UserRole.USER
    
    @staticmethod
    def is_manager(user):
        """Check if user has manager role."""
        return PermissionChecker.get_user_role(user) == UserRole.MANAGER
    
    @staticmethod
    def is_technician(user):
        """Check if user has technician role."""
        role = PermissionChecker.get_user_role(user)
        return role in [UserRole.TECHNICIAN, UserRole.MANAGER]
    
    @staticmethod
    def belongs_to_team(user, team):
        """Check if user is a member of a maintenance team."""
        return team.members.filter(id=user.id).exists()
    
    @staticmethod
    def can_assign_technician(user, request_obj):
        """
        Check if user can assign a technician to this request.
        
        Rules:
        - Manager: YES (always)
        - Technician: YES (can assign to themselves or teammates)
        - User: NO
        """
        if PermissionChecker.is_manager(user):
            return True
        
        if PermissionChecker.is_technician(user):
            # Technician can only assign within their teams
            if request_obj.assigned_team:
                return PermissionChecker.belongs_to_team(user, request_obj.assigned_team)
        
        return False
    
    @staticmethod
    def can_start_work(user, request_obj):
        """
        Check if user can start work (New -> In Progress).
        
        Rules:
        - Manager: YES
        - Technician: YES, but only if assigned to them
        - User: NO
        """
        if PermissionChecker.is_manager(user):
            return True
        
        # Technician must be the assigned technician
        if PermissionChecker.is_technician(user):
            return request_obj.assigned_technician == user
        
        return False
    
    @staticmethod
    def can_complete_work(user, request_obj):
        """
        Check if user can complete work (In Progress -> Repaired).
        
        Rules:
        - Manager: YES
        - Technician: YES, but only if assigned to them
        - User: NO
        """
        if PermissionChecker.is_manager(user):
            return True
        
        if PermissionChecker.is_technician(user):
            return request_obj.assigned_technician == user
        
        return False
    
    @staticmethod
    def can_scrap_request(user, request_obj):
        """
        Check if user can scrap a request.
        
        Rules:
        - Manager: YES
        - Technician: NO
        - User: NO
        """
        return PermissionChecker.is_manager(user)


# ============================================================================
# STATE MACHINE & WORKFLOW ENGINE
# ============================================================================

class WorkflowEngine:
    """
    Centralized state machine for MaintenanceRequest lifecycle.
    
    Valid state transitions:
    - New → In Progress (by assigned technician or manager)
    - In Progress → Repaired (by assigned technician or manager, requires duration)
    - Any → Scrap (by manager only)
    - Scrap is terminal state (no transitions out)
    
    Request creation rules:
    - Corrective: Any authenticated user can create
    - Preventive: Only managers can create, scheduled_date is mandatory
    """
    
    # State transition rules: (current_status) -> [list of valid next statuses]
    VALID_TRANSITIONS = {
        'New': ['In Progress', 'Scrap'],
        'In Progress': ['Repaired', 'Scrap'],
        'Repaired': ['Scrap'],  # Can only scrap a completed request
        'Scrap': [],  # Terminal state
    }
    
    @staticmethod
    def validate_status_transition(current_status, new_status):
        """
        Validate that a status transition is allowed.
        
        Raises InvalidTransitionError if invalid.
        """
        if new_status not in WorkflowEngine.VALID_TRANSITIONS.get(current_status, []):
            raise InvalidTransitionError(
                f"Cannot transition from '{current_status}' to '{new_status}'. "
                f"Valid transitions: {WorkflowEngine.VALID_TRANSITIONS[current_status]}"
            )
    
    @staticmethod
    def assign_technician(request_obj, technician, user):
        """
        Assign a technician to a maintenance request.
        
        Args:
            request_obj: MaintenanceRequest instance
            technician: User instance to assign
            user: User performing the action (for permission check)
        
        Raises:
            PermissionError: If user lacks permission
            MissingDataError: If request has no assigned team or equipment is scrapped
            ValidationError: If technician not in assigned team
        """
        # Check if equipment is scrapped
        if request_obj.equipment.is_scrapped:
            raise MissingDataError(
                f"Cannot assign technician: equipment '{request_obj.equipment.name}' is marked as scrapped. "
                "No further work can be assigned to this equipment."
            )
        
        # Permission check
        if not PermissionChecker.can_assign_technician(user, request_obj):
            raise PermissionError(
                f"{PermissionChecker.get_user_role(user).upper()} cannot assign technicians. "
                f"Only managers and team members can assign."
            )
        
        # Ensure request has an assigned team
        if not request_obj.assigned_team:
            raise MissingDataError(
                "Cannot assign technician: request has no assigned team. "
                "Auto-assign a team first via equipment's default team."
            )
        
        # Validate technician belongs to assigned team
        if not PermissionChecker.belongs_to_team(technician, request_obj.assigned_team):
            raise ValidationError(
                f"Technician {technician.get_full_name()} is not a member of "
                f"the assigned team '{request_obj.assigned_team.name}'."
            )
        
        # Assign
        request_obj.assigned_technician = technician
        request_obj.save()
        
        return {
            'success': True,
            'message': f"Assigned technician {technician.get_full_name()} to request #{request_obj.id}",
            'technician': technician.get_full_name()
        }
    
    @staticmethod
    def start_work(request_obj, user):
        """
        Transition request from 'New' to 'In Progress'.
        
        Args:
            request_obj: MaintenanceRequest instance
            user: User performing the action (must be assigned technician or manager)
        
        Raises:
            PermissionError: If user is not assigned technician or manager
            InvalidTransitionError: If not in 'New' status
            MissingDataError: If no technician assigned
        """
        # Check if technician is assigned
        if not request_obj.assigned_technician:
            raise MissingDataError(
                "Cannot start work: no technician assigned. "
                "Please assign a technician first."
            )
        
        # Validate status transition
        WorkflowEngine.validate_status_transition(request_obj.status, 'In Progress')
        
        # Permission check
        if not PermissionChecker.can_start_work(user, request_obj):
            raise PermissionError(
                f"Only the assigned technician or a manager can start work. "
                f"This request is assigned to {request_obj.assigned_technician.get_full_name()}."
            )
        
        # Transition
        request_obj.status = 'In Progress'
        request_obj.save()
        
        return {
            'success': True,
            'message': f"Started work on request #{request_obj.id}",
            'status': 'In Progress'
        }
    
    @staticmethod
    def complete_work(request_obj, duration_hours, user):
        """
        Transition request from 'In Progress' to 'Repaired'.
        
        Args:
            request_obj: MaintenanceRequest instance
            duration_hours: Float, hours spent on this work (required)
            user: User performing the action (must be assigned technician or manager)
        
        Raises:
            PermissionError: If user is not assigned technician or manager
            InvalidTransitionError: If not in 'In Progress' status
            MissingDataError: If duration is missing or invalid
        """
        # Validate duration is provided
        if duration_hours is None or duration_hours == '':
            raise MissingDataError(
                "Duration (in hours) is required to complete maintenance work. "
                "This records the actual time spent."
            )
        
        # Validate duration is positive number
        try:
            duration_float = float(duration_hours)
            if duration_float <= 0:
                raise ValueError("Duration must be positive")
        except (TypeError, ValueError):
            raise MissingDataError(
                f"Invalid duration: '{duration_hours}'. Must be a positive number."
            )
        
        # Validate status transition
        WorkflowEngine.validate_status_transition(request_obj.status, 'Repaired')
        
        # Permission check
        if not PermissionChecker.can_complete_work(user, request_obj):
            raise PermissionError(
                f"Only the assigned technician or a manager can complete work. "
                f"This request is assigned to {request_obj.assigned_technician.get_full_name()}."
            )
        
        # Transition
        request_obj.status = 'Repaired'
        request_obj.duration = duration_float
        request_obj.save()
        
        return {
            'success': True,
            'message': f"Completed work on request #{request_obj.id} ({duration_float} hours)",
            'status': 'Repaired',
            'duration': duration_float
        }
    
    @staticmethod
    def scrap_request(request_obj, user):
        """
        Transition request to 'Scrap' status (terminal state).
        
        Args:
            request_obj: MaintenanceRequest instance
            user: User performing the action (must be manager)
        
        Raises:
            PermissionError: If user is not a manager
            InvalidTransitionError: If already scrapped
        """
        # Permission check - managers only
        if not PermissionChecker.can_scrap_request(user, request_obj):
            raise PermissionError(
                "Only managers can scrap requests. "
                "Contact your manager if this request should be marked as unsalvageable."
            )
        
        # Validate status transition
        WorkflowEngine.validate_status_transition(request_obj.status, 'Scrap')
        
        # Transition
        request_obj.status = 'Scrap'
        request_obj.save()
        
        return {
            'success': True,
            'message': f"Marked request #{request_obj.id} as scrapped (terminal state)",
            'status': 'Scrap'
        }
    
    @staticmethod
    def validate_creation(request_type, user, scheduled_date=None, equipment_obj=None):
        """
        Validate that a user can create a request of the specified type.
        
        Rules:
        - Corrective: Any authenticated user (unless equipment is scrapped)
        - Preventive: Only managers; scheduled_date is mandatory
        - Scrapped equipment: Cannot create requests for scrapped equipment
        
        Raises:
            PermissionError: If user lacks permission
            MissingDataError: If preventive but scheduled_date missing, or equipment scrapped
        """
        # Check if equipment is scrapped
        if equipment_obj and equipment_obj.is_scrapped:
            raise MissingDataError(
                f"Cannot create maintenance request: equipment '{equipment_obj.name}' is marked as scrapped. "
                "No new requests can be created for scrapped equipment."
            )
        
        if request_type == 'Preventive':
            # Managers only
            if not PermissionChecker.is_manager(user):
                raise PermissionError(
                    "Only managers can create preventive (scheduled) maintenance requests. "
                    f"Your current role: {PermissionChecker.get_user_role(user).upper()}"
                )
            
            # scheduled_date mandatory
            if not scheduled_date:
                raise MissingDataError(
                    "Preventive maintenance requests require a scheduled date. "
                    "This date must be set when creating the request."
                )
        
        return {
            'success': True,
            'message': f"User authorized to create {request_type} request"
        }


# ============================================================================
# HELPER FUNCTIONS (Simplified API)
# ============================================================================

def get_available_actions(request_obj, user):
    """
    Get a list of available workflow actions for this user on this request.
    
    Returns: {
        'can_assign': bool,
        'can_start': bool,
        'can_complete': bool,
        'can_scrap': bool,
        'current_status': str,
        'assigned_technician': str or None
    }
    
    Used by frontend to show/hide action buttons.
    """
    return {
        'current_status': request_obj.status,
        'assigned_technician': request_obj.assigned_technician.get_full_name() if request_obj.assigned_technician else None,
        'can_assign': PermissionChecker.can_assign_technician(user, request_obj) and request_obj.status == 'New',
        'can_start': PermissionChecker.can_start_work(user, request_obj) and request_obj.status == 'New',
        'can_complete': PermissionChecker.can_complete_work(user, request_obj) and request_obj.status == 'In Progress',
        'can_scrap': PermissionChecker.can_scrap_request(user, request_obj) and request_obj.status != 'Scrap',
    }


def get_workflow_state(request_obj):
    """
    Get detailed workflow state information for a request.
    
    Returns comprehensive state data for display/debugging.
    """
    return {
        'id': request_obj.id,
        'status': request_obj.status,
        'request_type': request_obj.request_type,
        'subject': request_obj.subject,
        'equipment': request_obj.equipment.name,
        'assigned_team': request_obj.assigned_team.name if request_obj.assigned_team else None,
        'assigned_technician': request_obj.assigned_technician.get_full_name() if request_obj.assigned_technician else None,
        'duration': request_obj.duration,
        'created_at': request_obj.created_at.isoformat() if request_obj.created_at else None,
        'created_by': request_obj.created_by.get_full_name() if request_obj.created_by else None,
        'is_overdue': request_obj.is_overdue,
        'valid_next_transitions': WorkflowEngine.VALID_TRANSITIONS.get(request_obj.status, []),
    }
