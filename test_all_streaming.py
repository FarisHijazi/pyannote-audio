#!/usr/bin/env python3
"""
Master test script - runs all streaming diarization tests
"""

import sys
import subprocess
from pathlib import Path

print("=" * 70)
print("Master Test Suite for Streaming Diarization")
print("=" * 70)

tests = [
    {
        'name': 'Structure Tests',
        'script': 'test_realtime_structure.py',
        'description': 'Validates code structure and implementation',
        'required': True
    },
    {
        'name': 'Unit Tests',
        'script': 'test_realtime_unit.py',
        'description': 'Tests individual components with mocking',
        'required': True
    },
    {
        'name': 'Integration Tests',
        'script': 'test_realtime_integration.py',
        'description': 'Tests with actual pyannote models',
        'required': False  # May fail without models
    },
]

results = {}

for test in tests:
    print("\n" + "=" * 70)
    print(f"Running: {test['name']}")
    print(f"Description: {test['description']}")
    print("=" * 70)

    try:
        result = subprocess.run(
            [sys.executable, test['script']],
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode == 0:
            print(f"✅ {test['name']} PASSED")
            results[test['name']] = 'PASSED'
        else:
            print(f"❌ {test['name']} FAILED")
            print("\nError output:")
            print(result.stderr[-500:] if len(result.stderr) > 500 else result.stderr)
            results[test['name']] = 'FAILED'

            if test['required']:
                print(f"\n❌ Required test failed, stopping")
                sys.exit(1)

    except subprocess.TimeoutExpired:
        print(f"⏱️  {test['name']} TIMEOUT")
        results[test['name']] = 'TIMEOUT'
    except Exception as e:
        print(f"❌ {test['name']} ERROR: {e}")
        results[test['name']] = 'ERROR'

# Summary
print("\n" + "=" * 70)
print("Test Summary")
print("=" * 70)

for test_name, result in results.items():
    symbol = "✅" if result == "PASSED" else "❌"
    print(f"{symbol} {test_name}: {result}")

passed = sum(1 for r in results.values() if r == 'PASSED')
total = len(results)

print(f"\nTotal: {passed}/{total} test suites passed")

if passed == total:
    print("\n🎉 ALL TESTS PASSED!")
    sys.exit(0)
else:
    print("\n⚠️  Some tests did not pass")
    sys.exit(1 if any(r == 'FAILED' for r in results.values()) else 0)
