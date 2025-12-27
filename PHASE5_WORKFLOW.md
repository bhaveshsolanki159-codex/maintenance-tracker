PHASE 5: WORKFLOW LOGIC - Implementation Guide
================================================

## Overview

Phase 5 implements strict, realistic workflow rules that govern how Maintenance Requests 
move through their lifecycle. This is the core ERP engine that prevents invalid transitions 
and enforces role-based access control.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    PHASE 5: WORKFLOW ENGINE                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────┐      ┌──────────────────┐                │
│  │  PermissionCheck │      │ WorkflowEngine   │                │
│  │  (Role-based)    │      │ (State Machine)  │                │
│  └──────────────────┘      └──────────────────┘                │
│         │                           │                            │
│         └───────────────┬───────────┘                            │
│                         │                                        │
│                    ┌────▼─────┐                                 │
│                    │  Workflow│                                 │
│                    │Exceptions│                                 │
│                    └──────────┘                                 │
│                                                                   │
│  Integrated with:                                               │
│  - MaintenanceRequest model (methods)                           │
│  - Django views (controllers)                                   │
│  - JSON APIs (REST endpoints)                                   │
│  - Django ORM (database)                                        │
└─────────────────────────────────────────────────────────────────┘
```

## Files Created/Modified

### New Files
1. **maintenance/workflow.py** (~400 lines)
   - WorkflowEngine: State machine & business rules
   - PermissionChecker: Role-based access control
   - Helper functions: get_available_actions(), get_workflow_state()
   - Custom exceptions: WorkflowException, InvalidTransitionError, PermissionError, MissingDataError

### Modified Files
1. **maintenance/models.py**
   - Added: get_available_actions(), get_workflow_state(), clean() method
   - Integration with workflow engine

2. **maintenance/views.py**
   - Added 5 new workflow API endpoints:
     - assign_technician() - POST /maintenance/api/assign-technician/
     - start_work() - POST /maintenance/api/start-work/
     - complete_work() - POST /maintenance/api/complete-work/
     - scrap_request() - POST /maintenance/api/scrap-request/
     - get_request_actions() - GET /maintenance/api/request-actions/
   - Added request_detail() - GET /maintenance/request/<id>/

3. **maintenance/urls.py**
   - Added 6 new URL patterns for workflow actions

### New Template Files
1. **maintenance/templates/maintenance/request_detail.html**
   - Detailed request view with workflow actions
   - Role-based button visibility
   - Interactive action forms

## Workflow Rules

### FLOW 1: CORRECTIVE (Emergency/Unplanned)

```
Any User Creates Request
    │
    ▼
Status: New (Automatic)
Request Type: Corrective
    │
    ├─ Manager/Technician assigns self
    ▼
Status: In Progress
    │
    ├─ Technician records hours
    ▼
Status: Repaired
    │
    ├─ (Terminal transition possible)
    ▼
Status: Scrap (Manager only)
    │
    └─ Terminal State (Cannot transition out)
```

### FLOW 2: PREVENTIVE (Scheduled Maintenance)

```
Manager ONLY Creates Request
    │
    ├─ Scheduled Date MANDATORY
    ├─ Status: New (Automatic)
    ├─ Request Type: Preventive
    │
    ├─ Manager/Technician assigns technician
    ▼
Status: In Progress
    │
    ├─ Technician records hours
    ▼
Status: Repaired
    │
    ├─ (Terminal transition possible)
    ▼
Status: Scrap (Manager only)
    │
    └─ Terminal State
```

## State Transition Matrix

Valid transitions (enforced server-side):

| Current Status | Valid Next States | Allowed Roles    |
|----------------|-------------------|-----------------|
| New            | In Progress, Scrap | Tech, Manager   |
| In Progress    | Repaired, Scrap   | Tech, Manager   |
| Repaired       | Scrap             | Manager only    |
| Scrap          | (None - Terminal) | N/A             |

## Role Definition

```python
USER = 'user'              # Any authenticated user
TECHNICIAN = 'technician'  # Belongs to maintenance_teams
MANAGER = 'manager'        # is_staff or is_superuser
```

### Role Hierarchy

```
MANAGER (highest)
    └─ TECHNICIAN
        └─ USER (lowest)
