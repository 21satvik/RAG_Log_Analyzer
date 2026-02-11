#!/usr/bin/env python3
"""
Multi-Agent Analyzer v2.0 - WITH KNOWLEDGE AGENT
- 4 specialized agents: RootCause, Impact, Actions, Knowledge
- Knowledge agent provides company context (contacts, runbooks) - NOT compared to analysis agents
- Enhanced consensus detects factual vs interpretation conflicts AMONG ANALYSIS AGENTS ONLY
- KB treated as reference material, analysis agents compared for consistency
"""

import asyncio
import time
import logging
import re
import json
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output schemas
# ---------------------------------------------------------------------------

@dataclass
class RootCauseOutput:
    trigger: str = ""
    causal_chain: list = field(default_factory=list)
    confidence: int = 0
    reasoning: str = ""
    identified_system: str = ""  # NEW: what system does this agent think it is?

@dataclass
class ImpactOutput:
    affected_systems: list = field(default_factory=list)
    user_impact: str = ""
    estimated_duration: str = ""
    severity_justification: str = ""
    financial_impact: str = "Unknown"
    primary_system: str = ""  # NEW: what system does this agent think is primary?

@dataclass
class ActionsOutput:
    immediate: list = field(default_factory=list)
    short_term: list = field(default_factory=list)
    preventive: list = field(default_factory=list)
    rollback_plan: str = ""
    target_system: str = ""  # NEW: what system are these actions for?

@dataclass
class KnowledgeOutput:
    """Knowledge base findings - treated as suggestions, not facts"""
    suggested_system: str = ""
    confidence: float = 0.0
    
    primary_contact: Dict = field(default_factory=dict)
    backup_contacts: List[Dict] = field(default_factory=list)
    
    best_runbook: Dict = field(default_factory=dict)
    alternative_runbooks: List[Dict] = field(default_factory=list)
    
    similar_incidents: List[Dict] = field(default_factory=list)
    
    financial_context: Dict = field(default_factory=dict)
    
    reasoning: str = ""
    kb_sources_used: int = 0

@dataclass
class ConsistencyOutput:
    """Enhanced with factual vs interpretation conflict detection (among analysis agents only)"""
    factual_conflicts: list = field(default_factory=list)        # Root/Impact/Actions disagreements on facts (BAD)
    interpretation_conflicts: list = field(default_factory=list)  # Root/Impact/Actions different perspectives (EXPECTED)
    agreements: list = field(default_factory=list)
    confidence: int = 0
    quality_assessment: str = ""  # HIGH/MEDIUM/LOW based on conflict types
    recommendation: str = ""

@dataclass
class MultiAgentResult:
    root_cause: RootCauseOutput = field(default_factory=RootCauseOutput)
    impact: ImpactOutput = field(default_factory=ImpactOutput)
    actions: ActionsOutput = field(default_factory=ActionsOutput)
    knowledge: KnowledgeOutput = field(default_factory=KnowledgeOutput)  # NEW
    consistency: ConsistencyOutput = field(default_factory=ConsistencyOutput)
    mode_used: str = ""
    total_time: float = 0.0
    agent_times: Dict[str, float] = field(default_factory=dict)
    errors: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def parse_root_cause(text: str) -> RootCauseOutput:
    if not text:
        return RootCauseOutput()

    out = RootCauseOutput()

    m = re.search(r'TRIGGER:\s*(.+)', text, re.IGNORECASE)
    if m:
        out.trigger = m.group(1).strip()

    m = re.search(r'CHAIN:\s*(.+)', text, re.IGNORECASE)
    if m:
        raw = m.group(1).strip()
        parts = re.split(r'\s*(?:→|->|=>)\s*', raw)
        out.causal_chain = [p.strip() for p in parts if p.strip()]

    m = re.search(r'CONFIDENCE:\s*(\d+)', text, re.IGNORECASE)
    if m:
        out.confidence = min(int(m.group(1)), 100)

    m = re.search(r'REASONING:\s*(.*?)(?=\n[A-Z]+:|$)', text, re.IGNORECASE | re.DOTALL)
    if m:
        out.reasoning = m.group(1).strip()
    
    # NEW: extract system identification
    m = re.search(r'SYSTEM:\s*([^\n]+)', text, re.IGNORECASE)
    if m:
        out.identified_system = m.group(1).strip()

    return out


