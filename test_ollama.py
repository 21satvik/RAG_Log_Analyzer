#!/usr/bin/env python3
"""
Debug what query_kb_for_incidents returns
"""

from rag_engine import RAGLogAnalyzer, BackendType
import json

print("=" * 80)
print("CHECKING WHAT query_kb_for_incidents RETURNS")
print("=" * 80)

# Initialize analyzer
analyzer = RAGLogAnalyzer(backend=BackendType.GROQ_API)

# Sample log
log_text = """
2026-01-30 09:42:17.789 ERROR [Database] Connection pool exhausted
2026-01-30 09:42:17.890 ERROR [Database] Too many connections
"""

# Query for incidents
incidents = analyzer.query_kb_for_incidents(log_text)

print(f"\nFound {len(incidents)} incidents\n")

for i, inc in enumerate(incidents, 1):
    print(f"{'=' * 80}")
    print(f"INCIDENT #{i}")
    print(f"{'=' * 80}")
    print(json.dumps(inc, indent=2))
    
    # Check for HTML in the values
    if inc.get('users_affected'):
        print(f"\n👥 users_affected:")
        print(f"   Type: {type(inc['users_affected'])}")
        print(f"   Value: {repr(inc['users_affected'])}")
        print(f"   Has <span>: {'<span' in str(inc['users_affected'])}")
    
    if inc.get('financial_impact'):
        print(f"\n💰 financial_impact:")
        print(f"   Type: {type(inc['financial_impact'])}")
        print(f"   Value: {repr(inc['financial_impact'])}")
        print(f"   Has <span>: {'<span' in str(inc['financial_impact'])}")
    
    print()

print("=" * 80)