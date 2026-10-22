/**
 * audit.js - Interactive Transaction Audit & Pipeline Journey Explorer
 * Visualizes step-by-step instruction traversal, Dual-LLM routing, and HITL attestation.
 */

let allTraces = [];
let activeTraceId = null;
let currentStatusFilter = 'ALL';
let autoRefreshTimer = null;
let allExpanded = false;

// Stage Metadata Dictionary for Plain-Language Explanations
const STAGE_METADATA = {
    "INGRESS_CLIENT": {
        title: "Clinical Ingress & Role Authorization",
        icon: "📥",
        desc: "The instruction entered the platform through the secure API endpoint. OAuth 2.1 token verified and RBAC role privileges authenticated."
    },
    "INPUT_GUARDRAILS": {
        title: "Zero-Token Input Guardrails Scan",
        icon: "🛡️",
        desc: "The prompt was scanned by the zero-token perimeter engine for adversarial jailbreaks, prompt injection, and telemetry exfiltration attacks before calling any model."
    },
    "CLINICAL_RULES_ENGINE": {
        title: "Clinical Quality Rules & HEDIS Evaluation",
        icon: "📊",
        desc: "The clinical rule engine evaluated patient FHIR observations against deterministic HEDIS CDC (Diabetes) and CBP (Blood Pressure) quality metrics to detect chronic care gaps."
    },
    "HITL_GATE": {
        title: "Human-in-the-Loop Attestation Gate",
        icon: "🛑",
        desc: "The agent detected clinical write requests (medication, lab observation, or note update). The LangGraph state machine paused execution to require explicit clinician attestation."
    },
    "PHI_SCAN_AND_DEID": {
        title: "Zero-Token PHI Classifier & Privacy Router",
        icon: "🔒",
        desc: "The prompt was evaluated by the zero-token PHI classifier. Direct patient identifiers were redacted and replaced with synthetic surrogates before off-premise routing."
    },
    "LOCAL_LLM_INFERENCE": {
        title: "On-Premise Local LLM Inference",
        icon: "💻",
        desc: "Clinical instruction processed on-premise without external network exposure using local Ollama model to protect patient privacy."
    },
    "CLOUD_LLM_INFERENCE": {
        title: "Google Gemini Cloud Reasoning",
        icon: "☁️",
        desc: "Dispatched de-identified reasoning prompt to Google Gemini under enterprise Zero Data Retention (ZDR) privacy agreements."
    },
    "MCP_TOOL_DISPATCH": {
        title: "Healthcare MCP Tool Invocation",
        icon: "⚙️",
        desc: "Agent executed Model Context Protocol (MCP) tool call to query or update patient electronic health records."
    },
    "LLM_INFERENCE_AND_ROUTING": {
        title: "Dual-LLM Routing & Token Telemetry",
        icon: "⚡",
        desc: "The prompt was evaluated by the active LLM provider. Tracks exact prompt tokens, completion tokens, connection endpoint, and session quota."
    },
    "CLINICIAN_ATTESTATION": {
        title: "Attending Clinician Review & Decision",
        icon: "🩺",
        desc: "An authorized attending clinician reviewed the staged clinical actions, assessed confidence scores, and submitted an authenticated attestation decision."
    },
    "EXECUTE_CRUD_ACTIONS": {
        title: "EHR Database Committal",
        icon: "💾",
        desc: "The approved clinical orders were executed against the electronic health record system, generating unique audit-tracked clinical entity IDs."
    },
    "EHR_DB_COMMITTAL": {
        title: "EHR Database Committal",
        icon: "💾",
        desc: "The approved clinical orders were executed against the electronic health record system, generating unique audit-tracked clinical entity IDs."
    },
    "EGRESS_CLIENT": {
        title: "Clinical Response Delivery",
        icon: "📤",
        desc: "The sanitized clinical summary and attestation banner were packaged with field-level RBAC filtering and returned to the client interface."
    }
};

document.addEventListener('DOMContentLoaded', () => {
    // Check URL parameters for direct trace linking
    const urlParams = new URLSearchParams(window.location.search);
    const linkedTraceId = urlParams.get('trace_id');

    loadTraces(linkedTraceId);
    toggleAutoRefresh(true);
});

// Auto-Refresh Manager
function toggleAutoRefresh(enabled) {
    if (autoRefreshTimer) {
        clearInterval(autoRefreshTimer);
        autoRefreshTimer = null;
    }
    if (enabled) {
        autoRefreshTimer = setInterval(() => {
            loadTracesSilently();
        }, 4000);
    }
}