def parse_impact(text: str) -> ImpactOutput:
    if not text:
        return ImpactOutput()

    # Clean up LaTeX math notation and formatting issues
    text = re.sub(r'\$+', '$', text)  # Normalize multiple $ signs
    text = re.sub(r'\\[a-z]+\{', '', text)  # Remove LaTeX commands like \text{
    text = re.sub(r'\}', '', text)  # Remove closing braces
    
    out = ImpactOutput()

    m = re.search(r'AFFECTED SYSTEMS:\s*(.+?)(?=\n[A-Z]|\Z)', text, re.IGNORECASE | re.DOTALL)
    if m:
        raw = m.group(1).strip()
        parts = re.split(r'[,\n]', raw)
        out.affected_systems = [p.strip().lstrip('-•*').strip() for p in parts if p.strip()]

    m = re.search(r'USER IMPACT:\s*(.+?)(?=\n[A-Z]|\Z)', text, re.IGNORECASE | re.DOTALL)
    if m:
        user_impact_raw = m.group(1).strip()
        # Take only the first sentence/paragraph to avoid repetition
        first_part = user_impact_raw.split('\n\n')[0] if '\n\n' in user_impact_raw else user_impact_raw
        lines = first_part.split('\n')
        # Keep only non-repetitive lines (first occurrence)
        seen = set()
        clean_lines = []
        for line in lines[:5]:  # Limit to 5 lines max
            normalized = re.sub(r'\s+', ' ', line.strip().lower())
            if normalized and normalized not in seen:
                seen.add(normalized)
                clean_lines.append(line.strip())
        out.user_impact = '\n'.join(clean_lines)

    m = re.search(r'ESTIMATED DURATION:\s*(.+?)(?=\n[A-Z]|\Z)', text, re.IGNORECASE | re.DOTALL)
    if m:
        duration_raw = m.group(1).strip()
        # Take only the first line
        out.estimated_duration = duration_raw.split('\n')[0].strip()

    m = re.search(r'SEVERITY JUSTIFICATION:\s*(.+?)(?=\n[A-Z]|\Z)', text, re.IGNORECASE | re.DOTALL)
    if m:
        severity_raw = m.group(1).strip()
        # Take only the first paragraph
        first_para = severity_raw.split('\n\n')[0] if '\n\n' in severity_raw else severity_raw
        lines = first_para.split('\n')
        out.severity_justification = ' '.join(lines[:3])  # Max 3 lines

    m = re.search(r'FINANCIAL IMPACT:\s*(.+?)(?=\n[A-Z]|\Z)', text, re.IGNORECASE | re.DOTALL)
    if m:
        financial_raw = m.group(1).strip()
        # Extract only the first line and clean it up
        first_line = financial_raw.split('\n')[0].strip()
        # Remove calculation work indicators
        if 'CALCULATION WORK' in first_line.upper() or 'FINAL ESTIMATION' in first_line.upper():
            # Try to find actual estimate
            estimate_match = re.search(r'\$[\d,]+k?\s*-?\s*\$?[\d,]+[kM]?', financial_raw, re.IGNORECASE)
            if estimate_match:
                first_line = estimate_match.group(0)
        # Clean up LaTeX notation from financial impact
        first_line = re.sub(r'\\[a-z]+', '', first_line)
        first_line = re.sub(r'[\{\}]', '', first_line)
        out.financial_impact = first_line
    
    # NEW: extract primary system
    m = re.search(r'PRIMARY SYSTEM:\s*([^\n]+)', text, re.IGNORECASE)
    if m:
        out.primary_system = m.group(1).strip()
    elif out.affected_systems:
        out.primary_system = out.affected_systems[0]

    return out


