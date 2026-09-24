// Healthcare Multi-Agent Web UI Logic
let currentThreadId = `thread_session_${Date.now()}`;

document.addEventListener('DOMContentLoaded', () => {
    fetchPendingTickets();
    setInterval(fetchPendingTickets, 10000); // Poll pending tickets every 10s
});

function getActiveRole() {
    return document.getElementById('role-select').value;
}

function getSelectedPatient() {
    return document.getElementById('patient-select').value;
}

function sendQuickPrompt(promptText) {
    document.getElementById('prompt-input').value = promptText;
    submitPrompt();
}

async function submitPrompt() {
    const promptInput = document.getElementById('prompt-input');
    const promptText = promptInput.value.trim();
    if (!promptText) return;

    const patientId = getSelectedPatient();
    const role = getActiveRole();

    // Render User Message
    renderMessage('user', promptText);
    promptInput.value = '';

    // Render Thinking Indicator
    const loaderId = renderLoader();

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${role.toLowerCase()}_token`
            },
            body: JSON.stringify({
                prompt: promptText,
                patient_id: patientId,
                thread_id: currentThreadId,
                use_hitl: true
            })
        });

        const data = await response.json();
        removeLoader(loaderId);

        if (data.status === 'AWAITING_CLINICIAN_APPROVAL') {
            renderHITLMessage(data);
            fetchPendingTickets();
        } else if (data.status === 'agent_error') {
            renderErrorMessage(data);
        } else {
            renderAgentResponse(data);
        }
    } catch (err) {
        removeLoader(loaderId);
        renderMessage('system', `⚠️ Network / Connection Error: ${err.message}`);
    }
}

function renderMessage(sender, text) {
    const chatFeed = document.getElementById('chat-messages');
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${sender}`;

    const icon = sender === 'user' ? '👤' : '❖';
    msgDiv.innerHTML = `
        <div class="avatar">${icon}</div>
        <div class="content"><p>${escapeHtml(text)}</p></div>
    `;

    chatFeed.appendChild(msgDiv);
    chatFeed.scrollTop = chatFeed.scrollHeight;
}

function renderHITLMessage(data) {
    const chatFeed = document.getElementById('chat-messages');
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message system';

    const ticket = data.ticket || {};
    const pendingAction = data.pending_action || {};
    const params = pendingAction.params || {};
    const detailsStr = params.reason || (params.drug_name ? `${params.drug_name} ${params.dosage || ''}` : JSON.stringify(params));

    msgDiv.innerHTML = `
        <div class="avatar">❖</div>
        <div class="content">
            <h4>🟡 Action Paused - Clinician Attestation Required</h4>
            <p>The AI Agent requested to execute a clinical write action. Pursuant to HIPAA and HITL governance rules, execution is suspended until an authorized clinician approves the order.</p>
            <div class="hitl-ticket-box">
                <div class="hitl-header">
                    <span class="hitl-title">🎫 Ticket ID: ${ticket.ticket_id || 'HITL-001'}</span>
                    <span class="eta-badge">⏱️ Est. ETA: ${ticket.estimated_eta || '15 mins'}</span>
                </div>
                <div class="hitl-action-details">
                    <strong>Action:</strong> ${pendingAction.action_type || 'CREATE_MEDICATION_ORDER'}<br>
                    <strong>Details:</strong> ${escapeHtml(detailsStr)}<br>
                    <strong>Status:</strong> ${ticket.status || 'AWAITING_CLINICIAN_APPROVAL'}
                </div>
                <div class="hitl-buttons">
                    <button class="btn-approve" onclick="attestTicket('${ticket.ticket_id}', true)">✓ Approve & Execute Order</button>
                    <button class="btn-reject" onclick="attestTicket('${ticket.ticket_id}', false)">✕ Reject & Cancel</button>
                </div>
            </div>
        </div>
    `;

    chatFeed.appendChild(msgDiv);
    chatFeed.scrollTop = chatFeed.scrollHeight;
}

function disableHitlButtons(ticketId) {
    const btns = document.querySelectorAll(`button[onclick*="${ticketId}"]`);
    btns.forEach(b => {
        b.disabled = true;
        b.style.opacity = '0.4';
        b.style.cursor = 'not-allowed';
        b.innerText = 'Processing...';
    });
}

function renderAgentResponse(data) {
    const chatFeed = document.getElementById('chat-messages');
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message system';

    let summaryText = data.final_summary || data.data_ingestion?.patient_summary || 'Task completed successfully.';
    let extraHTML = formatMarkdownText(summaryText);

    if (data.quality_metrics && data.quality_metrics.length > 0) {
        extraHTML += `<div style="margin-top: 10px;"><strong>HEDIS Compliance:</strong>`;
        data.quality_metrics.forEach(m => {
            const statusClass = m.status === 'COMPLIANT' || m.status === 'PASS' ? 'success' : 'warning';
            extraHTML += `<br><span class="badge ${statusClass}">${m.metric || m.metric_id}: ${m.status} (${m.value})</span>`;
        });
        extraHTML += `</div>`;
    }

    msgDiv.innerHTML = `
        <div class="avatar">❖</div>
        <div class="content">
            ${extraHTML}
        </div>
    `;

    chatFeed.appendChild(msgDiv);
    chatFeed.scrollTop = chatFeed.scrollHeight;
}

