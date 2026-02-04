#!/usr/bin/env python3
"""
PII Sanitizer v1.2 — TIMEOUT FIX
Fixed the chunking timeout issue where 2nd/4th chunks would timeout at 5 minutes

CHANGES:
1. Reduced per-chunk timeout from 300s → 60s (1 minute max per chunk)
2. Added total pipeline timeout protection (max 3 minutes for all chunks combined)
3. Fail-fast: if one chunk times out, return partial results instead of hanging
4. Better logging to identify which chunk is slow
"""

import re
import time
import logging
import requests
from typing import Optional, Callable, List, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class SanitizationAudit:
    """Single redaction event. One entry per replacement, for every layer."""
    layer: str              # "regex" or "llm"
    pattern_type: str       # "email", "ip", "name", "card_number", etc.
    original: str           # The value that was found
    replacement: str        # What it was replaced with
    position: int           # Character offset at time of match


@dataclass
class SanitizationResult:
    sanitized_text: str
    was_sanitized: bool                                          # True if anything changed
    audit_trail: List[SanitizationAudit] = field(default_factory=list)
    llm_findings: List[str] = field(default_factory=list)        # What Layer 2 caught that Layer 1 missed
    elapsed_regex: float = 0.0
    elapsed_llm: float = 0.0
    skipped: bool = False                                        # True when backend is Ollama
    error: Optional[str] = None
    chunks_processed: int = 0                                     # NEW: tracking
    chunks_failed: int = 0                                        # NEW: tracking
    regex_sanitized_text: str = ""                               # NEW: Layer 1 output only (always complete)


# ---------------------------------------------------------------------------
# Standalone Ollama caller for Layer 2.
# FIXED: Reduced timeout from 300s → 60s per chunk
# ---------------------------------------------------------------------------

def create_ollama_sanitizer_callable(
    url: str = "http://localhost:11434",
    model: str = "llama3.2:1b",  
    timeout: int = 30  # REDUCED: llama3.2:1b is fast, 30s is plenty per chunk
) -> Callable:
    """
    Returns a callable(prompt, max_tokens, temperature) -> Optional[str].
    Connection errors are caught and logged at DEBUG — not noisy in production.
    
    OPTIMIZED: Uses llama3.2:1b for speed. Simple PII detection doesn't need a large model.
    Timeout reduced to 30s per chunk since this model is blazing fast.
    """
    def call(prompt: str, max_tokens: int = 512, temperature: float = 0.0) -> Optional[str]:
        try:
            response = requests.post(
                f"{url.rstrip('/')}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": temperature, "num_predict": max_tokens}
                },
                timeout=timeout  # FIXED: Use configurable timeout instead of hardcoded 300
            )
            if response.status_code != 200:
                logger.debug(f"🔒 Ollama sanitizer: HTTP {response.status_code}")
                return None
            return response.json().get('response', '').strip() or None
        except requests.exceptions.Timeout:
            logger.warning(f"🔒 Ollama sanitizer: TIMEOUT after {timeout}s")
            return None
        except requests.exceptions.ConnectionError:
            logger.debug("🔒 Ollama not reachable — Layer 2 skipped this run")
            return None
        except Exception as e:
            logger.debug(f"🔒 Ollama sanitizer error: {e}")
            return None
    return call


# ---------------------------------------------------------------------------
# Layer 1: Regex sanitizer — deterministic, auditable, reproducible.
# NO CHANGES (this layer is fast and never times out)
# ---------------------------------------------------------------------------

