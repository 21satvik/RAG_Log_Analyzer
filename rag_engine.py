import os
import json
import requests
import time
import logging
import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from dotenv import load_dotenv

import chromadb

from multi_agent import run_multi_agent_v2 as run_multi_agent, MultiAgentResult as _MultiAgentResult
from sanitizer import SanitizationPipeline, create_ollama_sanitizer_callable

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BackendType(Enum):
    GROQ_API = "groq"
    CLAUDE_API = "claude"
    OLLAMA_LOCAL = "ollama"


@dataclass
class Contact:
    """Structured contact information"""
    name: str
    role: str
    email: str
    phone: Optional[str] = None
    team: Optional[str] = None
    escalation_contact: Optional[str] = None
    escalation_time: Optional[str] = None


@dataclass
class Solution:
    """Structured solution from runbooks"""
    title: str
    steps: List[str]
    owner: Contact
    duration: str
    prerequisites: List[str]
    source: str


@dataclass
class AnalysisResult:
    success: bool
    severity: str
    system: str
    issue_type: str
    analysis: str
    confidence: float
    
    # Structured data
    contacts: List[Contact] = field(default_factory=list)
    solutions: List[Solution] = field(default_factory=list)
    related_incidents: List[Dict[str, str]] = field(default_factory=list)  # Changed from List[str] to List[Dict]
    
    # Additional extracted data
    timestamp: Optional[str] = None
    error_code: Optional[str] = None
    affected_component: Optional[str] = None
    timeline: List[Dict] = field(default_factory=list)
    confidence_explanation: str = ""
    
    # NEW: Detection metadata
    system_confidence: float = 0.0
    detection_explanation: str = ""
    
    # NEW: Multi-agent outputs (None when single-agent mode)
    multi_agent: Optional[Any] = None
    
    # NEW: Sanitization audit trail (None when skipped — e.g. Ollama backend)
    sanitization: Optional[Any] = None
    
    # Metadata
    knowledge_sources: int = 0
    processing_time: float = 0.0
    backend_used: str = ""
    error: Optional[str] = None


class DirectContactMapping:
    """Direct system→contact mapping for 100% accuracy"""
    
    SYSTEM_CONTACTS = {
        'Server_A': {
            'primary': Contact(
                name='Sarah Chen',
                role='Senior Database Engineer',
                email='sarah.chen@company.com',
                phone='ext. 5432',
                team='Database Team',
                escalation_contact='Emma Walsh',
                escalation_time='15 minutes'
            ),
            'backup': Contact(
                name='Michael O\'Brien',
                role='Database Engineer',
                email='michael.obrien@company.com',
                phone='ext. 5433',
                team='Database Team'
            )
        },
        'Server_B': {
            'primary': Contact(
                name='Mike Rodriguez',
                role='Senior Platform Engineer',
                email='mike.r@company.com',
                phone='ext. 5401',
                team='Platform Team',
                escalation_contact='Alex Kim',
                escalation_time='15 minutes'
            ),
            'backup': Contact(
                name='Priya Patel',
                role='Platform Engineer',
                email='priya.patel@company.com',
                phone='ext. 5402',
                team='Platform Team'
            )
        },
        'Server_C': {
            'primary': Contact(
                name='Lisa Park',
                role='Senior Performance Engineer',
                email='lisa.park@company.com',
                phone='ext. 5289',
                team='Performance Team',
                escalation_contact='Dr. Richard Lee',
                escalation_time='20 minutes'
            )
        },
        'Memory': {
            'primary': Contact(
                name='Lisa Park',
                role='Senior Performance Engineer',
                email='lisa.park@company.com',
                phone='ext. 5289',
                team='Performance Team'
            )
        },
        'Disk': {
            'primary': Contact(
                name='Tom Bradley',
                role='Senior DevOps Engineer',
                email='tom.bradley@company.com',
                phone='ext. 5500',
                team='Infrastructure Team'
            )
        },
        'Payment': {
            'primary': Contact(
                name='Mike Rodriguez',
                role='Senior Platform Engineer',
                email='mike.r@company.com',
                phone='ext. 5401',
                team='Platform Team'
            )
        },
        'Network': {
            'primary': Contact(
                name='Carlos Mendez',
                role='Network Infrastructure Engineer',
                email='carlos.mendez@company.com',
                phone='ext. 5520',
                team='Infrastructure Team'
            )
        },
        'Security': {
            'primary': Contact(
                name='Dr. James Wilson',
                role='Chief Security Officer',
                email='james.wilson@company.com',
                phone='ext. 5100',
                team='Security Team',
                escalation_contact='CEO',
                escalation_time='30 minutes'
            ),
            'backup': Contact(
                name='Rachel Thompson',
                role='Security Operations Manager',
                email='rachel.thompson@company.com',
                phone='ext. 5310',
                team='Security Team'
            )
        }
    }
    
    @classmethod
    def get_contacts(cls, system: str) -> List[Contact]:
        """Get contacts for a system"""
        system_data = cls.SYSTEM_CONTACTS.get(system, {})
        contacts = []
        
        if 'primary' in system_data:
            contacts.append(system_data['primary'])
        if 'backup' in system_data:
            contacts.append(system_data['backup'])
        
        return contacts


