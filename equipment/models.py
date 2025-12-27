from django.db import models
from django.contrib.auth.models import User
from teams.models import MaintenanceTeam


class Equipment(models.Model):
    """
    Represents a company asset requiring maintenance tracking.
    """
    name = models.CharField(
        max_length=150,
        help_text="Equipment name (e.g., 'Hydraulic Press A1', 'CNC Machine 3')"
    )
    serial_number = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique manufacturer serial number"
    )
    department = models.CharField(
        max_length=100,
        help_text="Department responsible for this equipment"
    )
    location = models.CharField(
        max_length=200,
        help_text="Physical location within facility (e.g., 'Building A, Floor 2, Section 3')"
    )
    assigned_employee = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_equipment',
        help_text="Primary employee responsible for this equipment"
    )
    default_maintenance_team = models.ForeignKey(
        MaintenanceTeam,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='default_for_equipment',
        help_text="Default team for maintenance requests on this equipment"
    )
    default_technician = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='default_technician_for_equipment',
        help_text="Preferred technician for this equipment"
    )
    purchase_date = models.DateField(
        help_text="Date equipment was purchased"
    )
    warranty_expiry_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date warranty expires"
    )
    is_scrapped = models.BooleanField(
        default=False,
        help_text="Whether equipment is logically scrapped (not deleted from system)"
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Equipment"
        verbose_name_plural = "Equipment"
        ordering = ['name']
        indexes = [
            models.Index(fields=['serial_number']),
            models.Index(fields=['is_scrapped']),
        ]

    def __str__(self):
        status = "[SCRAPPED]" if self.is_scrapped else ""
        return f"{self.name} (SN: {self.serial_number}) {status}"

    @property
    def is_under_warranty(self):
        """Check if equipment is still under warranty."""
        if not self.warranty_expiry_date:
            return False
        from datetime import date
        return date.today() <= self.warranty_expiry_date
    def get_open_request_count(self):
        """
        Return count of open maintenance requests (New + In Progress).
        Used for Smart Button badge.
        """
        return self.maintenance_requests.filter(
            status__in=['New', 'In Progress']
        ).count()

    def mark_scrapped(self):
        """
        Mark equipment as scrapped (irreversible).
        Called when a maintenance request is moved to Scrap status.
        """
        if not self.is_scrapped:
            self.is_scrapped = True
            self.save(update_fields=['is_scrapped', 'updated_at'])