def _extract_numbered_or_bulleted_list(text: str, label: str, all_labels: Optional[list] = None) -> list:
    """
    Enhanced version that handles:
    - Bold markdown: **LABEL** or **LABEL:**
    - Parenthetical notes: LABEL (details)
    - Various separators
    - Filters out placeholder text like "[Empty if none found]"
    """
    if all_labels is None:
        all_labels = ['IMMEDIATE', 'SHORT-TERM', 'PREVENTIVE', 'ROLLBACK PLAN', 'TARGET SYSTEM']
    
    # Clean the label of any markdown
    clean_label = label.strip('*')
    
    # Build pattern that matches label with optional markdown and parentheticals
    # Matches: "IMMEDIATE", "**IMMEDIATE**", "IMMEDIATE (within 5 minutes)", etc.
    label_pattern = rf'\*{{0,2}}{re.escape(clean_label)}\*{{0,2}}\s*(?:\([^)]+\))?\s*:?'
    
    # Build boundary pattern from other labels
    other_labels = [l for l in all_labels if l.strip('*') != clean_label]
    boundary_patterns = []
    for other_label in other_labels:
        clean_other = other_label.strip('*')
        boundary_patterns.append(rf'\*{{0,2}}{re.escape(clean_other)}\*{{0,2}}\s*(?:\([^)]+\))?\s*:?')
    
    boundary = '|'.join(boundary_patterns) if boundary_patterns else r'$'
    
    # Extract the section
    pattern = rf'{label_pattern}\s*(.*?)(?=(?:{boundary})|$)'
    m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    
    if not m:
        return []
    
    block = m.group(1).strip()
    
    # Extract items from the block
    lines = block.split('\n')
    items = []
    
    # Placeholder patterns to filter out
    placeholder_patterns = [
        r'^\[.*empty.*\]$',
        r'^\[.*none.*found.*\]$',
        r'^\[.*if.*none.*\]$',
        r'^none$',
        r'^none\s+found$',
        r'^n/a$',
        r'^empty$',
        r'.*none\s+found.*',  # Catch "None found" anywhere in the line
        r'^\s*-?\s*none\s*$',  # Catch "- None" or just "None"
    ]
    
    for line in lines:
        # Remove markdown bold, bullets, numbers
        cleaned = re.sub(r'^\s*\*{0,2}', '', line)  # Remove leading markdown
        cleaned = re.sub(r'\*{0,2}\s*$', '', cleaned)  # Remove trailing markdown
        cleaned = re.sub(r'^[\s]*(?:\d+[\.\)]\s*|[-•*]\s*)', '', cleaned).strip()
        
        # Skip empty lines
        if not cleaned:
            continue
        
        # Skip placeholder text
        is_placeholder = any(re.match(pattern, cleaned, re.IGNORECASE) for pattern in placeholder_patterns)
        if is_placeholder:
            continue
        
        items.append(cleaned)
    
    return items


def parse_actions(text: str) -> ActionsOutput:
    """
    Enhanced parser that handles markdown formatting and flexible structure.
    """
    if not text:
        return ActionsOutput()

    logging.info(f"🔍 Actions agent raw output:\n{text}\n" + "="*80)
    
    out = ActionsOutput()
    
    # Extract lists with enhanced parser
    out.immediate = _extract_numbered_or_bulleted_list(text, 'IMMEDIATE')
    out.short_term = _extract_numbered_or_bulleted_list(text, 'SHORT-TERM')
    out.preventive = _extract_numbered_or_bulleted_list(text, 'PREVENTIVE')

    # Extract rollback plan (handle markdown)
    rollback_pattern = r'\*{0,2}ROLLBACK\s*PLAN\*{0,2}\s*:?\s*(.*?)(?=\n\*{0,2}[A-Z][A-Z\s]+\*{0,2}\s*:?|$)'
    m = re.search(rollback_pattern, text, re.IGNORECASE | re.DOTALL)
    if m:
        out.rollback_plan = m.group(1).strip()
    
    # Extract target system (handle markdown and comma-separated values)
    target_pattern = r'\*{0,2}TARGET\s*SYSTEM\*{0,2}\s*:?\s*([^\n]+)'
    m = re.search(target_pattern, text, re.IGNORECASE)
    if m:
        # Clean markdown from the extracted value
        target_value = m.group(1).strip()
        target_value = re.sub(r'^\*{2,}|\*{2,}$', '', target_value).strip()
        out.target_system = target_value

    # Debug logging
    logging.info(f"✅ Parsed Actions:")
    logging.info(f"   Target System: {out.target_system}")
    logging.info(f"   Immediate: {len(out.immediate)} items")
    logging.info(f"   Short-term: {len(out.short_term)} items")
    logging.info(f"   Preventive: {len(out.preventive)} items")
    logging.info(f"   Rollback: {len(out.rollback_plan)} chars")

    return out


