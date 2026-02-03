#!/usr/bin/env python3
"""
Test Suite - Validate RAG v2.0
Tests contact extraction, solution matching, and end-to-end analysis
"""

import os
import sys
from pathlib import Path

# Test data
TEST_LOGS = {
    'database_connection': """
2026-01-30 08:35:47 ERROR [pool-manager] Connection pool exhausted
2026-01-30 08:35:47 ERROR [api-gateway] Cannot acquire database connection
2026-01-30 08:35:48 CRITICAL [Server_A] Max connections reached: 250/250
2026-01-30 08:35:48 ERROR [transaction] Database connection timeout after 30s
2026-01-30 08:35:49 ERROR [api] HTTP 503 Service Unavailable - connection pool exhausted
""",
    'memory_leak': """
2026-01-30 08:35:47 WARNING [jvm] Heap memory at 92% (3.68 GB / 4 GB)
2026-01-30 08:35:47 CRITICAL [gc] Full GC triggered - memory pressure critical
2026-01-30 08:35:48 INFO [gc] GC completed in 778ms, freed 1.34 GB
2026-01-30 08:35:49 WARNING [monitor] Possible memory leak detected - heap growing
""",
    'disk_space': """
2026-01-30 08:47:12 CRITICAL [filesystem] Disk usage at 98% on /data
2026-01-30 08:47:13 ERROR [upload-service] Cannot write file - no space left on device
2026-01-30 08:47:14 ERROR [database] Snapshot job failed - insufficient disk space
2026-01-30 08:47:15 CRITICAL [Server_A] File system /data is full (3.9T / 4.0T used)
""",
    'payment_timeout': """
2026-01-30 08:29:14 ERROR [payment-service] Stripe API timeout after 30s
2026-01-30 08:29:15 ERROR [Server_B] Payment processing queue backing up
2026-01-30 08:29:16 CRITICAL [api-gateway] 342 payment transactions pending
2026-01-30 08:29:17 ERROR [payment] Connection exhausted to payment microservice
"""
}

EXPECTED_RESULTS = {
    'database_connection': {
        'severity': 'CRITICAL',
        'system': 'Server_A',
        'issue_type': 'connection_pool',
        'expected_contact': 'Sarah Chen',
        'expected_solution': 'Connection Pool Recovery'
    },
    'memory_leak': {
        'severity': 'CRITICAL',
        'system': 'Memory',
        'issue_type': 'memory_leak',
        'expected_contact': 'Lisa Park',
        'expected_solution': 'Memory Leak Investigation'
    },
    'disk_space': {
        'severity': 'CRITICAL',
        'system': 'Disk',
        'issue_type': 'disk_space',
        'expected_contact': 'Tom Bradley',
        'expected_solution': 'Disk Space Emergency'
    },
    'payment_timeout': {
        'severity': 'CRITICAL',
        'system': 'Payment',
        'issue_type': 'timeout',
        'expected_contact': 'Mike Rodriguez',
        'expected_solution': 'Payment Service'
    }
}


def test_imports():
    """Test 1: Verify modules can be imported"""
    print("\n" + "="*60)
    print("TEST 1: Module Imports")
    print("="*60)
    
    try:
        from rag_engine import RAGLogAnalyzer, BackendType, Contact, Solution
        print("✅ rag_engine_v2 imported successfully")
        
        import chromadb
        print("✅ chromadb imported successfully")
        
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False


def test_kb_exists():
    """Test 2: Verify KB is embedded"""
    print("\n" + "="*60)
    print("TEST 2: Knowledge Base Check")
    print("="*60)
    
    try:
        import chromadb
        client = chromadb.PersistentClient(path="./chroma_db")
        collection = client.get_collection("company_knowledge")
        count = collection.count()
        
        print(f"✅ Knowledge base found: {count} documents")
        
        if count < 10:
            print(f"⚠️  Warning: Only {count} docs - expected 50+")
            print("   Run: python embed_knowledge_v2.py")
            return False
        
        return True
    except Exception as e:
        print(f"❌ Knowledge base not found: {e}")
        print("   Run: python embed_knowledge_v2.py first")
        return False


