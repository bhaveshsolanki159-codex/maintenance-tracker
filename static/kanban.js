// Kanban board client (Phase 6)
// - Loads board via /maintenance/api/kanban-data/
// - Uses HTML5 Drag & Drop
// - Calls /maintenance/api/kanban-move/ to persist moves

(function(){
    const ROOT = document.getElementById('kanban-root');
    const ALERT = document.getElementById('kanban-alert');
    let boardData = null;
    let userRole = 'user';

    // CSRF helper
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let c of cookies) {
                c = c.trim();
                if (c.startsWith(name + '=')) {
                    cookieValue = decodeURIComponent(c.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    function showAlert(msg, type='info'){
        ALERT.textContent = msg;
        ALERT.className = 'kanban-alert kanban-alert-' + type;
        setTimeout(()=>{ ALERT.className = 'kanban-alert'; ALERT.textContent = ''; }, 5000);
    }

    async function fetchBoard(){
        try{
            const res = await fetch('/maintenance/api/kanban-data/');
            const data = await res.json();
            if(!data.success){ showAlert(data.error || 'Failed to load board','error'); return; }
            boardData = data.data;
            userRole = data.user_role || 'user';
            renderBoard(boardData);
        }catch(err){
            console.error(err);
            showAlert('Network error while loading board','error');
        }
    }

    function renderBoard(data){
        ROOT.innerHTML = '';
        const columns = ['New','In Progress','Repaired','Scrap'];

        const board = document.createElement('div');
        board.className = 'kg-board';

        columns.forEach(status => {
            const col = document.createElement('div');
            col.className = 'kg-column';
            col.setAttribute('data-status', status);
            col.addEventListener('dragover', allowDrop);
            col.addEventListener('drop', drop);

            const header = document.createElement('div');
            header.className = 'kg-column-header';
            header.innerHTML = `<h3>${status}</h3>`;

            const list = document.createElement('div');
            list.className = 'kg-column-list';

            const cards = data[status] || [];
            if(cards.length===0){
                const empty = document.createElement('div');
                empty.className = 'kg-empty';
                empty.textContent = 'No requests';
                list.appendChild(empty);
            }

            cards.forEach(card => {
                const el = buildCard(card);
                list.appendChild(el);
            });

            col.appendChild(header);
            col.appendChild(list);
            board.appendChild(col);
        });

        ROOT.appendChild(board);
    }

    function buildCard(card){
        const el = document.createElement('div');
        el.className = 'kg-card';
        el.setAttribute('draggable', userCanDrag(card) ? 'true' : 'false');
        el.dataset.id = card.id;
        el.dataset.status = card.status;

        if(el.getAttribute('draggable')==='true'){
            el.addEventListener('dragstart', drag);
        }

        const subject = document.createElement('div');
        subject.className = 'kg-card-subject';
        subject.textContent = card.subject;

        const meta = document.createElement('div');
        meta.className = 'kg-card-meta';
        meta.innerHTML = `
            <span class="kg-equip">⚙️ ${escapeHtml(card.equipment||'—')}</span>
            <span class="kg-tech">${card.assigned_technician ? escapeHtml(card.assigned_technician.name) : ''}</span>
            <span class="kg-date">${card.scheduled_date ? new Date(card.scheduled_date).toLocaleDateString() : ''}</span>
        `;

        if(card.is_overdue){
            const overdue = document.createElement('div');
            overdue.className = 'kg-overdue';
            overdue.textContent = 'OVERDUE';
            el.appendChild(overdue);
        }

        el.appendChild(subject);
        el.appendChild(meta);

        return el;
    }

    function escapeHtml(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

    function allowDrop(ev){ ev.preventDefault(); }

    function drag(ev){
        ev.dataTransfer.setData('text/plain', ev.target.dataset.id);
        ev.dataTransfer.effectAllowed = 'move';
        ev.target.classList.add('kg-dragging');
    }

    async function drop(ev){
        ev.preventDefault();
        const cardId = ev.dataTransfer.getData('text/plain');
        const cardEl = document.querySelector(`[data-id='${cardId}']`);
        const fromStatus = cardEl.dataset.status;
        const toStatus = ev.currentTarget.getAttribute('data-status');

        // Visual - optimistic move
        const list = ev.currentTarget.querySelector('.kg-column-list');
        list.appendChild(cardEl);

        // If no permission, revert immediately
        if(!canUserMoveTo(fromStatus, toStatus, cardEl)){
            showAlert('You do not have permission to move this card','error');
            fetchBoard();
            return;
        }

        // If moving to Repaired, prompt for duration
        let duration = null;
        if(toStatus === 'Repaired'){
            duration = prompt('Enter hours spent (e.g. 2.5):');
            if(duration===null || duration.trim()===''){
                showAlert('Duration required to complete work; action cancelled','error');
                fetchBoard();
                return;
            }
            duration = parseFloat(duration);
            if(isNaN(duration) || duration <= 0){ showAlert('Invalid duration','error'); fetchBoard(); return; }
        }

        try{
            const res = await fetch('/maintenance/api/kanban-move/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({ id: parseInt(cardId,10), new_status: toStatus, duration: duration })
            });

            const data = await res.json();
            if(!data.success){
                showAlert(data.error || 'Move rejected by server','error');
                fetchBoard();
                return;
            }

            showAlert(data.message || 'Card moved','success');
            // Refresh a little to reflect authoritative state
            setTimeout(fetchBoard, 300);

        }catch(err){
            console.error(err);
            showAlert('Network error while saving move','error');
            fetchBoard();
        }
    }

    function userCanDrag(card){
        // Role-based rules: Users read-only
        if(userRole === 'user') return false;
        // Managers can move all
        if(userRole === 'manager') return true;
        // Technicians: can move New->In Progress only if assigned, and In Progress->Repaired
        if(userRole === 'technician'){
            // We'll enable dragging; final permission checked on drop by server
            return true;
        }
        return false;
    }

    function canUserMoveTo(from, to, cardEl){
        if(userRole === 'manager') return true;
        if(userRole === 'user') return false;
        if(userRole === 'technician'){
            const assignedName = cardEl.querySelector('.kg-tech')?.textContent?.trim();
            // If moving New -> In Progress, technician must be assigned (and be them) — server enforces exact user check
            if(from === 'New' && to === 'In Progress') return true;
            if(from === 'In Progress' && to === 'Repaired') return true;
            // Technicians cannot move to Scrap
            return false;
        }
        return false;
    }

    // Initial load
    fetchBoard();

})();