class DirectSolutionMapping:
    """Direct issue→solution mapping for 100% accuracy"""
    
    ISSUE_SOLUTIONS = {
        'memory_leak': Solution(
            title='Memory Leak Investigation',
            steps=[
                'Confirm Memory Spike (5 minutes)',
                'Generate Heap Dump (10 minutes)',
                'Analyze Heap Dump (15-30 minutes)',
                'Identify Leak Source (30-60 minutes)',
                'Confirm/Deny Leak (5 minutes)'
            ],
            owner=Contact('Lisa Park', 'Performance Team', 'lisa.park@company.com', 'ext. 5289'),
            duration='60-120 minutes',
            prerequisites=['SSH access', 'jps/jmap utilities', 'Grafana access'],
            source='Memory Leak Investigation Runbook'
        ),
        'connection_pool': Solution(
            title='Database Connection Pool Recovery',
            steps=[
                'Diagnose Pool Status (2 minutes)',
                'Identify Long-Running Queries (5 minutes)',
                'Terminate Stale Connections (5 minutes)',
                'Kill Long-Running Report Queries (if stuck)',
                'Monitor Recovery (5 minutes)'
            ],
            owner=Contact('Sarah Chen', 'Database Team', 'sarah.chen@company.com', 'ext. 5432'),
            duration='15-20 minutes',
            prerequisites=['SSH access to Server_A', 'PostgreSQL client', 'Database admin credentials'],
            source='Database Connection Pool Recovery Runbook'
        ),
        'disk_space': Solution(
            title='Disk Space Emergency Response',
            steps=[
                'Assess Disk Usage (2 minutes)',
                'Identify Large Files/Directories (5 minutes)',
                'Emergency Cleanup (10 minutes)',
                'Archive and Compress Logs (15 minutes)',
                'Monitor Space Recovery (5 minutes)'
            ],
            owner=Contact('Tom Bradley', 'Infrastructure', 'tom.bradley@company.com', 'ext. 5500'),
            duration='30-40 minutes',
            prerequisites=['SSH access', 'Root/sudo privileges', 'du/df/find utilities'],
            source='Disk Space Emergency Response Runbook'
        ),
        'timeout': Solution(
            title='Payment Service Restart',
            steps=[
                'Check Payment Service Status (2 minutes)',
                'Graceful Restart (5 minutes)',
                'Verify Connectivity (3 minutes)',
                'Monitor for Issues (10 minutes)',
                'Process Backlogged Transactions (5 minutes)'
            ],
            owner=Contact('Mike Rodriguez', 'Platform Team', 'mike.r@company.com', 'ext. 5401'),
            duration='20-25 minutes',
            prerequisites=['SSH access to Server_B', 'Payment service credentials'],
            source='Payment Service Restart Runbook'
        ),
        'replication_lag': Solution(
            title='Database Replication Recovery',
            steps=[
                'Check Replication Status (3 minutes)',
                'Diagnose Lag Cause (5 minutes)',
                'Pause/Resume Replication (if needed)',
                'Rebuild Replica (if broken)'
            ],
            owner=Contact('Sarah Chen', 'Database Team', 'sarah.chen@company.com', 'ext. 5432'),
            duration='10-60 minutes',
            prerequisites=['SSH access to primary and replica', 'PostgreSQL admin credentials'],
            source='Database Replication Recovery Runbook'
        ),
        'security': Solution(
            title='Security Incident Response',
            steps=[
                'Activate Incident Response (Immediate)',
                'Isolate Affected Systems (5 minutes)',
                'Collect Forensic Evidence (30 minutes)',
                'Notify Stakeholders (10 minutes)',
                'Contain & Remediate (1-24 hours)'
            ],
            owner=Contact('Dr. James Wilson', 'Security Team', 'james.wilson@company.com', 'ext. 5100'),
            duration='Variable (1-48 hours)',
            prerequisites=['Incident response team on call', 'SIEM access', 'Legal contact info'],
            source='Security Incident Response Runbook'
        )
    }
    
    @classmethod
    def get_solution(cls, issue_type: str) -> Optional[Solution]:
        """Get solution for an issue type"""
        return cls.ISSUE_SOLUTIONS.get(issue_type)


