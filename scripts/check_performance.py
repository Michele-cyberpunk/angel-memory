#!/usr/bin/env python3
"""
Quick Performance Check Script

Simple script to verify if the webhook system meets the <1s response time requirement.
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

async def check_performance():
    """Quick performance check"""

    base_url = f"http://localhost:{WebhookConfig.PORT}"

    # Test data - small transcript for quick check
    test_memory = {
        "id": f"perf_check_{int(time.time())}",
        "created_at": "2024-01-01T00:00:00Z",
        "structured": {
            "overview": "Performance check conversation",
            "category": "conversation"
        },
        "transcript_segments": [
            {"text": "Hello, this is a quick performance check to ensure the system responds within 1 second.", "start": 0, "end": 5}
        ],
        "text": "Hello, this is a quick performance check to ensure the system responds within 1 second."
    }

    async with aiohttp.ClientSession() as session:
        url = f"{base_url}/webhook/memory?uid=perf_check_user"
        start_time = time.time()

        try:
            async with session.post(url, json=test_memory, headers={"Content-Type": "application/json"}) as response:
                end_time = time.time()
                response_time = end_time - start_time

                if response.status == 200:
                    result = await response.json()
                    meets_requirement = response_time < 1.0

                    print("✅ Performance Check Results:")
                    print(".3f")
                    print(f"   Meets <1s requirement: {'✅ YES' if meets_requirement else '❌ NO'}")
                    print(f"   Response status: {response.status}")
                    print(f"   Steps completed: {len(result.get('steps_completed', []))}")

                    if not meets_requirement:
                        print("\n⚠️  WARNING: Response time exceeds 1 second target!")
                        print("   Consider the following optimizations:")
                        print("   - Check if workspace automation is running in background")
                        print("   - Verify psychological analysis caching is working")
                        print("   - Monitor system resources (CPU/memory)")
                        print("   - Run benchmark_webhook.py for detailed analysis")

                    return meets_requirement

                else:
                    print(f"❌ Performance check failed with status {response.status}")
                    return False

        except Exception as e:
            print(f"❌ Performance check failed: {e}")
            return False

if __name__ == "__main__":
    print("Running quick performance check...")
    success = asyncio.run(check_performance())
    sys.exit(0 if success else 1)