def parse_knowledge(text: str) -> KnowledgeOutput:
    """Parse KB agent output - expects JSON format"""
    if not text:
        return KnowledgeOutput()
    
    out = KnowledgeOutput()
    
    try:
        # Try to extract JSON from response
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            
            out.suggested_system = data.get('suggested_system', '')
            out.confidence = float(data.get('confidence', 0.0))
            
            out.primary_contact = data.get('primary_contact', {})
            out.backup_contacts = data.get('backup_contacts', [])
            
            out.best_runbook = data.get('best_runbook', {})
            out.alternative_runbooks = data.get('alternative_runbooks', [])
            
            out.similar_incidents = data.get('similar_incidents', [])
            out.financial_context = data.get('financial_context', {})
            
            out.reasoning = data.get('reasoning', '')
            out.kb_sources_used = data.get('kb_sources_used', 0)
    
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Failed to parse KB output as JSON: {e}")
        # Fallback: extract what we can from text
        m = re.search(r'SUGGESTED SYSTEM:\s*([^\n]+)', text, re.IGNORECASE)
        if m:
            out.suggested_system = m.group(1).strip()
        
        m = re.search(r'CONFIDENCE:\s*([\d.]+)', text, re.IGNORECASE)
        if m:
            out.confidence = float(m.group(1))
    
    return out


# ---------------------------------------------------------------------------
# Enhanced Consistency Checker - Detects Factual vs Interpretation Conflicts
# ---------------------------------------------------------------------------

_CONSISTENCY_LABELS = ['FACTUAL CONFLICTS', 'INTERPRETATION CONFLICTS', 
                       'AGREEMENTS', 'QUALITY ASSESSMENT', 'RECOMMENDATION']


def build_consistency_prompt_v2(
    rc: RootCauseOutput,
    imp: ImpactOutput,
    act: ActionsOutput,
    kb: KnowledgeOutput
) -> str:
    """
    Enhanced prompt that separates factual from interpretation conflicts.
    
    KEY CHANGE: KB Agent is NOT compared to other agents - it's reference material.
    Only Root Cause, Impact, and Actions agents are compared for consistency.
    """
    
    # Serialize ANALYSIS agents only (exclude KB from comparison)
    analysis_sections = []
    
    # Root Cause Agent
    rc_text = f"""ROOT CAUSE AGENT says:
  Identified System: {rc.identified_system}
  Trigger: {rc.trigger}
  Causal Chain: {' → '.join(rc.causal_chain)}
  Confidence: {rc.confidence}%
  Reasoning: {rc.reasoning[:200]}..."""
    analysis_sections.append(rc_text)
    
    # Impact Agent
    imp_text = f"""IMPACT AGENT says:
  Primary System: {imp.primary_system}
  Affected Systems: {', '.join(imp.affected_systems)}
  User Impact: {imp.user_impact}
  Financial Impact: {imp.financial_impact}
  Severity: {imp.severity_justification[:100]}..."""
    analysis_sections.append(imp_text)
    
    # Actions Agent
    act_text = f"""ACTIONS AGENT says:
  Target System: {act.target_system}
  Immediate Actions: {len(act.immediate)} steps
  First Action: {act.immediate[0] if act.immediate else 'None'}
  Rollback: {act.rollback_plan[:100]}..."""
    analysis_sections.append(act_text)
    
    # KB is shown separately as reference only
    kb_text = f"""
KNOWLEDGE BASE (REFERENCE ONLY - NOT COMPARED):
  System: {kb.suggested_system} (confidence: {kb.confidence:.0%})
  Primary Contact: {kb.primary_contact.get('name', 'Unknown')} ({kb.primary_contact.get('role', 'Unknown')})
  Best Runbook: {kb.best_runbook.get('title', 'Not found')}
  Similar Incidents: {len(kb.similar_incidents)} found"""
    
    analysis_summary = '\n\n'.join(analysis_sections)
    
    prompt = f"""You are a consistency validator for a multi-agent incident response system.

IMPORTANT: Only compare the 3 ANALYSIS agents (Root Cause, Impact, Actions) with each other.
The Knowledge Base provides company context and should NOT be compared to analysis agents.

ANALYSIS AGENTS TO COMPARE:
{analysis_summary}

{kb_text}

YOUR TASK:
Compare ONLY the 3 analysis agents and classify conflicts into TWO types:

1. FACTUAL CONFLICTS - Objective facts where agents disagree (SERIOUS)
   Examples: Different system IDs, mismatched severity, actions targeting wrong system
   
2. INTERPRETATION CONFLICTS - Subjective perspectives (EXPECTED)
   Examples: Different root cause theories, different action priorities

CRITICAL FORMATTING RULES:
- If NO conflicts exist in a category, output ONLY the header with NO text below it
- DO NOT write "None found", "No conflicts", or any explanatory text
- Empty sections should look like: "FACTUAL CONFLICTS:\n\n" (header with blank lines)

Analyze and return EXACTLY this structure:

FACTUAL CONFLICTS:
- [Specific disagreement 1]
- [Specific disagreement 2]

INTERPRETATION CONFLICTS:
- [Subjective difference 1]
- [Subjective difference 2]

AGREEMENTS:
- [What all agents agree on]

QUALITY ASSESSMENT:
[HIGH if 0 factual conflicts / MEDIUM if 1-2 factual OR many interpretation / LOW if 3+ factual]

RECOMMENDATION:
[What engineer should focus on - prioritize factual conflicts]

EXAMPLE - When NO conflicts exist:

FACTUAL CONFLICTS:

INTERPRETATION CONFLICTS:

AGREEMENTS:
- All agents agree on Server_A as affected system
- All agents identify connection pool exhaustion as root cause

QUALITY ASSESSMENT:
HIGH - Perfect agent agreement on all objective facts

RECOMMENDATION:
Proceed with confidence - all agents aligned on system and cause
"""
    
    return prompt


