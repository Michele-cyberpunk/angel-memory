#!/usr/bin/env python3
"""
Load Testing Script for Webhook Processing

Uses Locust for distributed load testing with realistic webhook payloads.
Tests system behavior under high concurrent load.
"""

import json
import time
import random
from locust import HttpUser, task, between
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import WebhookConfig

class WebhookUser(HttpUser):
    """Simulates OMI app sending webhook requests"""

    # Wait between 0.5 to 2 seconds between requests
    wait_time = between(0.5, 2.0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.test_memories = self.generate_test_memories()

    def generate_test_memories(self):
        """Generate a pool of test memory payloads"""

        memories = []

        # Small conversations (most common)
        small_transcripts = [
            "Hello, how are you today? I'm doing well, thank you for asking. How about you?",
            "Can you help me with this task? I need to understand the requirements better.",
            "Thanks for your help. I appreciate your time and expertise.",
            "Let's schedule a meeting to discuss this further. What time works for you?",
            "I have a question about the project timeline. Can we review it together?"
        ]

        for i, transcript in enumerate(small_transcripts):
            memories.append({
                "id": f"load_test_memory_small_{i}_{int(time.time())}",
                "created_at": "2024-01-01T00:00:00Z",
                "structured": {
                    "overview": f"Short conversation {i}",
                    "category": "conversation"
                },
                "transcript_segments": [
                    {"text": transcript, "start": 0, "end": len(transcript.split()) * 0.3}
                ],
                "text": transcript
            })

        # Medium conversations
        medium_transcripts = [
            """
            Hello, I wanted to discuss the project progress. We've been working on this for two weeks now,
            and I think we're making good progress on the main features. However, I'm concerned about the
            timeline. We originally planned to finish by next Friday, but some of the integration work is
            taking longer than expected. Do you think we can adjust the schedule or should we prioritize
            the core functionality first?
            """,
            """
            I've been thinking about our team structure and how we can improve collaboration. Currently,
            we have daily standups and weekly planning meetings, but I feel like we could be more efficient.
            Have you noticed any bottlenecks in our current process? I'd like to hear your thoughts on
            potentially implementing some agile practices or using different tools to streamline our workflow.
            """
        ]

        for i, transcript in enumerate(medium_transcripts):
            memories.append({
                "id": f"load_test_memory_medium_{i}_{int(time.time())}",
                "created_at": "2024-01-01T00:00:00Z",
                "structured": {
                    "overview": f"Medium conversation {i}",
                    "category": "conversation"
                },
                "transcript_segments": [
                    {"text": transcript, "start": 0, "end": len(transcript.split()) * 0.3}
                ],
                "text": transcript
            })

        # Large conversations (less frequent)
        large_transcript = """
        This is a comprehensive discussion about our quarterly planning and strategic initiatives. We started
        by reviewing the previous quarter's performance metrics, which showed strong growth in user acquisition
        but some challenges with retention rates. The team discussed various hypotheses for why users might be
        churning, including product complexity, competition, and onboarding experience. We then moved into
        planning for the next quarter, identifying key objectives around improving user experience, expanding
        our feature set, and entering new markets. The conversation covered technical architecture decisions,
        resource allocation, hiring plans, and partnership opportunities. We also discussed risk mitigation
        strategies and contingency plans for potential challenges. By the end of the meeting, we had clear
        action items, assigned owners, and timelines for each major initiative. The team felt energized about
        the direction and committed to executing on the plan.
        """ * 3

        memories.append({
            "id": f"load_test_memory_large_{int(time.time())}",
            "created_at": "2024-01-01T00:00:00Z",
            "structured": {
                "overview": "Comprehensive strategic planning discussion",
                "category": "meeting"
            },
            "transcript_segments": [
                {"text": large_transcript, "start": 0, "end": len(large_transcript.split()) * 0.3}
            ],
            "text": large_transcript
        })

        return memories

    @task(70)  # 70% small conversations
    def send_small_webhook(self):
        """Send small webhook (most common)"""
        memory = random.choice([m for m in self.test_memories if "small" in m["id"]])
        self.send_webhook(memory)

    @task(20)  # 20% medium conversations
    def send_medium_webhook(self):
        """Send medium webhook"""
        memory = random.choice([m for m in self.test_memories if "medium" in m["id"]])
        self.send_webhook(memory)

    @task(10)  # 10% large conversations
    def send_large_webhook(self):
        """Send large webhook (least common but most resource intensive)"""
        memory = random.choice([m for m in self.test_memories if "large" in m["id"]])
        self.send_webhook(memory)

    def send_webhook(self, memory_data):
        """Send webhook request with proper headers and error handling"""

        # Generate unique user ID for this request
        uid = f"load_test_user_{random.randint(1, 1000)}"

        with self.client.post(
            "/webhook/memory",
            params={"uid": uid},
            json=memory_data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "OMI-App-Load-Test/1.0"
            },
            catch_response=True
        ) as response:
            # Validate response
            if response.status_code == 200:
                response_data = response.json()
                if response_data.get("status") in ["success", "partial_success"]:
                    response.success()
                else:
                    response.failure(f"Processing failed: {response_data.get('status')}")
            elif response.status_code == 429:
                response.failure("Rate limited")
            elif response.status_code >= 500:
                response.failure(f"Server error: {response.status_code}")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(1)  # Occasional health checks
    def health_check(self):
        """Periodic health check"""
        with self.client.get("/health", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: {response.status_code}")

class SpikeTestUser(WebhookUser):
    """User class for spike testing - sends bursts of requests"""

    wait_time = between(0.1, 0.5)  # Faster requests for spike testing

    @task
    def send_burst_webhook(self):
        """Send webhook in burst pattern"""
        memory = random.choice(self.test_memories)
        self.send_webhook(memory)

if __name__ == "__main__":
    # This allows running the script directly for testing
    import locust

    # Default to webhook port if not specified
    host = os.getenv("LOCUST_HOST", f"http://localhost:{WebhookConfig.PORT}")

    print(f"Starting load test against: {host}")
    print("Run with: locust -f scripts/load_test_webhook.py --host http://localhost:8000")
    print("Or use the web UI: locust -f scripts/load_test_webhook.py --host http://localhost:8000 --web-host localhost --web-port 8089")