```

Managers inherit all permissions of lower roles.

## Permission Rules

| Action                | User | Technician | Manager |
|-----------------------|------|-----------|---------|
| Create Corrective     | ✓    | ✓         | ✓       |
| Create Preventive     | ✗    | ✗         | ✓       |
| Assign Technician     | ✗    | ✓ (team)  | ✓       |
| Start Work (assign)   | ✗    | ✓ (own)   | ✓       |
| Complete Work         | ✗    | ✓ (own)   | ✓       |
| Scrap Request         | ✗    | ✗         | ✓       |

## API Endpoints

### 1. Assign Technician
```
POST /maintenance/api/assign-technician/
```

**Request Body (form-data):**
```
request_id: int
technician_id: int
csrfmiddlewaretoken: string
```

**Success Response (200):**
```json
{
  "success": true,
  "message": "Assigned technician John Doe to request #42",
  "technician": "John Doe"
}
```

**Error Responses:**
- 403 (Permission): "Only managers and team members can assign"
- 400 (Missing Data): "Cannot assign: request has no assigned team"
- 400 (Validation): "Technician not a member of assigned team"

---

### 2. Start Work
```
POST /maintenance/api/start-work/
```

**Request Body:**
```
request_id: int
csrfmiddlewaretoken: string
```

**Success Response (200):**
```json
{
  "success": true,
  "message": "Started work on request #42",
  "status": "In Progress"
}
```

**Error Responses:**
- 403 (Permission): "Only assigned technician or manager can start work"
- 400 (Workflow): "Cannot transition from New to In Progress. ..."
- 400 (Missing Data): "No technician assigned"

---

### 3. Complete Work
```
POST /maintenance/api/complete-work/
```

**Request Body:**
```
request_id: int
duration_hours: float (required, > 0)
csrfmiddlewaretoken: string
```

**Success Response (200):**
```json
{
  "success": true,
  "message": "Completed work on request #42 (2.5 hours)",
  "status": "Repaired",
  "duration": 2.5
}
```

**Error Responses:**
- 403 (Permission): "Only assigned technician or manager..."
- 400 (Workflow): "Cannot transition from... to Repaired"
- 400 (Missing Data): "Duration required and must be positive"

---

### 4. Scrap Request
```
POST /maintenance/api/scrap-request/
```

**Request Body:**
```
request_id: int
csrfmiddlewaretoken: string
```

**Success Response (200):**
```json
{
  "success": true,
  "message": "Marked request #42 as scrapped (terminal state)",
  "status": "Scrap"
}
```

**Error Responses:**
- 403 (Permission): "Only managers can scrap requests"
- 400 (Workflow): "Cannot transition... already scrapped"

---

### 5. Get Request Actions
```
GET /maintenance/api/request-actions/?request_id=42
```

**Success Response (200):**
```json
{
  "success": true,
  "actions": {
    "current_status": "New",
    "assigned_technician": null,
    "can_assign": true,
    "can_start": false,
    "can_complete": false,
    "can_scrap": true
  },
  "state": {
    "id": 42,
    "status": "New",
    "request_type": "Corrective",
    "subject": "Hydraulic pump leaking",
    "equipment": "Press A1",
    "assigned_team": "Hydraulics Team",
    "assigned_technician": null,
    "duration": null,
    "is_overdue": false,
    "valid_next_transitions": ["In Progress", "Scrap"]
  },
  "user_role": "manager"
}
```

---

### 6. Request Detail View
```
GET /maintenance/request/<request_id>/
```

Displays full request details with interactive workflow buttons. Buttons are enabled/disabled based on:
- User role
- Request status
- Available next transitions
- Permission checks

## Request Detail Page Features

1. **Header Section**
   - Request ID and subject
   - Equipment info
   - Creation date/user
   - Status badge (color-coded)
   - User role indicator

2. **Information Grid** (2-column responsive)
   - Equipment Details: name, serial, department, location
   - Assignment: team, technician, warranty status
   - Schedule: scheduled date, due date, duration
   - Timeline: created, last updated

3. **Workflow Actions Section**
   - Context-aware buttons (enabled/disabled dynamically)
   - Assign Technician (dropdown + confirm)
   - Start Work (instant transition)
   - Complete Work (input duration + confirm)
   - Mark as Scrap (requires confirmation)

4. **Alert System**
   - Success, error, and info messages
   - Auto-dismiss after 5 seconds
   - Ajax-based (no page reload)

## Example Usage (Frontend JavaScript)

```javascript
// Get available actions
async function updateActionUI() {
  const response = await fetch('/maintenance/api/request-actions/?request_id=42');
  const data = await response.json();
  
  if (data.success) {
    // Show only allowed actions
    document.getElementById('btn-assign').disabled = !data.actions.can_assign;
    document.getElementById('btn-start').disabled = !data.actions.can_start;
    document.getElementById('btn-complete').disabled = !data.actions.can_complete;
  }
}