// Fetch all traces from server
async function loadTraces(preferredTraceId = null) {
    try {
        const response = await fetch('/api/audit/traces');
        if (!response.ok) throw new Error('Failed to fetch transaction traces');
        const data = await response.json();
        allTraces = data.traces || [];
        // Ensure strictly sorted newest-first
        allTraces.sort((a, b) => new Date(b.start_timestamp) - new Date(a.start_timestamp));

        updateKpiMetrics();
        renderTracesList();

        // Select initial trace
        if (preferredTraceId && allTraces.some(t => t.trace_id === preferredTraceId)) {
            selectTrace(preferredTraceId);
        } else if (activeTraceId && allTraces.some(t => t.trace_id === activeTraceId)) {
            selectTrace(activeTraceId);
        } else if (allTraces.length > 0) {
            selectTrace(allTraces[0].trace_id);
        } else {
            renderEmptyDetailState();
        }
    } catch (err) {
        console.error('Error loading traces:', err);
    }
}

// Background silent refresh that preserves active selection
async function loadTracesSilently() {
    try {
        const response = await fetch('/api/audit/traces');
        if (!response.ok) return;
        const data = await response.json();
        allTraces = data.traces || [];
        allTraces.sort((a, b) => new Date(b.start_timestamp) - new Date(a.start_timestamp));
        updateKpiMetrics();
        renderTracesList(true); // Preserve scroll & selection
    } catch (err) {
        // Silent fail on background poll
    }
}

// Determine if a trace executed via Cloud Gemini or Local LLM
function getTraceRoute(trace) {
    if (trace.route_type) {
        return trace.route_type.toUpperCase();
    }
    const llm = trace.llm_telemetry;
    if (llm) {
        if (llm.route_type) return llm.route_type.toUpperCase();
        const prov = (llm.provider || '').toLowerCase();
        const mod = (llm.model || '').toLowerCase();
        if (prov.includes('google') || prov.includes('gemini') || prov.includes('cloud') || mod.includes('gemini')) {
            return 'CLOUD';
        }
        if (prov.includes('local') || prov.includes('ollama') || prov.includes('llama') || prov.includes('privacy') || prov.includes('on-premise')) {
            return 'LOCAL';
        }
    }
    const steps = trace.journey_steps || [];
    if (steps.some(s => s.stage === 'CLOUD_LLM_INFERENCE')) return 'CLOUD';
    if (steps.some(s => s.stage === 'LOCAL_LLM_INFERENCE')) return 'LOCAL';
    for (const s of steps) {
        const prov = (s.details?.provider || '').toLowerCase();
        if (prov.includes('google') || prov.includes('gemini') || prov.includes('cloud')) return 'CLOUD';
        if (prov.includes('local') || prov.includes('ollama') || prov.includes('llama')) return 'LOCAL';
    }
    return 'CLOUD';
}

// Update top KPI cards
function updateKpiMetrics() {
    const total = allTraces.length;
    let awaiting = 0;
    let committed = 0;
    let cloudCount = 0;
    let localCount = 0;

    allTraces.forEach(t => {
        const route = getTraceRoute(t);
        if (route === 'CLOUD') {
            cloudCount++;
        } else {
            localCount++;
        }

        const st = (t.final_status || '').toUpperCase();
        if (st.includes('AWAITING') || st.includes('PAUSED') || st.includes('PENDING')) {
            awaiting++;
        }
        if (st.includes('COMMITTED') || st.includes('COMPLETED') || st.includes('APPROVED')) {
            committed++;
        }
    });

    document.getElementById('kpi-total-traces').textContent = total;
    const cloudEl = document.getElementById('kpi-cloud-requests');
    if (cloudEl) cloudEl.textContent = cloudCount;
    const localEl = document.getElementById('kpi-local-requests');
    if (localEl) localEl.textContent = localCount;
    document.getElementById('kpi-awaiting-approval').textContent = awaiting;
    document.getElementById('kpi-committed').textContent = committed;
}

// Filter traces based on search query and status pill
function getFilteredTraces() {
    const query = (document.getElementById('trace-search').value || '').toLowerCase().trim();

    return allTraces.filter(t => {
        // Status & Route filter
        if (currentStatusFilter !== 'ALL') {
            if (currentStatusFilter === 'CLOUD_LLM') {
                if (getTraceRoute(t) !== 'CLOUD') return false;
            } else if (currentStatusFilter === 'LOCAL_LLM') {
                if (getTraceRoute(t) !== 'LOCAL') return false;
            } else {
                const st = (t.final_status || '').toUpperCase();
                if (currentStatusFilter === 'AWAITING_APPROVAL' && !st.includes('AWAITING') && !st.includes('PAUSED') && !st.includes('PENDING')) {
                    return false;
                }
                if (currentStatusFilter === 'COMPLETED' && !st.includes('COMPLETED')) {
                    return false;
                }
                if (currentStatusFilter === 'COMMITTED' && !st.includes('COMMITTED') && !st.includes('APPROVED')) {
                    return false;
                }
                if (currentStatusFilter === 'BLOCKED' && !st.includes('BLOCKED')) {
                    return false;
                }
            }
        }

        // Search query
        if (query) {
            const matchesId = (t.trace_id || '').toLowerCase().includes(query);
            const matchesPrompt = (t.prompt || '').toLowerCase().includes(query);
            const matchesPatient = (t.patient_id || '').toLowerCase().includes(query);
            const matchesRole = (t.user_role || '').toLowerCase().includes(query);
            const route = getTraceRoute(t).toLowerCase();
            const matchesRoute = route.includes(query) || (route === 'cloud' && 'gemini'.includes(query)) || (route === 'local' && 'ollama'.includes(query));
            return matchesId || matchesPrompt || matchesPatient || matchesRole || matchesRoute;
        }

        return true;
    });
}