def parse_consistency_v2(text: str) -> ConsistencyOutput:
    """Enhanced parser for new consistency format"""
    if not text:
        return ConsistencyOutput()

    out = ConsistencyOutput()

    # Factual conflicts (serious)
    out.factual_conflicts = _extract_numbered_or_bulleted_list(
        text, 'FACTUAL CONFLICTS', _CONSISTENCY_LABELS
    )

    # Interpretation conflicts (expected)
    out.interpretation_conflicts = _extract_numbered_or_bulleted_list(
        text, 'INTERPRETATION CONFLICTS', _CONSISTENCY_LABELS
    )

    # Agreements
    out.agreements = _extract_numbered_or_bulleted_list(
        text, 'AGREEMENTS', _CONSISTENCY_LABELS
    )

    # Quality assessment
    m = re.search(r'QUALITY ASSESSMENT:\s*(.+?)(?=\n[A-Z][A-Z ]+:|$)', text, re.IGNORECASE | re.DOTALL)
    if m:
        out.quality_assessment = m.group(1).strip()
        # Extract quality level
        if 'HIGH' in out.quality_assessment.upper():
            out.confidence = 90
        elif 'MEDIUM' in out.quality_assessment.upper():
            out.confidence = 60
        else:
            out.confidence = 30

    # Recommendation
    m = re.search(r'RECOMMENDATION:\s*(.+)', text, re.IGNORECASE | re.DOTALL)
    if m:
        out.recommendation = m.group(1).strip()

    return out


# ---------------------------------------------------------------------------
# Prompt Builders
# ---------------------------------------------------------------------------

def build_root_cause_prompt(ctx: Dict[str, Any]) -> str:
    """Build root cause analysis prompt"""
    prompt = f"""You are a Root Cause Analysis expert. Analyze this incident and identify the PRIMARY trigger.

INCIDENT DATA:
System: {ctx.get('system', 'unknown')}
Severity: {ctx.get('severity', 'unknown')}
Issue Type: {ctx.get('issue_type', 'unknown')}

TIMELINE:
{ctx.get('timeline_text', 'No timeline')}

ERROR EXCERPT:
{ctx.get('error_excerpt', 'No errors extracted')}

YOUR TASK:
Identify what STARTED this chain of events. Return EXACTLY this structure:

SYSTEM: [Which system/server is affected - be specific]
TRIGGER: [The first event that started everything]
CHAIN: [Event1] → [Event2] → [Event3] → [Final symptom]
CONFIDENCE: [0-100]
REASONING: [Why you believe this is the root cause]

Focus on the FIRST event in the chain, not just symptoms.
"""
    return prompt


def build_impact_prompt(ctx: Dict[str, Any]) -> str:
    """Build impact analysis prompt with concise financial extraction"""
    prompt = f"""You are an Impact Assessment expert. Analyze the scope and severity of this incident.

INCIDENT DATA:
System: {ctx.get('system', 'unknown')}
Severity: {ctx.get('severity', 'unknown')}
Issue Type: {ctx.get('issue_type', 'unknown')}

TIMELINE:
{ctx.get('timeline_text', 'No timeline')}

ERROR EXCERPT:
{ctx.get('error_excerpt', 'No errors extracted')}

YOUR TASK:
Assess the full impact. Return EXACTLY this structure (be CONCISE):

PRIMARY SYSTEM: [Main system affected]
AFFECTED SYSTEMS: [System1], [System2], [System3]
USER IMPACT: [How many users affected? What can't they do?]
ESTIMATED DURATION: [How long will this last?]
FINANCIAL IMPACT: [Single concise estimate]
SEVERITY JUSTIFICATION: [Brief explanation of severity level]

FINANCIAL IMPACT GUIDELINES:
- Look for explicit costs in logs first
- If not found, estimate based on: 10k+ users = $500k-$1M, 1k-10k users = $50k-$500k, 100-1k users = $5k-$50k
- Format: "$X-$Y estimated (reason)" or "Unknown - insufficient data"
- Keep it to ONE LINE - no calculation steps, no work shown

Be specific but CONCISE. No repetition. No verbose explanations.
"""
    return prompt


