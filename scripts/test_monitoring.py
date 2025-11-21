#!/usr/bin/env python3
"""
Test script for the monitoring system

Tests the health checks, metrics collection, and alerting functionality.
"""

import asyncio
import aiohttp
import json
import time
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import WebhookConfig

async def test_monitoring_endpoints():
    """Test all monitoring endpoints"""
    base_url = f"http://localhost:{WebhookConfig.PORT}"

    print("Testing monitoring system endpoints...")
    print(f"Server URL: {base_url}")
    print()

    async with aiohttp.ClientSession() as session:
        # Test 1: Basic health check
        print("1. Testing /health endpoint...")
        try:
            async with session.get(f"{base_url}/health") as response:
                if response.status == 200:
                    health_data = await response.json()
                    print("   ✅ Health check passed")
                    print(f"   Overall status: {health_data.get('overall_status', 'unknown')}")
                    print(f"   Checks: {len(health_data.get('checks', {}))}")
                else:
                    print(f"   ❌ Health check failed with status {response.status}")
        except Exception as e:
            print(f"   ❌ Health check error: {e}")

        # Test 2: Metrics endpoint
        print("\n2. Testing /metrics endpoint...")
        try:
            async with session.get(f"{base_url}/metrics") as response:
                if response.status == 200:
                    metrics_data = await response.json()
                    print("   ✅ Metrics endpoint accessible")
                    print(f"   System metrics: {len(metrics_data.get('system', {}))} keys")
                    print(f"   Request metrics: {len(metrics_data.get('requests', {}))} keys")
                    print(f"   Processing metrics: {len(metrics_data.get('processing', {}))} keys")
                else:
                    print(f"   ❌ Metrics endpoint failed with status {response.status}")
        except Exception as e:
            print(f"   ❌ Metrics endpoint error: {e}")

        # Test 3: Alerts endpoint
        print("\n3. Testing /alerts endpoint...")
        try:
            async with session.get(f"{base_url}/alerts") as response:
                if response.status == 200:
                    alerts_data = await response.json()
                    print("   ✅ Alerts endpoint accessible")
                    print(f"   Active alerts: {alerts_data.get('total_active', 0)}")
                else:
                    print(f"   ❌ Alerts endpoint failed with status {response.status}")
        except Exception as e:
            print(f"   ❌ Alerts endpoint error: {e}")

        # Test 4: Performance endpoint (legacy)
        print("\n4. Testing /performance endpoint...")
        try:
            async with session.get(f"{base_url}/performance") as response:
                if response.status == 200:
                    perf_data = await response.json()
                    print("   ✅ Performance endpoint accessible")
                    print(f"   Performance stats available: {'performance_stats' in perf_data}")
                else:
                    print(f"   ❌ Performance endpoint failed with status {response.status}")
        except Exception as e:
            print(f"   ❌ Performance endpoint error: {e}")

        # Test 5: Generate some test traffic
        print("\n5. Generating test traffic...")
        test_memory = {
            "id": f"monitoring_test_{int(time.time())}",
            "created_at": "2024-01-01T00:00:00Z",
            "structured": {
                "overview": "Monitoring system test",
                "category": "test"
            },
            "transcript_segments": [
                {"text": "This is a test for the monitoring system.", "start": 0, "end": 5}
            ],
            "text": "This is a test for the monitoring system."
        }

        try:
            async with session.post(
                f"{base_url}/webhook/memory?uid=test_user",
                json=test_memory,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status in [200, 207]:
                    result = await response.json()
                    print("   ✅ Test webhook processed successfully")
                    print(f"   Status: {result.get('status')}")
                    print(f"   Steps completed: {len(result.get('details', {}).get('steps_completed', []))}")
                else:
                    print(f"   ❌ Test webhook failed with status {response.status}")
        except Exception as e:
            print(f"   ❌ Test webhook error: {e}")

        # Wait a moment for metrics to be processed
        await asyncio.sleep(2)

        # Test 6: Check metrics after test traffic
        print("\n6. Checking metrics after test traffic...")
        try:
            async with session.get(f"{base_url}/metrics") as response:
                if response.status == 200:
                    metrics_data = await response.json()
                    requests = metrics_data.get('requests', {})
                    processing = metrics_data.get('processing', {})

                    print("   ✅ Post-test metrics retrieved")
                    print(f"   Total requests: {requests.get('total_requests', 0)}")
                    print(f"   Processing success rate: {processing.get('success_rate', 0):.1%}")
                else:
                    print(f"   ❌ Post-test metrics failed with status {response.status}")
        except Exception as e:
            print(f"   ❌ Post-test metrics error: {e}")

    print("\nMonitoring system test completed!")

if __name__ == "__main__":
    print("Monitoring System Test")
    print("=" * 50)

    # Check if server is running
    print("Note: Make sure the webhook server is running before running this test.")
    print("Start the server with: python webhook_server.py")
    print()

    try:
        asyncio.run(test_monitoring_endpoints())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        sys.exit(1)