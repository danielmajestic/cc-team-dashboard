# CC Team Dashboard - Product Requirements Document

**Internal Team Dashboard for Claude Code Agent Monitoring & GitHub Issue Tracking**

| Field | Value |
|-------|-------|
| Document Version | 1.0 |
| Date | February 6, 2026 |
| Status | Ready for Development |
| Product Name | CC Team Dashboard |
| Tech Stack | Python Flask, SQLite, Jinja2, HTML/CSS/JS |
| Theme | Dark Theme |

---

## 1. Executive Summary

### 1.1 Product Overview

CC Team Dashboard is an internal web application built with Flask that provides a centralized view of Claude Code agent activity and GitHub issue tracking. The dashboard features a dark theme UI and serves as the primary monitoring interface for the CC development team to track agent status, review GitHub issues, and monitor project health at a glance.

### 1.2 Core Value Proposition

- **Real-time agent monitoring** — view the status of all Claude Code agents in one place
- **GitHub issue integration** — pull and display issues from GitHub repositories without leaving the dashboard
- **Dark theme UI** — optimized for extended use and reduced eye strain
- **Lightweight deployment** — Flask-based with minimal infrastructure requirements
- **Team-oriented** — built for internal use with a focus on developer productivity

---

## 2. Goals & Objectives

### 2.1 Primary Goals

1. Provide a single-pane-of-glass view for CC agent operational status
2. Surface GitHub issues with filtering, sorting, and label-based categorization
3. Deliver a fast, responsive dark-themed interface
4. Keep the stack simple — Flask, SQLite, server-rendered templates
5. Enable the team to quickly identify blocked agents, stale issues, and project bottlenecks

### 2.2 Target Users

| User | Role | Primary Need |
|------|------|--------------|
| CC Engineers | Core development team | Monitor agent health, triage issues |
| Team Leads | Project oversight | Track milestone progress, identify blockers |
| On-Call Engineers | Incident response | Quickly assess agent status and recent failures |

---

## 3. Feature Specifications

### 3.1 Agent Status Panel

The main dashboard view displays all Claude Code agents and their current operational state.

| Feature | Description |
|---------|-------------|
| Agent List | Table/card view of all registered agents |
| Status Indicator | Color-coded badges: Online (green), Idle (yellow), Offline (red), Error (orange) |
| Last Active | Timestamp of most recent agent activity |
| Current Task | Brief description of what the agent is working on |
| Uptime | Duration since last restart or deployment |
| Health Check | Periodic ping status with latency display |
| Filtering | Filter agents by status, name, or task type |

### 3.2 GitHub Issues View

Displays issues pulled from one or more configured GitHub repositories via the GitHub API.

| Feature | Description |
|---------|-------------|
| Issue List | Paginated table of open issues with title, labels, assignee, and age |
| Label Filtering | Filter issues by label (bug, enhancement, priority, etc.) |
| Repository Selector | Toggle between multiple configured repositories |
| Issue Detail | Expandable view showing issue body, comments count, and linked PRs |
| Status Badges | Visual indicators for open, closed, and in-progress states |
| Sort Options | Sort by created date, updated date, comments, or priority label |
| Refresh | Manual and auto-refresh (configurable interval) |

### 3.3 Dashboard Overview

A summary landing page with key metrics and quick-glance widgets.

| Widget | Content |
|--------|---------|
| Agent Summary | Count of agents by status (e.g., 5 Online, 2 Idle, 1 Error) |
| Open Issues | Total open issues across all configured repos |
| Recent Activity | Timeline of recent agent events and issue updates |
| Milestone Progress | Progress bars for each active milestone |
| Alerts | Highlighted cards for agents in error state or critical issues |

### 3.4 Dark Theme UI

