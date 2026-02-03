#!/usr/bin/env python3
"""
Log Analyzer Pro - IMPROVED VERSION
With better prompts, timeline, examples, and more!
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

# Custom CSS - IMPROVED
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    .main {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    
    .block-container {
        padding: 2rem 3rem;
        max-width: 1400px;
    }
    
    h1 {
        color: white !important;
        font-weight: 800 !important;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
    }
    
    .contact-card {
        background: rgba(255,255,255,0.1);
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 0.5rem;
        border-left: 4px solid #00ff88;
    }
    
    .solution-card {
        background: rgba(255,255,255,0.1);
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 0.5rem;
        border-left: 4px solid #667eea;
    }
    
    .incident-detail {
        background: rgba(0,0,0,0.2);
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 0.5rem;
    }
    
    .timeline-event {
        padding: 0.5rem;
        margin-bottom: 0.3rem;
        background: rgba(0,0,0,0.1);
        border-radius: 4px;
    }
    
    [data-testid="stMetricValue"] {
        font-size: 2rem !important;
        font-weight: 700 !important;
    }
    
    code {
        background-color: rgba(0,0,0,0.8) !important;
        color: #00ff88 !important;
        border-radius: 6px;
        padding: 0.5rem !important;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def load_analyzer(_backend_type: BackendType, enable_layer2: bool):
    """
    Load RAG analyzer with optional Layer 2 sanitization.
    Cache key includes enable_layer2 so toggling the switch creates a new instance.
    """
    return RAGLogAnalyzer(backend=_backend_type, enable_layer2_sanitization=enable_layer2)


def render_contact(contact: Contact):
    """Render a contact card"""
    st.markdown(f"""
    <div class='contact-card'>
        <strong style='color: #00ff88; font-size: 1.1rem;'>{contact.name}</strong><br>
        <span style='opacity: 0.9;'>{contact.role}</span><br>
        <span style='opacity: 0.8;'>📧 {contact.email}</span>
        {f"<br><span style='opacity: 0.8;'>📞 {contact.phone}</span>" if contact.phone else ""}
        {f"<br><span style='color: #ffd700;'>⚡ Escalate to: {contact.escalation_contact}</span>" if contact.escalation_contact else ""}
        {f" <span style='opacity: 0.7;'>({contact.escalation_time})</span>" if contact.escalation_time else ""}
    </div>
    """, unsafe_allow_html=True)


def render_solution(solution: Solution):
    """Render a solution card"""
    steps_html = "<br>".join([f"  {i}. {step}" for i, step in enumerate(solution.steps, 1)])
    
    st.markdown(f"""
    <div class='solution-card'>
        <strong style='color: #667eea; font-size: 1.1rem;'>{solution.title}</strong><br>
        <span style='opacity: 0.8;'>👤 Owner: {solution.owner.name}</span><br>
        <span style='opacity: 0.8;'>⏱️ Duration: {solution.duration}</span><br>
        <br>
        <strong>Quick Steps:</strong><br>
        {steps_html}
    </div>
    """, unsafe_allow_html=True)


def highlight_errors(log_text: str) -> str:
    """
    Highlight log lines with color-coded text (simple version that works):
    - ERROR/CRITICAL/FATAL: Red
    - WARNING/WARN: Orange  
    - INFO: Cyan
    - Others: Gray
    No icons, clean and simple
    """
    lines = log_text.split('\n')
    
    highlighted = []
    for line in lines:
        # Skip completely empty lines
        if not line.strip():
            highlighted.append('')
            continue
            
        # Escape HTML to prevent injection
        safe_line = html.escape(line)
        line_lower = line.lower()
        
        # Red for errors
        if any(word in line_lower for word in ['error', 'critical', 'fail', 'exception', 'fatal', '错误']):
            highlighted.append(f'<span style="color: #ff6b6b; font-weight: 600;">{safe_line}</span>')
        # Orange for warnings
        elif any(word in line_lower for word in ['warning', 'warn', '警告']):
            highlighted.append(f'<span style="color: #ffa500; font-weight: 500;">{safe_line}</span>')
        # Cyan for info
        elif any(word in line_lower for word in ['info', 'debug', 'trace']):
            highlighted.append(f'<span style="color: #61dafb;">{safe_line}</span>')
        # Gray for everything else
        else:
            highlighted.append(f'<span style="color: #aaaaaa;">{safe_line}</span>')
    
    return '\n'.join(highlighted)



def format_for_slack(result: AnalysisResult) -> str:
    """Format analysis for Slack - improved with more context"""
    
    # Multi-agent analysis if available
    analysis_text = ""
    if hasattr(result, 'multi_agent') and result.multi_agent:
        ma = result.multi_agent
        if ma.root_cause and ma.root_cause.trigger:
            analysis_text = f"*Root Cause*: {ma.root_cause.trigger}\n"
        if ma.impact and ma.impact.user_impact:
            analysis_text += f"*Impact*: {ma.impact.user_impact[:200]}...\n"
    else:
        # Fallback to regular analysis
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
    
    # Add escalation info if present
    if result.contacts and result.contacts[0].escalation_contact:
        slack_message += f"• Escalate to: {result.contacts[0].escalation_contact}"
        if result.contacts[0].escalation_time:
            slack_message += f" after {result.contacts[0].escalation_time}"
        slack_message += "\n"
    
    # Add immediate actions
    slack_message += "\n*Immediate Actions*:\n"
    if result.solutions and result.solutions[0].steps:
        for i, step in enumerate(result.solutions[0].steps[:5], 1):
            slack_message += f"{i}. {step}\n"
    else:
        slack_message += "See full runbook in system\n"
    
    return slack_message


def main():
    # Header
    st.markdown("""
        <h1 style='text-align: center; margin-bottom: 0;'>
            🛡️ LogGuard
        </h1>
        <p style='text-align: center; color: white; opacity: 0.9; margin-top: 0.5rem; font-size: 1.1rem;'>
            AI-powered incident analysis with instant knowledge base insights
        </p>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Backend selection - LOCKED TO GROQ for hosted version
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

    # Check if we're in hosted mode (no Ollama available)
    def is_ollama_available():
        """Check if Ollama is running locally"""
        try:
            import requests
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            return response.status_code == 200
        except:
            return False

    ollama_available = is_ollama_available()

    with col1:
        if ollama_available:
            # Local dev - show all options
            backend_choice = st.selectbox(
                "🚀 Analysis Backend",
                ["⚡ Groq API", "☁️ Claude API", "🏠 Local Ollama"],
                help="Choose your analysis backend"
            )
        else:
            # Hosted - locked to Groq, just show info
            st.markdown("""
                <div style='padding: 8px; background: rgba(255,255,255,0.1); border-radius: 8px;'>
                    <strong>🚀 Analysis Backend</strong><br/>
                    <span style='color: #00ff88;'>⚡ Groq API</span>
                </div>
            """, unsafe_allow_html=True)
            backend_choice = "⚡ Groq API"

    # Layer 2 Sanitization toggle - show status even if disabled
    use_layer2_sanitization = False

    with col2:
        if ollama_available:
            use_layer2_sanitization = st.toggle(
                "🔒 Layer 2",
                value=True,
                help="Use local LLM to catch context-based PII after regex redaction."
            )
        else:
            st.markdown("<div style='opacity: 0.5; padding: 8px; text-align: center;'>🔒 Layer 2<br/><small style='color: #ff6b6b;'>Ollama offline</small></div>", unsafe_allow_html=True)

    # Multi-agent is now always ON
    use_multi_agent = True

    # Map choice to backend
    if "Groq" in backend_choice:
        backend = BackendType.GROQ_API
    elif "Claude" in backend_choice:
        backend = BackendType.CLAUDE_API
    else:
        backend = BackendType.OLLAMA_LOCAL
    
    # Load analyzer with layer2 sanitization preference
    try:
        analyzer = load_analyzer(backend, use_layer2_sanitization)
    except Exception as e:
        st.error(f"❌ Failed to initialize backend: {e}")
        st.info("💡 Setup Instructions:")
        st.markdown("""
        1. Create a `.env` file in your project directory
        2. Add your API key:
        """)
        st.code("""# .env file
GROQ_API_KEY=gsk_your_key_here
# or
ANTHROPIC_API_KEY=sk-ant-your_key_here""")
        st.info("🔑 Get free Groq API key: https://console.groq.com/keys")
        return
    
    # Status cards
    with col3:
        kb_count = analyzer.collection.count() if analyzer.collection else 0
        st.metric("Knowledge Base", f"{kb_count} docs", delta="Online" if kb_count > 0 else "Offline")
    
    with col4:
        speed = "<1s" if backend == BackendType.GROQ_API else ("2-3s" if backend == BackendType.CLAUDE_API else "15-30s")
        st.metric("Avg Speed", speed)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # File upload section
    st.markdown("### 📁 Upload Production Log")
    
    # Load example logs from test_logs folder or use hardcoded examples
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
                st.error(f"Could not load {log_file}: {e}")
    
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
    
    # Display example logs section
    example_count = len(example_logs)
    source_info = f" (from test_logs/)" if os.path.exists(test_logs_dir) else ""
    
    # Keep expander open if user is interacting with it
    if 'examples_expanded' not in st.session_state:
        st.session_state.examples_expanded = False
    
    with st.expander(f"💡 Don't have a log? Try an example", 
                     expanded=st.session_state.examples_expanded):
        
        selected_example = st.selectbox("Choose example:", list(example_logs.keys()))
        
        if st.button("📂 Load Example"):
            st.session_state.example_log = example_logs[selected_example]
            st.session_state.example_name = selected_example
            st.session_state.examples_expanded = False  # Collapse after loading
            st.rerun()
        
        # Keep expanded when user interacts
        if selected_example:
            st.session_state.examples_expanded = True
    
    # Handle file upload or example
    log_content = None
    analyze_button = False
    
    if 'example_log' in st.session_state:
        log_content = st.session_state.example_log
        example_name = st.session_state.get('example_name', 'Example')
        st.info(f"📄 Loaded example: **{example_name}**")
        del st.session_state.example_log
        if 'example_name' in st.session_state:
            del st.session_state.example_name
        analyze_button = True  # Auto-analyze examples
    else:
        uploaded_file = st.file_uploader(
            "Upload Production Log",
            type=["log", "txt", "csv"],
            help="Drag & drop your log file here",
            label_visibility="hidden"
        )
        
        if uploaded_file:
            col1, col2 = st.columns([3, 1])
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
    
    # Analysis
    if log_content and analyze_button:
        # NEW: Random loading messages
        loading_messages = [
            "🔍 Reading your log file...",
            "🧠 Analyzing with AI...",
            "📚 Searching knowledge base...",
            "👥 Finding the right contact...",
            "📋 Matching runbooks...",
            "✅ Almost done..."
        ]
        
        with st.spinner(random.choice(loading_messages)):
            start_time = time.time()
            if use_multi_agent:
                result = analyzer.analyze_multi(log_content)
            else:
                result = analyzer.analyze(log_content)
            elapsed = time.time() - start_time
        
        if not result.success:
            st.error(f"❌ Analysis failed: {result.error}")
            return
        
        # Analysis complete
        st.success(f"✅ Analysis complete in {elapsed:.2f}s")
        st.markdown("<br>", unsafe_allow_html=True)
        
        # === DASHBOARD ===
        
        # Metrics - IMPROVED with more info
        col1, col2, col3, col4, col5 = st.columns(5)
        
        severity_emoji = {
            "CRITICAL": "🔴",
            "ERROR": "🟠",
            "WARNING": "🟡",
            "INFO": "🟢"
        }
        
        with col1:
            st.metric("Severity", f"{severity_emoji.get(result.severity, '⚪')} {result.severity}")
        with col2:
            st.metric("System", result.system)
        with col3:
            st.metric("Confidence", f"{result.confidence:.0%}")
        with col4:
            st.metric("KB Matches", f"{result.knowledge_sources}")
        with col5:
            st.metric("Component", result.affected_component or "N/A")
        
        # NEW: Confidence explanation
        if result.confidence_explanation:
            st.caption(result.confidence_explanation)
        
        # NEW: Sanitization audit (compliance transparency)
        if result.sanitization and result.sanitization.was_sanitized:
            san = result.sanitization
            total_count = len(san.audit_trail) + len(san.llm_findings)
            
            with st.expander(f"🔒 Privacy — {total_count} item(s) redacted", expanded=False):
                if san.audit_trail:
                    # Group by pattern type
                    by_type = {}
                    for item in san.audit_trail:
                        by_type.setdefault(item.pattern_type, []).append(item)
                    for ptype, items in sorted(by_type.items()):
                        st.markdown(f"  • {ptype}: {len(items)}")
                
                if san.llm_findings:
                    st.markdown(f"  • contextual identifiers: {len(san.llm_findings)}")
                
                st.caption("Personal data removed before analysis")

        st.markdown("<br>", unsafe_allow_html=True)
        
        # === STRUCTURED DATA DISPLAY ===
        
        # Row 1: Contacts
        if result.contacts:
            st.markdown("### 📞 Who to Contact")
            
            for contact in result.contacts[:3]:
                render_contact(contact)
            
            st.markdown("<br>", unsafe_allow_html=True)
        
        # Row 2: Solutions
        if result.solutions:
            st.markdown("### 🛠️ Solutions from Runbooks")
            
            render_solution(result.solutions[0])
            
            if len(result.solutions) > 1:
                with st.expander(f"📋 View {len(result.solutions) - 1} more solution(s)"):
                    for sol in result.solutions[1:]:
                        render_solution(sol)
            
            st.markdown("<br>", unsafe_allow_html=True)
        
        # Row 3: Related Incidents - RICH DISPLAY with details
        if result.related_incidents:
            st.markdown("### 🎟️ Related Past Incidents")
            
            # Display each incident with full details
            for inc in result.related_incidents[:5]:
                # Severity color
                severity_colors = {
                    'CRITICAL': '#ff5555',
                    'HIGH': '#ffaa00',
                    'MEDIUM': '#ffff55',
                    'LOW': '#00ff88'
                }
                sev_color = severity_colors.get(inc.get('severity', 'MEDIUM'), '#ffff55')
                
                # Clean title - strip HTML tags to prevent rendering issues
                title_raw = inc.get('title', 'No description available')
                title_clean = re.sub(r'<[^>]+>', '', title_raw)  # Strip all HTML tags

                # Build impact HTML parts separately
                impact_parts = []
                if inc.get('financial_impact'):
                    impact_parts.append(f"💰 Revenue: <span style='color: #ff9955;'>{inc.get('financial_impact')}</span>")
                if inc.get('users_affected'):
                    impact_parts.append(f"👥 Users: <span style='color: #aaaaff;'>{inc.get('users_affected')}</span>")
                
                impact_html = "        ".join(impact_parts) if impact_parts else ""
                
                st.markdown(f"""
                <div class='incident-detail'>
                    <div style='display: flex; align-items: center; gap: 1rem; margin-bottom: 0.5rem;'>
                        <strong style='color: {sev_color}; font-size: 1.1rem;'>{inc.get('id', 'Unknown')}</strong>
                        <span style='opacity: 0.6;'>•</span>
                        <span style='opacity: 0.8;'>{inc.get('date', 'Unknown date')}</span>
                        <span style='opacity: 0.6;'>•</span>
                        <span style='color: {sev_color};'>{inc.get('severity', 'MEDIUM')}</span>
                        <span style='opacity: 0.6;'>•</span>
                        <span style='color: #00ff88;'>{inc.get('similarity', 'N/A')} match</span>
                    </div>
                    <div style='font-size: 0.95rem; margin-bottom: 0.3rem;'>
                        {title_clean}
                    </div>
                    <div style='opacity: 0.7; font-size: 0.85rem; display: flex; gap: 1.2rem; margin-bottom: 0.25rem;'>
                        {impact_html}
                    </div>
                    <div style='opacity: 0.7; font-size: 0.85rem;'>
                        → Resolved in {inc.get('resolution_time', 'unknown time')} by {inc.get('owner', 'unknown')}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
        
        # NEW: Timeline view
        if result.timeline:
            st.markdown("### ⏱️ Incident Timeline")
            
            for event in result.timeline[:15]:
                st.markdown(f"""
                <div class='timeline-event'>
                    <span style='opacity: 0.6;'>{event['timestamp']}</span>
                    {event['icon']}
                    <strong>{event['component']}</strong>: {event['message']}
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
        
        # === MULTI-AGENT PANEL (only when multi-agent mode was used) ===
        if result.multi_agent is not None:
            ma = result.multi_agent

            # Mode badge
            mode_color = "#ffd700" if ma.mode_used == "partial_sequential" else "#00ff88"
            mode_label = "⚡ Partial Sequential (CRITICAL)" if ma.mode_used == "partial_sequential" else "⚡ Parallel"
            st.markdown(f"""
            <div style='display:inline-block; background:{mode_color}22; border:1px solid {mode_color}; 
                         color:{mode_color}; padding:0.25rem 0.75rem; border-radius:20px; font-size:0.85rem; margin-bottom:0.5rem;'>
                🤖 {mode_label} &nbsp;|&nbsp; {ma.total_time:.2f}s total
            </div>
            """, unsafe_allow_html=True)

            tab1, tab2, tab3 = st.tabs(["🔍 Root Cause", "📊 Impact", "🛠️ Actions"])

            # --- TAB 1: ROOT CAUSE ---
            with tab1:
                rc = ma.root_cause
                if rc.trigger:
                    st.markdown(f"**Trigger:** {rc.trigger}")
                    st.markdown("")

                    if rc.causal_chain:
                        # Render causal chain as visual flow
                        chain_html = ""
                        for i, event in enumerate(rc.causal_chain):
                            arrow = " <span style='color:#667eea; font-size:1.2rem;'>→</span> " if i < len(rc.causal_chain) - 1 else ""
                            is_last = (i == len(rc.causal_chain) - 1)
                            bg = "rgba(102,126,234,0.15)" if not is_last else "rgba(255,80,80,0.15)"
                            border = "#667eea" if not is_last else "#ff5050"
                            chain_html += f"""<span style='display:inline-block; background:{bg}; border:1px solid {border}; 
                                padding:0.3rem 0.6rem; border-radius:6px; margin:0.15rem; font-size:0.9rem;'>{event}</span>{arrow}"""
                        st.markdown(f"<div style='line-height:2;'>{chain_html}</div>", unsafe_allow_html=True)
                        st.markdown("")

                    if rc.confidence:
                        st.progress(rc.confidence / 100, text=f"Root Cause Confidence: {rc.confidence}%")

                    if rc.reasoning:
                        st.markdown(f"**Reasoning:** {rc.reasoning}")
                else:
                    st.info("Root cause agent did not produce a result.")

            # --- TAB 2: IMPACT ---
            with tab2:
                imp = ma.impact
                col_a, col_b = st.columns(2)
                with col_a:
                    if imp.affected_systems:
                        st.markdown("**Affected Systems**")
                        for s in imp.affected_systems:
                            st.markdown(f"  • {s}")
                    if imp.estimated_duration:
                        st.markdown(f"\n**Duration:** {imp.estimated_duration}")
                with col_b:
                    if imp.financial_impact:
                        # Enhanced financial impact display
                        if imp.financial_impact == "Unknown" or "unknown" in imp.financial_impact.lower():
                            # Try to estimate from user impact
                            estimated_cost = None
                            if imp.user_impact:
                                users_match = re.search(r'(\d+(?:,\d+)?)', imp.user_impact)
                                if users_match:
                                    users = int(users_match.group(1).replace(',', ''))
                                    if users > 10000:
                                        estimated_cost = f"$500k-$1M estimated (based on {users:,} users affected)"
                                    elif users > 1000:
                                        estimated_cost = f"$50k-$500k estimated (based on {users:,} users affected)"
                                    elif users > 100:
                                        estimated_cost = f"$5k-$50k estimated (based on {users:,} users affected)"
                            
                            if estimated_cost:
                                st.markdown(f"**💰 Financial Impact:** {estimated_cost}")
                                st.caption("⚠️ Estimated - actual cost may vary")
                            else:
                                st.markdown(f"**💰 Financial Impact:** {imp.financial_impact}")
                        else:
                            st.markdown(f"**💰 Financial Impact:** {imp.financial_impact}")
                    
                    if imp.severity_justification:
                        st.markdown(f"\n**Why this severity:** {imp.severity_justification}")

                if imp.user_impact:
                    st.markdown("")
                    st.markdown(f"> {imp.user_impact}")

                if not any([imp.affected_systems, imp.user_impact, imp.estimated_duration]):
                    st.info("Impact agent did not produce a result.")

            # --- TAB 3: ACTIONS ---
            with tab3:
                act = ma.actions
                if act.immediate:
                    st.markdown("### 🔴 Immediate — Do NOW")
                    for i, step in enumerate(act.immediate, 1):
                        st.markdown(f"  {i}. {step}")
                    st.markdown("")

                if act.short_term:
                    st.markdown("### 🟡 Short-Term — Next 1-2 hours")
                    for i, step in enumerate(act.short_term, 1):
                        st.markdown(f"  {i}. {step}")
                    st.markdown("")

                if act.preventive:
                    st.markdown("### 🟢 Preventive — After incident")
                    for i, step in enumerate(act.preventive, 1):
                        st.markdown(f"  {i}. {step}")
                    st.markdown("")

                if act.rollback_plan:
                    st.markdown(f"**🔙 Rollback Plan:** {act.rollback_plan}")

                if not any([act.immediate, act.short_term, act.preventive]):
                    st.info("Actions agent did not produce a result.")

            # --- Enhanced Consistency check results (compares 3 analysis agents) ---
            if ma.consistency:
                cons = ma.consistency
                st.markdown("")

                # Display factual conflicts (CRITICAL - needs review)
                if hasattr(cons, 'factual_conflicts') and cons.factual_conflicts:
                    st.error(f"🔴 **Factual Conflicts** — {len(cons.factual_conflicts)} detected")
                    st.warning("**Analysis agents disagree on objective facts - MANUAL REVIEW REQUIRED**")
                    st.caption("These are disagreements between Root Cause, Impact, and Actions agents on factual details from the log (system ID, severity, etc.)")
                    for i, c in enumerate(cons.factual_conflicts, 1):
                        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;{i}. {c}")
                    st.markdown("")

                # Display interpretation conflicts (EXPECTED - multiple perspectives)
                if hasattr(cons, 'interpretation_conflicts') and cons.interpretation_conflicts:
                    st.info(f"⚠️ **Interpretation Variance** — {len(cons.interpretation_conflicts)} perspective(s)")
                    st.caption("Different perspectives among Root Cause, Impact, and Actions agents (healthy disagreement)")
                    with st.expander("View different interpretations"):
                        for i, c in enumerate(cons.interpretation_conflicts, 1):
                            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;{i}. {c}")
                    st.markdown("")
                
                # Backward compatibility for old multi_agent
                elif hasattr(cons, 'contradictions') and cons.contradictions:
                    st.warning(f"⚠️ **Agent Disagreement** — {len(cons.contradictions)} contradiction(s) detected")
                    for i, c in enumerate(cons.contradictions, 1):
                        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;{i}. {c}")
                    st.markdown("")

                # Display quality assessment (new in enhanced)
                if hasattr(cons, 'quality_assessment') and cons.quality_assessment:
                    quality_icons = {'HIGH': '🟢', 'MEDIUM': '🟡', 'LOW': '🔴'}
                    quality_level = cons.quality_assessment.split()[0] if cons.quality_assessment else 'UNKNOWN'
                    quality_icon = quality_icons.get(quality_level, '⚪')
                    st.markdown(f"**Quality:** {quality_icon} {cons.quality_assessment}")
                    st.markdown("")

                if cons.recommendation:
                    st.info(f"💡 **Recommendation:** {cons.recommendation}")

                if cons.agreements:
                    with st.expander("✅ Agent Agreements", expanded=False):
                        for a in cons.agreements:
                            st.markdown(f"  • {a}")

                if cons.confidence:
                    st.progress(
                        cons.confidence / 100,
                        text=f"Overall coherence: {cons.confidence}%"
                    )


            st.markdown("<br>", unsafe_allow_html=True)

        # NOTE: AI Analysis section removed - redundant with multi-agent output above
        
        # === EXPANDABLE SECTIONS ===
        
        # No contacts/solutions warning
        if not result.contacts and not result.solutions:
            st.warning("⚠️ No contacts or solutions found in KB. The incident may not match known patterns.")
            st.info("💡 Tip: Ensure knowledge base is properly embedded with contacts.md and runbooks.md")
        
        # Sanitized log preview with highlighting
        sanitized_text = result.sanitization.sanitized_text if result.sanitization else log_content
        redaction_info = ""
        if result.sanitization and result.sanitization.was_sanitized:
            redaction_count = len(result.sanitization.audit_trail)
            llm_count = len(result.sanitization.llm_findings)
            total_redacted = redaction_count + llm_count
            redaction_info = f" • {total_redacted} item(s) redacted"
        
        with st.expander(f"📋 Sanitized Log (sent to AI){redaction_info}", expanded=False):
            st.markdown(f"""
            <div style='background: rgba(0,0,0,0.8); padding: 1rem; border-radius: 8px; 
                        max-height: 500px; overflow-y: auto; font-family: monospace; 
                        font-size: 0.85rem; line-height: 1.4;'>
                {highlight_errors(sanitized_text).replace(chr(10), "<br>")}
            </div>
            """, unsafe_allow_html=True)
            
            # Show what was redacted
            if result.sanitization and result.sanitization.was_sanitized:
                st.caption("🔒 Privacy: PII was redacted before sending to AI")
                if result.sanitization.audit_trail:
                    redacted_types = {}
                    for audit in result.sanitization.audit_trail:
                        redacted_types[audit.pattern_type] = redacted_types.get(audit.pattern_type, 0) + 1
                    type_summary = ", ".join([f"{count} {ptype}" for ptype, count in redacted_types.items()])
                    st.caption(f"Redacted: {type_summary}")

        
        # Technical details
        with st.expander("⚙️ Technical Details", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"""
                **System Information:**
                - Issue Type: `{result.issue_type}`
                - Severity: `{result.severity}`
                - System: `{result.system}`
                - Timestamp: `{result.timestamp or 'N/A'}`
                - Component: `{result.affected_component or 'N/A'}`
                - Contacts Found: `{len(result.contacts)}`
                - Solutions Found: `{len(result.solutions)}`
                """)
            with col2:
                st.markdown(f"""
                **Analysis Metadata:**
                - Backend: `{result.backend_used}`
                - KB Sources: `{result.knowledge_sources}`
                - Confidence: `{result.confidence:.1%}`
                - Processing Time: `{result.processing_time:.2f}s`
                - Timeline Events: `{len(result.timeline)}`
                """)
        
        # Export section
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Create unified button HTML for all 3 buttons
        def create_action_button(button_id: str, label: str, action_type: str):
            """Creates a unified HTML button style for all actions"""
            slack_text_json = ""
            if action_type == "slack":
                slack_text_json = json.dumps(format_for_slack(result))
            
            button_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    * {{
                        margin: 0;
                        padding: 0;
                        box-sizing: border-box;
                    }}
                    
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                        background: transparent;
                        position: relative;
                    }}
                    
                    .action-button {{
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        border: none;
                        border-radius: 8px;
                        color: white;
                        cursor: pointer;
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                        font-size: 14px;
                        font-weight: 600;
                        padding: 12px 24px;
                        text-align: center;
                        width: 100%;
                        height: 44px;
                        transition: all 0.2s ease;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        gap: 8px;
                        box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
                    }}
                    
                    .action-button:hover {{
                        transform: translateY(-2px);
                        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
                    }}
                    
                    .action-button:active {{
                        transform: translateY(0);
                    }}
                    
                    .toast {{
                        position: absolute;
                        top: 50%;
                        left: 50%;
                        transform: translate(-50%, -50%);
                        background: white;
                        color: #1f2937;
                        padding: 12px 20px;
                        border-radius: 8px;
                        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15);
                        z-index: 10000;
                        font-size: 14px;
                        font-weight: 500;
                        display: flex;
                        align-items: center;
                        gap: 12px;
                        animation: fadeIn 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                        white-space: nowrap;
                    }}
                    
                    .toast.success {{
                        border-left: 4px solid #10b981;
                    }}
                    
                    .toast.error {{
                        border-left: 4px solid #ef4444;
                    }}
                    
                    .toast.hide {{
                        animation: fadeOut 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                    }}
                    
                    @keyframes fadeIn {{
                        from {{
                            opacity: 0;
                            transform: translate(-50%, -50%) scale(0.9);
                        }}
                        to {{
                            opacity: 1;
                            transform: translate(-50%, -50%) scale(1);
                        }}
                    }}
                    
                    @keyframes fadeOut {{
                        from {{
                            opacity: 1;
                            transform: translate(-50%, -50%) scale(1);
                        }}
                        to {{
                            opacity: 0;
                            transform: translate(-50%, -50%) scale(0.9);
                        }}
                    }}
                </style>
            </head>
            <body>
                <button class="action-button" onclick="handleClick()" id="{button_id}">
                    {label}
                </button>
                
                <script>
                function showToast(message, type = 'success') {{
                    const toast = document.createElement('div');
                    toast.className = `toast ${{type}}`;
                    const icon = type === 'success' ? '✅' : '❌';
                    toast.innerHTML = `<span>${{icon}}</span><span>${{message}}</span>`;
                    document.body.appendChild(toast);
                    
                    setTimeout(() => {{
                        toast.classList.add('hide');
                        setTimeout(() => document.body.removeChild(toast), 300);
                    }}, 2500);
                }}
                
                function handleClick() {{
                    const actionType = '{action_type}';
                    
                    if (actionType === 'slack') {{
                        const text = {slack_text_json};
                        navigator.clipboard.writeText(text).then(
                            () => showToast('Copied to clipboard!', 'success'),
                            () => showToast('Failed to copy', 'error')
                        );
                    }} else if (actionType === 'new') {{
                        window.parent.postMessage({{type: 'streamlit:setComponentValue', value: 'new_analysis'}}, '*');
                    }}
                }}
                </script>
            </body>
            </html>
            """
            return button_html
        
        col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
        
        # Export as PDF
        with col2:
            if REPORTLAB_AVAILABLE:
                try:
                    # Generate PDF
                    buffer = io.BytesIO()
                    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
                    story = []
                    styles = getSampleStyleSheet()
                    
                    # Custom styles
                    title_style = ParagraphStyle(
                        'CustomTitle',
                        parent=styles['Heading1'],
                        fontSize=24,
                        textColor=colors.HexColor('#667eea'),
                        spaceAfter=12,
                        alignment=TA_CENTER
                    )
                    
                    heading_style = ParagraphStyle(
                        'CustomHeading',
                        parent=styles['Heading2'],
                        fontSize=16,
                        textColor=colors.HexColor('#764ba2'),
                        spaceAfter=10,
                        spaceBefore=15
                    )
                    
                    # Title
                    story.append(Paragraph("🔥 Incident Analysis Report", title_style))
                    story.append(Spacer(1, 0.3*inch))
                    
                    # Summary table
                    summary_data = [
                        ['System:', result.system],
                        ['Severity:', result.severity],
                        ['Issue Type:', result.issue_type],
                        ['Confidence:', f'{result.confidence:.0%}'],
                        ['Timestamp:', result.timestamp or 'Unknown'],
                        ['Component:', result.affected_component or 'N/A']
                    ]
                    
                    summary_table = Table(summary_data, colWidths=[2*inch, 4*inch])
                    summary_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f4f6')),
                        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 11),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                        ('TOPPADDING', (0, 0), (-1, -1), 8),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
                    ]))
                    story.append(summary_table)
                    story.append(Spacer(1, 0.3*inch))
                    
                    # Contacts
                    if result.contacts:
                        story.append(Paragraph("📞 Who to Contact", heading_style))
                        for contact in result.contacts[:3]:
                            contact_text = f"<b>{contact.name}</b> - {contact.role}<br/>"
                            contact_text += f"Email: {contact.email}<br/>"
                            if contact.phone:
                                contact_text += f"Phone: {contact.phone}<br/>"
                            if contact.escalation_contact:
                                contact_text += f"<font color='#d97706'>Escalate to: {contact.escalation_contact}"
                                if contact.escalation_time:
                                    contact_text += f" (after {contact.escalation_time})"
                                contact_text += "</font>"
                            story.append(Paragraph(contact_text, styles['Normal']))
                            story.append(Spacer(1, 0.15*inch))
                    
                    # Solutions
                    if result.solutions:
                        story.append(Paragraph("🛠️ Solutions from Runbooks", heading_style))
                        for sol in result.solutions:
                            story.append(Paragraph(f"<b>{sol.title}</b>", styles['Normal']))
                            story.append(Paragraph(f"Owner: {sol.owner.name} ({sol.owner.email})", styles['Normal']))
                            story.append(Paragraph(f"Duration: {sol.duration}", styles['Normal']))
                            story.append(Spacer(1, 0.1*inch))
                            
                            story.append(Paragraph("<b>Steps:</b>", styles['Normal']))
                            for i, step in enumerate(sol.steps, 1):
                                story.append(Paragraph(f"{i}. {step}", styles['Normal']))
                            story.append(Spacer(1, 0.15*inch))
                    
                    # Analysis
                    story.append(Paragraph("🧠 AI Analysis", heading_style))
                    story.append(Paragraph(result.analysis, styles['Normal']))
                    
                    doc.build(story)
                    pdf_data = buffer.getvalue()
                    buffer.close()
                    
                    st.download_button(
                        label="📥 Export PDF Report",
                        data=pdf_data,
                        file_name=f"incident_analysis_{int(time.time())}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                    
                except Exception as e:
                    st.error(f"Failed to generate PDF: {e}")
            else:
                # Fallback to markdown if reportlab not available
                export_content = f"""# Incident Analysis Report