// Complete work
async function completeWork() {
  const formData = new FormData();
  formData.append('request_id', 42);
  formData.append('duration_hours', 2.5);
  
  const response = await fetch('/maintenance/api/complete-work/', {
    method: 'POST',
    body: formData
  });
  
  const data = await response.json();
  if (data.success) {
    alert(`Work recorded: ${data.duration} hours`);
    location.reload();
  }
}
```

## Error Handling Hierarchy

```
WorkflowException (Base)
├── InvalidTransitionError
│   └── "Cannot transition from X to Y"
├── PermissionError
│   └── "User lacks required role for this action"
├── MissingDataError
│   └── "Required field missing (e.g., duration, scheduled_date)"
└── ValidationError (Django)
    └── "Invalid data (e.g., technician not in team)"
```

All errors return JSON with:
```json
{
  "success": false,
  "error": "Human-readable message",
  "error_type": "permission|workflow|validation|unknown"
}
```

## Edge Cases Handled

1. **Attempt status change without assignment**
   - Error: "No technician assigned. Please assign first."

2. **Duration missing on completion**
   - Error: "Duration required. Must be positive number."

3. **Unauthorized user attempts transition**
   - Error: "Only assigned technician or manager can..."

4. **Scrapped equipment receives request**
   - Prevented at creation (clean() method)
   - API also blocks with 422 Unprocessable Entity

5. **Technician not in team**
   - Validation error during assignment
   - Prevents inconsistent state

6. **Preventive request missing scheduled date**
   - Validation error at creation
   - Required by business rule

## Testing Scenarios

### Scenario 1: Happy Path (Manager)
```
1. Manager creates Corrective request (request.status = "New")
2. Manager assigns technician (WorkflowEngine.assign_technician)
3. Technician starts work (request.status = "In Progress")
4. Technician completes work with 2.5 hours (request.status = "Repaired")
5. Manager scraps request (request.status = "Scrap")
```

### Scenario 2: Unauthorized Access
```
1. User creates Corrective request (allowed)
2. User attempts to complete work
3. PermissionError: "Only assigned technician or manager..."
```

### Scenario 3: Preventive Workflow
```
1. User attempts to create Preventive request
2. PermissionError: "Only managers can create preventive..."
3. Manager creates with scheduled_date = "2024-01-15"
4. Request appears in calendar
5. Technician executes as normal (same state machine)
```

### Scenario 4: Invalid Transition
```
1. Request in "New" status
2. Technician attempts: New → Repaired (skip In Progress)
3. InvalidTransitionError: "Cannot transition from New to Repaired"
```

## Database Integrity

All validations occur at:
1. **Model level** (clean() method) - Preventive scheduling, scrapped equipment
2. **API level** (views) - Permission checks, role validation
3. **Business logic level** (WorkflowEngine) - State machine rules

No client-side validation can bypass server-side rules.

## Security Considerations

1. **CSRF Protection**: All POST endpoints require csrfmiddlewaretoken
2. **Authentication**: @login_required on all views
3. **Authorization**: Server-side permission checks (not client-side)
4. **Input Validation**: Duration must be positive, scheduled_date must be valid
5. **State Isolation**: Users cannot see transitions they don't have permission for

## Performance

- Minimal database queries (uses select_related/prefetch_related)
- JSON APIs enable quick UI updates without page reload
- Action availability computed on-demand (not cached)

## Integration Points

### With Phase 4 (Auto-Fill)
- Equipment details auto-populate team/technician at creation
- Workflow respects pre-filled assignments

### With Kanban Board
- Status changes via workflow reflected in kanban immediately
- Filter by status showing only "New", "In Progress", "Repaired"

### With Calendar
- Preventive requests with scheduled_date appear in calendar view
- Can trigger workflow from calendar context

## Migration Notes

No database changes required. Workflow logic uses existing fields:
- request.status (existing choices)
- request.assigned_technician (existing FK)
- request.assigned_team (existing FK)
- request.duration (existing float field)

All workflow validations are business logic, not schema changes.

---

**Phase 5 Status: COMPLETE**

All workflow rules implemented, tested, and documented.
Ready for integration with Phase 6 (Kanban enhancements) and Phase 7 (Calendar).