| Aspect | Specification |
|--------|---------------|
| Background | Dark gray (#1a1a2e or similar) |
| Surface | Slightly lighter panels (#16213e) |
| Text | Light gray (#e0e0e0) for body, white (#ffffff) for headings |
| Accent | Blue (#0f3460) for interactive elements, teal (#53d8fb) for highlights |
| Status Colors | Green (#4ecca3), Yellow (#f0c040), Red (#e74c3c), Orange (#f39c12) |
| Font | System monospace stack for data, sans-serif for headings |
| Contrast | WCAG AA compliant minimum contrast ratios |

---

## 4. Technical Architecture

### 4.1 Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Backend | Python Flask | Web framework, routing, API endpoints |
| Templating | Jinja2 | Server-side HTML rendering |
| Database | SQLite | Agent registration, configuration, cached data |
| Frontend | HTML, CSS, JavaScript | Dark theme UI, interactive tables, auto-refresh |
| GitHub Integration | GitHub REST API (via `requests` or `PyGithub`) | Fetch issues, PRs, repo metadata |
| Styling | Custom CSS (dark theme) | No heavy framework dependency |

### 4.2 Project Structure

```
cc-team-dashboard/
├── app.py                  # Flask application entry point
├── config.py               # Configuration (GitHub tokens, repos, refresh intervals)
├── requirements.txt        # Python dependencies
├── models.py               # SQLite models (agents, settings)
├── github_client.py        # GitHub API integration
├── templates/
│   ├── base.html           # Base layout with dark theme, nav
│   ├── dashboard.html      # Overview / landing page
│   ├── agents.html         # Agent status panel
│   └── issues.html         # GitHub issues view
├── static/
│   ├── css/
│   │   └── style.css       # Dark theme styles
│   └── js/
│       └── dashboard.js    # Auto-refresh, filtering, interactivity
├── PRD.md                  # This document
└── LICENSE
```

### 4.3 Key Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Dashboard overview with summary widgets |
| `/agents` | GET | Agent status panel |
| `/agents/<id>` | GET | Individual agent detail view |
| `/issues` | GET | GitHub issues list with filters |
| `/api/agents` | GET | JSON endpoint for agent data |
| `/api/agents/<id>/status` | POST | Update agent status (webhook/heartbeat) |
| `/api/issues/refresh` | POST | Trigger GitHub issue re-fetch |

### 4.4 Configuration

```python
# config.py
GITHUB_TOKEN = "..."                    # Personal access token or GitHub App token
GITHUB_REPOS = [                        # Repositories to track
    "org/repo-1",
    "org/repo-2",
]
ISSUE_REFRESH_INTERVAL = 300            # Seconds between auto-refresh
AGENT_HEARTBEAT_TIMEOUT = 60            # Seconds before marking agent as offline
SECRET_KEY = "..."                      # Flask session secret
DATABASE_URI = "sqlite:///dashboard.db"
```

---

## 5. Development Milestones

### Milestone 1: Project Foundation

**Goal:** Set up the Flask application skeleton with dark theme and basic routing.

- Initialize Flask project structure
- Create base HTML template with dark theme CSS
- Implement navigation between dashboard, agents, and issues views
- Set up SQLite database with agent model
- Add configuration management (config.py, environment variables)
- Create requirements.txt with initial dependencies

**Deliverable:** Running Flask app with dark-themed placeholder pages and working navigation.

### Milestone 2: Agent Status Panel

**Goal:** Build the agent monitoring interface with real-time status display.

- Implement agent registration and database storage
- Create API endpoint for agent heartbeat/status updates
- Build agent list view with status indicators (online, idle, offline, error)
- Add agent detail view with history and current task info
- Implement heartbeat timeout logic (auto-mark offline)
- Add filtering and sorting to agent list

**Deliverable:** Functional agent status panel with live status updates and detail views.

### Milestone 3: GitHub Issues Integration

**Goal:** Connect to GitHub API and display issues in the dashboard.

- Implement GitHub API client with authentication
- Fetch and cache issues from configured repositories
- Build issues list view with pagination
- Add label-based filtering and sorting
- Implement repository selector for multi-repo support
- Add expandable issue detail with body and comment count
- Configure auto-refresh interval for issue data

**Deliverable:** GitHub issues view with filtering, sorting, and auto-refresh.

### Milestone 4: Dashboard Overview & Widgets

**Goal:** Create the summary landing page with key metrics and alerts.

- Build agent summary widget (counts by status)
- Add open issue count widget with breakdown by repo
- Implement recent activity timeline
- Create milestone progress bars
- Add alert cards for agents in error state or critical issues
- Wire up auto-refresh for dashboard widgets

**Deliverable:** Dashboard overview page with live summary widgets and alerts.

### Milestone 5: Polish & Deployment

**Goal:** Refine the UI, add final features, and prepare for deployment.

- Responsive layout adjustments for various screen sizes
- Keyboard shortcuts for common actions (refresh, filter toggle)
- Error handling and graceful degradation (GitHub API failures, DB issues)
- Loading states and skeleton screens
- Configuration documentation
- Deployment setup (systemd service, Docker option, or similar)
- Final QA pass on dark theme consistency and accessibility

**Deliverable:** Production-ready dashboard with documentation and deployment configuration.

---

## 6. Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Page Load Time | < 1 second for all views |
| Auto-Refresh | Configurable, default 5 minutes for issues, 30 seconds for agents |
| Browser Support | Chrome, Firefox, Safari (latest versions) |
| Accessibility | WCAG AA contrast ratios for dark theme |
| Security | GitHub token stored securely, no token exposure in frontend |
| Data Freshness | Agent status within 60 seconds, issues within 5 minutes |

---

## 7. Success Criteria

| Metric | Target |
|--------|--------|
| Agent Visibility | 100% of active agents displayed with correct status |
| Issue Accuracy | All open issues from configured repos displayed |
| Uptime | Dashboard available during working hours without manual restarts |
| Team Adoption | Used daily by CC engineering team |
| Response Time | All pages render in under 1 second |

---

*End of Document*

**CC Team Dashboard** | PRD v1.0 | February 2026
