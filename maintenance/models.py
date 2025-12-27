from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from equipment.models import Equipment
from teams.models import MaintenanceTeam


class MaintenanceRequest(models.Model):
    """
    Transactional core: represents a maintenance work order.
    Supports both corrective (emergency) and preventive (scheduled) maintenance.
    """

    REQUEST_TYPE_CHOICES = [
        ('Corrective', 'Corrective - Emergency/Unplanned'),
        ('Preventive', 'Preventive - Scheduled Maintenance'),
    ]

    STATUS_CHOICES = [
        ('New', 'New - Created, not yet assigned'),
        ('In Progress', 'In Progress - Technician is working'),
        ('Repaired', 'Repaired - Completed successfully'),
        ('Scrap', 'Scrap - Equipment marked for disposal'),
    ]

    # Core request fields
    subject = models.CharField(
        max_length=255,
        help_text="Brief description of the problem or maintenance task"
    )
    request_type = models.CharField(
        max_length=20,
        choices=REQUEST_TYPE_CHOICES,
        help_text="Type of maintenance request"
    )
    
    # Equipment and team assignment
    equipment = models.ForeignKey(
        Equipment,
        on_delete=models.CASCADE,
        related_name='maintenance_requests',
        help_text="Equipment requiring maintenance"
    )
    assigned_team = models.ForeignKey(
        MaintenanceTeam,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='maintenance_requests',
        help_text="Team assigned to handle this request (auto-filled from equipment default)"
    )
    assigned_technician = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_maintenance_requests',
        help_text="Individual technician assigned to complete the work"
    )
    
    # Status and lifecycle
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='New',
        help_text="Current status of the maintenance request"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_maintenance_requests',
        help_text="User who created this maintenance request"
    )
    
    # Scheduling and duration
    scheduled_date = models.DateField(
        null=True,
        blank=True,
        help_text="Scheduled date for preventive maintenance"
    )
    due_date = models.DateField(
        null=True,
        blank=True,
        help_text="Target completion date"
    )
    duration = models.FloatField(
        null=True,
        blank=True,
        help_text="Estimated or actual duration in hours"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Maintenance Request"
        verbose_name_plural = "Maintenance Requests"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['request_type']),
            models.Index(fields=['equipment']),
            models.Index(fields=['assigned_technician']),
            models.Index(fields=['scheduled_date']),
        ]

    def __str__(self):
        return f"[{self.get_status_display()}] {self.subject} - {self.equipment.name}"

    def save(self, *args, **kwargs):
        """
        Auto-populate assigned_team from equipment default if not provided.
        """
        if not self.assigned_team and self.equipment.default_maintenance_team:
            self.assigned_team = self.equipment.default_maintenance_team
        super().save(*args, **kwargs)

    @property
    def is_overdue(self):
        """Check if request is past due date."""
        if not self.due_date:
            return False
        from datetime import date
        return date.today() > self.due_date and self.status != 'Repaired'

    @property
    def is_preventive(self):
        """Check if this is a preventive maintenance request."""
        return self.request_type == 'Preventive'

    @property
    def is_corrective(self):
        """Check if this is a corrective maintenance request."""
        return self.request_type == 'Corrective'
    # ========================================================================
    # WORKFLOW STATE MACHINE METHODS (PHASE 5)
    # ========================================================================
    # These methods integrate with the WorkflowEngine for strict state management
    
    def get_available_actions(self, user):
        """
        Get available workflow actions for a user on this request.
        
        Delegates to WorkflowEngine.get_available_actions() for role-based access.
        
        Returns: dict with can_assign, can_start, can_complete, can_scrap
        """
        from maintenance.workflow import get_available_actions
        return get_available_actions(self, user)
    
    def get_workflow_state(self):
        """
        Get complete workflow state information.
        
        Used for status tracking, debugging, and state machine visualization.
        """
        from maintenance.workflow import get_workflow_state
        return get_workflow_state(self)
    
    def clean(self):
        """
        Validate request data before saving (Django validation hook).
        
        Prevents:
        - Preventive requests without scheduled_date
        - Requests for scrapped equipment
        - Invalid status values
        """
        super().clean()
        
        # Prevent preventive requests without scheduling
        if self.request_type == 'Preventive' and not self.scheduled_date:
            raise ValidationError(
                "Preventive maintenance requests require a scheduled date."
            )
        
        # Prevent requests on scrapped equipment
        if self.equipment and self.equipment.is_scrapped:
            raise ValidationError(
                "Cannot create maintenance requests for scrapped equipment."
            )