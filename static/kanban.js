function allowDrop(ev) {
    ev.preventDefault();
}

function drag(ev) {
    ev.dataTransfer.setData("text", ev.target.id);
}

function drop(ev) {
    ev.preventDefault();

    let data = ev.dataTransfer.getData("text");
    let card = document.getElementById(data);
    let newStatus = ev.currentTarget.getAttribute("data-status");

    ev.currentTarget.appendChild(card);

    let requestId = card.getAttribute("data-id");

    updateStatus(requestId, newStatus);
}

function updateStatus(requestId, status) {
    fetch('/maintenance/update-status/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            id: requestId,
            status: status
        })
    });
}

// CSRF Helper
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