function renderErrorMessage(data) {
    const chatFeed = document.getElementById('chat-messages');
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message system';

    msgDiv.innerHTML = `
        <div class="avatar">⚠️</div>
        <div class="content" style="border-color: var(--accent-danger);">
            <h4 style="color: var(--accent-danger);">Execution Incident Logged</h4>
            <p>${escapeHtml(data.error_message)}</p>
            <p style="font-size: 12px; color: var(--text-muted); margin-top: 6px;">
                <strong>Draft Preserved:</strong> "${escapeHtml(data.draft_prompt || '')}"<br>
                ${data.recommendation}
            </p>
        </div>
    `;

    chatFeed.appendChild(msgDiv);
    chatFeed.scrollTop = chatFeed.scrollHeight;
}

async function attestTicket(ticketId, isApproved) {
    disableHitlButtons(ticketId);
    const endpoint = isApproved ? '/api/hitl/approve' : '/api/hitl/reject';
    const role = getActiveRole();

    try {
        const res = await fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${role.toLowerCase()}_token`
            },
            body: JSON.stringify({
                ticket_id: ticketId,
                clinician_notes: isApproved ? 'Approved by attending clinician via Web UI.' : 'Rejected due to clinical contraindication.'
            })
        });

        const data = await res.json();
        if (res.ok) {
            renderMessage('system', `${isApproved ? '✅' : '🚫'} ${data.message}`);
            if (data.final_state) {
                renderAgentResponse(data.final_state);
            }
            fetchPendingTickets();
        } else {
            renderMessage('system', `⚠️ Attestation Error: ${data.detail || 'Permission denied.'}`);
        }
    } catch (err) {
        renderMessage('system', `⚠️ Network Error during attestation: ${err.message}`);
    }
}

function formatMarkdownText(str) {
    if (!str) return '';
    let html = escapeHtml(str);
    html = html.replace(/^### (.*$)/gim, '<h4 style="margin-top: 10px; color: var(--accent-cyan);">$1</h4>');
    html = html.replace(/^## (.*$)/gim, '<h3 style="margin-top: 12px; color: var(--accent-cyan);">$1</h3>');
    html = html.replace(/^# (.*$)/gim, '<h2 style="margin-top: 14px; font-family: var(--font-heading);">$1</h2>');
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/`(.*?)`/g, '<code style="background: rgba(255,255,255,0.1); padding: 2px 6px; border-radius: 4px;">$1</code>');
    html = html.replace(/\n/g, '<br>');
    return html;
}

async function fetchPendingTickets() {
    try {
        const res = await fetch('/api/tickets/pending');
        const tickets = await res.json();
        const listDiv = document.getElementById('pending-tickets-list');
        const badge = document.getElementById('ticket-count-badge');

        badge.innerText = `${tickets.length} Pending`;

        if (tickets.length === 0) {
            listDiv.innerHTML = `<p class="empty-text">No pending tickets awaiting attestation.</p>`;
            return;
        }

        listDiv.innerHTML = tickets.map(t => `
            <div style="background: rgba(0,0,0,0.3); border: 1px solid var(--border-color); border-radius: 8px; padding: 10px; font-size: 12px;">
                <div style="display: flex; justify-content: space-between;">
                    <strong>${t.ticket_id}</strong>
                    <span class="badge warning">Pending</span>
                </div>
                <div style="margin-top: 4px; color: var(--text-secondary);">
                    Action: ${t.action_type}<br>
                    ETA: ${t.estimated_eta}
                </div>
                <div style="display: flex; gap: 6px; margin-top: 8px;">
                    <button class="btn-approve" style="padding: 4px 8px; font-size: 10px;" onclick="attestTicket('${t.ticket_id}', true)">Approve</button>
                    <button class="btn-reject" style="padding: 4px 8px; font-size: 10px;" onclick="attestTicket('${t.ticket_id}', false)">Reject</button>
                </div>
            </div>
        `).join('');
    } catch (err) {
        console.error('Failed to fetch pending tickets:', err);
    }
}

function renderLoader() {
    const loaderId = `loader_${Date.now()}`;
    const chatFeed = document.getElementById('chat-messages');
    const msgDiv = document.createElement('div');
    msgDiv.id = loaderId;
    msgDiv.className = 'message system';
    msgDiv.innerHTML = `
        <div class="avatar">❖</div>
        <div class="content"><p>⚡ Orchestrating Multi-Agent Workflow & PHI Privacy Checks...</p></div>
    `;
    chatFeed.appendChild(msgDiv);
    chatFeed.scrollTop = chatFeed.scrollHeight;
    return loaderId;
}

function removeLoader(loaderId) {
    const loader = document.getElementById(loaderId);
    if (loader) loader.remove();
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