class ImprovedMatcher:
    """
    IMPROVED: Better matching logic with confidence scoring
    Fixes the "Sarah Chen shows up everywhere" problem
    """
    
    # Severity indicators
    CRITICAL_PATTERNS = [
        r'critical|fatal|emergency|panic|down',
        r'out of memory|oom|disk full',
        r'connection refused|cannot connect',
        r'replication failed|failover'
    ]
    
    ERROR_PATTERNS = [
        r'error|exception|failed|failure',
        r'timeout|timed out',
        r'refused|denied|rejected'
    ]
    
    # IMPROVED: Separate by specificity
    EXACT_SERVER_PATTERNS = {
        'Server_A': [r'\bserver[_\s-]?a\b', r'prod-db-01'],
        'Server_B': [r'\bserver[_\s-]?b\b', r'prod-api-01'],
        'Server_C': [r'\bserver[_\s-]?c\b', r'prod-redis-01'],
    }
    
    # IMPROVED: Only match if DOMINANT theme
    COMPONENT_PATTERNS = {
        'database': {
            'keywords': ['database', 'postgres', 'mysql', 'sql', 'table', 'query', 'connection pool'],
            'strong_indicators': ['pgpool', 'replication', 'pg_stat'],
            'min_mentions': 2,
            'system': 'Server_A'
        },
        'api': {
            'keywords': ['api', 'endpoint', 'gateway', 'kong', 'nginx'],
            'strong_indicators': ['rate limit', 'http', 'rest'],
            'min_mentions': 2,
            'system': 'Server_B'
        },
        'cache': {
            'keywords': ['redis', 'cache', 'memcached'],
            'strong_indicators': ['cluster', 'eviction', 'ttl'],
            'min_mentions': 1,  # Redis is specific enough
            'system': 'Server_C'
        },
        'payment': {
            'keywords': ['payment', 'stripe', 'transaction'],
            'strong_indicators': ['checkout', 'card', 'invoice'],
            'min_mentions': 2,
            'system': 'Payment'
        },
        'memory': {
            'keywords': ['memory', 'heap', 'gc', 'oom'],
            'strong_indicators': ['garbage collect', 'leak', 'allocation'],
            'min_mentions': 2,
            'system': 'Memory'
        },
        'disk': {
            'keywords': ['disk', 'storage', 'filesystem'],
            'strong_indicators': ['full', 'space', 'inode'],
            'min_mentions': 2,
            'system': 'Disk'
        },
        'network': {
            'keywords': ['network', 'latency', 'packet', 'dns'],
            'strong_indicators': ['tcp', 'socket', 'traceroute'],
            'min_mentions': 2,
            'system': 'Network'
        },
        'security': {
            'keywords': ['security', 'vulnerability', 'cve', 'breach'],
            'strong_indicators': ['exploit', 'attack', 'malware'],
            'min_mentions': 1,
            'system': 'Security'
        }
    }
    
    # Issue type patterns
    ISSUE_PATTERNS = {
        'memory_leak': [r'memory leak|heap.*grow|oom'],
        'connection_pool': [r'connection pool|too many connections|max connections'],
        'disk_space': [r'disk full|no space|disk usage'],
        'timeout': [r'timeout|timed out'],
        'replication_lag': [r'replication lag|replica.*behind'],
        'payment_failure': [r'payment.*fail|stripe.*error'],
        'security': [r'security|vulnerability|cve|breach']
    }
    
    @classmethod
    def extract_severity(cls, log_text: str) -> str:
        """Extract severity from log"""
        text_lower = log_text.lower()
        
        for pattern in cls.CRITICAL_PATTERNS:
            if re.search(pattern, text_lower):
                return "CRITICAL"
        
        for pattern in cls.ERROR_PATTERNS:
            if re.search(pattern, text_lower):
                return "ERROR"
        
        if re.search(r'warn|warning', text_lower):
            return "WARNING"
        
        return "INFO"
    
    @classmethod
    def extract_system_with_confidence(cls, log_text: str) -> Tuple[str, float, str]:
        """
        Extract system with confidence score and explanation.

        Strategy: exact server-name mentions and component keyword counts are
        scored together, then the winner is chosen by total evidence weight.
        This prevents a single incidental server-name mention (e.g. prod-redis-01
        in a startup health-check) from overriding dozens of keyword hits for the
        actual failing component.

        Returns:
            (system_name, confidence_score, explanation)
        """

        text_lower = log_text.lower()

        # ── STEP 1: Score every component by keyword volume ──
        component_scores = {}      # component → total score
        component_details = {}     # component → list of evidence strings
        component_systems = {}     # component → target system name

        for component, config in cls.COMPONENT_PATTERNS.items():
            score = 0
            mentions = 0
            found_keywords = []

            for keyword in config['keywords']:
                count = len(re.findall(r'\b' + re.escape(keyword) + r'\b', text_lower))
                if count > 0:
                    mentions += count
                    score += count
                    found_keywords.append(f"{keyword}({count}x)")

            for indicator in config['strong_indicators']:
                if indicator in text_lower:
                    score += 5
                    mentions += 1
                    found_keywords.append(f"STRONG:'{indicator}'")

            if mentions >= config['min_mentions']:
                component_scores[component] = score
                component_details[component] = found_keywords[:4]
                component_systems[component] = config['system']

        # ── STEP 2: Boost the component that owns each exact server name ──
        # An explicit "Server_B" or "prod-db-01" adds a large but not
        # unconditional bonus to the owning component.  If that component
        # already has keyword evidence it will likely win; if it has none
        # (i.e. the mention was incidental) it still has to compete.
        EXACT_SERVER_BONUS = 15   # worth ~15 keyword mentions
        server_match_info = {}    # server → matched pattern string

        # Map each exact-server pattern back to the component it belongs to
        SERVER_TO_COMPONENT = {
            'Server_A': 'database',
            'Server_B': 'api',
            'Server_C': 'cache',
        }

        for server, patterns in cls.EXACT_SERVER_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    comp = SERVER_TO_COMPONENT.get(server)
                    if comp:
                        # Ensure the component entry exists even with 0 prior keywords
                        if comp not in component_scores:
                            component_scores[comp] = 0
                            component_details[comp] = []
                            component_systems[comp] = cls.COMPONENT_PATTERNS[comp]['system']
                        component_scores[comp] += EXACT_SERVER_BONUS
                        component_details[comp].append(f"exact:'{server}'")
                        server_match_info[server] = pattern
                    break  # one match per server is enough

        # ── STEP 3: Also check for explicit service names in log lines ──
        # e.g. "P1 incident triggered: user-database connection pool exhausted"
        # These are stronger than hostname patterns because they appear in
        # application-level alert text.
        SERVICE_NAME_MAP = {
            r'user-database': ('database', 'Server_A', 20),
            r'analytics-db':  ('database', 'Server_A', 15),
            r'api-gateway':   ('api',      'Server_B', 20),
            r'auth-service':  ('security', 'Security', 20),
            r'payment-processor': ('payment', 'Payment', 20),
            r'cache-cluster': ('cache',    'Server_C', 20),
        }
        for svc_pattern, (comp, sys_name, bonus) in SERVICE_NAME_MAP.items():
            if re.search(svc_pattern, text_lower):
                if comp not in component_scores:
                    component_scores[comp] = 0
                    component_details[comp] = []
                    component_systems[comp] = sys_name
                component_scores[comp] += bonus
                component_details[comp].append(f"service:'{svc_pattern}'")

        # ── STEP 4: Pick the winner ──
        if not component_scores:
            return "Unknown", 0.30, "No clear system indicators found"

        best_component = max(component_scores, key=component_scores.get)
        best_score = component_scores[best_component]
        total_score = sum(component_scores.values())

        # Confidence tiers based on how dominant the winner is
        dominance = best_score / total_score if total_score > 0 else 0

        # Did the winner have an exact server or service name match?
        has_explicit = (
            any(f"exact:" in d for d in component_details.get(best_component, [])) or
            any(f"service:" in d for d in component_details.get(best_component, []))
        )

        if has_explicit and dominance > 0.5:
            confidence = 0.95
        elif dominance > 0.7:
            confidence = 0.85
        elif dominance > 0.5:
            confidence = 0.70
        else:
            confidence = 0.55

        system = component_systems[best_component]
        evidence = ', '.join(component_details[best_component][:4])
        explanation = f"{best_component} (dominance {dominance:.0%}): {evidence}"

        return system, confidence, explanation
    
    @classmethod
    def extract_issue_type(cls, log_text: str) -> str:
        """Extract issue type"""
        text_lower = log_text.lower()
        
        for issue_type, patterns in cls.ISSUE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return issue_type
        
        return "general_error"
    
    @classmethod
    def extract_timestamp(cls, log_text: str) -> Optional[str]:
        """Find when incident started — prefer the first ERROR/CRITICAL timestamp,
        fall back to the very first timestamp in the log."""
        patterns = [
            r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})',        # bare:      2026-02-01 14:31:05
            r'\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\]',    # bracketed: [2026-02-01 14:31:05]
            r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})',           # ISO:       2026-02-01T14:31:05
        ]

        # First pass: find timestamp on the first ERROR/CRITICAL line
        for line in log_text.split('\n'):
            if re.search(r'ERROR|CRITICAL|FATAL', line):
                for pattern in patterns:
                    match = re.search(pattern, line)
                    if match:
                        return match.group(1)

        # Second pass: fall back to very first timestamp in the log
        for pattern in patterns:
            match = re.search(pattern, log_text)
            if match:
                return match.group(1)

        return None
    
    @classmethod
    def extract_error_code(cls, log_text: str) -> Optional[str]:
        """Find error codes"""
        patterns = [
            r'Error Code:\s*(\d+)',
            r'HTTP\s+(\d{3})',
            r'errno:\s*(\d+)',
            r'exit code\s*(\d+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, log_text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None
    
    @classmethod
    def extract_affected_component(cls, log_text: str) -> Optional[str]:
        """What component broke?"""
        text_lower = log_text.lower()
        
        for component, config in cls.COMPONENT_PATTERNS.items():
            for keyword in config['keywords']:
                if keyword in text_lower:
                    return component
        return None
    
    @classmethod
    def extract_timeline(cls, log_text: str) -> List[Dict]:
        """Extract events in chronological order.

        Handles two common log formats:
            [2026-02-01 14:31:10] CRITICAL [component] message   (bracketed timestamp)
            2026-02-01 14:31:10 CRITICAL [component] message     (bare timestamp)
        """
        events = []

        # Two timestamp patterns: with and without surrounding brackets
        TS_PATTERNS = [
            r'\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\]',   # [2026-02-01 14:31:10]
            r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})',        # 2026-02-01 14:31:10
        ]

        # Two message patterns matching each timestamp style
        # Bracketed:  ...] LEVEL [component] message
        # Bare:       ...TIMESTAMP LEVEL [component] message
        MSG_PATTERNS = [
            r'\]\s+(\w+)\s+\[([^\]]+)\]\s+(.*)',      # after a ]
            r'\d{2}:\d{2}:\d{2}\s+(\w+)\s+\[([^\]]+)\]\s+(.*)',  # after bare timestamp
        ]

        for line in log_text.split('\n')[:80]:   # scan more lines — errors often appear later
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            # Extract timestamp
            timestamp = None
            for pat in TS_PATTERNS:
                m = re.search(pat, line)
                if m:
                    timestamp = m.group(1)
                    break
            if not timestamp:
                continue

            # Classify severity
            if re.search(r'CRITICAL|FATAL', line):
                event_type, icon = 'critical', '🔴'
            elif re.search(r'ERROR', line):
                event_type, icon = 'error', '🔴'
            elif re.search(r'WARN(?:ING)?', line):
                event_type, icon = 'warning', '⚠️'
            else:
                event_type, icon = 'info', 'ℹ️'

            # Extract component + message
            component, message = None, None
            for pat in MSG_PATTERNS:
                m = re.search(pat, line)
                if m:
                    # Pattern has 3 groups: (level, component, message)
                    component = m.group(2)
                    message = m.group(3)[:120]
                    break

            if component and message:
                events.append({
                    'timestamp': timestamp,
                    'type': event_type,
                    'icon': icon,
                    'component': component,
                    'message': message
                })

        return events[:20]