## Summary
- **System**: {result.system}
- **Severity**: {result.severity}
- **Issue Type**: {result.issue_type}
- **Confidence**: {result.confidence:.0%}
- **Timestamp**: {result.timestamp or 'Unknown'}

## Contacts
"""
                if result.contacts:
                    for c in result.contacts:
                        export_content += f"\n### {c.name}\n"
                        export_content += f"- **Role**: {c.role}\n"
                        export_content += f"- **Email**: {c.email}\n"
                        if c.phone:
                            export_content += f"- **Phone**: {c.phone}\n"
                        if c.escalation_contact:
                            export_content += f"- **Escalate to**: {c.escalation_contact}"
                            if c.escalation_time:
                                export_content += f" (after {c.escalation_time})"
                            export_content += "\n"
                else:
                    export_content += "No contacts identified\n"
                
                export_content += "\n## Solutions\n"
                if result.solutions:
                    for sol in result.solutions:
                        export_content += f"\n### {sol.title}\n"
                        export_content += f"- **Owner**: {sol.owner.name} ({sol.owner.email})\n"
                        export_content += f"- **Duration**: {sol.duration}\n"
                        export_content += "\n**Steps**:\n"
                        for i, step in enumerate(sol.steps, 1):
                            export_content += f"{i}. {step}\n"
                else:
                    export_content += "No solutions identified\n"
                
                export_content += f"\n## AI Analysis\n{result.analysis}\n"
                
                st.download_button(
                    label="📥 Export Report (MD)",
                    data=export_content,
                    file_name=f"analysis_{int(time.time())}.md",
                    mime="text/markdown",
                    use_container_width=True
                )
        
        # Copy for Slack
        with col3:
            slack_text = format_for_slack(result)
            st.components.v1.html(
                create_action_button("slack_btn", "📋 Copy for Slack", "slack"),
                height=44
            )
        
        # New analysis button
        with col4:
            st.components.v1.html(
                create_action_button("new_btn", "🔄 New Analysis", "new"),
                height=44
            )
            
            # Handle new analysis trigger
            if st.session_state.get('new_analysis_clicked'):
                del st.session_state.new_analysis_clicked
                st.rerun()


if __name__ == "__main__":
    main()