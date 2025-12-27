PHASE 5: QUICK START GUIDE
==========================

## Testing the Workflow System

### Setup (One-time)

1. **Create test users with different roles**:
   ```bash
   python manage.py createsuperuser
   # Create user1 (manager) - use is_staff=True
   
   python manage.py shell
   >>> from django.contrib.auth.models import User
   >>> user2 = User.objects.create_user('tech1', 'tech1@ex.com', 'pass123')
   >>> user3 = User.objects.create_user('user1', 'user1@ex.com', 'pass123')
   ```

2. **Create maintenance team and add technician**:
   ```bash
   python manage.py shell
   >>> from teams.models import MaintenanceTeam
   >>> from django.contrib.auth.models import User
   >>> team = MaintenanceTeam.objects.create(name='Hydraulics Team')
   >>> tech = User.objects.get(username='tech1')
   >>> team.members.add(tech)
   ```

3. **Create equipment with team assignment**:
   ```bash
   >>> from equipment.models import Equipment
   >>> eq = Equipment.objects.create(
   ...     name='Hydraulic Press A1',
   ...     serial_number='SN-HYD-001',
   ...     department='Manufacturing',
   ...     location='Floor 1',
   ...     purchase_date='2023-01-01',
   ...     default_maintenance_team=team,
   ...     default_technician=tech
   ... )
   ```

### Test Scenario 1: Manager Workflow

```bash
# Start development server
python manage.py runserver

# 1. Login as manager (is_staff=True)
# Visit: http://localhost:8000/maintenance/request/new/

# 2. Create Corrective request
- Select Equipment: Hydraulic Press A1
- Subject: "Pump leaking"
- Type: Corrective
- Submit

# 3. Note request ID (e.g., #42)

# 4. View request details
# Visit: http://localhost:8000/maintenance/request/42/

# 5. Click "Assign Technician" button
# - Select: tech1
# - Confirm

# 6. Click "Start Work"
# - Status changes: New → In Progress

# 7. Click "Complete Work"
# - Enter Duration: 2.5
# - Record

# 8. Click "Mark as Scrap"
# - Confirm (terminal state)
```

### Test Scenario 2: Permission Denial

```bash
# 1. Login as regular user (not is_staff, not in team)

# 2. Create Corrective request (ALLOWED)
# - Subject: "Preventive check"
# - Type: Corrective

# 3. Try to click "Assign Technician" (DISABLED)
# - Button is disabled (frontend)
# - If clicked directly via curl:
#   Response: 403 Forbidden
#   Error: "Only managers and team members can assign"

# 4. Try to complete work
# - Button disabled
# - Cannot proceed
```

### Test Scenario 3: Preventive Request (Manager Only)

```bash
# 1. Login as manager

# 2. Create Preventive request
# - Must set Scheduled Date (mandatory)
# - Type: Preventive
# - Subject: "Monthly maintenance"

# 3. Request now appears in calendar (future phase)

# 4. Same workflow: assign → start → complete → scrap
```

### Test Scenario 4: Invalid Transition

```bash
# Using browser DevTools or curl:

# 1. Create request in "New" status (request_id=42)

# 2. Try to skip "In Progress" and go directly to "Repaired"
# POST /maintenance/api/complete-work/
# {request_id: 42, duration_hours: 2}

# Response: 400 Bad Request
# Error: "Cannot transition from New to Repaired"
```

### Test Scenario 5: Missing Duration

```bash
# 1. Put request in "In Progress" status

# 2. Try to complete without duration
# POST /maintenance/api/complete-work/
# {request_id: 42, duration_hours: ""}

# Response: 400 Bad Request
# Error: "Duration required and must be positive"
```

## API Testing with curl

### Assign Technician
```bash
curl -X POST http://localhost:8000/maintenance/api/assign-technician/ \
  -H "Cookie: sessionid=YOUR_SESSION" \
  -d "request_id=42&technician_id=2&csrfmiddlewaretoken=TOKEN"
```

### Start Work
```bash
curl -X POST http://localhost:8000/maintenance/api/start-work/ \
  -H "Cookie: sessionid=YOUR_SESSION" \
  -d "request_id=42&csrfmiddlewaretoken=TOKEN"
```

