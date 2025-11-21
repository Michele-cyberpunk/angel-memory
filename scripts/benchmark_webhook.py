#!/usr/bin/env python3
"""
Webhook Performance Benchmarking Script

Tests webhook processing performance with various payload sizes and concurrent requests.
Measures response times, throughput, and resource usage.
"""

import asyncio
import aiohttp
import json
import time
import statistics
from typing import List, Dict, Any
import argparse
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import WebhookConfig

class WebhookBenchmarker:
    """Benchmark webhook performance under various conditions"""

    def __init__(self, base_url: str = None, concurrent_requests: int = 10):
        self.base_url = base_url or f"http://localhost:{WebhookConfig.PORT}"
        self.concurrent_requests = concurrent_requests
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def generate_test_memory(self, size: str = "small") -> Dict[str, Any]:
        """Generate test memory data of different sizes"""

        base_memory = {
            "id": f"test_memory_{int(time.time())}",
            "created_at": "2024-01-01T00:00:00Z",
            "structured": {
                "overview": "Test conversation for benchmarking",
                "category": "conversation"
            }
        }

        if size == "small":
            transcript = "Hello, how are you today? I'm doing well, thank you for asking."
        elif size == "medium":
            transcript = """
            Hello, I wanted to discuss the project timeline. We've been working on this for several weeks now,
            and I think we're making good progress. The main challenges we've faced include coordinating
            between different teams and ensuring that all requirements are properly documented.
            Overall, I'm optimistic about the outcome, but we need to make sure we meet the deadline.
            """ * 5
        elif size == "large":
            transcript = """
            This is a comprehensive discussion about various topics including technology, business strategy,
            and personal development. We covered machine learning algorithms, their applications in modern
            business environments, the importance of continuous learning, and how to balance work-life
            demands in a fast-paced industry. The conversation touched on several key points: first, the
            evolution of AI technologies and their impact on job markets; second, the need for companies
            to adapt to changing workforce dynamics; third, the role of leadership in fostering innovation;
            and fourth, the importance of mental health awareness in professional settings. We also discussed
            specific tools and frameworks that can help teams collaborate more effectively, including project
            management software, communication platforms, and development methodologies. The discussion
            concluded with actionable insights about implementing these changes in real-world scenarios.
            """ * 20
        else:
            raise ValueError(f"Unknown size: {size}")

        base_memory["transcript_segments"] = [
            {"text": transcript, "start": 0, "end": len(transcript.split()) * 0.3}
        ]
        base_memory["text"] = transcript

        return base_memory

    async def send_webhook_request(self, memory_data: Dict[str, Any], uid: str = "benchmark_user") -> Dict[str, Any]:
        """Send a single webhook request and measure response"""

        url = f"{self.base_url}/webhook/memory?uid={uid}"
        start_time = time.time()

        try:
            async with self.session.post(
                url,
                json=memory_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                end_time = time.time()
                response_data = await response.json()

                return {
                    "success": response.status == 200,
                    "status_code": response.status,
                    "response_time": end_time - start_time,
                    "response_size": len(str(response_data)),
                    "data": response_data
                }

        except Exception as e:
            end_time = time.time()
            return {
                "success": False,
                "status_code": None,
                "response_time": end_time - start_time,
                "error": str(e)
            }

    async def benchmark_single_request(self, size: str = "small", iterations: int = 10) -> Dict[str, Any]:
        """Benchmark single requests sequentially"""

        print(f"Benchmarking single {size} requests ({iterations} iterations)...")

        results = []
        for i in range(iterations):
            memory_data = self.generate_test_memory(size)
            result = await self.send_webhook_request(memory_data)
            results.append(result)

            if (i + 1) % 5 == 0:
                print(f"  Completed {i + 1}/{iterations} requests")

        successful_results = [r for r in results if r["success"]]
        response_times = [r["response_time"] for r in successful_results]

        return {
            "test_type": "single_request",
            "size": size,
            "iterations": iterations,
            "total_requests": len(results),
            "successful_requests": len(successful_results),
            "success_rate": len(successful_results) / len(results) if results else 0,
            "avg_response_time": statistics.mean(response_times) if response_times else 0,
            "median_response_time": statistics.median(response_times) if response_times else 0,
            "min_response_time": min(response_times) if response_times else 0,
            "max_response_time": max(response_times) if response_times else 0,
            "p95_response_time": statistics.quantiles(response_times, n=20)[18] if len(response_times) >= 20 else max(response_times) if response_times else 0
        }

    async def benchmark_concurrent_requests(self, size: str = "small", concurrent: int = 10) -> Dict[str, Any]:
        """Benchmark concurrent requests"""

        print(f"Benchmarking concurrent {size} requests ({concurrent} concurrent)...")

        async def worker(worker_id: int):
            memory_data = self.generate_test_memory(size)
            result = await self.send_webhook_request(memory_data, f"benchmark_user_{worker_id}")
            return result

        start_time = time.time()
        tasks = [worker(i) for i in range(concurrent)]
        results = await asyncio.gather(*tasks)
        end_time = time.time()

        successful_results = [r for r in results if r["success"]]
        response_times = [r["response_time"] for r in successful_results]

        return {
            "test_type": "concurrent_request",
            "size": size,
            "concurrent_requests": concurrent,
            "total_requests": len(results),
            "successful_requests": len(successful_results),
            "success_rate": len(successful_results) / len(results) if results else 0,
            "total_time": end_time - start_time,
            "throughput": len(results) / (end_time - start_time),
            "avg_response_time": statistics.mean(response_times) if response_times else 0,
            "median_response_time": statistics.median(response_times) if response_times else 0,
            "min_response_time": min(response_times) if response_times else 0,
            "max_response_time": max(response_times) if response_times else 0,
            "p95_response_time": statistics.quantiles(response_times, n=20)[18] if len(response_times) >= 20 else max(response_times) if response_times else 0
        }

    async def run_comprehensive_benchmark(self) -> Dict[str, Any]:
        """Run comprehensive benchmark suite"""

        print("Starting comprehensive webhook benchmark...")
        print(f"Target URL: {self.base_url}")
        print()

        results = {
            "timestamp": time.time(),
            "target_url": self.base_url,
            "tests": []
        }

        # Test different payload sizes
        sizes = ["small", "medium", "large"]

        for size in sizes:
            print(f"\n=== Testing {size} payloads ===")

            # Single request benchmark
            single_result = await self.benchmark_single_request(size, iterations=5)
            results["tests"].append(single_result)
            print(f"Single requests: {single_result['avg_response_time']:.3f}s avg, {single_result['success_rate']*100:.1f}% success")

            # Concurrent request benchmark
            concurrent_result = await self.benchmark_concurrent_requests(size, concurrent=self.concurrent_requests)
            results["tests"].append(concurrent_result)
            print(f"Concurrent ({self.concurrent_requests}): {concurrent_result['throughput']:.2f} req/s, {concurrent_result['avg_response_time']:.3f}s avg")

        # Performance analysis
        print("\n=== Performance Analysis ===")

        # Check if we meet the <1s requirement
        all_response_times = []
        for test in results["tests"]:
            if "avg_response_time" in test:
                all_response_times.append(test["avg_response_time"])

        if all_response_times:
            overall_avg = statistics.mean(all_response_times)
            meets_requirement = overall_avg < 1.0
            print(f"Overall average response time: {overall_avg:.3f}s")
            print(f"Meets <1s requirement: {'✓' if meets_requirement else '✗'}")

            results["analysis"] = {
                "overall_avg_response_time": overall_avg,
                "meets_1s_requirement": meets_requirement,
                "recommendations": []
            }

            if not meets_requirement:
                results["analysis"]["recommendations"].append("Response time exceeds 1s target - consider optimization")
            if overall_avg > 2.0:
                results["analysis"]["recommendations"].append("Response time >2s - critical performance issue")

        return results

async def main():
    parser = argparse.ArgumentParser(description="Webhook Performance Benchmark")
    parser.add_argument("--url", default=None, help="Webhook server URL")
    parser.add_argument("--concurrent", type=int, default=10, help="Number of concurrent requests")
    parser.add_argument("--output", default="benchmark_results.json", help="Output file for results")

    args = parser.parse_args()

    async with WebhookBenchmarker(args.url, args.concurrent) as benchmarker:
        results = await benchmarker.run_comprehensive_benchmark()

        # Save results
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)

        print(f"\nResults saved to {args.output}")

        # Print summary
        print("\n=== Summary ===")
        for test in results["tests"]:
            if test["test_type"] == "single_request":
                print(f"{test['size']} single: {test['avg_response_time']:.3f}s avg")
            elif test["test_type"] == "concurrent_request":
                print(f"{test['size']} concurrent: {test['throughput']:.2f} req/s")

if __name__ == "__main__":
    asyncio.run(main())