def build_actions_prompt(ctx: Dict[str, Any], agent_context: Optional[str] = None) -> str:
    """Build actions recommendation prompt"""
    base_context = f"""INCIDENT DATA:
System: {ctx.get('system', 'unknown')}
Severity: {ctx.get('severity', 'unknown')}
Issue Type: {ctx.get('issue_type', 'unknown')}

TIMELINE:
{ctx.get('timeline_text', 'No timeline')}

ERROR EXCERPT:
{ctx.get('error_excerpt', 'No errors extracted')}"""

    if agent_context:
        base_context += f"\n\nOTHER AGENTS FOUND:\n{agent_context}"

    prompt = f"""You are an Incident Response expert. Recommend specific actions to resolve this incident.

{base_context}

YOUR TASK:
Provide actionable steps in 3 phases. Return EXACTLY this structure:

TARGET SYSTEM: [Which system needs action]
IMMEDIATE: [Do RIGHT NOW - within 5 minutes]
- [Specific action 1]
- [Specific action 2]

SHORT-TERM: [Next 1-2 hours]
- [Action 1]
- [Action 2]

PREVENTIVE: [After incident resolved]
- [Prevention 1]
- [Prevention 2]

ROLLBACK PLAN: [How to undo if things get worse]

Be specific - include commands, contacts, or tools where applicable.
"""
    return prompt


def build_knowledge_prompt(ctx: Dict[str, Any], kb_results: Dict[str, Any]) -> str:
    """Build knowledge synthesis prompt"""
    
    contacts_text = "No contacts found"
    if kb_results.get('contacts'):
        contacts_text = "\n".join([
            f"- {c.get('name', 'Unknown')} ({c.get('role', 'Unknown')}) - {c.get('team', 'Unknown')}"
            for c in kb_results['contacts'][:5]
        ])
    
    runbooks_text = "No runbooks found"
    if kb_results.get('runbooks'):
        runbooks_text = "\n".join([
            f"- {r.get('title', 'Unknown')} (Owner: {r.get('owner', 'Unknown')})"
            for r in kb_results['runbooks'][:3]
        ])
    
    incidents_text = "No past incidents found"
    if kb_results.get('past_incidents'):
        incidents_text = "\n".join([
            f"- {i.get('id', 'Unknown')}: {i.get('description', 'No description')[:100]}"
            for i in kb_results['past_incidents'][:3]
        ])
    
    prompt = f"""You are a Knowledge Base Synthesis Agent. Analyze these KB search results and provide the MOST RELEVANT suggestions.

INCIDENT CONTEXT:
System: {ctx.get('system', 'unknown')}
Severity: {ctx.get('severity', 'unknown')}
Issue: {ctx.get('issue_type', 'unknown')}

ERROR EXCERPT:
{ctx.get('error_excerpt', 'No errors')[:500]}

KNOWLEDGE BASE RESULTS:

Contacts Found ({len(kb_results.get('contacts', []))}):
{contacts_text}

Runbooks Found ({len(kb_results.get('runbooks', []))}):
{runbooks_text}

Past Incidents ({len(kb_results.get('past_incidents', []))}):
{incidents_text}

YOUR TASK:
Synthesize this KB data and return a JSON object with your SUGGESTIONS (not facts):

{{
    "suggested_system": "System name based on KB evidence",
    "confidence": 0.85,
    "primary_contact": {{"name": "", "role": "", "email": "", "team": ""}},
    "backup_contacts": [{{"name": "", "role": ""}}],
    "best_runbook": {{"title": "", "owner": "", "steps_preview": "First 3 steps..."}},
    "alternative_runbooks": [],
    "similar_incidents": [
        {{"id": "", "similarity": 0.89, "resolution_summary": "", "cost": ""}}
    ],
    "financial_context": {{
        "historical_costs": ["$X for incident Y"],
        "estimated_range": "$X - $Y"
    }},
    "reasoning": "Why these KB items are relevant...",
    "kb_sources_used": {len(kb_results.get('contacts', [])) + len(kb_results.get('runbooks', [])) + len(kb_results.get('past_incidents', []))}
}}

IMPORTANT: These are SUGGESTIONS to be validated by other agents, NOT definitive facts.
Return valid JSON only.
"""
    return prompt


