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

/**
 * Extracts plain text / Markdown from any response payload,
 * ensuring raw Python dict lists, JSON blocks, or signature envelopes are cleanly unpacked.
 */
function extractTextFromPayload(input) {
    if (!input) return '';

    // If already an array of parts/blocks
    if (Array.isArray(input)) {
        return input.map(item => {
            if (item && typeof item === 'object') {
                return item.text || item.content || '';
            }
            return String(item || '');
        }).join('');
    }

    if (typeof input !== 'string') {
        return String(input);
    }

    let trimmed = input.trim();

    // Check if string is a serialized Python repr or JSON array like "[{'type': 'text', ...}]"
    if ((trimmed.startsWith("[{'") || trimmed.startsWith('[{"') || trimmed.startsWith("[{ '") || trimmed.startsWith('[{ "')) && trimmed.endsWith("]")) {
        try {
            const parsed = JSON.parse(trimmed);
            if (Array.isArray(parsed)) {
                return extractTextFromPayload(parsed);
            }
        } catch (e) {
            // Python literal representation: extract 'text' properties via regex
            const textParts = [];
            const regex = /['"]text['"]\s*:\s*(?:'((?:\\'|[^'])*)'|"((?:\\"|[^"])*)")/g;
            let match;
            while ((match = regex.exec(trimmed)) !== null) {
                let chunk = match[1] !== undefined ? match[1] : match[2];
                // Unescape common sequences
                chunk = chunk
                    .replace(/\\n/g, '\n')
                    .replace(/\\'/g, "'")
                    .replace(/\\"/g, '"')
                    .replace(/\\\\/g, '\\');
                textParts.push(chunk);
            }
            if (textParts.length > 0) {
                return textParts.join('');
            }
        }
    }

    return input;
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

        if (!response.ok) {
            // Handle HTTP errors gracefully (e.g. 403 Forbidden, 500 Server Error)
            renderGracefulError({
                status: response.status === 403 ? 'permission_denied' : 'system_error',
                error_title: response.status === 403 ? 'Access Authorization Notice (RBAC)' : 'Clinical Platform Notice',
                error_message: data.detail || data.error_message || `HTTP ${response.status} returned by clinical server.`,
                user_message: response.status === 403
                    ? `Role '${role}' is not authorized to perform this operation under active HIPAA/RBAC policy.`
                    : 'A server exception occurred while processing this request. The incident has been recorded in the audit log.',
                draft_prompt: promptText,
                incident_id: data.incident_id || `INC-${Date.now().toString().slice(-6)}`,
                recommendation: response.status === 403
                    ? 'Switch your Active Role in the top header to "Clinician" to proceed with full clinical access.'
                    : 'Your prompt draft has been safely preserved. Click below to restore and retry.'
            });
            return;
        }

        if (data.status === 'AWAITING_CLINICIAN_APPROVAL') {
            renderHITLMessage(data);
            fetchPendingTickets();
        } else if (data.status === 'agent_error' || data.status === 'system_error') {
            renderGracefulError(data);
        } else {
            renderAgentResponse(data);
        }
    } catch (err) {
        removeLoader(loaderId);
        renderGracefulError({
            status: 'network_error',
            error_title: 'Connection & Network Notice',
            error_message: `Unable to reach Healthcare Multi-Agent backend: ${err.message}`,
            user_message: 'The clinical assistant is currently unreachable. Please verify your network connection and ensure the FastAPI backend is running.',
            draft_prompt: promptText,
            recommendation: 'Your draft has been preserved. You can click "Restore Draft" once the service reconnects.'
        });
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

    let detailsStr = params.reason;
    if (!detailsStr) {
        if (params.drug_name) {
            detailsStr = `Order ${params.drug_name} ${params.dosage || ''} ${params.frequency || 'daily'} for patient ${params.patient_id || 'P101'}`;
        } else if (params.note_content) {
            detailsStr = `Update progress note: "${params.note_content}"`;
        } else if (params.recommendation) {
            detailsStr = `Remediate ${params.title || params.gap_id || 'Care Gap'}: ${params.recommendation}`;
        } else {
            detailsStr = `Action ${pendingAction.action_type || 'WRITE_ACTION'} requested for patient ${params.patient_id || 'P101'}`;
        }
    }

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

    let rawSummary = data.final_summary || data.data_ingestion?.patient_summary || 'Task completed successfully.';
    let cleanSummary = extractTextFromPayload(rawSummary);
    let extraHTML = formatMarkdownText(cleanSummary);

    if (data.quality_metrics && data.quality_metrics.length > 0) {
        extraHTML += `<div style="margin-top: 14px; padding-top: 10px; border-top: 1px solid var(--border-color);"><strong>HEDIS Quality Compliance:</strong>`;
        data.quality_metrics.forEach(m => {
            const statusClass = (m.status === 'COMPLIANT' || m.status === 'PASS') ? 'success' : 'warning';
            extraHTML += `<br><span class="badge ${statusClass}" style="display:inline-block; margin-top:4px;">${m.metric || m.metric_id}: ${m.status} (${m.value})</span>`;
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

/**
 * Renders a graceful, professional incident notice to the user and preserves draft prompt.
 */
function renderGracefulError(data) {
    const chatFeed = document.getElementById('chat-messages');
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message system';

    const incidentId = data.incident_id || `INC-${Date.now().toString().slice(-6)}`;
    const title = data.error_title || 'Clinical System Notice';
    const explanation = data.user_message || data.error_message || 'An unexpected condition was encountered during processing.';
    const draftText = data.draft_prompt || '';
    const recommendation = data.recommendation || 'Your request has been safely saved. You may retry or adjust your inquiry.';

    msgDiv.innerHTML = `
        <div class="avatar" style="background: var(--accent-warning); color: #000;">🛡️</div>
        <div class="content graceful-error-content">
            <div class="graceful-error-header">
                <h4 style="color: var(--accent-warning); margin: 0;">${escapeHtml(title)}</h4>
                <span class="incident-badge">Ref: ${escapeHtml(incidentId)}</span>
            </div>
            <p style="margin-top: 8px;">${escapeHtml(explanation)}</p>
            ${recommendation ? `<p class="graceful-recommendation"><strong>Next Steps:</strong> ${escapeHtml(recommendation)}</p>` : ''}
            ${draftText ? `
                <div class="draft-restore-dock">
                    <span class="draft-indicator">📝 Prompt Preserved</span>
                    <button class="btn-restore-draft" onclick="restoreDraftPrompt(${escapeHtml(JSON.stringify(draftText))})">
                        ↩ Restore Prompt Draft
                    </button>
                </div>
            ` : ''}
        </div>
    `;

    chatFeed.appendChild(msgDiv);
    chatFeed.scrollTop = chatFeed.scrollHeight;
}

function restoreDraftPrompt(text) {
    const input = document.getElementById('prompt-input');
    if (input) {
        input.value = text;
        input.focus();
        input.scrollIntoView({ behavior: 'smooth' });
    }
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
        } else {
            renderGracefulError({
                error_title: 'Attestation Authorization Error',
                error_message: data.detail || 'Permission denied during attestation.',
                recommendation: 'Ensure your active role in the header is set to "Clinician" with active prescribing credentials.'
            });
        }
    } catch (err) {
        renderGracefulError({
            error_title: 'Network Communication Error',
            error_message: `Could not submit attestation decision: ${err.message}`,
            recommendation: 'Verify the connection and retry attestation.'
        });
    } finally {
        fetchPendingTickets();
    }
}

/**
 * Transforms Markdown into clean, accessible, publication-grade HTML.
 * Handles headings, bold/italics, tables, unordered/ordered lists, blockquotes, and code blocks.
 */
function formatMarkdownText(raw) {
    if (!raw) return '';

    // Normalize input
    let str = extractTextFromPayload(raw);

    // Strip accidental base64 signatures or metadata envelope remnants if present
    str = str.replace(/['"]extras['"]\s*:\s*\{['"]signature['"]:\s*['"][A-Za-z0-9+/=]+['"]\}/g, '');

    const lines = str.split('\n');
    let output = [];

    let inTable = false;
    let tableRows = [];

    let inUl = false;
    let inOl = false;
    let inCodeBlock = false;
    let codeBlockContent = [];

    function flushTable() {
        if (!inTable || tableRows.length === 0) return;
        let tHtml = '<div class="table-responsive"><table class="clinical-table">';
        tableRows.forEach((row, idx) => {
            if (idx === 0) {
                tHtml += '<thead><tr>';
                row.forEach(c => {
                    tHtml += `<th>${c}</th>`;
                });
                tHtml += '</tr></thead><tbody>';
            } else {
                tHtml += '<tr>';
                row.forEach(c => {
                    tHtml += `<td>${c}</td>`;
                });
                tHtml += '</tr>';
            }
        });
        tHtml += '</tbody></table></div>';
        output.push(tHtml);
        tableRows = [];
        inTable = false;
    }

    function flushList() {
        if (inUl) {
            output.push('</ul>');
            inUl = false;
        }
        if (inOl) {
            output.push('</ol>');
            inOl = false;
        }
    }

    function inlineFormat(text) {
        let t = escapeHtml(text);
        // Bold
        t = t.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        // Italic
        t = t.replace(/\*(.*?)\*/g, '<em>$1</em>');
        // Inline code
        t = t.replace(/`(.*?)`/g, '<code class="inline-code">$1</code>');
        return t;
    }

    for (let i = 0; i < lines.length; i++) {
        let line = lines[i];
        let trimmed = line.trim();

        // Check code blocks ```
        if (trimmed.startsWith('```')) {
            flushTable();
            flushList();
            if (inCodeBlock) {
                // End code block
                output.push(`<pre class="code-block"><code>${escapeHtml(codeBlockContent.join('\n'))}</code></pre>`);
                codeBlockContent = [];
                inCodeBlock = false;
            } else {
                inCodeBlock = true;
            }
            continue;
        }

        if (inCodeBlock) {
            codeBlockContent.push(line);
            continue;
        }

        // Markdown Table
        if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
            flushList();
            if (trimmed.includes('---')) {
                // Separator row
                continue;
            }
            const cells = trimmed.split('|').slice(1, -1).map(c => inlineFormat(c.trim()));
            inTable = true;
            tableRows.push(cells);
            continue;
        } else {
            flushTable();
        }

        // Unordered list items: * or -
        const ulMatch = line.match(/^(\s*)([\*\-])\s+(.*)$/);
        if (ulMatch) {
            if (!inUl) {
                flushList();
                output.push('<ul class="clinical-list">');
                inUl = true;
            }
            output.push(`<li>${inlineFormat(ulMatch[3])}</li>`);
            continue;
        }

        // Ordered list items: 1. 2.
        const olMatch = line.match(/^(\s*)(\d+)\.\s+(.*)$/);
        if (olMatch) {
            if (!inOl) {
                flushList();
                output.push('<ol class="clinical-list ordered">');
                inOl = true;
            }
            output.push(`<li>${inlineFormat(olMatch[3])}</li>`);
            continue;
        }

        // If not in a list, close any open list
        flushList();

        // Empty line
        if (!trimmed) {
            output.push('<div class="spacer"></div>');
            continue;
        }

        // Blockquotes
        if (trimmed.startsWith('>')) {
            const bText = trimmed.replace(/^>\s*/, '');
            output.push(`<blockquote class="clinical-callout">${inlineFormat(bText)}</blockquote>`);
            continue;
        }

        // Headers
        if (trimmed.startsWith('### ')) {
            output.push(`<h4 class="clinical-h4">${inlineFormat(trimmed.substring(4))}</h4>`);
            continue;
        }
        if (trimmed.startsWith('## ')) {
            output.push(`<h3 class="clinical-h3">${inlineFormat(trimmed.substring(3))}</h3>`);
            continue;
        }
        if (trimmed.startsWith('# ')) {
            output.push(`<h2 class="clinical-h2">${inlineFormat(trimmed.substring(2))}</h2>`);
            continue;
        }

        // Horizontal Rules
        if (trimmed === '---' || trimmed === '***') {
            output.push('<hr class="clinical-divider">');
            continue;
        }

        // Regular paragraph line
        output.push(`<p class="clinical-para">${inlineFormat(trimmed)}</p>`);
    }

    flushTable();
    flushList();
    if (inCodeBlock && codeBlockContent.length > 0) {
        output.push(`<pre class="code-block"><code>${escapeHtml(codeBlockContent.join('\n'))}</code></pre>`);
    }

    return output.join('\n');
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
