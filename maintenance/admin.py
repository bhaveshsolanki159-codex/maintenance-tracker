from django.contrib import admin

# Register your models here.
from django.contrib import admin
from django.utils.html import format_html
from .models import MaintenanceRequest
from .workflow import get_available_actions, PermissionChecker

@admin.register(MaintenanceRequest)
class MaintenanceRequestAdmin(admin.ModelAdmin):
	"""
	Django admin interface for MaintenanceRequest with workflow visualization.
    
	PHASE 5: Shows workflow state and available actions for each request.
	"""
    
	list_display = (
		'id_link',
		'subject_truncated',
		'equipment_name',
		'status_badge',
		'request_type',
		'assigned_technician_name',
		'assigned_team_name',
		'is_overdue_badge',
		'created_at_short'
	)
    
	list_filter = (
		'status',
		'request_type',
		'assigned_team',
		'created_at',
	)
    
	search_fields = (
		'subject',
		'equipment__name',
		'assigned_technician__first_name',
		'assigned_technician__last_name',
		'assigned_team__name',
	)
    
	readonly_fields = (
		'created_by',
		'created_at',
		'updated_at',
		'workflow_state_display',
		'available_actions_display',
	)
    
	fieldsets = (
		('Request Details', {
			'fields': ('subject', 'request_type', 'equipment')
		}),
		('Assignment', {
			'fields': ('assigned_team', 'assigned_technician')
		}),
		('Scheduling', {
			'fields': ('scheduled_date', 'due_date', 'duration')
		}),
		('Status & Workflow', {
			'fields': (
				'status',
				'workflow_state_display',
				'available_actions_display',
			),
			'classes': ('wide',)
		}),
		('Metadata', {
			'fields': ('created_by', 'created_at', 'updated_at'),
			'classes': ('collapse',)
		}),
	)
    
	def id_link(self, obj):
		"""Render request ID as link to detail page."""
		return format_html('<b>#{}</b>', obj.id)
	id_link.short_description = 'ID'
    
	def subject_truncated(self, obj):
		"""Truncate subject to 50 chars."""
		return obj.subject[:50] + ('...' if len(obj.subject) > 50 else '')
	subject_truncated.short_description = 'Subject'
    
	def equipment_name(self, obj):
		"""Display equipment name."""
		return obj.equipment.name if obj.equipment else '—'
	equipment_name.short_description = 'Equipment'
    
	def status_badge(self, obj):
		"""Render status as colored badge."""
		color_map = {
			'New': '#3b82f6',
			'In Progress': '#f59e0b',
			'Repaired': '#10b981',
			'Scrap': '#ef4444',
		}
		color = color_map.get(obj.status, '#6b7280')
        
		return format_html(
			'<span style="background-color: {}; color: white; padding: 3px 10px; '
			'border-radius: 3px; font-weight: bold;">{}</span>',
			color,
			obj.get_status_display()
		)
	status_badge.short_description = 'Status'
    
	def request_type(self, obj):
		"""Display request type with icon."""
		icon = '🔴' if obj.request_type == 'Corrective' else '📅'
		return f'{icon} {obj.get_request_type_display()}'
	request_type.short_description = 'Type'
    
	def assigned_technician_name(self, obj):
		"""Display assigned technician."""
		if obj.assigned_technician:
			return obj.assigned_technician.get_full_name()
		return format_html('<em>Not assigned</em>')
	assigned_technician_name.short_description = 'Technician'
    
	def assigned_team_name(self, obj):
		"""Display assigned team."""
		if obj.assigned_team:
			return f"{obj.assigned_team.name} ({obj.assigned_team.member_count})"
		return format_html('<em>Not assigned</em>')
	assigned_team_name.short_description = 'Team'
    
	def is_overdue_badge(self, obj):
		"""Display overdue status."""
		if obj.is_overdue:
			return format_html(
				'<span style="background-color: #ef4444; color: white; '
				'padding: 3px 10px; border-radius: 3px; font-weight: bold;">OVERDUE</span>'
			)
		return '✓ On Time'
	is_overdue_badge.short_description = 'Schedule'
    
	def created_at_short(self, obj):
		"""Display creation date."""
		if obj.created_at:
			return obj.created_at.strftime('%b %d, %y')
		return '—'
	created_at_short.short_description = 'Created'
    
	def workflow_state_display(self, obj):
		"""Display complete workflow state."""
		state = obj.get_workflow_state()
        
		html = '<table style="width: 100%; border-collapse: collapse;">'
		html += '<tr style="background: #f3f4f6;"><td style="padding: 8px; border: 1px solid #d1d5db;"><b>ID</b></td>'
		html += f'<td style="padding: 8px; border: 1px solid #d1d5db;">{state["id"]}</td></tr>'
        
		html += f'<tr><td style="padding: 8px; border: 1px solid #d1d5db;"><b>Status</b></td>'
		html += f'<td style="padding: 8px; border: 1px solid #d1d5db;"><b>{state["status"]}</b></td></tr>'
        
		html += f'<tr style="background: #f3f4f6;"><td style="padding: 8px; border: 1px solid #d1d5db;"><b>Type</b></td>'
		html += f'<td style="padding: 8px; border: 1px solid #d1d5db;">{state["request_type"]}</td></tr>'
        
		html += f'<tr><td style="padding: 8px; border: 1px solid #d1d5db;"><b>Equipment</b></td>'
		html += f'<td style="padding: 8px; border: 1px solid #d1d5db;">{state["equipment"]}</td></tr>'
        
		html += f'<tr style="background: #f3f4f6;"><td style="padding: 8px; border: 1px solid #d1d5db;"><b>Team</b></td>'
		html += f'<td style="padding: 8px; border: 1px solid #d1d5db;">{state["assigned_team"] or "—"}</td></tr>'
        
		html += f'<tr><td style="padding: 8px; border: 1px solid #d1d5db;"><b>Technician</b></td>'
		html += f'<td style="padding: 8px; border: 1px solid #d1d5db;">{state["assigned_technician"] or "—"}</td></tr>'
        
		html += f'<tr style="background: #f3f4f6;"><td style="padding: 8px; border: 1px solid #d1d5db;"><b>Duration</b></td>'
		html += f'<td style="padding: 8px; border: 1px solid #d1d5db;">{state["duration"] or "—"} hrs</td></tr>'
        
		html += f'<tr><td style="padding: 8px; border: 1px solid #d1d5db;"><b>Created</b></td>'
		html += f'<td style="padding: 8px; border: 1px solid #d1d5db;">{state["created_at"][:19] if state["created_at"] else "—"}</td></tr>'
        
		html += f'<tr style="background: #f3f4f6;"><td style="padding: 8px; border: 1px solid #d1d5db;"><b>Created By</b></td>'
		html += f'<td style="padding: 8px; border: 1px solid #d1d5db;">{state["created_by"] or "—"}</td></tr>'
        
		html += '</table>'
        
		return format_html(html)
	workflow_state_display.short_description = 'Workflow State'
    
	def available_actions_display(self, obj):
		"""Display available workflow actions for current user."""
		valid_next = obj.get_workflow_state().get('valid_next_transitions', [])
        
		html = '<div style="margin: 10px 0;">'
		html += '<b>Valid Next Transitions:</b><br>'
        
		if valid_next:
			for transition in valid_next:
				color = '#3b82f6' if transition != 'Scrap' else '#ef4444'
				html += format_html(
					'<span style="display: inline-block; margin: 5px 5px 5px 0; '
					'background-color: {}; color: white; padding: 5px 12px; '
					'border-radius: 3px; font-size: 12px;">{}</span>',
					color, transition
				)
		else:
			html += '<em>No transitions available (terminal state)</em>'
        
		html += '</div>'
        
		return format_html(html)
	available_actions_display.short_description = 'Available Transitions'
    
	def get_queryset(self, request):
		"""Optimize queryset with select_related."""
		qs = super().get_queryset(request)
		return qs.select_related(
			'equipment',
			'assigned_team',
			'assigned_technician',
			'created_by'
		)
    
	def has_add_permission(self, request):
		"""Allow admin to create requests."""
		return True
    
	def has_change_permission(self, request, obj=None):
		"""Allow admin to view/edit requests."""
		return True
    
	def has_delete_permission(self, request, obj=None):
		"""Allow admin to delete requests."""
		return request.user.is_superuser
    
	def save_model(self, request, obj, form, change):
		"""Set created_by when creating new request."""
		if not change:
			obj.created_by = request.user
		super().save_model(request, obj, form, change)
