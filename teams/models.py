from django.db import models
from django.contrib.auth.models import User

class MaintenanceTeam(models.Model):
    team_name = models.CharField(max_length=100)
    members = models.ManyToManyField(User)

    def __str__(self):
        return self.team_name