function setStatusFilter(status) {
    currentStatusFilter = status;
    document.querySelectorAll('#status-filter-group .filter-pill').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.status === status);
    });
    renderTracesList();
}

function applyFilters() {
    renderTracesList();
}

// Render Left Sidebar Transaction Cards
function renderTracesList(preserveScroll = false) {
    const container = document.getElementById('traces-list');
    const filtered = getFilteredTraces();
    document.getElementById('filtered-count').textContent = `${filtered.length} items`;

    if (filtered.length === 0) {
        container.innerHTML = `
            <div class="empty-list-state">
                <p>No transaction traces match your criteria.</p>
            </div>
        `;
        return;
    }

    const scrollPos = preserveScroll ? container.scrollTop : 0;

    let html = '';
    filtered.forEach(trace => {
        const isActive = trace.trace_id === activeTraceId;
        const statusClass = getStatusBadgeClass(trace.final_status);
        const dateStr = formatTimestamp(trace.start_timestamp);
        const stepsCount = (trace.journey_steps || []).length || trace.total_steps || 1;
        const route = getTraceRoute(trace);
        const routeBadgeClass = route === 'CLOUD' ? 'cloud' : 'local';
        const routeLabel = route === 'CLOUD' ? '☁️ Cloud Gemini' : '🏠 Local On-Prem';

        html += `
            <div class="trace-card ${isActive ? 'active' : ''}" onclick="selectTrace('${trace.trace_id}')">
                <div class="card-top">
                    <span class="trace-id-label">${escapeHtml(trace.trace_id)}</span>
                    <span class="route-badge ${routeBadgeClass}">${routeLabel}</span>
                    <span class="status-pill ${statusClass}">${escapeHtml(trace.final_status || 'UNKNOWN')}</span>
                </div>
                <p class="card-prompt-preview">${escapeHtml(trace.prompt || 'No prompt content')}</p>
                <div class="card-bottom">
                    <span class="card-meta"><strong class="highlight-cyan">${escapeHtml(trace.patient_id || 'P101')}</strong> • ${escapeHtml(trace.user_role || 'Clinician')}</span>
                    <span class="card-steps-count">${stepsCount} Stages</span>
                </div>
                <div class="card-time">${dateStr}</div>
            </div>
        `;
    });

    container.innerHTML = html;
    if (preserveScroll) container.scrollTop = scrollPos;
}

// Select and Display a Specific Transaction Trace
function selectTrace(traceId) {
    activeTraceId = traceId;

    // Highlight card in sidebar
    document.querySelectorAll('.trace-card').forEach(card => {
        card.classList.toggle('active', card.querySelector('.trace-id-label')?.textContent === traceId);
    });

    const trace = allTraces.find(t => t.trace_id === traceId);
    if (!trace) {
        renderEmptyDetailState();
        return;
    }

    renderTraceDetail(trace);
}

function renderEmptyDetailState() {
    document.getElementById('empty-detail-placeholder').style.display = 'flex';
    document.getElementById('active-journey-content').style.display = 'none';
}