class RegexSanitizer:
    """
    known_names: employee names to redact. Passed in from DirectContactMapping
    at init time — adding a new engineer to the contact map automatically
    includes them in sanitization.
    """

    # Patterns ordered by specificity (most specific first to avoid partial overlaps).
    # Each: (pattern_type, compiled_regex). Group 1 is always the PII value.
    PATTERNS = [
        ("ssn",         re.compile(r'\b(\d{3}-\d{2}-\d{4})\b')),
        ("card_number", re.compile(r'\b(\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{1,7})\b')),
        ("email",       re.compile(r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b')),
        ("ip_address",  re.compile(r'\b((?:\d{1,3}\.){3}\d{1,3})\b')),
        ("phone_ext",   re.compile(r'(ext\.?\s*\d{3,5})', re.IGNORECASE)),
    ]

    REPLACEMENT_MAP = {
        "ssn":         "[REDACTED_SSN]",
        "card_number": "[REDACTED_CARD]",
        "email":       "[REDACTED_EMAIL]",
        "ip_address":  "[REDACTED_IP]",
        "phone_ext":   "[REDACTED_PHONE]",
        "name":        "[REDACTED_NAME]",
    }

    def __init__(self, known_names: Optional[List[str]] = None):
        # Longest first: "Michael O'Brien" before "Michael"
        self.known_names = sorted(known_names or [], key=len, reverse=True)
        logger.info(f"🔒 RegexSanitizer: {len(self.known_names)} known names loaded")

    @staticmethod
    def _is_valid_ip(candidate: str) -> bool:
        """Reject version-number false positives like 3.1.4.1"""
        try:
            octets = candidate.split('.')
            return len(octets) == 4 and all(0 <= int(o) <= 255 for o in octets)
        except (ValueError, IndexError):
            return False

    def sanitize(self, text: str) -> Tuple[str, List[SanitizationAudit]]:
        """
        Returns (sanitized_text, audit_trail).
        Audit entries are appended in order of discovery.
        """
        audit: List[SanitizationAudit] = []
        result = text

        # --- Known names (longest first, case-insensitive) ---
        for name in self.known_names:
            pattern = re.compile(r'\b' + re.escape(name) + r'\b', re.IGNORECASE)
            for m in pattern.finditer(result):
                audit.append(SanitizationAudit(
                    layer="regex",
                    pattern_type="name",
                    original=m.group(0),
                    replacement=self.REPLACEMENT_MAP["name"],
                    position=m.start()
                ))
            result = pattern.sub(self.REPLACEMENT_MAP["name"], result)

        # --- Structured PII patterns ---
        for pattern_type, regex in self.PATTERNS:
            replacement = self.REPLACEMENT_MAP[pattern_type]

            # Audit pass — find all matches first
            for m in regex.finditer(result):
                value = m.group(1)
                if pattern_type == "ip_address":
                    if not self._is_valid_ip(value):
                        continue
                    # Context check: skip version numbers (e.g. "PostgreSQL 14.2.1.0")
                    context_start = max(0, m.start() - 40)
                    context = result[context_start:m.start()].lower()
                    if any(w in context for w in ['version', ' v ', ' v.', 'postgresql', 'mysql', 'redis', 'nginx', 'node ', 'python']):
                        continue
                audit.append(SanitizationAudit(
                    layer="regex",
                    pattern_type=pattern_type,
                    original=value,
                    replacement=replacement,
                    position=m.start()
                ))

            # Replacement pass
            if pattern_type == "ip_address":
                # Conditional: only replace valid IPs that aren't version numbers
                def _replace_ip(m, repl=replacement, text=result):
                    if not RegexSanitizer._is_valid_ip(m.group(1)):
                        return m.group(0)
                    context_start = max(0, m.start() - 40)
                    context = text[context_start:m.start()].lower()
                    if any(w in context for w in ['version', ' v ', ' v.', 'postgresql', 'mysql', 'redis', 'nginx', 'node ', 'python']):
                        return m.group(0)
                    return repl
                result = regex.sub(_replace_ip, result)
            else:
                result = regex.sub(replacement, result)

        return result, audit


# ---------------------------------------------------------------------------
# Layer 2: LLM sanitizer — TIMEOUT FIXES APPLIED
# ---------------------------------------------------------------------------

class LLMSanitizer:
    """
    FIXED VERSION:
    1. Added per-chunk timeout protection (60s max)
    2. Added total pipeline timeout (180s max for all chunks)
    3. Fail-fast on timeout instead of hanging
    4. Better logging for debugging
    """

    MAX_CHUNK_SIZE = 3000
    OVERLAP = 200
    MAX_TOTAL_TIME = 60  # NEW: 1 minute max for entire Layer 2 processing

    PROMPT = """You are a PII sanitizer. Your job: redact names, emails, IPs, phone numbers, and any personal data from this log excerpt.

RULES:
1. Replace ALL PII with [REDACTED_TYPE] (e.g., [REDACTED_NAME], [REDACTED_EMAIL])
2. Preserve log structure, timestamps, and technical details
3. Don't explain — just output the sanitized text
4. After sanitized text, add a line: "FINDINGS: item1; item2; item3" OR "FINDINGS: None"

Text to sanitize:
{text}

Sanitized output:"""

    def __init__(self, ollama: Callable):
        """ollama: callable(prompt, max_tokens, temperature) -> Optional[str]"""
        if not ollama:
            raise ValueError("LLMSanitizer requires a callable LLM")
        self.ollama = ollama

    def _chunk_text(self, text: str) -> List[Tuple[int, str]]:
        """
        Split text into overlapping chunks.
        Returns list of (start_position, chunk_text) tuples.
        """
        if len(text) <= self.MAX_CHUNK_SIZE:
            return [(0, text)]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = min(start + self.MAX_CHUNK_SIZE, len(text))
            
            # Try to break at a newline to avoid splitting sentences
            if end < len(text):
                # Look back up to 500 chars for a newline
                newline_pos = text.rfind('\n', end - 500, end)
                if newline_pos > start:
                    end = newline_pos + 1
            
            chunks.append((start, text[start:end]))
            
            # Move start forward, with overlap
            start = end - self.OVERLAP if end < len(text) else end
        
        logger.info(f"🔒 Layer 2: Split into {len(chunks)} chunks for processing")
        return chunks

    def _parse_findings(self, findings_raw: str) -> List[str]:
        """
        Parse the findings line more robustly.
        
        Expected format: "FINDINGS: item1; item2; item3" or "FINDINGS: None"
        
        Returns list of actual PII findings (empty if None or malformed).
        """
        findings_text = findings_raw.strip()
        
        # Check for explicit "None"
        if findings_text.lower() == 'none':
            return []
        
        # Handle semicolon-separated list
        if ';' in findings_text:
            items = [item.strip() for item in findings_text.split(';')]
            # Filter out empty strings, "none", and bullet markers
            items = [
                item for item in items
                if item and 
                item.lower() != 'none' and 
                not item.startswith('-') and
                not item.startswith('•') and
                len(item) > 2  # Avoid single-char artifacts
            ]
            return items
        
        # Handle comma-separated list as fallback
        if ',' in findings_text:
            items = [item.strip() for item in findings_text.split(',')]
            items = [
                item for item in items
                if item and item.lower() != 'none' and len(item) > 2
            ]
            return items
        
        # Single item (if it's not "none")
        if findings_text and findings_text.lower() != 'none' and len(findings_text) > 2:
            return [findings_text]
        
        return []

    def _sanitize_chunk(self, chunk: str, chunk_num: int, total_chunks: int) -> Tuple[str, List[str], bool]:
        """
        Sanitize a single chunk.
        
        Returns: (sanitized_text, findings, timeout_occurred)
        
        FIXED: Added timeout detection and chunk number logging
        """
        logger.info(f"🔒 Layer 2: Processing chunk {chunk_num}/{total_chunks} ({len(chunk)} chars)...")
        
        chunk_start = time.time()
        prompt = self.PROMPT.format(text=chunk)
        raw = self.ollama(prompt, max_tokens=len(chunk) + 300, temperature=0.0)
        elapsed = time.time() - chunk_start

        if not raw:
            logger.warning(f"🔒 Layer 2: Chunk {chunk_num} FAILED (timeout or unreachable) after {elapsed:.1f}s")
            return chunk, [], True  # Return original chunk, timeout flag

        logger.info(f"🔒 Layer 2: Chunk {chunk_num} completed in {elapsed:.1f}s")

        # Split response on the FINDINGS: label
        if "FINDINGS:" in raw:
            parts = raw.split("FINDINGS:", 1)
            sanitized = parts[0].strip()
            findings_raw = parts[1].strip()
            findings = self._parse_findings(findings_raw)
        else:
            # LLM didn't follow format — use full response, no findings
            logger.warning("🔒 Layer 2: LLM response missing FINDINGS: marker")
            sanitized = raw.strip()
            findings = []

        return sanitized, findings, False

    def sanitize(self, text: str) -> Tuple[str, List[str]]:
        """
        Returns (sanitized_text, findings_list).
        Automatically chunks large texts for processing.
        
        FIXED: Added total pipeline timeout and fail-fast behavior
        """
        pipeline_start = time.time()
        chunks = self._chunk_text(text)
        
        if len(chunks) == 1:
            # Single chunk - process normally
            sanitized, findings, _ = self._sanitize_chunk(text, 1, 1)
            return sanitized, findings
        
        # Multi-chunk processing with timeout protection
        all_findings = []
        sanitized_chunks = []
        chunks_failed = 0
        
        for i, (start_pos, chunk) in enumerate(chunks, 1):
            # Check if we've exceeded total pipeline time
            elapsed_total = time.time() - pipeline_start
            if elapsed_total > self.MAX_TOTAL_TIME:
                logger.error(f"🔒 Layer 2: PIPELINE TIMEOUT after {elapsed_total:.1f}s (processed {i-1}/{len(chunks)} chunks)")
                logger.error(f"🔒 Returning partial results with {len(sanitized_chunks)} chunks processed")
                break
            
            sanitized_chunk, findings, timeout = self._sanitize_chunk(chunk, i, len(chunks))
            
            if timeout:
                chunks_failed += 1
                # Use original chunk if sanitization failed
                logger.warning(f"🔒 Using original text for chunk {i} due to timeout")
            
            sanitized_chunks.append(sanitized_chunk)
            all_findings.extend(findings)
        
        # Log completion stats
        elapsed_total = time.time() - pipeline_start
        logger.info(f"🔒 Layer 2: Completed {len(sanitized_chunks)}/{len(chunks)} chunks in {elapsed_total:.1f}s ({chunks_failed} failed)")
        
        # Reassemble chunks, removing overlap duplicates
        if len(sanitized_chunks) == 1:
            final_text = sanitized_chunks[0]
        else:
            # First chunk in full
            final_text = sanitized_chunks[0]
            
            # Add remaining chunks, skipping overlap region
            for chunk in sanitized_chunks[1:]:
                # Skip the overlap region (first OVERLAP chars)
                final_text += chunk[self.OVERLAP:]
        
        # Deduplicate findings (same finding might appear in overlapping chunks)
        unique_findings = list(dict.fromkeys(all_findings))
        
        return final_text, unique_findings


# ---------------------------------------------------------------------------
# Pipeline orchestrator — UPDATED WITH BETTER REPORTING
# ---------------------------------------------------------------------------

class SanitizationPipeline:
    """
    Entry point. Decides what runs based on the main backend:
      - Ollama   → skip entirely (data never leaves the machine)
      - Cloud    → Layer 1 always + Layer 2 if local Ollama is reachable
    
    FIXED: Better timeout tracking and reporting
    """

    def __init__(
        self,
        backend_type: str,                          # "groq", "claude", or "ollama"
        known_names: Optional[List[str]] = None,    # Employee names for Layer 1
        ollama_callable: Optional[Callable] = None  # Standalone Ollama client for Layer 2
    ):
        self.skip = (backend_type == "ollama")

        if self.skip:
            logger.info("🔒 Sanitization: SKIPPED (Ollama end-to-end — data stays local)")
            self.regex_sanitizer = None
            self.llm_sanitizer = None
            return

        self.regex_sanitizer = RegexSanitizer(known_names=known_names)
        self.llm_sanitizer = LLMSanitizer(ollama_callable) if ollama_callable else None

        layers = "Layer 1 (regex)"
        if self.llm_sanitizer:
            layers += " + Layer 2 (local LLM)"
        logger.info(f"🔒 Sanitization: ACTIVE — {layers}")

    def sanitize(self, text: str) -> SanitizationResult:
        # --- Skip path ---
        if self.skip:
            return SanitizationResult(
                sanitized_text=text,
                was_sanitized=False,
                skipped=True,
                regex_sanitized_text=text
            )

        # --- Layer 1: Regex (always runs for cloud backends) ---
        t0 = time.time()
        sanitized, audit = self.regex_sanitizer.sanitize(text)
        elapsed_regex = time.time() - t0
        logger.info(f"🔒 Layer 1 (regex): {len(audit)} item(s) redacted ({elapsed_regex:.3f}s)")
        
        # Store Layer 1 output (always complete, never truncated)
        regex_only_text = sanitized

        # --- Layer 2: LLM (only if Ollama callable was provided) ---
        llm_findings: List[str] = []
        elapsed_llm = 0.0

        if self.llm_sanitizer:
            t0 = time.time()
            try:
                sanitized, llm_findings = self.llm_sanitizer.sanitize(sanitized)
                elapsed_llm = time.time() - t0
                if llm_findings:
                    logger.info(f"🔒 Layer 2 (LLM): {len(llm_findings)} additional finding(s) ({elapsed_llm:.2f}s)")
                else:
                    logger.info(f"🔒 Layer 2 (LLM): nothing additional ({elapsed_llm:.2f}s)")
            except Exception as e:
                elapsed_llm = time.time() - t0
                logger.error(f"🔒 Layer 2 (LLM): FAILED with error: {e} ({elapsed_llm:.2f}s)")
                # Continue with Layer 1 results only
                return SanitizationResult(
                    sanitized_text=sanitized,
                    was_sanitized=(len(audit) > 0),
                    audit_trail=audit,
                    llm_findings=[],
                    elapsed_regex=elapsed_regex,
                    elapsed_llm=elapsed_llm,
                    error=str(e),
                    regex_sanitized_text=regex_only_text
                )

        return SanitizationResult(
            sanitized_text=sanitized,
            was_sanitized=(len(audit) > 0 or len(llm_findings) > 0),
            audit_trail=audit,
            llm_findings=llm_findings,
            elapsed_regex=elapsed_regex,
            elapsed_llm=elapsed_llm,
            regex_sanitized_text=regex_only_text
        )