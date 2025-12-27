from django.db import models
from equipment.models import Equipment
from teams.models import MaintenanceTeam
from django.contrib.auth.models import User

class MaintenanceRequest(models.Model):

    STATUS_CHOICES = [
        ('New', 'New'),
        ('In Progress', 'In Progress'),
        ('Repaired', 'Repaired'),
        ('Scrap', 'Scrap'),
    ]

    TYPE_CHOICES = [
        ('Corrective', 'Corrective'),
        ('Preventive', 'Preventive'),
    ]

    subject = models.CharField(max_length=200)
    request_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE)
    team = models.ForeignKey(MaintenanceTeam, on_delete=models.CASCADE)
    assigned_technician = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='New')
    scheduled_date = models.DateField(null=True, blank=True)
    duration = models.FloatField(null=True, blank=True)

    def __str__(self):
        return self.subject
