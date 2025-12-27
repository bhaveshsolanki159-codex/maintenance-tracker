from django.db import models
from django.contrib.auth.models import User


class MaintenanceTeam(models.Model):
    """
    Represents a specialized maintenance repair team.
    Team members are linked via ManyToMany relationship.
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        default='Unnamed Team',
        help_text="Unique team name (e.g., 'Hydraulics Team', 'Electrical Team')"
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Team specialization and responsibilities"
    )
    members = models.ManyToManyField(
        User,
        related_name='maintenance_teams',
        help_text="Team members eligible to be assigned as technicians"
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Maintenance Team"
        verbose_name_plural = "Maintenance Teams"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.members.count()} members)"

    @property
    def member_count(self):
        """Total count of team members."""
        return self.members.count()