def calculate_smart_confidence(
    system_confidence: float,
    has_solution: bool,
    has_contact: bool,
    kb_sources: int
) -> Tuple[float, str]:
    """
    Calculate confidence based on ACTUAL evidence quality
    
    Returns: (confidence_score, explanation)
    """
    
    reasons = []
    
    # Start with system detection confidence
    confidence = system_confidence
    
    if system_confidence >= 0.90:
        reasons.append("✅ Explicit system mention")
    elif system_confidence >= 0.75:
        reasons.append("✅ Strong system indicators")
    elif system_confidence >= 0.60:
        reasons.append("⚠️ Moderate system match")
    else:
        reasons.append("❌ System unclear")
    
    # Solution match (but only if system is reasonably certain)
    if has_solution and system_confidence >= 0.60:
        confidence += 0.10
        reasons.append("✅ Matched runbook")
    elif has_solution and system_confidence < 0.60:
        reasons.append("⚠️ Runbook match uncertain")
    
    # Contact match
    if has_contact and system_confidence >= 0.60:
        confidence += 0.05
        reasons.append("✅ Found contact")
    elif has_contact and system_confidence < 0.60:
        reasons.append("⚠️ Contact match uncertain")
    
    # KB sources
    if kb_sources > 0:
        confidence += min(0.05, kb_sources * 0.01)
        reasons.append(f"✅ {kb_sources} related incidents")
    
    # Cap at 0.98 (never 100% certain)
    confidence = min(confidence, 0.98)
    
    explanation = " | ".join(reasons)
    
    return confidence, explanation


