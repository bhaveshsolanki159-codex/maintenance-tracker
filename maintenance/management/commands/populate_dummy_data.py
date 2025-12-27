import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gearguard.settings')
django.setup()

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from django.contrib.auth.models import Permission
from datetime import date, timedelta
from equipment.models import Equipment
from teams.models import MaintenanceTeam
from maintenance.models import MaintenanceRequest


class Command(BaseCommand):
    help = 'Populate database with dummy data for testing'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting dummy data population...'))
        
        # Create groups if they don't exist
        tech_group, _ = Group.objects.get_or_create(name='Technician')
        manager_group, _ = Group.objects.get_or_create(name='Manager')
        
        # Create users
        users = {}
        
        # Create manager user
        try:
            manager = User.objects.create_user(
                username='manager',
                email='manager@gearguard.local',
                password='manager123',
                first_name='Alice',
                last_name='Manager',
                is_staff=True,
                is_superuser=True
            )
            manager.groups.add(manager_group)
            users['manager'] = manager
            self.stdout.write(self.style.SUCCESS('✓ Created manager user (username: manager, password: manager123)'))
        except Exception as e:
            users['manager'] = User.objects.get(username='manager')
            self.stdout.write(self.style.WARNING(f'⚠ Manager user already exists: {e}'))
        
        # Create technician users
        technician_data = [
            ('technician1', 'John', 'Smith', 'john@gearguard.local'),
            ('technician2', 'Sarah', 'Johnson', 'sarah@gearguard.local'),
            ('technician3', 'Mike', 'Davis', 'mike@gearguard.local'),
        ]
        
        for username, first, last, email in technician_data:
            try:
                tech = User.objects.create_user(
                    username=username,
                    email=email,
                    password='tech123',
                    first_name=first,
                    last_name=last,
                    is_staff=False
                )
                tech.groups.add(tech_group)
                users[username] = tech
                self.stdout.write(self.style.SUCCESS(f'✓ Created technician user ({username}, password: tech123)'))
            except Exception as e:
                users[username] = User.objects.get(username=username)
                self.stdout.write(self.style.WARNING(f'⚠ Technician {username} already exists'))
        
        # Create maintenance teams
        teams = {}
        team_data = [
            ('Mechanical Team', 'Handles mechanical and hydraulic systems'),
            ('Electrical Team', 'Handles electrical and control systems'),
            ('Automation Team', 'Handles automated equipment and PLC systems'),
        ]
        
        for name, desc in team_data:
            try:
                team = MaintenanceTeam.objects.create(
                    name=name,
                    description=desc
                )
                # Add technicians to teams
                if 'mechanical' in name.lower():
                    team.members.add(users['technician1'], users['technician2'])
                elif 'electrical' in name.lower():
                    team.members.add(users['technician2'], users['technician3'])
                else:
                    team.members.add(users['technician1'], users['technician3'])
                
                teams[name] = team
                self.stdout.write(self.style.SUCCESS(f'✓ Created team: {name}'))
            except Exception as e:
                teams[name] = MaintenanceTeam.objects.get(name=name)
                self.stdout.write(self.style.WARNING(f'⚠ Team {name} already exists'))
        
        # Create equipment
        equipment_data = [
            {
                'name': 'Hydraulic Press A1',
                'serial_number': 'HP-2025-001',
                'department': 'Manufacturing',
                'location': 'Building A, Floor 2',
                'team': 'Mechanical Team',
                'technician': 'technician1',
            },
            {
                'name': 'CNC Machine 3',
                'serial_number': 'CNC-2024-003',
                'department': 'Production',
                'location': 'Building B, Floor 1',
                'team': 'Automation Team',
                'technician': 'technician3',
            },
            {
                'name': 'Conveyor System B2',
                'serial_number': 'CONV-2023-002',
                'department': 'Logistics',
                'location': 'Warehouse Section B',
                'team': 'Mechanical Team',
                'technician': 'technician1',
            },
            {
                'name': 'Electrical Panel EP-500',
                'serial_number': 'EP-2024-500',
                'department': 'Power Management',
                'location': 'Control Room A',
                'team': 'Electrical Team',
                'technician': 'technician2',
            },
            {
                'name': 'Pump Unit P7',
                'serial_number': 'PUMP-2023-007',
                'department': 'Manufacturing',
                'location': 'Building A, Floor 1',
                'team': 'Mechanical Team',
                'technician': 'technician2',
            },
        ]
        
        equipment_objs = {}
        for eq_data in equipment_data:
            try:
                eq = Equipment.objects.create(
                    name=eq_data['name'],
                    serial_number=eq_data['serial_number'],
                    department=eq_data['department'],
                    location=eq_data['location'],
                    purchase_date=date.today() - timedelta(days=365),
                    warranty_expiry_date=date.today() + timedelta(days=180),
                    default_maintenance_team=teams[eq_data['team']],
                    default_technician=users[eq_data['technician']],
                    assigned_employee=users['manager']
                )
                equipment_objs[eq_data['name']] = eq
                self.stdout.write(self.style.SUCCESS(f'✓ Created equipment: {eq_data["name"]}'))
            except Exception as e:
                equipment_objs[eq_data['name']] = Equipment.objects.get(name=eq_data['name'])
                self.stdout.write(self.style.WARNING(f'⚠ Equipment {eq_data["name"]} already exists'))
        
        # Create maintenance requests
        request_data = [
            {
                'subject': 'Hydraulic fluid leak detected',
                'request_type': 'Corrective',
                'equipment': 'Hydraulic Press A1',
                'technician': 'technician1',
                'status': 'New',
                'team': 'Mechanical Team',
            },
            {
                'subject': 'Monthly preventive maintenance',
                'request_type': 'Preventive',
                'equipment': 'CNC Machine 3',
                'technician': 'technician3',
                'status': 'In Progress',
                'team': 'Automation Team',
                'scheduled_date': date.today() + timedelta(days=5),
            },
            {
                'subject': 'Belt replacement',
                'request_type': 'Corrective',
                'equipment': 'Conveyor System B2',
                'technician': 'technician1',
                'status': 'In Progress',
                'team': 'Mechanical Team',
                'duration': 2.5,
            },
            {
                'subject': 'Quarterly electrical inspection',
                'request_type': 'Preventive',
                'equipment': 'Electrical Panel EP-500',
                'technician': 'technician2',
                'status': 'Repaired',
                'team': 'Electrical Team',
                'scheduled_date': date.today() - timedelta(days=7),
                'duration': 1.5,
            },
            {
                'subject': 'Pump seal maintenance',
                'request_type': 'Preventive',
                'equipment': 'Pump Unit P7',
                'technician': 'technician2',
                'status': 'New',
                'team': 'Mechanical Team',
                'scheduled_date': date.today() + timedelta(days=3),
            },
            {
                'subject': 'Emergency repair - Motor failure',
                'request_type': 'Corrective',
                'equipment': 'Hydraulic Press A1',
                'technician': 'technician1',
                'status': 'In Progress',
                'team': 'Mechanical Team',
            },
        ]
        
        for req_data in request_data:
            try:
                eq = equipment_objs[req_data['equipment']]
                tech = users[req_data['technician']]
                team = teams[req_data['team']]
                
                mr = MaintenanceRequest.objects.create(
                    subject=req_data['subject'],
                    request_type=req_data['request_type'],
                    equipment=eq,
                    assigned_technician=tech,
                    assigned_team=team,
                    status=req_data['status'],
                    created_by=users['manager'],
                    scheduled_date=req_data.get('scheduled_date'),
                    due_date=date.today() + timedelta(days=14) if req_data['status'] == 'New' else None,
                    duration=req_data.get('duration'),
                )
                self.stdout.write(self.style.SUCCESS(f'✓ Created request: {req_data["subject"]}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'✗ Failed to create request {req_data["subject"]}: {e}'))
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('✓ Dummy data population complete!'))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(self.style.WARNING('\n📝 Test Credentials:'))
        self.stdout.write('  Manager:')
        self.stdout.write('    Username: manager')
        self.stdout.write('    Password: manager123')
        self.stdout.write('\n  Technicians:')
        self.stdout.write('    Username: technician1, technician2, technician3')
        self.stdout.write('    Password: tech123')
        self.stdout.write('\n  Dashboard URL: http://localhost:8000/')
        self.stdout.write('  Kanban URL: http://localhost:8000/maintenance/')
        self.stdout.write('  Calendar URL: http://localhost:8000/maintenance/calendar/')
        self.stdout.write('  Reports URL: http://localhost:8000/maintenance/reports/team-requests/')
        self.stdout.write('  Admin URL: http://localhost:8000/admin/')
