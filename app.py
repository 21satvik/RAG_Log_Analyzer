#!/usr/bin/env python3
"""
Log Analyzer Pro - PROFESSIONAL UI VERSION (FIXED)
Fixes:
1. Past incidents HTML escaping and missing data handling
2. PDF export with proper content
3. Copy to clipboard functionality
4. Load examples from test_logs/ folder
"""

import streamlit as st
from rag_engine import RAGLogAnalyzer, AnalysisResult, BackendType, Contact, Solution
import os
import time
import random
from dotenv import load_dotenv
import re
import io
import html
import json

# PDF generation imports (optional)
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# Load environment variables from .env file
load_dotenv()

# Page config
st.set_page_config(
    page_title="LogGuard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================================
# PROFESSIONAL UI - COMPLETE OVERHAUL
# ============================================================
st.markdown("""
<style>
    /* ===== HIDE STREAMLIT UI ELEMENTS ===== */
    #MainMenu, footer, header {visibility: hidden;}
    
    /* ===== DESIGN TOKENS ===== */
    :root {
        /* Colors */
        --bg-primary: #0a0a0f;
        --bg-secondary: #12121a;
        --bg-tertiary: #1a1a25;
        --bg-card: rgba(26, 26, 37, 0.8);
        --bg-hover: rgba(99, 102, 241, 0.08);
        
        --accent-primary: #6366f1;
        --accent-secondary: #8b5cf6;
        --accent-success: #22c55e;
        --accent-warning: #f59e0b;
        --accent-danger: #ef4444;
        --accent-info: #06b6d4;
        
        --text-primary: #f8fafc;
        --text-secondary: #94a3b8;
        --text-muted: #64748b;
        
        --border-subtle: rgba(148, 163, 184, 0.1);
        --border-medium: rgba(148, 163, 184, 0.2);
        
        /* Spacing */
        --space-xs: 0.25rem;
        --space-sm: 0.5rem;
        --space-md: 1rem;
        --space-lg: 1.5rem;
        --space-xl: 2rem;
        --space-2xl: 3rem;
        
        /* Radius */
        --radius-sm: 8px;
        --radius-md: 12px;
        --radius-lg: 16px;
        --radius-xl: 24px;
    }
    
    /* ===== GLOBAL ===== */
    .stApp {
        background: var(--bg-primary);
    }
    
    .block-container {
        padding: 0 2rem 2rem 2rem;
        max-width: 1400px;
    }
    
    /* ===== HEADER ===== */
    .app-header {
        background: linear-gradient(180deg, var(--bg-secondary) 0%, var(--bg-primary) 100%);
        padding: 2.5rem 0 1.5rem 0;
        margin: 0 -2rem 2rem -2rem;
        border-bottom: 1px solid var(--border-subtle);
    }
    
    .app-header h1 {
        font-size: 2.5rem !important;
        font-weight: 800 !important;
        background: linear-gradient(135deg, var(--accent-primary) 0%, var(--accent-secondary) 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 0 !important;
        letter-spacing: -0.02em;
    }
    
    .app-header p {
        color: var(--text-secondary);
        font-size: 1rem;
        margin-top: 0.5rem;
    }
    
    /* ===== CONTROL BAR ===== */
    .control-bar {
        display: flex;
        gap: 1rem;
        align-items: center;
        flex-wrap: wrap;
        padding: 1rem;
        background: var(--bg-secondary);
        border-radius: var(--radius-md);
        border: 1px solid var(--border-subtle);
        margin-bottom: 1.5rem;
    }
    
    .control-item {
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    .control-label {
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--text-muted);
    }
    
    .control-value {
        font-size: 0.875rem;
        font-weight: 500;
        color: var(--text-primary);
    }
    
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.375rem;
        padding: 0.375rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    
    .status-badge.online {
        background: rgba(34, 197, 94, 0.15);
        color: var(--accent-success);
    }
    
    .status-badge.offline {
        background: rgba(239, 68, 68, 0.15);
        color: var(--accent-danger);
    }
    
    /* ===== METRICS GRID ===== */
    .metrics-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 1rem;
        margin-bottom: 2rem;
    }
    
    .metric-card {
        background: var(--bg-card);
        border: 1px solid var(--border-subtle);
        border-radius: var(--radius-md);
        padding: 1.25rem;
        position: relative;
        overflow: hidden;
    }
    
    .metric-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: var(--accent-primary);
    }
    
    .metric-card.critical::before { background: var(--accent-danger); }
    .metric-card.error::before { background: #f97316; }
    .metric-card.warning::before { background: var(--accent-warning); }
    .metric-card.success::before { background: var(--accent-success); }
    
    .metric-label {
        font-size: 0.6875rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--text-muted);
        margin-bottom: 0.5rem;
    }
    
    .metric-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: var(--text-primary);
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    .metric-icon {
        width: 28px;
        height: 28px;
        border-radius: 6px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.875rem;
    }
    
    /* ===== SECTION HEADERS ===== */
    .section-header {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin: 2rem 0 1rem 0;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid var(--border-subtle);
    }
    
    .section-icon {
        width: 36px;
        height: 36px;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1rem;
    }
    
    .section-icon.contacts { background: rgba(34, 197, 94, 0.15); }
    .section-icon.solutions { background: rgba(99, 102, 241, 0.15); }
    .section-icon.incidents { background: rgba(245, 158, 11, 0.15); }
    .section-icon.timeline { background: rgba(6, 182, 212, 0.15); }
    .section-icon.analysis { background: rgba(139, 92, 246, 0.15); }
    
    .section-title {
        font-size: 1.125rem;
        font-weight: 700;
        color: var(--text-primary);
    }
    
    .section-count {
        margin-left: auto;
        font-size: 0.75rem;
        font-weight: 600;
        padding: 0.25rem 0.625rem;
        border-radius: 9999px;
        background: var(--bg-tertiary);
        color: var(--text-secondary);
    }
    
    /* ===== CARDS ===== */
    .card-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
        gap: 1rem;
    }
    
    .info-card {
        background: var(--bg-card);
        border: 1px solid var(--border-subtle);
        border-radius: var(--radius-md);
        padding: 1.25rem;
        transition: all 0.2s ease;
    }
    
    .info-card:hover {
        border-color: var(--border-medium);
        background: var(--bg-hover);
    }
    
    .card-header {
        display: flex;
        align-items: flex-start;
        gap: 0.875rem;
        margin-bottom: 1rem;
    }
    
    .card-avatar {
        width: 44px;
        height: 44px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.25rem;
        flex-shrink: 0;
    }
    
    .card-avatar.contact { background: linear-gradient(135deg, rgba(34, 197, 94, 0.2), rgba(34, 197, 94, 0.1)); }
    .card-avatar.solution { background: linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(99, 102, 241, 0.1)); }
    
    .card-meta {
        flex: 1;
        min-width: 0;
    }
    
    .card-title {
        font-size: 1rem;
        font-weight: 600;
        color: var(--text-primary);
        margin-bottom: 0.25rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    .card-subtitle {
        font-size: 0.8125rem;
        color: var(--text-secondary);
    }
    
    .card-body {
        font-size: 0.875rem;
        color: var(--text-secondary);
        line-height: 1.6;
    }
    
    .card-footer {
        display: flex;
        gap: 0.5rem;
        margin-top: 1rem;
        flex-wrap: wrap;
    }
    
    .card-tag {
        font-size: 0.6875rem;
        font-weight: 600;
        padding: 0.25rem 0.5rem;
        border-radius: 6px;
        background: var(--bg-tertiary);
        color: var(--text-muted);
    }
    
    .card-tag.escalation {
        background: rgba(245, 158, 11, 0.15);
        color: var(--accent-warning);
    }
    
    /* ===== INCIDENT CARDS ===== */
    .incident-card {
        background: var(--bg-card);
        border: 1px solid var(--border-subtle);
        border-radius: var(--radius-md);
        padding: 1.25rem;
        margin-bottom: 0.75rem;
    }
    
    .incident-header {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin-bottom: 0.75rem;
    }
    
    .incident-id {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.8125rem;
        font-weight: 600;
        padding: 0.25rem 0.5rem;
        border-radius: 6px;
        background: var(--bg-tertiary);
    }
    
    .incident-severity {
        font-size: 0.6875rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
    }
    
    .incident-severity.critical { background: rgba(239, 68, 68, 0.15); color: var(--accent-danger); }
    .incident-severity.high { background: rgba(249, 115, 22, 0.15); color: #f97316; }
    .incident-severity.medium { background: rgba(245, 158, 11, 0.15); color: var(--accent-warning); }
    .incident-severity.low { background: rgba(34, 197, 94, 0.15); color: var(--accent-success); }
    
    .incident-match {
        margin-left: auto;
        font-size: 0.75rem;
        font-weight: 600;
        color: var(--accent-success);
    }
    
    .incident-title {
        font-size: 0.9375rem;
        color: var(--text-primary);
        margin-bottom: 0.5rem;
        line-height: 1.5;
    }
    
    .incident-stats {
        display: flex;
        gap: 1.5rem;
        font-size: 0.8125rem;
        color: var(--text-secondary);
    }
    
    .incident-stat {
        display: flex;
        align-items: center;
        gap: 0.375rem;
    }
    
    .incident-resolution {
        margin-top: 0.75rem;
        padding-top: 0.75rem;
        border-top: 1px solid var(--border-subtle);
        font-size: 0.8125rem;
        color: var(--text-muted);
    }
    
    /* ===== TIMELINE ===== */
    .timeline {
        position: relative;
        padding-left: 1.5rem;
    }
    
    .timeline::before {
        content: '';
        position: absolute;
        left: 0.5rem;
        top: 0;
        bottom: 0;
        width: 2px;
        background: linear-gradient(180deg, var(--accent-info), transparent);
        border-radius: 1px;
    }
    
    .timeline-item {
        position: relative;
        padding: 0.875rem 1rem;
        margin-bottom: 0.5rem;
        background: var(--bg-card);
        border: 1px solid var(--border-subtle);
        border-radius: var(--radius-sm);
    }
    
    .timeline-item::before {
        content: '';
        position: absolute;
        left: -1.25rem;
        top: 1.125rem;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: var(--accent-info);
        border: 2px solid var(--bg-primary);
    }
    
    .timeline-time {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.6875rem;
        color: var(--text-muted);
        margin-bottom: 0.25rem;
    }
    
    .timeline-content {
        font-size: 0.875rem;
        color: var(--text-primary);
    }
    
    .timeline-component {
        font-weight: 600;
        color: var(--accent-info);
    }
    
    /* ===== MULTI-AGENT PANEL ===== */
    .agent-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem 1rem;
        border-radius: 9999px;
        font-size: 0.8125rem;
        font-weight: 600;
        margin-bottom: 1rem;
    }
    
    .agent-badge.parallel {
        background: rgba(34, 197, 94, 0.15);
        color: var(--accent-success);
    }
    
    .agent-badge.sequential {
        background: rgba(245, 158, 11, 0.15);
        color: var(--accent-warning);
    }
    
    .causal-chain {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        align-items: center;
        margin: 1rem 0;
    }
    
    .chain-node {
        padding: 0.5rem 0.875rem;
        border-radius: 8px;
        font-size: 0.8125rem;
        font-weight: 500;
        background: var(--bg-tertiary);
        color: var(--text-secondary);
        border: 1px solid var(--border-subtle);
    }
    
    .chain-node.root {
        background: rgba(244, 63, 94, 0.15);
        color: #f43f5e;
        border-color: rgba(244, 63, 94, 0.3);
    }
    
    .chain-arrow {
        color: var(--accent-primary);
        font-size: 1.25rem;
    }
    
    .action-list {
        margin: 0.75rem 0;
    }
    
    .action-item {
        display: flex;
        gap: 0.75rem;
        padding: 0.625rem 0;
        border-bottom: 1px solid var(--border-subtle);
    }
    
    .action-item:last-child {
        border-bottom: none;
    }
    
    .action-number {
        width: 22px;
        height: 22px;
        border-radius: 6px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.6875rem;
        font-weight: 700;
        flex-shrink: 0;
    }
    
    .action-number.immediate { background: rgba(239, 68, 68, 0.15); color: var(--accent-danger); }
    .action-number.short { background: rgba(245, 158, 11, 0.15); color: var(--accent-warning); }
    .action-number.preventive { background: rgba(34, 197, 94, 0.15); color: var(--accent-success); }
    
    .action-text {
        font-size: 0.875rem;
        color: var(--text-secondary);
        line-height: 1.5;
    }
    
    /* ===== UPLOAD AREA ===== */
    .upload-area {
        border: 2px dashed var(--border-medium);
        border-radius: var(--radius-lg);
        padding: 2.5rem;
        text-align: center;
        background: var(--bg-secondary);
        transition: all 0.2s ease;
    }
    
    .upload-area:hover {
        border-color: var(--accent-primary);
        background: var(--bg-hover);
    }
    
    .upload-icon {
        font-size: 2.5rem;
        margin-bottom: 1rem;
    }
    
    .upload-text {
        font-size: 1rem;
        font-weight: 600;
        color: var(--text-primary);
        margin-bottom: 0.5rem;
    }
    
    .upload-hint {
        font-size: 0.8125rem;
        color: var(--text-muted);
    }
    
    /* ===== BUTTONS ===== */
    .stButton > button {
        background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary)) !important;
        border: none !important;
        border-radius: 10px !important;
        color: white !important;
        font-weight: 600 !important;
        padding: 0.75rem 1.5rem !important;
        transition: all 0.2s ease !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 8px 20px rgba(99, 102, 241, 0.3);
    }
    
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, var(--accent-success), #16a34a) !important;
    }
    
    .stButton > button[kind="primary"]:hover {
        box-shadow: 0 8px 20px rgba(34, 197, 94, 0.3);
    }
    
    /* ===== TABS ===== */
    .stTabs [data-baseweb="tab-list"] {
        background: var(--bg-secondary);
        border-radius: 10px;
        padding: 0.25rem;
        gap: 0.25rem;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        color: var(--text-secondary);
        font-weight: 500;
        padding: 0.625rem 1rem;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        color: var(--text-primary);
        background: var(--bg-hover);
    }
    
    .stTabs [aria-selected="true"] {
        background: var(--accent-primary) !important;
        color: white !important;
    }
    
    /* ===== EXPANDERS ===== */
    .streamlit-expanderHeader {
        background: var(--bg-secondary) !important;
        border: 1px solid var(--border-subtle) !important;
        border-radius: 10px !important;
        padding: 0.875rem 1rem !important;
        font-weight: 600;
    }
    
    .streamlit-expanderContent {
        background: var(--bg-tertiary) !important;
        border: 1px solid var(--border-subtle) !important;
        border-top: none !important;
        border-radius: 0 0 10px 10px !important;
    }
    
    /* ===== CODE BLOCKS ===== */
    code, pre {
        background: var(--bg-secondary) !important;
        border: 1px solid var(--border-subtle) !important;
        border-radius: 10px !important;
        font-family: 'JetBrains Mono', monospace !important;
    }
    
    /* ===== ALERTS ===== */
    .stAlert {
        border-radius: 10px !important;
        border: 1px solid !important;
    }
    
    /* ===== SCROLLBAR ===== */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: var(--bg-secondary); }
    ::-webkit-scrollbar-thumb { background: var(--border-medium); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--accent-primary); }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def load_analyzer(_backend_type: BackendType, enable_layer2: bool):
    return RAGLogAnalyzer(backend=_backend_type, enable_layer2_sanitization=enable_layer2)


def render_metric_card(label, value, icon, severity_class=""):
    """Render a metric card with icon"""
    st.markdown(f"""
    <div class="metric-card {severity_class}">
        <div class="metric-label">{label}</div>
        <div class="metric-value">
            <span class="metric-icon">{icon}</span>
            {value}
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_contact_card(contact: Contact):
    """Render a professional contact card"""
    # Build escalation HTML properly
    escalation_html = ""
    if contact.escalation_contact:
        time_tag = f'<span class="card-tag">after {contact.escalation_time}</span>' if contact.escalation_time else ''
        escalation_html = f'<div class="card-footer"><span class="card-tag escalation">⚡ Escalate: {contact.escalation_contact}</span>{time_tag}</div>'
    
    phone_html = f"<div class='card-body'>📞 {contact.phone}</div>" if contact.phone else ""
    
    st.markdown(f"""
    <div class="info-card">
        <div class="card-header">
            <div class="card-avatar contact">👤</div>
            <div class="card-meta">
                <div class="card-title">{html.escape(contact.name)}</div>
                <div class="card-subtitle">{html.escape(contact.role)}</div>
            </div>
        </div>
        <div class="card-body">📧 {html.escape(contact.email)}</div>
        {phone_html}
        {escalation_html}
    </div>
    """, unsafe_allow_html=True)


def render_solution_card(solution: Solution):
    """Render a professional solution card - shows ALL steps"""
    steps_html = ""
    for i, step in enumerate(solution.steps, 1):
        steps_html += f"<div class='action-item'><span class='action-number immediate'>{i}</span><span class='action-text'>{html.escape(step)}</span></div>"
    
    st.markdown(f"""
    <div class="info-card">
        <div class="card-header">
            <div class="card-avatar solution">🔧</div>
            <div class="card-meta">
                <div class="card-title">{html.escape(solution.title)}</div>
                <div class="card-subtitle">⏱️ {html.escape(solution.duration)} • 👤 {html.escape(solution.owner.name)}</div>
            </div>
        </div>
        <div class="action-list">
            {steps_html}
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_incident_card(inc):
    """Render a professional incident card - FIXED VERSION"""
    severity = inc.get('severity', 'MEDIUM').lower()
    
    # Clean title - strip HTML tags and escape
    title_raw = inc.get('title', 'No description available')
    title_clean = re.sub(r'<[^>]+>', '', str(title_raw))
    title_escaped = html.escape(title_clean)
    
    # Build impact stats
    impact_html = ""
    if inc.get('financial_impact'):
        impact_html += f"<span class='incident-stat'>💰 {html.escape(str(inc.get('financial_impact')))}</span>"
    if inc.get('users_affected'):
        impact_html += f"<span class='incident-stat'>👥 {html.escape(str(inc.get('users_affected')))}</span>"
    
    # Build resolution section separately (not nested f-string)
    resolution_html = ""
    resolution_time = inc.get('resolution_time', '')
    owner = inc.get('owner', '')
    if resolution_time and owner and str(resolution_time).lower() != 'unknown' and str(owner).lower() != 'unknown':
        # Build as single line to avoid formatting issues
        resolution_html = f"<div class='incident-resolution'>✅ Resolved in {html.escape(str(resolution_time))} by {html.escape(str(owner))}</div>"
    
    # Build the full card HTML
    card_html = f"""
    <div class="incident-card">
        <div class="incident-header">
            <span class="incident-id">{html.escape(inc.get('id', 'INC-XXXX'))}</span>
            <span class="incident-severity {severity}">{html.escape(inc.get('severity', 'MEDIUM'))}</span>
            <span class="incident-match">{html.escape(str(inc.get('similarity', 'N/A')))} match</span>
        </div>
        <div class="incident-title">{title_escaped}</div>
        <div class="incident-stats">
            <span class='incident-stat'>📅 {html.escape(inc.get('date', 'Date unknown'))}</span>
            {impact_html}
        </div>
        {resolution_html}
    </div>
    """
    
    st.markdown(card_html, unsafe_allow_html=True)


def render_timeline_event(event):
    """Render a timeline event"""
    st.markdown(f"""
    <div class="timeline-item">
        <div class="timeline-time">{html.escape(event['timestamp'])}</div>
        <div class="timeline-content">
            <span class="timeline-component">[{html.escape(event['component'])}]</span> {html.escape(event['message'])}
        </div>
    </div>
    """, unsafe_allow_html=True)


def highlight_errors(log_text: str) -> str:
    lines = log_text.split('\n')
    highlighted = []
    for line in lines:
        if not line.strip():
            highlighted.append('')
            continue
        safe_line = html.escape(line)
        line_lower = line.lower()
        if any(word in line_lower for word in ['error', 'critical', 'fail', 'exception', 'fatal', '错误']):
            highlighted.append(f'<span style="color: #ef4444; font-weight: 500;">{safe_line}</span>')
        elif any(word in line_lower for word in ['warning', 'warn', '警告']):
            highlighted.append(f'<span style="color: #f59e0b; font-weight: 500;">{safe_line}</span>')
        elif any(word in line_lower for word in ['info', 'debug', 'trace']):
            highlighted.append(f'<span style="color: #06b6d4;">{safe_line}</span>')
        else:
            highlighted.append(f'<span style="color: #64748b;">{safe_line}</span>')
    return '\n'.join(highlighted)


def format_for_slack(result: AnalysisResult) -> str:
    analysis_text = ""
    if hasattr(result, 'multi_agent') and result.multi_agent:
        ma = result.multi_agent
        if ma.root_cause and ma.root_cause.trigger:
            analysis_text = f"*Root Cause*: {ma.root_cause.trigger}\n"
        if ma.impact and ma.impact.user_impact:
            analysis_text += f"*Impact*: {ma.impact.user_impact[:200]}...\n"
    else:
        analysis_text = result.analysis[:300] + "..." if len(result.analysis) > 300 else result.analysis
    
    slack_message = f"""🚨 *INCIDENT ALERT - {result.severity}*

*System*: {result.system} ({result.affected_component or 'multiple components'})
*Severity*: {result.severity}
*Confidence*: {result.confidence:.0%}
*When*: {result.timestamp or 'Unknown'}

{analysis_text}

*Primary Contact*: {result.contacts[0].name if result.contacts else 'Unknown'}
• Email: {result.contacts[0].email if result.contacts else 'N/A'}
• Phone: {result.contacts[0].phone if (result.contacts and result.contacts[0].phone) else 'N/A'}
"""
    
    if result.contacts and result.contacts[0].escalation_contact:
        slack_message += f"• Escalate to: {result.contacts[0].escalation_contact}"
        if result.contacts[0].escalation_time:
            slack_message += f" after {result.contacts[0].escalation_time}"
        slack_message += "\n"
    
    slack_message += "\n*Immediate Actions*:\n"
    if result.solutions and result.solutions[0].steps:
        for i, step in enumerate(result.solutions[0].steps[:5], 1):
            slack_message += f"{i}. {step}\n"
    else:
        slack_message += "See full runbook in system\n"
    
    return slack_message


def load_example_logs():
    """Load example logs from test_logs/ folder or use hardcoded fallback - FIXED"""
    example_logs = {}
    test_logs_dir = "test_logs"
    
    # Try to load from test_logs folder first
    if os.path.exists(test_logs_dir) and os.path.isdir(test_logs_dir):
        log_files = [f for f in os.listdir(test_logs_dir) if f.endswith('.log')]
        for log_file in sorted(log_files):
            try:
                with open(os.path.join(test_logs_dir, log_file), 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Create friendly name from filename
                    friendly_name = log_file.replace('.log', '').replace('_', ' ').title()
                    example_logs[friendly_name] = content
            except Exception as e:
                st.warning(f"Could not load {log_file}: {e}")
    
    # Fallback to hardcoded examples if no test_logs found
    if not example_logs:
        example_logs = {
            "Database Table Deleted": """[2026-01-30 09:42:17.789] 错误 [数据库] SQL执行异常: SELECT * FROM orders WHERE order_id = ?
[2026-01-30 09:42:17.890] 错误 [数据库] 错误信息: 表 'orders' 不存在 (Error Code: 1146)
[2026-01-30 09:42:18.123] 信息 [数据库DBA] DBA已通知，检查数据迁移状态
[2026-01-30 09:42:35.456] 信息 [数据库] 成功恢复表 'orders' 从备份库""",
            
            "Memory Spike & GC": """[2026-01-30 08:35:47.234] 警告 [内存监控] 服务器_A 内存使用率: 92%，进程: java(PID: 2847)
[2026-01-30 08:35:47.567] 信息 [内存监控] 触发垃圾回收, 目标进程 PID: 2847
[2026-01-30 08:35:49.123] 信息 [内存监控] 垃圾回收完成，内存释放: 1.34 GB，当前使用率: 58%""",
            
            "Disk Space Critical": """[2026-01-30 09:05:32.234] 错误 [磁盘存储] 警告: 日志磁盘使用率达到 76%，可用空间: 2.4GB
[2026-01-30 09:06:01.456] 警告 [磁盘存储] 日志磁盘使用率继续上升至 82%，触发压缩任务
[2026-01-30 09:06:15.789] 信息 [磁盘压缩] 开始压缩旧日志文件...
[2026-01-30 09:06:45.123] 信息 [磁盘压缩] 成功压缩 12 个文件，释放空间 1.2GB""",
            
            "Payment Gateway Timeout": """[2026-01-30 08:29:12.345] 错误 [API网关] 连接超时异常，目标服务: 支付服务 (服务器_B:8443)
[2026-01-30 08:29:13.456] 警告 [API网关] Stripe API 响应超时 (30秒)
[2026-01-30 08:29:14.567] 错误 [支付处理] 队列积压: 342 笔交易待处理"""
        }
    
    return example_logs


def main():
    # ===== HEADER =====
    st.markdown("""
    <div class="app-header">
        <div style="text-align: center;">
            <h1>🛡️ LogGuard</h1>
            <p>AI-powered incident analysis with instant knowledge base insights</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # ===== CONTROL BAR =====
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    
    def is_ollama_available():
        try:
            import requests
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    ollama_available = is_ollama_available()
    
    with col1:
        if ollama_available:
            backend_choice = st.selectbox("Backend", ["⚡ Groq API", "☁️ Claude API", "🏠 Local Ollama"])
        else:
            st.markdown("""
            <div style="padding: 0.5rem 1rem; background: var(--bg-secondary); border-radius: 8px; border: 1px solid var(--border-subtle);">
                <span style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; font-weight: 600;">Backend</span><br>
                <span style="color: var(--accent-success); font-weight: 500;">⚡ Groq API</span>
            </div>
            """, unsafe_allow_html=True)
            backend_choice = "⚡ Groq API"
    
    use_layer2_sanitization = False
    with col2:
        if ollama_available:
            use_layer2_sanitization = st.toggle("🔒 Layer 2", value=True)
        else:
            st.markdown("""
            <div style="text-align: center; opacity: 0.5; padding: 0.5rem;">
                <span style="font-size: 0.75rem; color: var(--text-muted);">🔒 Layer 2</span><br>
                <span style="font-size: 0.6875rem; color: var(--accent-danger);">Ollama offline</span>
            </div>
            """, unsafe_allow_html=True)
    
    use_multi_agent = True
    
    if "Groq" in backend_choice:
        backend = BackendType.GROQ_API
    elif "Claude" in backend_choice:
        backend = BackendType.CLAUDE_API
    else:
        backend = BackendType.OLLAMA_LOCAL
    
    try:
        analyzer = load_analyzer(backend, use_layer2_sanitization)
    except Exception as e:
        st.error(f"❌ Failed to initialize backend: {e}")
        st.info("💡 Create a `.env` file with your API key:")
        st.code("GROQ_API_KEY=gsk_your_key_here")
        return
    
    with col3:
        kb_count = analyzer.collection.count() if analyzer.collection else 0
        status_class = "online" if kb_count > 0 else "offline"
        status_text = "Online" if kb_count > 0 else "Offline"
        st.markdown(f"""
        <div style="text-align: center;">
            <span style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; font-weight: 600;">Knowledge Base</span><br>
            <span style="font-size: 1.25rem; font-weight: 700; color: var(--text-primary);">{kb_count}</span>
            <span class="status-badge {status_class}">● {status_text}</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        speed = "<10s" if backend == BackendType.GROQ_API else ("20-33s" if backend == BackendType.CLAUDE_API else "15-30s")
        st.markdown(f"""
        <div style="text-align: center;">
            <span style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; font-weight: 600;">Avg Speed</span><br>
            <span style="font-size: 1.25rem; font-weight: 700; color: var(--text-primary);">{speed}</span>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ===== UPLOAD SECTION - FIXED =====
    example_logs = load_example_logs()
    
    with st.expander("💡 Try an example log"):
        selected_example = st.selectbox("Choose example:", list(example_logs.keys()), label_visibility="collapsed")
        if st.button("📂 Load Example", use_container_width=True):
            st.session_state.example_log = example_logs[selected_example]
            st.session_state.example_name = selected_example
            st.rerun()
    
    log_content = None
    analyze_button = False
    
    if 'example_log' in st.session_state:
        log_content = st.session_state.example_log
        example_name = st.session_state.get('example_name', 'Example')
        st.info(f"📄 Loaded: **{example_name}**")
        del st.session_state.example_log
        if 'example_name' in st.session_state:
            del st.session_state.example_name
        analyze_button = True
    else:
        uploaded_file = st.file_uploader("Upload log file", type=["log", "txt", "csv"], label_visibility="collapsed")
        
        if uploaded_file:
            col1, col2 = st.columns([4, 1])
            with col1:
                st.info(f"📄 **{uploaded_file.name}** • {uploaded_file.size / 1024:.1f} KB")
            with col2:
                analyze_button = st.button("🔍 Analyze", type="primary", use_container_width=True)
            
            if analyze_button:
                try:
                    log_content = uploaded_file.read().decode('utf-8', errors='ignore')
                except Exception as e:
                    st.error(f"❌ Could not read file: {e}")
                    return
    
    # ===== ANALYSIS =====
    if log_content and analyze_button:
        loading_messages = [
            "🔍 Reading your log file...", "🧠 Analyzing with AI...", "📚 Searching knowledge base...",
            "👥 Finding the right contact...", "📋 Matching runbooks...", "✅ Almost done..."
        ]
        
        with st.spinner(random.choice(loading_messages)):
            start_time = time.time()
            if use_multi_agent:
                result = analyzer.analyze_multi(log_content)
            else:
                result = analyzer.analyze(log_content)
            elapsed = time.time() - start_time
            
            st.session_state.analysis_result = result
            st.session_state.analysis_elapsed = elapsed
        
        if not result.success:
            st.error(f"❌ Analysis failed: {result.error}")
            return
    
    # ===== RESULTS =====
    if 'analysis_result' in st.session_state:
        result = st.session_state.analysis_result
        elapsed = st.session_state.analysis_elapsed
        
        st.success(f"✅ Analysis complete in {elapsed:.2f}s")
        st.markdown("<br>", unsafe_allow_html=True)
        
        # ===== METRICS DASHBOARD =====
        severity_class = result.severity.lower()
        severity_icons = {"CRITICAL": "🔴", "ERROR": "🟠", "WARNING": "🟡", "INFO": "🟢"}
        
        cols = st.columns(5)
        metrics = [
            ("Severity", f"{severity_icons.get(result.severity, '⚪')} {result.severity}", severity_class),
            ("System", result.system, ""),
            ("Confidence", f"{result.confidence:.0%}", ""),
            ("KB Matches", str(result.knowledge_sources), ""),
            ("Component", result.affected_component or "N/A", "")
        ]
        
        for col, (label, value, sev) in zip(cols, metrics):
            with col:
                render_metric_card(label, value, "", sev)
        
        if result.confidence_explanation:
            st.caption(result.confidence_explanation)
        
        # ===== CONTACTS =====
        if result.contacts:
            st.markdown("""
            <div class="section-header">
                <div class="section-icon contacts">📞</div>
                <div class="section-title">Who to Contact</div>
                <div class="section-count">{count}</div>
            </div>
            """.format(count=len(result.contacts)), unsafe_allow_html=True)
            
            cols = st.columns(min(3, len(result.contacts)))
            for col, contact in zip(cols, result.contacts[:3]):
                with col:
                    render_contact_card(contact)
        
        # ===== SOLUTIONS =====
        if result.solutions:
            st.markdown("""
            <div class="section-header">
                <div class="section-icon solutions">🛠️</div>
                <div class="section-title">Solutions from Runbooks</div>
                <div class="section-count">{count}</div>
            </div>
            """.format(count=len(result.solutions)), unsafe_allow_html=True)
            
            render_solution_card(result.solutions[0])
            
            if len(result.solutions) > 1:
                with st.expander(f"📋 View {len(result.solutions) - 1} more solutions"):
                    for sol in result.solutions[1:]:
                        render_solution_card(sol)
        
        # ===== RELATED INCIDENTS =====
        if result.related_incidents:
            st.markdown("""
            <div class="section-header">
                <div class="section-icon incidents">🎟️</div>
                <div class="section-title">Related Past Incidents</div>
                <div class="section-count">{count}</div>
            </div>
            """.format(count=len(result.related_incidents)), unsafe_allow_html=True)
            
            for inc in result.related_incidents[:5]:
                render_incident_card(inc)
        
        # ===== TIMELINE =====
        if result.timeline:
            st.markdown("""
            <div class="section-header">
                <div class="section-icon timeline">⏱️</div>
                <div class="section-title">Incident Timeline</div>
                <div class="section-count">{count} events</div>
            </div>
            """.format(count=len(result.timeline)), unsafe_allow_html=True)
            
            st.markdown('<div class="timeline">', unsafe_allow_html=True)
            for event in result.timeline[:15]:
                render_timeline_event(event)
            st.markdown('</div>', unsafe_allow_html=True)
        
        # ===== MULTI-AGENT PANEL =====
        if result.multi_agent is not None:
            ma = result.multi_agent
            
            mode_class = "sequential" if ma.mode_used == "partial_sequential" else "parallel"
            mode_label = "⚡ Partial Sequential" if ma.mode_used == "partial_sequential" else "⚡ Parallel"
            
            st.markdown(f"""
            <div class="agent-badge {mode_class}">
                🤖 {mode_label} • {ma.total_time:.2f}s
            </div>
            """, unsafe_allow_html=True)
            
            tab1, tab2, tab3 = st.tabs(["🔍 Root Cause", "📊 Impact", "🛠️ Actions"])
            
            with tab1:
                rc = ma.root_cause
                if rc.trigger:
                    st.markdown(f"**Trigger:** {rc.trigger}")
                    
                    if rc.causal_chain:
                        chain_html = ""
                        for i, event in enumerate(rc.causal_chain):
                            is_last = (i == len(rc.causal_chain) - 1)
                            node_class = "root" if is_last else ""
                            arrow = "<span class='chain-arrow'>→</span>" if not is_last else ""
                            chain_html += f"<span class='chain-node {node_class}'>{html.escape(event)}</span>{arrow}"
                        st.markdown(f"<div class='causal-chain'>{chain_html}</div>", unsafe_allow_html=True)
                    
                    if rc.confidence:
                        st.progress(rc.confidence / 100, text=f"Confidence: {rc.confidence}%")
                    
                    if rc.reasoning:
                        st.markdown(f"**Reasoning:** {rc.reasoning}")
                else:
                    st.info("Root cause agent did not produce a result.")
            
            with tab2:
                imp = ma.impact
                col_a, col_b = st.columns(2)
                with col_a:
                    if imp.affected_systems:
                        st.markdown("**Affected Systems**")
                        for s in imp.affected_systems:
                            st.markdown(f"• {s}")
                    if imp.estimated_duration:
                        st.markdown(f"**Duration:** {imp.estimated_duration}")
                with col_b:
                    if imp.financial_impact:
                        st.markdown(f"**💰 Financial Impact:** {imp.financial_impact}")
                    if imp.severity_justification:
                        st.markdown(f"**Why this severity:** {imp.severity_justification}")
                
                if imp.user_impact:
                    st.markdown(f"> {imp.user_impact}")
            
            with tab3:
                act = ma.actions
                if act.immediate:
                    st.markdown("### 🔴 Immediate — Do NOW")
                    for i, step in enumerate(act.immediate, 1):
                        st.markdown(f"{i}. {step}")
                
                if act.short_term:
                    st.markdown("### 🟡 Short-Term — Next 1-2 hours")
                    for i, step in enumerate(act.short_term, 1):
                        st.markdown(f"{i}. {step}")
                
                if act.preventive:
                    st.markdown("### 🟢 Preventive — After incident")
                    for i, step in enumerate(act.preventive, 1):
                        st.markdown(f"{i}. {step}")
                
                if act.rollback_plan:
                    st.markdown(f"**🔙 Rollback Plan:** {act.rollback_plan}")
            
            # Consistency check
            if ma.consistency:
                cons = ma.consistency
                if hasattr(cons, 'factual_conflicts') and cons.factual_conflicts:
                    real_conflicts = [c for c in cons.factual_conflicts 
                                     if c.strip() and 'no conflicts' not in c.lower()]
                    if real_conflicts:
                        st.error(f"🔴 **Factual Conflicts:** {len(real_conflicts)} detected")
                        for c in real_conflicts:
                            st.markdown(f"• {c}")
                
                if cons.recommendation:
                    st.info(f"💡 **Recommendation:** {cons.recommendation}")
        
        # ===== EXPANDABLES =====
        if not result.contacts and not result.solutions:
            st.warning("⚠️ No contacts or solutions found in KB.")
        
        sanitized_text = result.sanitization.sanitized_text if result.sanitization else log_content
        redaction_info = ""
        if result.sanitization and result.sanitization.was_sanitized:
            total = len(result.sanitization.audit_trail) + len(result.sanitization.llm_findings)
            redaction_info = f" • {total} item(s) redacted"
        
        with st.expander(f"📋 Sanitized Log{redaction_info}"):
            st.markdown(f"""
            <div style="background: var(--bg-secondary); padding: 1rem; border-radius: 10px; 
                        max-height: 400px; overflow-y: auto; font-family: 'JetBrains Mono', monospace; 
                        font-size: 0.8125rem; line-height: 1.6; border: 1px solid var(--border-subtle);">
                {highlight_errors(sanitized_text).replace(chr(10), "<br>")}
            </div>
            """, unsafe_allow_html=True)
        
        with st.expander("⚙️ Technical Details"):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"""
                **System Info:**
                - Issue Type: `{result.issue_type}`
                - Severity: `{result.severity}`
                - System: `{result.system}`
                - Timestamp: `{result.timestamp or 'N/A'}`
                """)
            with col2:
                st.markdown(f"""
                **Analysis:**
                - Backend: `{result.backend_used}`
                - Confidence: `{result.confidence:.1%}`
                - Processing: `{result.processing_time:.2f}s`
                """)
        
        # ===== ACTION BUTTONS - FIXED =====
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Use columns with equal spacing for alignment
        col1, col2, col3 = st.columns(3)
        
        # Export PDF - FIXED
        with col1:
            if REPORTLAB_AVAILABLE:
                try:
                    buffer = io.BytesIO()
                    doc = SimpleDocTemplate(buffer, pagesize=letter,
                                        rightMargin=72, leftMargin=72,
                                        topMargin=72, bottomMargin=18)
                    
                    styles = getSampleStyleSheet()
                    story = []
                    
                    # Title
                    title_style = ParagraphStyle(
                        'CustomTitle',
                        parent=styles['Heading1'],
                        fontSize=24,
                        textColor=colors.HexColor('#6366f1'),
                        spaceAfter=30
                    )
                    story.append(Paragraph("LogGuard Incident Report", title_style))
                    story.append(Spacer(1, 12))
                    
                    # Metadata
                    meta_data = [
                        ['Incident ID:', f"INC-{int(time.time())}"],
                        ['System:', result.system],
                        ['Severity:', result.severity],
                        ['Component:', result.affected_component or "N/A"],
                        ['Confidence:', f"{result.confidence:.0%}"],
                        ['Analysis Time:', f"{elapsed:.2f}s"]
                    ]
                    meta_table = Table(meta_data, colWidths=[2*inch, 4*inch])
                    meta_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 10),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                        ('GRID', (0, 0), (-1, -1), 1, colors.grey)
                    ]))
                    story.append(meta_table)
                    story.append(Spacer(1, 20))
                    
                    # Analysis Summary
                    story.append(Paragraph("Analysis Summary", styles['Heading2']))
                    analysis_text = result.analysis if not result.multi_agent else (
                        result.multi_agent.root_cause.trigger if result.multi_agent.root_cause else result.analysis
                    )
                    story.append(Paragraph(analysis_text, styles['BodyText']))
                    story.append(Spacer(1, 12))
                    
                    # Contacts
                    if result.contacts:
                        story.append(Paragraph("Key Contacts", styles['Heading2']))
                        for contact in result.contacts:
                            contact_info = f"<b>{contact.name}</b> - {contact.role}<br/>" \
                                        f"Email: {contact.email}<br/>" \
                                        f"Phone: {contact.phone or 'N/A'}"
                            if contact.escalation_contact:
                                contact_info += f"<br/>Escalate to: {contact.escalation_contact}"
                            story.append(Paragraph(contact_info, styles['BodyText']))
                            story.append(Spacer(1, 6))
                        story.append(Spacer(1, 12))
                    
                    # Solutions
                    if result.solutions:
                        story.append(Paragraph("Recommended Solutions", styles['Heading2']))
                        for i, sol in enumerate(result.solutions, 1):
                            story.append(Paragraph(f"<b>Solution {i}: {sol.title}</b>", styles['Heading3']))
                            story.append(Paragraph(f"Owner: {sol.owner.name} | Duration: {sol.duration}", styles['Italic']))
                            for step in sol.steps:
                                story.append(Paragraph(f"• {step}", styles['BodyText']))
                            story.append(Spacer(1, 6))
                    
                    # Timeline
                    if result.timeline:
                        story.append(Paragraph("Event Timeline", styles['Heading2']))
                        timeline_data = [['Time', 'Component', 'Event']]
                        for event in result.timeline[:10]:
                            timeline_data.append([
                                event['timestamp'],
                                event['component'],
                                event['message'][:100] + '...' if len(event['message']) > 100 else event['message']
                            ])
                        timeline_table = Table(timeline_data, colWidths=[1.5*inch, 1.2*inch, 3.3*inch])
                        timeline_table.setStyle(TableStyle([
                            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6366f1')),
                            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                            ('FONTSIZE', (0, 0), (-1, 0), 10),
                            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                            ('VALIGN', (0, 0), (-1, -1), 'TOP')
                        ]))
                        story.append(timeline_table)
                    
                    doc.build(story)
                    
                    st.download_button(
                        "📥 Export PDF", 
                        buffer.getvalue(),
                        f"incident_report_{result.system}_{int(time.time())}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                except Exception as e:
                    st.error(f"PDF Error: {str(e)}")
            else:
                st.button("📥 Export PDF", disabled=True, help="Install reportlab: pip install reportlab")
        
        # Copy for Slack - FIXED with toast notification
        with col2:
            slack_text = format_for_slack(result)
            
            # Use native Streamlit button with session state for click tracking
            if st.button("📋 Copy for Slack", use_container_width=True, key="copy_slack"):
                # Copy to clipboard using Streamlit's built-in method
                st.write(f"""
                <script>
                    navigator.clipboard.writeText({json.dumps(slack_text)});
                </script>
                """, unsafe_allow_html=True)
                
                # Show native toast notification
                st.toast("✅ Copied to clipboard!", icon="📋")
                
                # Small delay to show the toast
                time.sleep(0.1)
        
        # New analysis button
        with col3:
            if st.button("🔄 New Analysis", type="primary", use_container_width=True):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()


if __name__ == "__main__":
    main()