def test_api_key():
    """Test 3: Verify API key exists"""
    print("\n" + "="*60)
    print("TEST 3: API Key Check")
    print("="*60)
    
    groq_key = os.getenv("GROQ_API_KEY")
    claude_key = os.getenv("ANTHROPIC_API_KEY")
    
    if groq_key:
        print(f"✅ GROQ_API_KEY found: {groq_key[:15]}...")
        return True
    elif claude_key:
        print(f"✅ ANTHROPIC_API_KEY found: {claude_key[:15]}...")
        return True
    else:
        print("⚠️  No API key found - will attempt local Ollama")
        print("   For better results, set GROQ_API_KEY")
        return True  # Don't fail, just warn


def test_pattern_matching():
    """Test 4: Verify pattern matching works"""
    print("\n" + "="*60)
    print("TEST 4: Pattern Matching")
    print("="*60)
    
    try:
        from rag_engine import IntelligentMatcher
        
        passed = 0
        total = 0
        
        for log_name, log_text in TEST_LOGS.items():
            expected = EXPECTED_RESULTS[log_name]
            
            severity = IntelligentMatcher.extract_severity(log_text)
            system = IntelligentMatcher.extract_system(log_text)
            issue = IntelligentMatcher.extract_issue_type(log_text)
            
            total += 3
            
            print(f"\n  {log_name}:")
            
            if severity == expected['severity']:
                print(f"    ✅ Severity: {severity}")
                passed += 1
            else:
                print(f"    ❌ Severity: {severity} (expected {expected['severity']})")
            
            if system == expected['system']:
                print(f"    ✅ System: {system}")
                passed += 1
            else:
                print(f"    ❌ System: {system} (expected {expected['system']})")
            
            if issue == expected['issue_type']:
                print(f"    ✅ Issue: {issue}")
                passed += 1
            else:
                print(f"    ❌ Issue: {issue} (expected {expected['issue_type']})")
        
        print(f"\n  Score: {passed}/{total} ({passed/total*100:.0f}%)")
        return passed == total
    
    except Exception as e:
        print(f"❌ Pattern matching test failed: {e}")
        return False