# ---------------------------------------------------------------------------
# Agent Execution
# ---------------------------------------------------------------------------

def _run_agent(
    name: str,
    prompt: str,
    llm_callable,
    parser,
    max_tokens: int = 450
) -> tuple:
    """Run one agent synchronously"""
    start = time.time()
    try:
        logger.info(f"🤖 [{name}] started")
        raw = llm_callable(prompt, max_tokens=max_tokens, temperature=0.2)
        elapsed = time.time() - start

        if not raw:
            logger.warning(f"🤖 [{name}] empty response")
            return (name, parser(""), elapsed, "Empty response from LLM")

        logger.info(f"🤖 [{name}] done in {elapsed:.2f}s")
        return (name, parser(raw), elapsed, None)

    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"🤖 [{name}] failed: {e}")
        return (name, parser(""), elapsed, str(e))


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

def build_shared_context(
    log_text: str,
    system: str,
    system_confidence: float,
    severity: str,
    issue_type: str,
    contacts: list,
    solutions: list,
    timeline: list
) -> Dict[str, Any]:
    """Build shared context for all agents"""
    timeline_lines = []
    for ev in timeline[:15]:
        timeline_lines.append(
            f"  {ev.get('timestamp', '?')} {ev.get('icon', '')} "
            f"[{ev.get('component', '?')}] {ev.get('message', '')}"
        )
    timeline_text = '\n'.join(timeline_lines) if timeline_lines else "  (no timeline events)"

    error_lines = []
    for line in log_text.split('\n'):
        if any(w in line.lower() for w in ['error', 'critical', 'fail', 'exception', 'fatal']):
            error_lines.append(line.strip())
            if len(error_lines) >= 5:
                break
    error_excerpt = '\n'.join(error_lines) if error_lines else log_text[:400]

    ctx = {
        'system': system,
        'system_confidence': system_confidence,
        'severity': severity,
        'issue_type': issue_type,
        'timeline_text': timeline_text,
        'error_excerpt': error_excerpt,
    }

    if solutions:
        ctx['runbook_title'] = solutions[0].title
    if contacts:
        ctx['contact_name'] = f"{contacts[0].name} ({contacts[0].role})"

    return ctx