// Render the complete visual journey in the right pane
function renderTraceDetail(trace) {
    document.getElementById('empty-detail-placeholder').style.display = 'none';
    document.getElementById('active-journey-content').style.display = 'block';

    // Populate Overview
    document.getElementById('active-trace-id').textContent = trace.trace_id;
    document.getElementById('active-prompt-text').textContent = `"${trace.prompt || ''}"`;
    document.getElementById('active-patient-id').textContent = trace.patient_id || 'P101';
    document.getElementById('active-user-role').textContent = trace.user_role || 'Clinician';
    document.getElementById('active-session-id').textContent = trace.session_id || 'default';
    document.getElementById('active-start-time').textContent = formatTimestamp(trace.start_timestamp);
    
    const steps = trace.journey_steps || [];
    document.getElementById('active-total-steps').textContent = `${steps.length} Stages`;

    // Status Badge
    const statusClass = getStatusBadgeClass(trace.final_status);
    const statusContainer = document.getElementById('active-status-badge');
    statusContainer.innerHTML = `<span class="badge ${statusClass}">${escapeHtml(trace.final_status || 'UNKNOWN')}</span>`;

    // Populate Execution Route & Governance Banner
    const route = getTraceRoute(trace);
    const isCloud = route === 'CLOUD';
    const bannerEl = document.getElementById('active-execution-route-banner');
    if (bannerEl) {
        bannerEl.className = `execution-route-banner ${isCloud ? 'cloud-route' : 'local-route'}`;
        const bannerBadge = isCloud ?
            '<span class="route-banner-badge cloud">☁️ CLOUD ROUTE (GOOGLE GEMINI)</span>' :
            '<span class="route-banner-badge local">🏠 LOCAL ROUTE (ON-PREMISE)</span>';
        const privacyBadge = isCloud ?
            '<span class="route-banner-privacy">🛡️ Zero Data Retention (ZDR) Privacy Proxy</span>' :
            '<span class="route-banner-privacy">🔒 Zero External Network Exfiltration</span>';
        const narrativeText = isCloud ?
            '<strong>Exact Data Traversal Flow:</strong> Client prompt evaluated by zero-token guardrails ➔ Direct identifiers redacted into cryptographic tokens by PHI Classifier (Safe Harbor) ➔ Dispatched to <code>Google Cloud Gemini (gemini-3.8-flash)</code> via HTTPS REST API ➔ De-identified model inference returned and re-identified into clinical EHR record.' :
            '<strong>Exact Data Traversal Flow:</strong> Client prompt evaluated by zero-token guardrails ➔ Sensitive clinical record retained strictly within on-premise host memory ➔ Reasoned on <code>Local LLM (llama3:8b on Ollama / Local Host Sandbox)</code> ➔ Zero bytes exfiltrated over external network ➔ Clinical summary delivered locally.';

        bannerEl.innerHTML = `
            <div class="route-banner-header">
                ${bannerBadge}
                ${privacyBadge}
            </div>
            <div class="route-banner-narrative">
                ${narrativeText}
            </div>
            <div class="route-flow-strip">
                <span class="route-hop-pill">📥 Client Ingress</span>
                <span class="route-hop-arrow">➔</span>
                <span class="route-hop-pill">🛡️ Guardrails</span>
                <span class="route-hop-arrow">➔</span>
                <span class="route-hop-pill">🔒 PHI Classifier</span>
                <span class="route-hop-arrow">➔</span>
                <span class="route-hop-pill active-hop ${isCloud ? 'cloud' : 'local'}">${isCloud ? '☁️ Cloud Gemini 3.8' : '🏠 Local LLM Llama-3'}</span>
                <span class="route-hop-arrow">➔</span>
                <span class="route-hop-pill">🩺 HITL Gate</span>
                <span class="route-hop-arrow">➔</span>
                <span class="route-hop-pill">💾 EHR Database</span>
                <span class="route-hop-arrow">➔</span>
                <span class="route-hop-pill">📤 Client Egress</span>
            </div>
        `;
    }

    // Populate LLM Routing & Token Telemetry Strip
    let llmTel = trace.llm_telemetry;
    if (!llmTel) {
        const llmStep = steps.find(s => s.stage === 'LLM_INFERENCE_AND_ROUTING' || s.stage === 'CLOUD_LLM_INFERENCE' || s.stage === 'LOCAL_LLM_INFERENCE');
        if (llmStep && llmStep.details) {
            llmTel = {
                provider: llmStep.details.provider,
                model: llmStep.details.model,
                endpoint: llmStep.details.endpoint,
                connection_type: llmStep.details.connection_type,
                call_tokens: {
                    prompt_tokens: llmStep.details.prompt_tokens,
                    completion_tokens: llmStep.details.completion_tokens,
                    total_tokens: llmStep.details.total_call_tokens
                },
                session_quota: {
                    tokens_used_so_far: llmStep.details.session_tokens_used_so_far,
                    remaining_tokens: llmStep.details.session_remaining_quota,
                    base_quota_limit: llmStep.details.session_quota_limit
                }
            };
        }
    }

    const modelEl = document.getElementById('active-telemetry-model');
    const tokensEl = document.getElementById('active-telemetry-tokens');
    const quotaEl = document.getElementById('active-telemetry-quota');

    if (llmTel) {
        const prov = llmTel.provider || 'Active Model';
        const mod = llmTel.model || '';
        const callTot = llmTel.call_tokens?.total_tokens || ((llmTel.call_tokens?.prompt_tokens || 0) + (llmTel.call_tokens?.completion_tokens || 0));
        const pTok = llmTel.call_tokens?.prompt_tokens || 0;
        const cTok = llmTel.call_tokens?.completion_tokens || 0;
        const used = llmTel.session_quota?.tokens_used_so_far ?? '--';
        const limit = llmTel.session_quota?.base_quota_limit ?? 8000;
        const rem = llmTel.session_quota?.remaining_tokens ?? '--';

        if (modelEl) modelEl.textContent = `${isCloud ? '☁️ ' : '🏠 '}${prov} (${mod})`;
        if (tokensEl) tokensEl.textContent = `${callTot} tokens (${pTok} in / ${cTok} out)`;
        if (quotaEl) quotaEl.textContent = `${used} used / ${limit} limit (${rem} remaining)`;
    } else {
        if (modelEl) modelEl.textContent = isCloud ? 'Google Gemini API (ZDR)' : 'Local Host Sandbox (ZDR)';
        if (tokensEl) tokensEl.textContent = 'Standard Token Usage';
        if (quotaEl) quotaEl.textContent = 'Within Quota Limits';
    }

    // Render Visual Stepper (The Pipeline Map)
    renderPipelineStepper(steps);

    // Render Detailed Stage Cards
    renderStageCards(steps);
}

