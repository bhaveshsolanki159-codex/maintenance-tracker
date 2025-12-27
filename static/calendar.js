(function(){
  const ROOT = document.getElementById('calendar-root');
  const MONTH_LABEL = document.getElementById('cal-month');
  const ALERT = document.getElementById('calendar-alert');
  const prevBtn = document.getElementById('cal-prev');
  const nextBtn = document.getElementById('cal-next');
  const todayBtn = document.getElementById('cal-today');

  let viewDate = new Date(); // month view

  function showAlert(msg){ ALERT.textContent = msg; ALERT.classList.add('show'); setTimeout(()=>{ ALERT.classList.remove('show'); ALERT.textContent=''; },4000); }

  function fetchEvents(year, month){
    return fetch(`/maintenance/api/calendar-data/?year=${year}&month=${month}`)
      .then(r=>r.json())
      .then(j=>{ if(!j.success) throw new Error(j.error||'Failed'); return j.events; });
  }

  function start(){ render(); }

  function render(){
    const year = viewDate.getFullYear();
    const month = viewDate.getMonth()+1; // 1-12
    MONTH_LABEL.textContent = viewDate.toLocaleString(undefined,{month:'long', year:'numeric'});
    ROOT.innerHTML = '';

    fetchEvents(year, month).then(events=>{
      const map = {};
      events.forEach(e=>{ map[e.date] = map[e.date]||[]; map[e.date].push(e); });

      buildCalendarGrid(year, month, map);
    }).catch(err=>{ console.error(err); showAlert('Failed to load calendar'); buildCalendarGrid(year, month, {}); });
  }

  function buildCalendarGrid(year, month, eventsMap){
    // first day of month
    const first = new Date(year, month-1, 1);
    const startDay = first.getDay(); // 0=Sun
    const daysInMonth = new Date(year, month, 0).getDate();

    // previous month tail
    const prevDays = startDay; // how many preceding cells
    const totalCells = Math.ceil((prevDays + daysInMonth)/7)*7;

    let cellIndex = 0;
    for(let i=0;i<totalCells;i++){
      const cell = document.createElement('div');
      cell.className = 'cal-cell';

      const cellDate = new Date(year, month-1, i - prevDays + 1);
      if(cellDate.getMonth() !== (month-1)) cell.classList.add('outside');

      const dayNum = document.createElement('div'); dayNum.className='day-num'; dayNum.textContent = cellDate.getDate();
      if(isToday(cellDate)) cell.classList.add('today');
      cell.appendChild(dayNum);

      const eventsWrap = document.createElement('div'); eventsWrap.className='cal-events';
      const key = cellDate.toISOString().slice(0,10);
      const evs = eventsMap[key]||[];
      evs.slice(0,3).forEach(ev=>{
        const evEl = document.createElement('div'); evEl.className='cal-event';
        evEl.innerHTML = `<div class="equip">${escapeHtml(ev.equipment||'—')}</div><div class="title">${escapeHtml(ev.subject)}</div>`;
        evEl.addEventListener('click', ()=>{ window.location.href = `/maintenance/request/${ev.id}/`; });
        eventsWrap.appendChild(evEl);
      });
      if(evs.length>3){ const more = document.createElement('div'); more.className='cal-event'; more.textContent = `+${evs.length-3} more`; eventsWrap.appendChild(more); }

      cell.appendChild(eventsWrap);

      // click to create preventive request with date prefilled
      cell.addEventListener('click', (e)=>{
        // if clicked on an event, handled above
        if(e.target.closest('.cal-event')) return;
        const iso = cellDate.toISOString().slice(0,10);
        // navigate to create page with scheduled_date param
        window.location.href = `/maintenance/request/new/?scheduled_date=${iso}&request_type=Preventive`;
      });

      ROOT.appendChild(cell);
      cellIndex++;
    }
  }

  function isToday(d){ const t = new Date(); return d.getFullYear()===t.getFullYear() && d.getMonth()===t.getMonth() && d.getDate()===t.getDate(); }
  function escapeHtml(s){ return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

  prevBtn.addEventListener('click', ()=>{ viewDate.setMonth(viewDate.getMonth()-1); render(); });
  nextBtn.addEventListener('click', ()=>{ viewDate.setMonth(viewDate.getMonth()+1); render(); });
  todayBtn.addEventListener('click', ()=>{ viewDate = new Date(); render(); });

  start();
})();
