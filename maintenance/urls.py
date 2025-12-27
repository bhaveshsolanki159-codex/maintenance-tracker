from django.urls import path
from . import views

app_name = 'maintenance'

urlpatterns = [
    # Existing views
    path('', views.kanban_board, name='kanban'),
    path('api/equipment-details/', views.get_equipment_details, name='api_equipment_details'),
    path('request/new/', views.create_maintenance_request, name='create_request'),
    
    # PHASE 5: Workflow transition APIs
    path('api/assign-technician/', views.assign_technician, name='api_assign_technician'),
    path('api/start-work/', views.start_work, name='api_start_work'),
    path('api/complete-work/', views.complete_work, name='api_complete_work'),
    path('api/scrap-request/', views.scrap_request, name='api_scrap_request'),
    path('api/request-actions/', views.get_request_actions, name='api_request_actions'),
    path('api/kanban-data/', views.kanban_data, name='api_kanban_data'),
    path('api/kanban-move/', views.kanban_move, name='api_kanban_move'),
    path('calendar/', views.calendar_page, name='calendar'),
    path('api/calendar-data/', views.calendar_data, name='api_calendar_data'),
    
    # PHASE 9: Reports
    path('reports/team-requests/', views.report_team_requests, name='report_team_requests'),
    path('reports/equipment-requests/', views.report_equipment_requests, name='report_equipment_requests'),
    path('reports/department-requests/', views.report_department_requests, name='report_department_requests'),
    
    # Request detail view
    path('request/<int:request_id>/', views.request_detail, name='request_detail'),
]
