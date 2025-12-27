from django import forms
from .models import MaintenanceRequest

class MaintenanceRequestForm(forms.ModelForm):
    class Meta:
        model = MaintenanceRequest
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        equipment = cleaned_data.get('equipment')

        if equipment:
            cleaned_data['team'] = equipment.maintenance_team
            cleaned_data['assigned_technician'] = equipment.default_technician

        return cleaned_data