// Render Visual Stepper (Horizontal Pipeline Graph)
function renderPipelineStepper(steps) {
    const track = document.getElementById('stepper-track');
    if (!steps || steps.length === 0) {
        track.innerHTML = '<p class="empty-text">No stage milestones recorded for this trace.</p>';
        return;
    }

    let html = '<div class="pipeline-track-line"></div>';

    steps.forEach((step, idx) => {
        let meta = STAGE_METADATA[step.stage] || { title: step.stage, icon: '❖' };
        if (step.stage === 'LLM_INFERENCE_AND_ROUTING') {
            const isCloud = (step.details?.provider || '').toLowerCase().includes('google') || (step.details?.provider || '').toLowerCase().includes('cloud');
            meta = isCloud ? { title: 'Cloud Gemini', icon: '☁️' } : { title: 'Local LLM', icon: '🏠' };
        } else if (step.stage === 'CLOUD_LLM_INFERENCE') {
            meta = { title: 'Cloud Gemini', icon: '☁️' };
        } else if (step.stage === 'LOCAL_LLM_INFERENCE') {
            meta = { title: 'Local LLM', icon: '🏠' };
        }

        const isPaused = (step.status || '').includes('PAUSED') || (step.status || '').includes('AWAITING');
        const isBlocked = (step.status || '').includes('BLOCKED') || (step.status || '').includes('REJECTED');
        let stepStateClass = 'completed';
        if (isPaused) stepStateClass = 'paused';
        if (isBlocked) stepStateClass = 'blocked';

        html += `
            <div class="stepper-node ${stepStateClass}" onclick="scrollToStageCard(${step.step_index})">
                <div class="node-circle" title="${escapeHtml(meta.title)}">
                    <span class="node-icon">${meta.icon}</span>
                    <span class="node-number">${step.step_index}</span>
                </div>
                <div class="node-label">
                    <span class="node-title">${escapeHtml(meta.title.split(' ')[0])}</span>
                    <span class="node-status ${stepStateClass}">${escapeHtml(step.status || 'OK')}</span>
                </div>
            </div>
        `;
    });

    track.innerHTML = html;
}