def run_multi_agent_v2(
    log_text: str,
    system: str,
    system_confidence: float,
    severity: str,
    issue_type: str,
    contacts: list,
    solutions: list,
    timeline: list,
    llm_callable,
    kb_search_results: Optional[Dict] = None  # NEW: KB search results
) -> MultiAgentResult:
    """
    Enhanced multi-agent with Knowledge agent providing company context.
    
    KB Agent provides reference material (contacts, runbooks, past incidents).
    Only the 3 analysis agents (Root Cause, Impact, Actions) are compared for consistency.
    
    Mode selection:
      - CRITICAL + confidence >= 0.75 → partial_sequential with KB validation
      - Everything else → parallel (all 4 at once)
    """
    start = time.time()
    result = MultiAgentResult()

    # 1. Build shared context
    ctx = build_shared_context(
        log_text, system, system_confidence, severity,
        issue_type, contacts, solutions, timeline
    )

    # 2. Prepare KB results (if not provided, create empty structure)
    if kb_search_results is None:
        kb_search_results = {
            'contacts': contacts,
            'runbooks': solutions,
            'past_incidents': []
        }

    # 3. Decide mode
    use_sequential = (severity == "CRITICAL" and system_confidence >= 0.75)
    result.mode_used = "partial_sequential" if use_sequential else "parallel"
    logger.info(f"🤖 Multi-agent mode: {result.mode_used}")

    # 4. Build prompts
    root_prompt = build_root_cause_prompt(ctx)
    impact_prompt = build_impact_prompt(ctx)
    knowledge_prompt = build_knowledge_prompt(ctx, kb_search_results)

    if use_sequential:
        # --- PARTIAL SEQUENTIAL: All 3 analysis agents + KB in parallel, then validate ---
        logger.info("🤖 Phase 1: Root + Impact + Knowledge (parallel)")

        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {
                'root_cause': pool.submit(_run_agent, 'RootCause', root_prompt, llm_callable, parse_root_cause),
                'impact':     pool.submit(_run_agent, 'Impact', impact_prompt, llm_callable, parse_impact),
                'knowledge':  pool.submit(_run_agent, 'Knowledge', knowledge_prompt, llm_callable, parse_knowledge, 600),
            }
            phase1 = {name: f.result() for name, f in futures.items()}

        # Unpack phase 1
        _, result.root_cause, rc_time, rc_err = phase1['root_cause']
        _, result.impact, imp_time, imp_err = phase1['impact']
        _, result.knowledge, kb_time, kb_err = phase1['knowledge']
        
        result.agent_times['root_cause'] = rc_time
        result.agent_times['impact'] = imp_time
        result.agent_times['knowledge'] = kb_time
        
        if rc_err:
            result.errors.append(f"RootCause: {rc_err}")
        if imp_err:
            result.errors.append(f"Impact: {imp_err}")
        if kb_err:
            result.errors.append(f"Knowledge: {kb_err}")

        # Build context for Actions from phase 1
        agent_context_parts = []
        
        # Include KB suggestions
        if result.knowledge.suggested_system:
            agent_context_parts.append(
                f"KB Suggests: {result.knowledge.suggested_system} "
                f"(confidence: {result.knowledge.confidence:.0%})"
            )
        
        if result.root_cause.trigger:
            agent_context_parts.append(f"Root Cause: {result.root_cause.trigger}")
            if result.root_cause.causal_chain:
                agent_context_parts.append(f"Chain: {' → '.join(result.root_cause.causal_chain)}")
        
        if result.impact.user_impact:
            agent_context_parts.append(f"Impact: {result.impact.user_impact}")
        if result.impact.affected_systems:
            agent_context_parts.append(f"Affected: {', '.join(result.impact.affected_systems)}")

        agent_context = '\n'.join(agent_context_parts) if agent_context_parts else None

        # Phase 2: Actions
        logger.info("🤖 Phase 2: Actions (with Phase 1 context)")
        action_prompt = build_actions_prompt(ctx, agent_context=agent_context)
        _, result.actions, act_time, act_err = _run_agent(
            'Actions', action_prompt, llm_callable, parse_actions
        )
        result.agent_times['actions'] = act_time
        if act_err:
            result.errors.append(f"Actions: {act_err}")

    else:
        # --- PARALLEL: all 4 at once ---
        action_prompt = build_actions_prompt(ctx)

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {
                'root_cause': pool.submit(_run_agent, 'RootCause', root_prompt, llm_callable, parse_root_cause),
                'impact':     pool.submit(_run_agent, 'Impact', impact_prompt, llm_callable, parse_impact),
                'actions':    pool.submit(_run_agent, 'Actions', action_prompt, llm_callable, parse_actions),
                'knowledge':  pool.submit(_run_agent, 'Knowledge', knowledge_prompt, llm_callable, parse_knowledge, 600),
            }
            results = {name: f.result() for name, f in futures.items()}

        for agent_name, (_, output, elapsed, err) in results.items():
            result.agent_times[agent_name] = elapsed
            if err:
                result.errors.append(f"{agent_name}: {err}")

        result.root_cause = results['root_cause'][1]
        result.impact = results['impact'][1]
        result.actions = results['actions'][1]
        result.knowledge = results['knowledge'][1]

    # --- ENHANCED Consistency check (compares 3 analysis agents only) ---
    logger.info("🤖 Enhanced consistency check: comparing Root Cause, Impact, and Actions agents...")
    consistency_prompt = build_consistency_prompt_v2(
        result.root_cause, result.impact, result.actions, result.knowledge
    )
    _, result.consistency, cons_time, cons_err = _run_agent(
        'Consistency', consistency_prompt, llm_callable, parse_consistency_v2, max_tokens=400
    )
    result.agent_times['consistency'] = cons_time
    if cons_err:
        result.errors.append(f"Consistency: {cons_err}")

    # Log consistency results
    if result.consistency.factual_conflicts:
        logger.warning(
            f"⚠️  FACTUAL CONFLICTS: {len(result.consistency.factual_conflicts)} - "
            "Analysis agents disagree on objective facts (system ID, severity, etc.)"
        )
    
    if result.consistency.interpretation_conflicts:
        logger.info(
            f"ℹ️  Interpretation variance: {len(result.consistency.interpretation_conflicts)} "
            "(expected - multiple perspectives on root cause/actions)"
        )
    
    logger.info(f"Quality: {result.consistency.quality_assessment}")

    result.total_time = time.time() - start
    logger.info(f"🤖 Multi-agent v2.0 complete: {result.total_time:.2f}s ({result.mode_used})")

    return result


# Backward compatibility: alias for old function name
run_multi_agent = run_multi_agent_v2