def test_kb_extraction():
    """Test 5: Verify KB extraction works"""
    print("\n" + "="*60)
    print("TEST 5: KB Data Extraction")
    print("="*60)
    
    try:
        from rag_engine import RAGLogAnalyzer, BackendType
        
        # Use Groq if available, otherwise skip
        if not os.getenv("GROQ_API_KEY"):
            print("⚠️  Skipping - no GROQ_API_KEY")
            return True
        
        analyzer = RAGLogAnalyzer(backend=BackendType.GROQ_API)
        
        passed = 0
        total = 0
        
        for log_name, log_text in TEST_LOGS.items():
            expected = EXPECTED_RESULTS[log_name]
            
            print(f"\n  {log_name}:")
            
            # Query KB
            contacts, solutions, incidents, raw = analyzer.query_knowledge_base(log_text, n_results=5)
            
            total += 2
            
            # Check contact
            contact_found = any(expected['expected_contact'] in c.name for c in contacts)
            if contact_found:
                print(f"    ✅ Found contact: {expected['expected_contact']}")
                passed += 1
            else:
                print(f"    ❌ Contact not found: {expected['expected_contact']}")
                if contacts:
                    print(f"       Got: {', '.join(c.name for c in contacts[:2])}")
            
            # Check solution
            solution_found = any(expected['expected_solution'] in s.title for s in solutions)
            if solution_found:
                print(f"    ✅ Found solution: {expected['expected_solution']}")
                passed += 1
            else:
                print(f"    ❌ Solution not found: {expected['expected_solution']}")
                if solutions:
                    print(f"       Got: {', '.join(s.title[:30] for s in solutions[:2])}")
        
        print(f"\n  Score: {passed}/{total} ({passed/total*100:.0f}%)")
        return passed >= total * 0.75  # 75% pass rate
    
    except Exception as e:
        print(f"❌ KB extraction test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_end_to_end():
    """Test 6: Full pipeline test"""
    print("\n" + "="*60)
    print("TEST 6: End-to-End Analysis")
    print("="*60)
    
    try:
        from rag_engine import RAGLogAnalyzer, BackendType
        
        if not os.getenv("GROQ_API_KEY"):
            print("⚠️  Skipping - no GROQ_API_KEY")
            return True
        
        analyzer = RAGLogAnalyzer(backend=BackendType.GROQ_API)
        
        # Test one scenario
        log_text = TEST_LOGS['database_connection']
        expected = EXPECTED_RESULTS['database_connection']
        
        print(f"\n  Analyzing: database_connection")
        
        result = analyzer.analyze(log_text)
        
        if not result.success:
            print(f"    ❌ Analysis failed: {result.error}")
            return False
        
        checks = []
        
        # Check severity
        if result.severity == expected['severity']:
            print(f"    ✅ Severity: {result.severity}")
            checks.append(True)
        else:
            print(f"    ❌ Severity: {result.severity} (expected {expected['severity']})")
            checks.append(False)
        
        # Check system
        if result.system == expected['system']:
            print(f"    ✅ System: {result.system}")
            checks.append(True)
        else:
            print(f"    ❌ System: {result.system} (expected {expected['system']})")
            checks.append(False)
        
        # Check contacts
        if result.contacts and len(result.contacts) > 0:
            print(f"    ✅ Contacts: {len(result.contacts)} found")
            print(f"       → {result.contacts[0].name} ({result.contacts[0].email})")
            checks.append(True)
        else:
            print(f"    ❌ No contacts found")
            checks.append(False)
        
        # Check solutions
        if result.solutions and len(result.solutions) > 0:
            print(f"    ✅ Solutions: {len(result.solutions)} found")
            print(f"       → {result.solutions[0].title}")
            checks.append(True)
        else:
            print(f"    ❌ No solutions found")
            checks.append(False)
        
        # Check analysis
        if result.analysis and len(result.analysis) > 50:
            print(f"    ✅ Analysis: {len(result.analysis)} chars")
            checks.append(True)
        else:
            print(f"    ❌ Analysis too short or missing")
            checks.append(False)
        
        passed = sum(checks)
        total = len(checks)
        print(f"\n  Score: {passed}/{total} ({passed/total*100:.0f}%)")
        
        return passed >= total * 0.8  # 80% pass rate
    
    except Exception as e:
        print(f"❌ End-to-end test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("🧪 RAG v2.0 Test Suite")
    print("="*60)
    
    tests = [
        ("Module Imports", test_imports),
        ("Knowledge Base", test_kb_exists),
        ("API Keys", test_api_key),
        ("Pattern Matching", test_pattern_matching),
        ("KB Extraction", test_kb_extraction),
        ("End-to-End", test_end_to_end)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"\n❌ {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*60)
    print("📊 Test Summary")
    print("="*60)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} - {test_name}")
    
    total_passed = sum(1 for _, passed in results if passed)
    total_tests = len(results)
    
    print(f"\n  Final Score: {total_passed}/{total_tests} ({total_passed/total_tests*100:.0f}%)")
    
    if total_passed == total_tests:
        print("\n🎉 All tests passed! System is ready.")
        return 0
    elif total_passed >= total_tests * 0.8:
        print("\n⚠️  Most tests passed. System should work.")
        return 0
    else:
        print("\n❌ Too many failures. Check setup:")
        print("   1. Run: python embed_knowledge_v2.py")
        print("   2. Set: export GROQ_API_KEY='...'")
        print("   3. Check: knowledge_base/*.md files exist")
        return 1


if __name__ == "__main__":
    exit(main())