// Render Stage-by-Stage Detailed Breakdown Cards
function renderStageCards(steps) {
    const container = document.getElementById('stage-cards-list');
    if (!steps || steps.length === 0) {
        container.innerHTML = '<p class="empty-text">No stage details available.</p>';
        return;
    }

    let html = '';
    steps.forEach(step => {
        let meta = STAGE_METADATA[step.stage] || {
            title: step.stage.replace(/_/g, ' '),
            icon: '❖',
            desc: 'System executed workflow milestone.'
        };
        if (step.stage === 'LLM_INFERENCE_AND_ROUTING') {
            const isCloud = (step.details?.provider || '').toLowerCase().includes('google') || (step.details?.provider || '').toLowerCase().includes('cloud');
            meta = isCloud ? { title: 'Cloud Gemini Reasoning (Zero Data Retention)', icon: '☁️', desc: meta.desc } : { title: 'On-Premise Local LLM Inference', icon: '🏠', desc: meta.desc };
        } else if (step.stage === 'CLOUD_LLM_INFERENCE') {
            meta = { title: 'Cloud Gemini Reasoning (Zero Data Retention)', icon: '☁️', desc: meta.desc };
        } else if (step.stage === 'LOCAL_LLM_INFERENCE') {
            meta = { title: 'On-Premise Local LLM Inference', icon: '🏠', desc: meta.desc };
        }

        const isPaused = (step.status || '').includes('PAUSED') || (step.status || '').includes('AWAITING');
        const isBlocked = (step.status || '').includes('BLOCKED') || (step.status || '').includes('REJECTED');
        const statusClass = isPaused ? 'warning' : (isBlocked ? 'danger' : 'success');

        // Formatted human explanation with dynamic context
        const dynamicExplanation = generateHumanExplanation(step);

        html += `
            <div class="card stage-detail-card ${statusClass}" id="stage-card-${step.step_index}">
                <div class="stage-card-header" onclick="toggleStageCardDetails(${step.step_index})">
                    <div class="stage-header-left">
                        <div class="stage-badge-icon ${statusClass}">${meta.icon}</div>
                        <div>
                            <div class="stage-number-tag">STAGE ${step.step_index} OF ${steps.length}</div>
                            <h4 class="stage-title">${escapeHtml(meta.title)}</h4>
                        </div>
                    </div>
                    <div class="stage-header-right">
                        <span class="badge ${statusClass}">${escapeHtml(step.status || 'SUCCESS')}</span>
                        <span class="stage-timestamp">${formatTimeOnly(step.timestamp)}</span>
                        <span class="accordion-arrow">▼</span>
                    </div>
                </div>

                <div class="stage-card-body" id="stage-body-${step.step_index}">
                    <!-- Human Understandable Story Block -->
                    <div class="stage-story-box">
                        <div class="story-icon">💡</div>
                        <div class="story-content">
                            <strong>What happened at this stage:</strong>
                            <p>${dynamicExplanation || meta.desc}</p>
                        </div>
                    </div>

                    <!-- Structured Parameters Grid -->
                    ${renderStepDetailsGrid(step)}

                    <!-- Raw JSON Telemetry Collapsible -->
                    <div class="raw-telemetry-section">
                        <button class="json-toggle-btn" onclick="toggleRawJson(${step.step_index})">
                            <span>{ }</span> Raw Step Telemetry
                        </button>
                        <pre class="raw-json-block" id="raw-json-${step.step_index}" style="display: none;"><code>${escapeHtml(JSON.stringify(step.details || {}, null, 2))}</code></pre>
                    </div>
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

// Generate Contextual Plain-Language Explanation
function generateHumanExplanation(step) {
    const stage = step.stage;
    const details = step.details || {};

    if (stage === 'INGRESS_CLIENT') {
        return `Instruction <em>"${escapeHtml(details.prompt || '')}"</em> was received at <code>${details.endpoint || '/api/chat'}</code> for patient <strong>${details.patient_id || 'P101'}</strong> under user role <strong>${details.role || 'Clinician'}</strong>.`;
    }

    if (stage === 'INPUT_GUARDRAILS') {
        if (step.status === 'BLOCKED') {
            return `<strong class="text-danger">Threat Blocked:</strong> Input guardrails identified an adversarial jailbreak or SQL injection attack and safely halted execution before model invocation.`;
        }
        return `The zero-token security perimeter scanned the prompt against adversarial injection dictionaries, sensitive leak vectors, and malicious tokens. <strong>Verification passed with 0 threats detected.</strong>`;
    }

    if (stage === 'CLINICAL_RULES_ENGINE') {
        const gapCount = details.care_gaps !== undefined ? details.care_gaps : 'Multiple';
        return `EHR laboratory records and prescription profiles were matched against HEDIS CDC and CBP guidelines. The rules engine identified <strong>${gapCount} chronic care compliance gap(s)</strong> and staged actionable remediation recommendations.`;
    }

    if (stage === 'HITL_GATE') {
        const pending = details.pending_actions || [];
        if (pending.length > 0) {
            const act = pending[0];
            const actName = act.action_type === 'CREATE_MEDICATION_ORDER' ? `Order medication (${act.drug_name} ${act.dosage})` :
                           act.action_type === 'ADD_LAB_RESULT' ? `Record lab observation (${act.test_name} = ${act.value}${act.unit || ''})` :
                           act.action_type === 'UPDATE_PATIENT_NOTE' ? `Update clinical progress note` : act.action_type;
            return `<strong class="text-warning">Attestation Gate Paused:</strong> System detected a sensitive clinical write action: <em>${escapeHtml(actName)}</em>. Graph execution paused to prevent automated EHR write and staged ticket for human physician approval.`;
        }
        return `Platform evaluated action permissions and paused execution pending clinician attestation.`;
    }

    if (stage === 'CLINICIAN_ATTESTATION') {
        const approved = details.approved;
        const clinician = details.clinician_id || 'Attending Physician';
        const comments = details.comments || 'No comments';
        if (approved) {
            return `Attending clinician <strong>${escapeHtml(clinician)}</strong> reviewed the clinical recommendation and submitted an <strong>APPROVED</strong> attestation: <em>"${escapeHtml(comments)}"</em>.`;
        }
        return `Attending clinician <strong>${escapeHtml(clinician)}</strong> submitted a <strong>REJECTION</strong>: <em>"${escapeHtml(comments)}"</em>. Database writes were safely cancelled.`;
    }

    if (stage === 'EXECUTE_CRUD_ACTIONS' || stage === 'EHR_DB_COMMITTAL') {
        const count = (details.execution_results || details.results || []).length;
        return `The approved action was executed in the mock EHR database. <strong>${count} transaction record(s)</strong> were permanently committed with audit timestamps.`;
    }

    if (stage === 'PHI_SCAN_AND_DEID') {
        const hasPhi = details.contains_phi;
        const score = details.sensitivity_score || 0;
        return `Perimeter PHI scan completed. <strong>PHI Detected: ${hasPhi ? 'YES' : 'NO'}</strong> (Sensitivity Score: ${score}). Direct identifiers were redacted to protect HIPAA Safe Harbor standards.`;
    }

    if (stage === 'LOCAL_LLM_INFERENCE') {
        const mod = details.model || 'llama3:8b';
        const callTot = details.total_call_tokens || ((details.prompt_tokens || 0) + (details.completion_tokens || 0));
        return `Instruction resolved entirely on <strong>Local On-Premise LLM</strong> (<code>${escapeHtml(mod)}</code>) within the hospital host boundary. <strong>Zero patient data bytes left local hospital perimeter.</strong> Single call tokens: <strong>${callTot} tokens</strong> (${details.prompt_tokens || 0} prompt / ${details.completion_tokens || 0} completion).`;
    }

    if (stage === 'CLOUD_LLM_INFERENCE') {
        const mod = details.model || 'gemini-3.8-flash';
        const callTot = details.total_call_tokens || ((details.prompt_tokens || 0) + (details.completion_tokens || 0));
        return `Instruction dispatched to <strong>Google Cloud Gemini API</strong> (<code>${escapeHtml(mod)}</code>) via HTTPS REST API under enterprise Zero Data Retention (ZDR) privacy agreements. Single call tokens: <strong>${callTot} tokens</strong> (${details.prompt_tokens || 0} prompt / ${details.completion_tokens || 0} completion). Direct PHI was protected via safe-harbor surrogate tokens.`;
    }

    if (stage === 'MCP_TOOL_DISPATCH') {
        return `Executed MCP Tool <code>${details.tool_name || 'read_patient_record'}</code> with parameters <code>${JSON.stringify(details.parameters || {})}</code>.`;
    }

    if (stage === 'LLM_INFERENCE_AND_ROUTING') {
        const prov = details.provider || 'Active LLM Provider';
        const model = details.model || '';
        const isCloud = prov.toLowerCase().includes('google') || prov.toLowerCase().includes('gemini') || prov.toLowerCase().includes('cloud');
        const routeLabel = isCloud ? '☁️ Cloud Gemini API' : '🏠 Local On-Premise LLM';
        const endp = details.endpoint || '';
        const callTot = details.total_call_tokens || ((details.prompt_tokens || 0) + (details.completion_tokens || 0));
        const used = details.session_tokens_used_so_far !== undefined ? details.session_tokens_used_so_far : '--';
        const limit = details.session_quota_limit || 8000;
        const rem = details.session_remaining_quota !== undefined ? details.session_remaining_quota : '--';
        return `Instruction processed via <strong>${routeLabel}</strong> (<code>${escapeHtml(model)}</code>) through endpoint <code>${escapeHtml(endp)}</code>. This single inference call consumed <strong>${callTot} tokens</strong> (${details.prompt_tokens || 0} prompt / ${details.completion_tokens || 0} completion). Across this session, <strong>${used} tokens</strong> have been used so far out of an <strong>${limit} token quota</strong> (<strong>${rem} tokens</strong> remaining).`;
    }

    if (stage === 'EGRESS_CLIENT') {
        return `The finalized clinical response was rendered with publication-grade Markdown and field-level RBAC sanitation. Transmitted to client interface.`;
    }

    return null;
}

// Render Structured Parameter Grid for a Step
function renderStepDetailsGrid(step) {
    const details = step.details || {};
    const keys = Object.keys(details);
    if (keys.length === 0) return '';

    // Check for pending actions array
    if (details.pending_actions && Array.isArray(details.pending_actions)) {
        let actionsHtml = '<div class="staged-actions-deck">';
        details.pending_actions.forEach((act, idx) => {
            const conf = Math.round((act.confidence_score || 0.95) * 100);
            actionsHtml += `
                <div class="staged-action-item">
                    <div class="action-item-header">
                        <span class="action-badge">${escapeHtml(act.action_type)}</span>
                        <span class="confidence-badge">Confidence: ${conf}%</span>
                    </div>
                    <div class="action-item-reason">${escapeHtml(act.reason || 'Clinical recommendation')}</div>
                    ${act.dosage ? `<div class="action-pill-row"><span class="pill-tag">Dosage: ${escapeHtml(act.dosage)}</span><span class="pill-tag">Frequency: ${escapeHtml(act.frequency || 'daily')}</span></div>` : ''}
                    ${act.test_name ? `<div class="action-pill-row"><span class="pill-tag">Test: ${escapeHtml(act.test_name)}</span><span class="pill-tag">Value: ${escapeHtml(act.value)}${escapeHtml(act.unit || '')}</span></div>` : ''}
                    ${act.note_content ? `<div class="note-quote-box">"${escapeHtml(act.note_content)}"</div>` : ''}
                </div>
            `;
        });
        actionsHtml += '</div>';
        return actionsHtml;
    }

    // Check for execution results array
    if (details.execution_results && Array.isArray(details.execution_results)) {
        let execHtml = '<div class="staged-actions-deck">';
        details.execution_results.forEach(res => {
            const orderId = res.order_id || res.lab_id || res.note_id || res.remediation_id || 'ID-N/A';
            execHtml += `
                <div class="staged-action-item committed">
                    <div class="action-item-header">
                        <span class="action-badge success">✅ ${escapeHtml(res.status || 'COMMITTED').toUpperCase()}</span>
                        <strong class="highlight-cyan">${escapeHtml(orderId)}</strong>
                    </div>
                    ${res.medication ? `<div class="action-item-reason">Prescription Committed: ${escapeHtml(res.medication.drug_name || '')}</div>` : ''}
                    ${res.lab_result ? `<div class="action-item-reason">Lab Record: ${escapeHtml(res.lab_result.name || '')} (${escapeHtml(res.lab_result.result_val || '')} ${escapeHtml(res.lab_result.unit_meas || '')})</div>` : ''}
                    ${res.note ? `<div class="action-item-reason">Progress Note Added: "${escapeHtml(res.note.content || '')}"</div>` : ''}
                </div>
            `;
        });
        execHtml += '</div>';
        return execHtml;
    }

    // Default key-value parameter pills
    let gridHtml = '<div class="step-meta-grid">';
    keys.forEach(k => {
        if (typeof details[k] === 'object') return; // Skip complex objects in quick grid
        gridHtml += `
            <div class="grid-param-item">
                <span class="param-key">${escapeHtml(k.replace(/_/g, ' '))}:</span>
                <strong class="param-val">${escapeHtml(String(details[k]))}</strong>
            </div>
        `;
    });
    gridHtml += '</div>';
    return gridHtml;
}

// Collapsible Stage Card Toggles
function toggleStageCardDetails(stepIndex) {
    const body = document.getElementById(`stage-body-${stepIndex}`);
    if (body) {
        const isHidden = body.style.display === 'none';
        body.style.display = isHidden ? 'block' : 'none';
    }
}

function toggleExpandAllStages() {
    allExpanded = !allExpanded;
    document.querySelectorAll('.stage-card-body').forEach(body => {
        body.style.display = allExpanded ? 'block' : 'none';
    });
    const btn = document.querySelector('.expand-all-btn');
    if (btn) btn.textContent = allExpanded ? 'Collapse All Details' : 'Expand All Details';
}

function toggleRawJson(stepIndex) {
    const pre = document.getElementById(`raw-json-${stepIndex}`);
    if (pre) {
        pre.style.display = pre.style.display === 'none' ? 'block' : 'none';
    }
}

function scrollToStageCard(stepIndex) {
    const card = document.getElementById(`stage-card-${stepIndex}`);
    if (card) {
        card.scrollIntoView({ behavior: 'smooth', block: 'center' });
        const body = document.getElementById(`stage-body-${stepIndex}`);
        if (body) body.style.display = 'block';
        card.classList.add('flash-highlight');
        setTimeout(() => card.classList.remove('flash-highlight'), 1200);
    }
}

// Copy Trace ID
function copyActiveTraceId() {
    if (!activeTraceId) return;
    navigator.clipboard.writeText(activeTraceId).then(() => {
        const btn = document.querySelector('.copy-btn');
        if (btn) {
            btn.textContent = '✅ Copied!';
            setTimeout(() => btn.textContent = '📋 Copy', 1500);
        }
    });
}

// View Mode Switching (Visual Stages vs Append-Only Journal Log)
function switchViewMode(mode) {
    const stagesWs = document.getElementById('stages-workspace');
    const journalWs = document.getElementById('journal-workspace');
    const btnStages = document.getElementById('view-mode-stages');
    const btnJournal = document.getElementById('view-mode-journal');

    if (mode === 'journal') {
        stagesWs.style.display = 'none';
        journalWs.style.display = 'block';
        btnStages.classList.remove('active');
        btnJournal.classList.add('active');
        loadJournalLog();
    } else {
        stagesWs.style.display = 'grid';
        journalWs.style.display = 'none';
        btnStages.classList.add('active');
        btnJournal.classList.remove('active');
    }
}

async function loadJournalLog() {
    const viewer = document.getElementById('journal-log-content');
    viewer.textContent = 'Loading audit journal from server...';
    try {
        const resp = await fetch('/api/audit/journey-log');
        if (!resp.ok) throw new Error('Failed to load log');
        const data = await resp.json();
        viewer.textContent = data.log || 'Log is empty.';
        viewer.scrollTop = viewer.scrollHeight; // Scroll to bottom
    } catch (err) {
        viewer.textContent = `Error loading journal log: ${err.message}`;
    }
}

function downloadJournalLog() {
    window.open('/api/audit/journey-log', '_blank');
}

// Helpers
function getStatusBadgeClass(status) {
    const st = (status || '').toUpperCase();
    if (st.includes('AWAITING') || st.includes('PAUSED') || st.includes('PENDING')) return 'warning';
    if (st.includes('BLOCKED') || st.includes('REJECTED')) return 'danger';
    return 'success';
}

function formatTimestamp(isoStr) {
    if (!isoStr) return '--';
    try {
        const d = new Date(isoStr);
        return d.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch (e) {
        return isoStr;
    }
}

function formatTimeOnly(isoStr) {
    if (!isoStr) return '--';
    try {
        const d = new Date(isoStr);
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch (e) {
        return isoStr;
    }
}

function escapeHtml(str) {
    if (typeof str !== 'string') return str;
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