### Complete Work
```bash
curl -X POST http://localhost:8000/maintenance/api/complete-work/ \
  -H "Cookie: sessionid=YOUR_SESSION" \
  -d "request_id=42&duration_hours=2.5&csrfmiddlewaretoken=TOKEN"
```

### Get Actions
```bash
curl -X GET "http://localhost:8000/maintenance/api/request-actions/?request_id=42" \
  -H "Cookie: sessionid=YOUR_SESSION"
```

## Browser Developer Tools Testing

### Get CSRF Token
```javascript
const token = document.querySelector('[name=csrfmiddlewaretoken]').value;
console.log(token);
```

### Assign Technician
```javascript
fetch('/maintenance/api/assign-technician/', {
  method: 'POST',
  body: new FormData(Object.assign(new FormData(), {
    request_id: '42',
    technician_id: '2',
    csrfmiddlewaretoken: token
  }))
}).then(r => r.json()).then(d => console.log(d));
```

### Check Available Actions
```javascript
fetch('/maintenance/api/request-actions/?request_id=42')
  .then(r => r.json())
  .then(d => console.log(d.actions));
```

## Verification Checklist

### Backend Logic
- [ ] PermissionChecker correctly identifies roles
- [ ] WorkflowEngine validates all transitions
- [ ] Exceptions raised for invalid actions
- [ ] JSON responses properly formatted
- [ ] CSRF token validation working

### Frontend
- [ ] Buttons show/hide based on permissions
- [ ] Status colors update correctly
- [ ] Forms appear/disappear as expected
- [ ] Ajax calls don't reload page
- [ ] Alerts display messages clearly

### Database
- [ ] Request status updates in DB
- [ ] Duration recorded on completion
- [ ] Technician assignment persists
- [ ] No orphaned requests

### Role-Based Access
- [ ] Manager: Full access to all actions
- [ ] Technician: Can work on own requests
- [ ] User: Can create, cannot manage

## Common Issues

### "Button disabled but should be enabled"
**Cause**: Server-side permission check failing
**Solution**: 
1. Check user role: `PermissionChecker.get_user_role(user)`
2. Check request status: `request.status`
3. Check team membership: `user in request.assigned_team.members.all()`

### "Got 403 Forbidden on API call"
**Cause**: Permission denied
**Solution**: Check user role vs required role for action

### "Got 400 Bad Request"
**Cause**: Invalid transition or missing data
**Solution**: Check request status matches valid transitions

### "CSRF token missing"
**Cause**: Form data not sending token
**Solution**: Ensure `csrfmiddlewaretoken` included in POST

## Debugging

### View Workflow State
```bash
python manage.py shell
>>> from maintenance.models import MaintenanceRequest
>>> r = MaintenanceRequest.objects.get(id=42)
>>> r.get_workflow_state()
{
  'id': 42,
  'status': 'In Progress',
  'assigned_technician': 'John Doe',
  ...
}
```

### Check User Role
```bash
>>> from maintenance.workflow import PermissionChecker
>>> PermissionChecker.get_user_role(user)
'manager'
```

### Check Available Actions
```bash
>>> r.get_available_actions(user)
{
  'can_assign': True,
  'can_start': False,
  'can_complete': True,
  'can_scrap': True,
  ...
}
```

### Trace Permission Denial
```bash
>>> PermissionChecker.can_start_work(user, r)
False

>>> r.assigned_technician
<User: john_doe>

>>> user
<User: jane_smith>

# → User is not assigned technician, cannot start
```

## Performance Testing

### Check Query Count
```bash
>>> from django.test.utils import override_settings
>>> with override_settings(DEBUG=True):
...     r = MaintenanceRequest.objects.get(id=42)
...     actions = r.get_available_actions(user)
>>> from django.db import connection
>>> len(connection.queries)  # Should be minimal (< 5)
```

### Response Time
- `/maintenance/api/request-actions/?request_id=42`: < 50ms
- `/maintenance/api/assign-technician/`: < 100ms
- `/maintenance/api/complete-work/`: < 100ms

## Next Steps (Phase 6)

Phase 5 provides:
- ✅ Strict state machine
- ✅ Role-based permissions
- ✅ REST APIs for workflow
- ✅ Detailed request view

Phase 6 will use these APIs to:
- Kanban drag-drop with workflow transitions
- Real-time request updates
- Status change animations
- Advanced filtering by role

---

**Ready to test? Start with the setup above!**
