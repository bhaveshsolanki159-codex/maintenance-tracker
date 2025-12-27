from django.db import models
from teams.models import MaintenanceTeam
from django.contrib.auth.models import User

class Equipment(models.Model):
    name = models.CharField(max_length=100)
    serial_number = models.CharField(max_length=100, unique=True)
    department = models.CharField(max_length=100)
    assigned_to = models.CharField(max_length=100)
    maintenance_team = models.ForeignKey(MaintenanceTeam, on_delete=models.CASCADE)
    default_technician = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    purchase_date = models.DateField()
    warranty_end = models.DateField()
    location = models.CharField(max_length=100)
    is_scrapped = models.BooleanField(default=False)

    def __str__(self):
        return self.name
