// CC Team Dashboard — Client-side JavaScript
// Auto-refresh agent status every 30 seconds

(function () {
    'use strict';

    var REFRESH_INTERVAL = 30000;
    var TERMINAL_REFRESH_INTERVAL = 10000;
    var ACTIVITY_REFRESH_INTERVAL = 15000;
    var ISSUES_REFRESH_INTERVAL = 300000; // 5 minutes
    var AGENT_API = '/api/agents';
    var ISSUES_API = '/api/issues';

    // Known team role mappings
    var ROLE_MAP = {
        'Dan': 'CEO',
        'Mat': 'PM',
        'Kat': 'Dev-1 (Backend)',
        'Sam': 'Dev-2 (Frontend)'
    };

    function getRole(name) {
        return ROLE_MAP[name] || 'Agent';
    }

    function timeAgo(isoString) {
        if (!isoString) return 'Never';
        var now = new Date();
        var then = new Date(isoString);
        var diffMs = now - then;
        if (diffMs < 0) return 'Just now';
        var seconds = Math.floor(diffMs / 1000);
        if (seconds < 60) return seconds + 's ago';
        var minutes = Math.floor(seconds / 60);
        if (minutes < 60) return minutes + 'm ago';
        var hours = Math.floor(minutes / 60);
        if (hours < 24) return hours + 'h ago';
        var days = Math.floor(hours / 24);
        return days + 'd ago';
    }

    function uptimeDuration(isoString) {
        if (!isoString) return '—';
        var now = new Date();
        var since = new Date(isoString);
        var diffMs = now - since;
        if (diffMs < 0) return '—';
        var hours = Math.floor(diffMs / 3600000);
        var minutes = Math.floor((diffMs % 3600000) / 60000);
        if (hours > 0) return hours + 'h ' + minutes + 'm';
        return minutes + 'm';
    }

    function statusClass(status) {
        var s = (status || 'offline').toLowerCase();
        if (s === 'online') return 'online';
        if (s === 'busy') return 'busy';
        if (s === 'idle') return 'idle';
        if (s === 'error') return 'error';
        return 'offline';
    }

    function statusLabel(status) {
        var s = (status || 'offline').toLowerCase();
        return s.charAt(0).toUpperCase() + s.slice(1);
    }

    // Render agent cards on the dashboard page
    function renderAgentCards(agents) {
        var container = document.getElementById('agent-cards');
        if (!container) return;

        if (!agents || agents.length === 0) {
            container.innerHTML = '<p class="empty-msg">No agents registered.</p>';
            return;
        }

        var html = '';
        for (var i = 0; i < agents.length; i++) {
            var a = agents[i];
            var sc = statusClass(a.status);
            html += '<div class="agent-card" data-status="' + sc + '" data-agent-id="' + a.id + '">'
                + '<div class="agent-card-header">'
                + '<span class="agent-name">' + escapeHtml(a.name) + '</span>'
                + '<span class="status-badge ' + sc + '">' + statusLabel(a.status) + '</span>'
                + '</div>'
                + '<div class="agent-card-body">'
                + '<div class="agent-role">' + escapeHtml(getRole(a.name)) + '</div>'
                + '<div class="agent-task">' + escapeHtml(a.current_task || 'No active task') + '</div>'
                + '<div class="agent-lastseen">Last seen: ' + timeAgo(a.last_active) + '</div>'
                + '</div>'
                + '<div class="agent-working" id="working-' + a.id + '"></div>'
                + '</div>';
        }
        container.innerHTML = html;

        for (var j = 0; j < agents.length; j++) {
            fetchWorkingMd(agents[j].id, agents[j].name);
        }
    }

    // Render agent table on the agents page
    function renderAgentTable(agents) {
        var tbody = document.getElementById('agent-table-body');
        if (!tbody) return;

        if (!agents || agents.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="empty-msg">No agents registered.</td></tr>';
            return;
        }

        var html = '';
        for (var i = 0; i < agents.length; i++) {
            var a = agents[i];
            var sc = statusClass(a.status);
            html += '<tr data-status="' + sc + '">'
                + '<td>' + escapeHtml(a.name) + '</td>'
                + '<td>' + escapeHtml(getRole(a.name)) + '</td>'
                + '<td><span class="status-badge ' + sc + '">' + statusLabel(a.status) + '</span></td>'
                + '<td>' + escapeHtml(a.current_task || '—') + '</td>'
                + '<td>' + timeAgo(a.last_active) + '</td>'
                + '<td>' + uptimeDuration(a.uptime_since) + '</td>'
                + '</tr>';
        }
        tbody.innerHTML = html;
    }

    function escapeHtml(str) {
        if (!str) return '';
        var div = document.createElement('div');
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }

    // --- Terminal live view (agents page) ---

    var knownAgentNames = [];

    function renderTerminalGrid(agents) {
        var grid = document.getElementById('terminal-grid');
        if (!grid) return;

        knownAgentNames = [];
        for (var i = 0; i < agents.length; i++) {
            knownAgentNames.push(agents[i].name);
        }

        if (knownAgentNames.length === 0) {
            grid.innerHTML = '<p class="empty-msg">No agents registered.</p>';
            return;
        }

        var html = '';
        for (var i = 0; i < knownAgentNames.length; i++) {
            var name = knownAgentNames[i];
            html += '<div class="terminal-box" id="term-' + escapeHtml(name) + '">'
                + '<div class="terminal-header">'
                + '<span class="terminal-title">' + escapeHtml(name) + '</span>'
                + '<span class="terminal-status" id="term-status-' + escapeHtml(name) + '">connecting...</span>'
                + '</div>'
                + '<div class="terminal-body" id="term-body-' + escapeHtml(name) + '">Loading...</div>'
                + '</div>';
        }
        grid.innerHTML = html;
        fetchAllTerminals();
    }

    function fetchTerminal(name) {
        var xhr = new XMLHttpRequest();
        xhr.open('GET', '/api/agents/' + encodeURIComponent(name) + '/terminal', true);
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== 4) return;
            var body = document.getElementById('term-body-' + name);
            var status = document.getElementById('term-status-' + name);
            if (!body || !status) return;

            if (xhr.status === 200) {
                try {
                    var data = JSON.parse(xhr.responseText);
                    var output = data.output || '';
                    if (output.trim() === '') {
                        body.innerHTML = '<span class="terminal-empty">No output</span>';
                    } else {
                        body.textContent = output;
                    }
                    status.textContent = 'live';
                    status.style.color = '';
                } catch (e) {
                    body.innerHTML = '<span class="terminal-empty">Parse error</span>';
                    status.textContent = 'error';
                    status.style.color = 'var(--status-red)';
                }
            } else {
                body.innerHTML = '<span class="terminal-empty">No tmux session</span>';
                status.textContent = 'disconnected';
                status.style.color = 'var(--status-red)';
            }
        };
        xhr.send();
    }

    function fetchAllTerminals() {
        for (var i = 0; i < knownAgentNames.length; i++) {
            fetchTerminal(knownAgentNames[i]);
        }
    }

    // --- WORKING.md display (dashboard cards) ---

    function fetchWorkingMd(agentId, agentName) {
        var xhr = new XMLHttpRequest();
        xhr.open('GET', '/api/agents/' + agentId + '/working', true);
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== 4) return;
            var container = document.getElementById('working-' + agentId);
            if (!container) return;

            if (xhr.status === 200) {
                try {
                    var data = JSON.parse(xhr.responseText);
                    var html = data.content_html || '';
                    if (html.trim()) {
                        container.innerHTML = '<div class="agent-working-label">Working Status</div>'
                            + '<div class="working-md-rendered">' + html + '</div>';
                    } else {
                        container.innerHTML = '';
                    }
                } catch (e) {
                    container.innerHTML = '';
                }
            } else {
                container.innerHTML = '';
            }
        };
        xhr.send();
    }

    // Fetch agents from API and update both views
    function fetchAgents() {
        var xhr = new XMLHttpRequest();
        xhr.open('GET', AGENT_API, true);
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== 4) return;
            if (xhr.status === 200) {
                try {
                    var agents = JSON.parse(xhr.responseText);
                    renderAgentCards(agents);
                    renderAgentTable(agents);
                    renderTerminalGrid(agents);
                } catch (e) {
                    showError('Failed to parse agent data.');
                }
            } else if (xhr.status === 404) {
                showError('Agent API not available yet.');
            } else {
                showError('Error loading agents (HTTP ' + xhr.status + ').');
            }
        };
        xhr.send();
    }

    function showError(msg) {
        var cards = document.getElementById('agent-cards');
        if (cards) cards.innerHTML = '<p class="error-msg">' + msg + '</p>';
        var tbody = document.getElementById('agent-table-body');
        if (tbody) tbody.innerHTML = '<tr><td colspan="6" class="error-msg">' + msg + '</td></tr>';
    }

    // Status filter buttons
    function initFilters() {
        var filterContainers = document.querySelectorAll('.status-filter');
        for (var i = 0; i < filterContainers.length; i++) {
            filterContainers[i].addEventListener('click', function (e) {
                if (!e.target.classList.contains('filter-btn')) return;

                // Update active button in this filter group
                var buttons = this.querySelectorAll('.filter-btn');
                for (var j = 0; j < buttons.length; j++) {
                    buttons[j].classList.remove('active');
                }
                e.target.classList.add('active');

                var filter = e.target.getAttribute('data-filter');
                applyFilter(filter);
            });
        }
    }

    function applyFilter(filter) {
        // Filter cards
        var cards = document.querySelectorAll('.agent-card');
        for (var i = 0; i < cards.length; i++) {
            if (filter === 'all' || cards[i].getAttribute('data-status') === filter) {
                cards[i].style.display = '';
            } else {
                cards[i].style.display = 'none';
            }
        }
        // Filter table rows
        var rows = document.querySelectorAll('#agent-table-body tr');
        for (var i = 0; i < rows.length; i++) {
            if (filter === 'all' || rows[i].getAttribute('data-status') === filter) {
                rows[i].style.display = '';
            } else {
                rows[i].style.display = 'none';
            }
        }
    }

    // --- Heartbeat status display ---

    function updateHeartbeatUI(active) {
        var badge = document.getElementById('heartbeat-badge');
        var btn = document.getElementById('toggle-btn') || document.getElementById('toggle-display');

        if (badge) {
            badge.textContent = active ? 'ON' : 'OFF';
            badge.className = 'heartbeat-status-badge ' + (active ? 'hb-on' : 'hb-off');
        }

        if (btn) {
            if (active) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        }
    }

    function fetchHeartbeatStatus() {
        var xhr = new XMLHttpRequest();
        xhr.open('GET', '/api/heartbeat/status', true);
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== 4) return;
            if (xhr.status === 200) {
                try {
                    var data = JSON.parse(xhr.responseText);
                    updateHeartbeatUI(data.active);
                } catch (e) { /* ignore */ }
            }
        };
        xhr.send();
    }

    function initHeartbeatToggle() {
        var toggleContainer = document.getElementById('heartbeat-toggle');
        var btn = document.getElementById('toggle-btn');

        fetchHeartbeatStatus();

        // Only set up click handler if admin mode (toggle button present)
        if (!btn || !toggleContainer || !toggleContainer.hasAttribute('data-admin-mode')) return;

        btn.addEventListener('click', function () {
            var xhr = new XMLHttpRequest();
            xhr.open('POST', '/api/heartbeat/toggle', true);
            xhr.setRequestHeader('Content-Type', 'application/json');
            // Pass admin key from URL for auth
            var params = new URLSearchParams(window.location.search);
            var adminKey = params.get('admin') || '';
            xhr.setRequestHeader('X-API-Key', adminKey);
            xhr.onreadystatechange = function () {
                if (xhr.readyState !== 4) return;
                if (xhr.status === 200) {
                    try {
                        var data = JSON.parse(xhr.responseText);
                        updateHeartbeatUI(data.active);
                    } catch (e) { /* ignore */ }
                }
            };
            xhr.send('{}');
        });
    }

    // --- Activity feed ---

    var ACTIVITY_ICONS = {
        commit: '\u25CF',
        heartbeat: '\u2665',
        slack: '\u0023'
    };

    function renderActivityFeed(events) {
        var container = document.getElementById('activity-feed');
        if (!container) return;

        if (!events || events.length === 0) {
            container.innerHTML = '<p class="empty-msg">No recent activity.</p>';
            return;
        }

        var html = '';
        for (var i = 0; i < events.length; i++) {
            var e = events[i];
            var icon = ACTIVITY_ICONS[e.type] || '\u2022';
            var iconClass = e.type || 'commit';
            html += '<div class="activity-item">'
                + '<span class="activity-icon ' + iconClass + '">' + icon + '</span>'
                + '<div class="activity-body">'
                + '<span class="activity-agent">' + escapeHtml(e.agent) + '</span>'
                + '<span class="activity-message">' + escapeHtml(e.message) + '</span>'
                + '</div>'
                + '<span class="activity-time">' + timeAgo(e.timestamp) + '</span>'
                + '</div>';
        }
        container.innerHTML = html;
    }

    function fetchActivity() {
        var container = document.getElementById('activity-feed');
        if (!container) return;

        var xhr = new XMLHttpRequest();
        xhr.open('GET', '/api/activity', true);
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== 4) return;
            if (xhr.status === 200) {
                try {
                    var events = JSON.parse(xhr.responseText);
                    renderActivityFeed(events);
                } catch (e) {
                    container.innerHTML = '<p class="error-msg">Failed to parse activity.</p>';
                }
            } else {
                container.innerHTML = '<p class="error-msg">Error loading activity.</p>';
            }
        };
        xhr.send();
    }

    // --- Issues / Kanban ---

    var COLUMN_IDS = {
        'Inbox': 'cards-inbox',
        'Assigned': 'cards-assigned',
        'In Progress': 'cards-in-progress',
        'Review': 'cards-review',
        'Done': 'cards-done'
    };

    var COUNT_IDS = {
        'Inbox': 'count-inbox',
        'Assigned': 'count-assigned',
        'In Progress': 'count-in-progress',
        'Review': 'count-review',
        'Done': 'count-done'
    };

    function repoShort(fullName) {
        if (!fullName) return '';
        var parts = fullName.split('/');
        return parts.length > 1 ? parts[1] : fullName;
    }

    function renderIssueCard(issue) {
        var labels = '';
        if (issue.labels && issue.labels.length > 0) {
            labels = '<div class="issue-labels">';
            for (var k = 0; k < issue.labels.length; k++) {
                labels += '<span class="issue-label">' + escapeHtml(issue.labels[k]) + '</span>';
            }
            labels += '</div>';
        }

        var assigneeHtml = issue.assignee
            ? '<span class="issue-assignee">' + escapeHtml(issue.assignee) + '</span>'
            : '';

        return '<div class="issue-card">'
            + '<div class="issue-card-title">'
            + '<a href="' + escapeHtml(issue.url) + '" target="_blank" rel="noopener">'
            + escapeHtml(issue.title)
            + '</a>'
            + '</div>'
            + '<div class="issue-card-meta">'
            + '<span class="issue-card-number">#' + issue.number + '</span>'
            + '<span class="repo-badge">' + escapeHtml(repoShort(issue.repo)) + '</span>'
            + assigneeHtml
            + '</div>'
            + labels
            + '</div>';
    }

    function renderKanbanBoard(issues) {
        var board = document.getElementById('kanban-board');
        if (!board) return;

        // Group issues by column
        var columns = { 'Inbox': [], 'Assigned': [], 'In Progress': [], 'Review': [], 'Done': [] };
        for (var i = 0; i < issues.length; i++) {
            var col = issues[i].column || 'Inbox';
            if (!columns[col]) col = 'Inbox';
            columns[col].push(issues[i]);
        }

        // Render each column
        for (var colName in COLUMN_IDS) {
            var container = document.getElementById(COLUMN_IDS[colName]);
            var countEl = document.getElementById(COUNT_IDS[colName]);
            if (!container) continue;

            var colIssues = columns[colName] || [];
            if (countEl) countEl.textContent = colIssues.length;

            if (colIssues.length === 0) {
                container.innerHTML = '<p class="empty-msg" style="padding:0.5rem;font-size:0.75rem;">No issues</p>';
                continue;
            }

            var html = '';
            for (var j = 0; j < colIssues.length; j++) {
                html += renderIssueCard(colIssues[j]);
            }
            container.innerHTML = html;
        }
    }

    function renderIssuesList(issues) {
        var tbody = document.getElementById('issues-table-body');
        if (!tbody) return;

        if (!issues || issues.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="empty-msg">No issues found.</td></tr>';
            return;
        }

        var html = '';
        for (var i = 0; i < issues.length; i++) {
            var issue = issues[i];
            var labelsStr = (issue.labels || []).join(', ');
            html += '<tr>'
                + '<td><a href="' + escapeHtml(issue.url) + '" target="_blank" rel="noopener">#' + issue.number + '</a></td>'
                + '<td>' + escapeHtml(issue.title) + '</td>'
                + '<td><span class="repo-badge">' + escapeHtml(repoShort(issue.repo)) + '</span></td>'
                + '<td>' + escapeHtml(issue.column) + '</td>'
                + '<td>' + escapeHtml(issue.assignee || '—') + '</td>'
                + '<td>' + escapeHtml(labelsStr || '—') + '</td>'
                + '<td>' + timeAgo(issue.updated_at) + '</td>'
                + '</tr>';
        }
        tbody.innerHTML = html;
    }

    function updateIssuesBadge(count) {
        var badge = document.getElementById('issues-badge');
        if (!badge) return;
        if (count > 0) {
            badge.textContent = count;
            badge.style.display = '';
        } else {
            badge.style.display = 'none';
        }
    }

    function fetchIssues() {
        var xhr = new XMLHttpRequest();
        xhr.open('GET', ISSUES_API, true);
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== 4) return;
            if (xhr.status === 200) {
                try {
                    var issues = JSON.parse(xhr.responseText);
                    renderKanbanBoard(issues);
                    renderIssuesList(issues);
                    updateIssuesBadge(issues.length);
                } catch (e) {
                    var board = document.getElementById('kanban-board');
                    if (board) board.innerHTML = '<p class="error-msg">Failed to parse issues data.</p>';
                }
            } else {
                var board = document.getElementById('kanban-board');
                if (board) board.innerHTML = '<p class="error-msg">Error loading issues (HTTP ' + xhr.status + ').</p>';
            }
        };
        xhr.send();
    }

    function initViewToggle() {
        var kanbanBtn = document.getElementById('kanban-view-btn');
        var listBtn = document.getElementById('list-view-btn');
        var kanbanBoard = document.getElementById('kanban-board');
        var issuesList = document.getElementById('issues-list');

        if (!kanbanBtn || !listBtn) return;

        kanbanBtn.addEventListener('click', function () {
            kanbanBtn.classList.add('active');
            listBtn.classList.remove('active');
            if (kanbanBoard) kanbanBoard.style.display = '';
            if (issuesList) issuesList.style.display = 'none';
        });

        listBtn.addEventListener('click', function () {
            listBtn.classList.add('active');
            kanbanBtn.classList.remove('active');
            if (kanbanBoard) kanbanBoard.style.display = 'none';
            if (issuesList) issuesList.style.display = '';
        });
    }

    // Initialize on DOM ready
    function init() {
        fetchAgents();
        initFilters();
        initHeartbeatToggle();
        fetchActivity();
        fetchIssues();
        initViewToggle();
        setInterval(fetchAgents, REFRESH_INTERVAL);
        setInterval(function () {
            if (knownAgentNames.length > 0) {
                fetchAllTerminals();
            }
        }, TERMINAL_REFRESH_INTERVAL);
        setInterval(fetchActivity, ACTIVITY_REFRESH_INTERVAL);
        setInterval(fetchIssues, ISSUES_REFRESH_INTERVAL);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