class RAGLogAnalyzer:
    """Main analyzer with IMPROVED matching and confidence scoring"""

    def __init__(self,
                 backend: BackendType = BackendType.GROQ_API,
                 groq_api_key: Optional[str] = None,
                 groq_model: str = "llama-3.3-70b-versatile",
                 claude_api_key: Optional[str] = None,
                 claude_model: str = "claude-sonnet-4-20250514",
                 ollama_url: str = "http://localhost:11434",
                 ollama_model: str = "llama3.1:8b",
                 db_path: str = "./chroma_db",
                 min_confidence_threshold: float = 0.60,
                 enable_layer2_sanitization: bool = True):  # NEW: control Layer 2
        
        self.backend = backend
        self.db_path = db_path
        self.matcher = ImprovedMatcher()
        self.contact_map = DirectContactMapping()
        self.solution_map = DirectSolutionMapping()
        self.min_confidence = min_confidence_threshold
        
        # Initialize backend
        if backend == BackendType.GROQ_API:
            self.groq_api_key = groq_api_key or os.getenv("GROQ_API_KEY")
            if not self.groq_api_key:
                raise ValueError("GROQ_API_KEY required")
            self.groq_model = groq_model
            self.backend_name = f"Groq API ({groq_model})"
            logger.info(f"✅ Using Groq API: {groq_model}")
        elif backend == BackendType.CLAUDE_API:
            self.claude_api_key = claude_api_key or os.getenv("ANTHROPIC_API_KEY")
            if not self.claude_api_key:
                raise ValueError("ANTHROPIC_API_KEY required")
            self.claude_model = claude_model
            self.backend_name = f"Claude API ({claude_model})"
            logger.info(f"✅ Using Claude API: {claude_model}")
        else:
            self.ollama_url = ollama_url.rstrip('/')
            self.ollama_model = ollama_model.strip()
            self.backend_name = f"Ollama ({ollama_model})"
            logger.info(f"✅ Using Ollama: {ollama_model}")
        
        # Initialize ChromaDB (optional - for incidents only)
        try:
            self.client = chromadb.PersistentClient(path=db_path)
            self.collection = self.client.get_collection("company_knowledge")
            logger.info(f"✅ KB: {self.collection.count()} docs")
        except Exception as e:
            logger.warning(f"⚠️ KB not found: {e}")
            self.collection = None

        # Initialize sanitization pipeline (GDPR compliance)
        # Extract known names from DirectContactMapping — new engineers auto-included
        known_names = set()
        for system_data in DirectContactMapping.SYSTEM_CONTACTS.values():
            for role in ['primary', 'backup']:
                c = system_data.get(role)
                if c:
                    known_names.add(c.name)
                    if c.escalation_contact and c.escalation_contact != 'CEO':
                        known_names.add(c.escalation_contact)

        # Layer 2 uses a standalone Ollama client — works even when main backend is Groq/Claude.
        # If Ollama isn't running, Layer 2 degrades silently.
        # NEW: Layer 2 can be disabled via enable_layer2_sanitization flag
        ollama_san_fn = None
        if backend != BackendType.OLLAMA_LOCAL and enable_layer2_sanitization:
            ollama_san_fn = create_ollama_sanitizer_callable()
            logger.info("🔒 Layer 2 (LLM) sanitization: ENABLED")
        elif backend != BackendType.OLLAMA_LOCAL:
            logger.info("🔒 Layer 2 (LLM) sanitization: DISABLED (user preference)")

        self.sanitizer = SanitizationPipeline(
            backend_type=backend.value,
            known_names=list(known_names),
            ollama_callable=ollama_san_fn
        )

    def _call_groq_api(self, prompt: str, max_tokens: int = 512, temperature: float = 0.1) -> Optional[str]:
        for attempt in range(3):
            try:
                logger.info("📡 Calling Groq...")
                response = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.groq_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.groq_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": temperature,
                        "max_tokens": max_tokens
                    },
                    timeout=30
                )
                
                if response.status_code == 429:
                    if attempt < 2:
                        logger.warning(f"⚠️  Rate limit - retrying in 5s...")
                        time.sleep(5)
                        continue
                    else:
                        logger.error(f"❌ Groq rate limit - max retries")
                        return None
                
                if response.status_code != 200:
                    logger.error(f"❌ Groq error {response.status_code}")
                    return None
                
                result = response.json()
                return result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
            
            except Exception as e:
                logger.error(f"❌ Groq error: {e}")
                return None
        
        return None

    def _call_claude_api(self, prompt: str, max_tokens: int = 512, temperature: float = 0.1) -> Optional[str]:
        try:
            logger.info("📡 Calling Claude...")
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.claude_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": self.claude_model,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=60
            )
            
            if response.status_code != 200:
                return None
            
            result = response.json()
            content_blocks = result.get('content', [])
            if content_blocks:
                return content_blocks[0].get('text', '').strip()
            return None
        
        except Exception as e:
            logger.error(f"❌ Claude error: {e}")
            return None

    def _call_ollama_local(self, prompt: str, max_tokens: int = 512, temperature: float = 0.1) -> Optional[str]:
        try:
            logger.info("📡 Calling Ollama...")
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens
                    }
                },
                timeout=180
            )
            
            if response.status_code != 200:
                return None
            
            result = response.json()
            return result.get('response', '').strip()
        
        except Exception as e:
            logger.error(f"❌ Ollama error: {e}")
            return None

    def _call_llm(self, prompt: str, max_tokens: int = 512, temperature: float = 0.1) -> Optional[str]:
        """Route to appropriate backend"""
        if self.backend == BackendType.GROQ_API:
            return self._call_groq_api(prompt, max_tokens, temperature)
        elif self.backend == BackendType.CLAUDE_API:
            return self._call_claude_api(prompt, max_tokens, temperature)
        else:
            return self._call_ollama_local(prompt, max_tokens, temperature)

    # Issue types that have a dedicated domain owner regardless of which server is affected.
    # When the issue_type maps here and the domain system differs from the detected server,
    # the domain expert becomes primary contact and the server owner becomes secondary.
    ISSUE_TYPE_DOMAIN_OWNERS = {
        'security': 'Security',
        'payment_failure': 'Payment',
        'connection_pool': 'Server_A',    # Database team owns all connection pool incidents
        'replication_lag': 'Server_A',    # Database team owns all replication incidents
    }

    def get_contacts_and_solutions(self, system: str, issue_type: str, 
                                   system_confidence: float) -> Tuple[List[Contact], List[Solution]]:
        """
        IMPROVED: Only return contacts/solutions if confidence is sufficient.
        Reconciles issue_type domain owners vs server owners — when they disagree
        the domain expert (e.g. Security team for a security incident) is surfaced first.
        """
        
        contacts = []
        solutions = []
        
        # Only provide contacts if we're confident about the system
        if system_confidence >= self.min_confidence:
            # 1. Solution is always driven by issue_type (it defines HOW to respond)
            solution = self.solution_map.get_solution(issue_type)
            if solution:
                solutions = [solution]
                logger.info(f"✅ Found solution for {issue_type}")
            else:
                logger.info(f"⚠️ No solution for {issue_type}")

            # 2. Server-based contacts (WHO owns the system)
            server_contacts = self.contact_map.get_contacts(system)

            # 3. Check if this issue_type has a domain-specific owner on a DIFFERENT team
            domain_system = self.ISSUE_TYPE_DOMAIN_OWNERS.get(issue_type)
            if domain_system and domain_system != system:
                domain_contacts = self.contact_map.get_contacts(domain_system)
                if domain_contacts:
                    # Domain expert first — they know how to handle this class of incident.
                    # Server owner second — they know the affected system.
                    domain_emails = {c.email for c in domain_contacts}
                    contacts = domain_contacts + [c for c in server_contacts if c.email not in domain_emails]
                    logger.info(
                        f"✅ Domain routing: {issue_type} → {domain_system} "
                        f"(primary), {system} (secondary)"
                    )
                else:
                    contacts = server_contacts
            else:
                contacts = server_contacts

            if contacts:
                logger.info(f"✅ Returning {len(contacts)} contact(s) for {system} (confidence: {system_confidence:.0%})")
            else:
                logger.info(f"⚠️ No contacts for {system}")
        else:
            logger.warning(f"⚠️ System confidence too low ({system_confidence:.0%} < {self.min_confidence:.0%}) - skipping contact lookup")
        
        return contacts, solutions

    def query_kb_for_incidents(self, log_text: str) -> List[Dict[str, str]]:
        """Query KB for related incidents with full details.

        The query vector sent to ChromaDB matters enormously for recall.
        Previously this used log_text[:300] which, for logs that start with
        normal startup/health lines, would be pure INFO text with zero
        semantic similarity to past incident documents.

        Now: extract the most signal-dense chunk — ERROR/CRITICAL lines
        first, then fall back to [:300] only if the log has no errors at all.
        """

        if not self.collection:
            return []

        try:
            # Build a query string from the highest-signal lines
            error_lines = []
            for line in log_text.split('\n'):
                if re.search(r'ERROR|CRITICAL|FATAL|pool exhausted|timeout|failed', line, re.IGNORECASE):
                    error_lines.append(line.strip())
                    if len(error_lines) >= 8:   # enough context for a good vector
                        break

            if error_lines:
                query_text = '\n'.join(error_lines)
            else:
                # No error lines at all — fall back to first 300 chars
                query_text = log_text[:300]

            # Cap at 500 chars for the embedding call
            query_text = query_text[:500]

            results = self.collection.query(
                query_texts=[query_text],
                n_results=5,
                include=["documents", "metadatas", "distances"]
            )
            
            incidents = []
            if results.get('documents') and results['documents'][0]:
                for idx, doc in enumerate(results['documents'][0]):
                    # Extract incident ID
                    inc_ids = re.findall(r'#\d{4}-\d{4}', doc)
                    if not inc_ids:
                        continue
                    
                    inc_id = inc_ids[0]
                    
                    # Get metadata
                    meta = results['metadatas'][0][idx] if results.get('metadatas') else {}
                    distance = results['distances'][0][idx] if results.get('distances') else 0
                    if distance > 0.9:
                        distance = 0.9
                    
                    # Extract title (first line or header)
                    lines = doc.split('\n')
                    title = "Unknown Incident"
                    for line in lines:
                        clean = line.strip().replace('#', '').strip()
                        if clean and len(clean) > 10 and inc_id not in clean:
                            title = clean[:100]
                            break
                    
                    # Extract date
                    date_match = re.search(r'(\d{4}-\d{2}-\d{2}|\w+ \d{1,2}, \d{4})', doc)
                    date = date_match.group(1) if date_match else "Unknown date"
                    
                    # Extract resolution time — format: **Resolution Time**: 41 minutes
                    resolution = "Unknown"
                    res_match = re.search(r'\*\*Resolution Time\*\*:\s*(\d+)\s*minutes', doc)
                    if res_match:
                        resolution = f"{res_match.group(1)} minutes"
                    else:
                        # Fallback: inline mention like "resolved in 41 minutes"
                        res_match = re.search(r'(?:resolved|fixed|closed)\s+.*?(\d+)\s*minutes', doc, re.IGNORECASE)
                        if res_match:
                            resolution = f"{res_match.group(1)} minutes"
                    
                    # Extract owner — format: **Resolved By**: Mike Rodriguez
                    owner = "Unknown"
                    if meta.get('contact_name'):
                        owner = meta['contact_name']
                    else:
                        owner_match = re.search(r'\*\*Resolved By\*\*:\s*(.+?)(?:\s*\n|\s*$)', doc)
                        if owner_match:
                            owner = owner_match.group(1).strip()
                        else:
                            # Fallback: inline "resolved by Name"
                            owner_match = re.search(r'(?:resolved by|owner:|contact:)\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', doc)
                            if owner_match:
                                owner = owner_match.group(1).strip()

                    # Extract financial impact — format: **Revenue Impact**: $66,612
                    # (flexible: works with or without ** markers in case ChromaDB strips them)
                    financial_impact = None
                    fin_match = re.search(r'Revenue Impact[^:]*:\s*(\$[\d,]+)', doc)
                    if fin_match:
                        financial_impact = fin_match.group(1)

                    # Extract users affected — format: **Users Affected**: 3,172
                    users_affected = None
                    users_match = re.search(r'Users Affected[^:]*:\s*([\d,]+)', doc)
                    if users_match:
                        users_affected = users_match.group(1)

                    incidents.append({
                        'id': inc_id,
                        'title': title,
                        'date': date,
                        'severity': meta.get('severity', 'MEDIUM'),
                        'resolution_time': resolution,
                        'owner': owner,
                        'financial_impact': financial_impact,
                        'users_affected': users_affected,
                        'similarity': f"{(1 - distance) * 100:.0f}%",
                        'snippet': doc[:200] + "..." if len(doc) > 200 else doc
                    })
            
            # Remove duplicates by ID
            seen = set()
            unique_incidents = []
            for inc in incidents:
                if inc['id'] not in seen:
                    seen.add(inc['id'])
                    unique_incidents.append(inc)
            
            logger.info(f"✅ Found {len(unique_incidents)} related incident(s)")
            return unique_incidents
        
        except Exception as e:
            logger.error(f"❌ KB query failed: {e}")
            return []

    def generate_analysis(self, log_text: str, contacts: List[Contact], solutions: List[Solution], 
                          system: str, severity: str, system_confidence: float) -> Tuple[str, float, str]:
        """Generate analysis with confidence awareness"""
        
        # Extract key error lines
        error_lines = []
        for line in log_text.split('\n'):
            if any(word in line.lower() for word in ['error', 'critical', 'fail', 'exception']):
                error_lines.append(line.strip())
                if len(error_lines) >= 3:
                    break
        
        error_excerpt = '\n'.join(error_lines[:3]) if error_lines else log_text[:300]
        
        # Build context with confidence awareness
        context = ""
        if solutions:
            sol = solutions[0]
            context += f"Available Runbook: {sol.title}\n"
            context += f"Runbook Owner: {sol.owner.name}\n"
        
        if contacts:
            contact = contacts[0]
            context += f"Primary Contact: {contact.name} ({contact.role})\n"
            if contact.escalation_contact:
                context += f"Escalate to: {contact.escalation_contact} after {contact.escalation_time or '15 minutes'}\n"
        
        # Add confidence caveat if low
        if system_confidence < 0.75:
            context += f"\nNOTE: System detection confidence is {system_confidence:.0%} - verify system before escalating\n"
        
        prompt = f"""You are an expert SRE analyzing a production incident. Provide a clear, actionable analysis.

INCIDENT LOG:
{error_excerpt}

CONTEXT:
- System: {system} (confidence: {system_confidence:.0%})
- Severity: {severity}
{context}

ANALYSIS REQUIREMENTS:
1. Identify the TECHNICAL ROOT CAUSE (not just symptoms)
2. Explain the IMPACT on users/business
3. Provide IMMEDIATE next steps

Format your response EXACTLY like this:

**What Happened**
[One clear sentence describing the core technical failure - be specific about WHAT broke, not just that there's an error]

**Root Cause**  
[One sentence explaining WHY it happened - trace back to the underlying cause, not the symptom]

**Impact**
[Quantify user/business impact - how many users affected, what functionality is down]

**Immediate Action**
[The ONE most critical step the on-call engineer should take RIGHT NOW]

**Escalation**
[When to escalate and to whom based on the context provided]

CRITICAL: Do NOT just repeat log timestamps or lines. ANALYZE and EXPLAIN what they mean."""
        
        try:
            response = self._call_llm(prompt, max_tokens=400, temperature=0.2)
            
            if not response:
                return "Error: No LLM response", 0.0, "No response from AI"
            
            # Calculate confidence using smart function
            confidence, explanation = calculate_smart_confidence(
                system_confidence,
                len(solutions) > 0,
                len(contacts) > 0,
                0  # KB sources added later
            )
            
            logger.info(f"✅ Analysis complete (confidence: {confidence:.0%})")
            return response.strip(), confidence, explanation
        
        except Exception as e:
            logger.error(f"❌ Analysis error: {e}")
            return f"Error: {str(e)}", 0.0, "Analysis failed"

    def analyze(self, log_text: str) -> AnalysisResult:
        """Full analysis pipeline with IMPROVED confidence-based matching"""
        
        start = time.time()
        
        try:
            # IMPROVED: Extract with confidence
            severity = self.matcher.extract_severity(log_text)
            system, system_confidence, detection_explanation = self.matcher.extract_system_with_confidence(log_text)
            issue_type = self.matcher.extract_issue_type(log_text)
            
            # Extract additional info
            timestamp = self.matcher.extract_timestamp(log_text)
            error_code = self.matcher.extract_error_code(log_text)
            affected_component = self.matcher.extract_affected_component(log_text)
            # Timeline extracted before sanitization - will be re-extracted after
            
            logger.info(f"📊 Detected: {system} / {severity} / {issue_type}")
            logger.info(f"   System Confidence: {system_confidence:.0%} - {detection_explanation}")
            if error_code:
                logger.info(f"   Error Code: {error_code}")
            if affected_component:
                logger.info(f"   Component: {affected_component}")
            
            # IMPROVED: Only get contacts/solutions if confident
            contacts, solutions = self.get_contacts_and_solutions(system, issue_type, system_confidence)
            
            # Get related incidents from KB
            incidents = self.query_kb_for_incidents(log_text)
            
            # Sanitize before sending to LLM (GDPR — pattern matching already ran on original)
            sanitization_result = self.sanitizer.sanitize(log_text)
            
            # FIXED: Extract timeline from SANITIZED text so LLM doesn't see raw IPs
            timeline = self.matcher.extract_timeline(sanitization_result.sanitized_text)
            
            # Generate analysis (with confidence awareness)
            analysis, base_confidence, base_explanation = self.generate_analysis(
                sanitization_result.sanitized_text, contacts, solutions, system, severity, system_confidence
            )
            
            # IMPROVED: Recalculate final confidence with KB sources
            final_confidence, confidence_explanation = calculate_smart_confidence(
                system_confidence,
                len(solutions) > 0,
                len(contacts) > 0,
                len(incidents)
            )
            
            elapsed = time.time() - start
            logger.info(f"✅ Complete in {elapsed:.2f}s")
            logger.info(f"   Final Confidence: {final_confidence:.0%}")
            
            return AnalysisResult(
                success=True,
                severity=severity,
                system=system,
                issue_type=issue_type,
                analysis=analysis,
                confidence=final_confidence,
                contacts=contacts,
                solutions=solutions,
                related_incidents=incidents,
                timestamp=timestamp,
                error_code=error_code,
                affected_component=affected_component,
                timeline=timeline,
                confidence_explanation=confidence_explanation,
                system_confidence=system_confidence,
                detection_explanation=detection_explanation,
                sanitization=sanitization_result,
                knowledge_sources=len(incidents),
                processing_time=elapsed,
                backend_used=self.backend_name
            )
        
        except Exception as e:
            logger.error(f"❌ Pipeline failed: {e}")
            return AnalysisResult(
                success=False,
                severity="ERROR",
                system="Unknown",
                issue_type="pipeline_failed",
                analysis=str(e),
                confidence=0.0,
                processing_time=time.time() - start,
                backend_used=self.backend_name,
                error=str(e)
            )


    def analyze_multi(self, log_text: str) -> AnalysisResult:
        """
        ENHANCED Multi-agent analysis pipeline with Knowledge Validator.
        
        Same as analyze() up to the LLM call, then replaces generate_analysis()
        with 4 agents (RootCause, Impact, Actions, Knowledge) running in parallel
        or partial-sequential mode.
        
        NEW in v7.0:
        - Knowledge agent treats KB data as suggestions (can be wrong)
        - Enhanced consensus detects:
          * Factual conflicts (KB vs Agents) → Need review
          * Interpretation conflicts (Agent perspectives) → Expected
        - Quality assessment: HIGH/MEDIUM/LOW based on conflict types
        
        The single-agent analyze() is untouched — both paths coexist.
        """
        start = time.time()

        try:
            # --- Identical to analyze(): pattern matching + lookups ---
            severity = self.matcher.extract_severity(log_text)
            system, system_confidence, detection_explanation = self.matcher.extract_system_with_confidence(log_text)
            issue_type = self.matcher.extract_issue_type(log_text)

            timestamp = self.matcher.extract_timestamp(log_text)
            error_code = self.matcher.extract_error_code(log_text)
            affected_component = self.matcher.extract_affected_component(log_text)
            # Timeline extracted BEFORE sanitization - will contain raw IPs
            # We'll re-extract after sanitization

            logger.info(f"📊 [multi] Detected: {system} / {severity} / {issue_type}")
            logger.info(f"   System Confidence: {system_confidence:.0%} - {detection_explanation}")

            contacts, solutions = self.get_contacts_and_solutions(system, issue_type, system_confidence)
            incidents = self.query_kb_for_incidents(log_text)

            # Sanitize before sending to cloud LLM (GDPR)
            # Pattern matching already ran on original — that's all local.
            sanitization_result = self.sanitizer.sanitize(log_text)
            
            # FIXED: Extract timeline from SANITIZED text so agents don't see raw IPs
            timeline = self.matcher.extract_timeline(sanitization_result.sanitized_text)

            # --- ENHANCED: Prepare KB search results for Knowledge agent ---
            kb_search_results = {
                'contacts': [
                    {
                        'name': c.name,
                        'role': c.role,
                        'email': c.email,
                        'team': c.team,
                        'phone': c.phone
                    } for c in contacts
                ],
                'runbooks': [
                    {
                        'title': s.title,
                        'owner': s.owner.name,
                        'steps': s.steps[:3] if len(s.steps) > 3 else s.steps,  # Preview only
                        'duration': s.duration
                    } for s in solutions
                ],
                'past_incidents': [
                    {
                        'id': inc.get('id', ''),
                        'description': inc.get('description', '')[:200],  # Truncate for prompt
                        'resolution': inc.get('resolution', '')[:100],
                        'cost': inc.get('cost', 'Unknown')
                    } for inc in incidents
                ]
            }

            # --- Multi-agent replaces generate_analysis() from here ---
            # ENHANCED: Now includes kb_search_results for Knowledge validator agent
            multi_result = run_multi_agent(
                log_text=sanitization_result.sanitized_text,
                system=system,
                system_confidence=system_confidence,
                severity=severity,
                issue_type=issue_type,
                contacts=contacts,
                solutions=solutions,
                timeline=timeline,
                llm_callable=self._call_llm,
                kb_search_results=kb_search_results  # ENHANCED: KB data for validation
            )

            # Build a combined analysis string for backward compat
            # (the UI can also read multi_result directly for the tabbed view)
            analysis_parts = []
            if multi_result.root_cause.trigger:
                analysis_parts.append(f"**Root Cause**: {multi_result.root_cause.trigger}")
            if multi_result.root_cause.causal_chain:
                analysis_parts.append(f"**Chain**: {' → '.join(multi_result.root_cause.causal_chain)}")
            if multi_result.impact.user_impact:
                analysis_parts.append(f"**Impact**: {multi_result.impact.user_impact}")
            if multi_result.actions.immediate:
                analysis_parts.append(f"**Immediate Action**: {multi_result.actions.immediate[0]}")

            combined_analysis = '\n'.join(analysis_parts) if analysis_parts else "Multi-agent analysis produced no output."

            # Confidence calc (same as v1.0)
            final_confidence, confidence_explanation = calculate_smart_confidence(
                system_confidence,
                len(solutions) > 0,
                len(contacts) > 0,
                len(incidents)
            )

            elapsed = time.time() - start
            logger.info(f"✅ [multi] Complete in {elapsed:.2f}s (agents: {multi_result.total_time:.2f}s)")

            return AnalysisResult(
                success=True,
                severity=severity,
                system=system,
                issue_type=issue_type,
                analysis=combined_analysis,
                confidence=final_confidence,
                contacts=contacts,
                solutions=solutions,
                related_incidents=incidents,
                timestamp=timestamp,
                error_code=error_code,
                affected_component=affected_component,
                timeline=timeline,
                confidence_explanation=confidence_explanation,
                system_confidence=system_confidence,
                detection_explanation=detection_explanation,
                multi_agent=multi_result,
                sanitization=sanitization_result,
                knowledge_sources=len(incidents),
                processing_time=elapsed,
                backend_used=self.backend_name
            )

        except Exception as e:
            logger.error(f"❌ Multi-agent pipeline failed: {e}")
            return AnalysisResult(
                success=False,
                severity="ERROR",
                system="Unknown",
                issue_type="pipeline_failed",
                analysis=str(e),
                confidence=0.0,
                processing_time=time.time() - start,
                backend_used=self.backend_name,
                error=str(e)
            )


if __name__ == "__main__":
    print("RAG Engine v6.3 IMPROVED - Import this module to use")