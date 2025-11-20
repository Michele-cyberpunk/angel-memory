"""
Example test script for OMI-Gemini Integration
"""
import sys
import os
import logging
from datetime import datetime, timezone

# Add modules to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from modules.omi_client import OMIClient
from modules.transcript_processor import TranscriptProcessor
from modules.psychological_analyzer import PsychologicalAnalyzer
from config.settings import AppSettings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_transcript_cleaning():
    """Test transcript cleaning with Gemini"""
    print("\n" + "="*60)
    print("TEST 1: Transcript Cleaning")
    print("="*60)

    processor = TranscriptProcessor()

    # Sample raw transcript with errors
    raw_transcript = """
    um so like i was thinking that maybe we could umm you know
    go to the store and like get some groceries and stuff because
    were out of milk and uhh bread i think also we need to uhh
    remember to pick up that package from the post office
    """

    print(f"\nRaw Transcript:\n{raw_transcript}\n")

    result = processor.process_transcript(raw_transcript.strip())

    print(f"Success: {result['success']}")
    print(f"Model Used: {result.get('model_used', 'N/A')}")
    print(f"Processing Time: {result.get('processing_time', 0):.2f}s")
    print(f"\nCleaned Transcript:\n{result['cleaned_text']}\n")

    return result['success']

def test_psychological_analysis():
    """Test psychological analysis"""
    print("\n" + "="*60)
    print("TEST 2: Psychological Analysis")
    print("="*60)

    analyzer = PsychologicalAnalyzer()

    # Sample transcript showing some ADHD-like patterns
    sample_text = """
    So I was working on the project, but then I remembered I need to call mom,
    oh and also I saw this article about space exploration which is super
    interesting, anyway back to the project - wait did I send that email?
    I should check. The project deadline is coming up and I'm a bit worried
    about finishing on time, there's so much to do and I keep getting distracted.
    Maybe I should make a list? Actually I already have three lists but I never
    look at them. This is stressing me out.
    """

    print(f"\nTranscript to Analyze:\n{sample_text}\n")

    analysis = analyzer.analyze(sample_text, include_details=True)

    print("\nAnalysis Results:")
    print("-" * 40)

    # ADHD indicators
    adhd = analysis.get('adhd_indicators', {})
    print(f"\nADHD Indicators: {adhd.get('score', 0)}/10 ({adhd.get('confidence', 'unknown')} confidence)")
    if adhd.get('evidence'):
        print("Evidence:")
        for ev in adhd['evidence'][:3]:  # Show first 3
            print(f"  - {ev}")

    # Anxiety patterns
    anxiety = analysis.get('anxiety_patterns', {})
    print(f"\nAnxiety Patterns: {anxiety.get('score', 0)}/10 ({anxiety.get('confidence', 'unknown')} confidence)")
    if anxiety.get('themes'):
        print("Themes:")
        for theme in anxiety['themes']:
            print(f"  - {theme}")

    # Emotional tone
    emotion = analysis.get('emotional_tone', {})
    print(f"\nEmotional Tone: {emotion.get('primary_emotion', 'unknown')}")
    print(f"Stability: {emotion.get('stability', 'unknown')}")
    print(f"Description: {emotion.get('description', 'N/A')}")

    # Overall
    print(f"\nOverall Assessment:\n{analysis.get('overall_assessment', 'N/A')}")

    # Summary
    print("\n" + "-"*40)
    summary = analyzer.generate_summary(analysis)
    print(summary)

    return 'adhd_indicators' in analysis

def test_omi_client():
    """Test OMI client connectivity"""
    print("\n" + "="*60)
    print("TEST 3: OMI Client Connectivity")
    print("="*60)

    try:
        client = OMIClient()

        # Test reading conversations
        print("\nReading last 3 conversations...")
        conversations = client.read_conversations(limit=3)

        print(f"Retrieved {len(conversations)} conversations")

        if conversations:
            print("\nFirst conversation:")
            conv = conversations[0]
            print(f"  ID: {conv.get('id')}")
            print(f"  Created: {conv.get('created_at', 'N/A')}")
            print(f"  Text preview: {conv.get('text', '')[:100]}...")

        # Test reading memories
        print("\nReading last 3 memories...")
        memories = client.read_memories(limit=3)

        print(f"Retrieved {len(memories)} memories")

        if memories:
            print("\nFirst memory:")
            mem = memories[0]
            print(f"  ID: {mem.get('id')}")
            print(f"  Created: {mem.get('created_at', 'N/A')}")

        client.close()
        return True

    except Exception as e:
        logger.error(f"OMI client test failed: {str(e)}")
        return False

def test_full_pipeline():
    """Test complete pipeline with mock data"""
    print("\n" + "="*60)
    print("TEST 4: Full Pipeline (Mock Memory Webhook)")
    print("="*60)

    from modules.orchestrator import OMIGeminiOrchestrator

    orchestrator = OMIGeminiOrchestrator()

    # Mock memory data (similar to what OMI webhook sends)
    mock_memory = {
        "id": 9999,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "transcript_segments": [
            {
                "text": "Hey umm I was thinking we should like maybe schedule a meeting to discuss the project and stuff",
                "speaker": "SPEAKER_00",
                "start": 0.0,
                "end": 5.0
            },
            {
                "text": "Yeah that sounds good um when are you free this week",
                "speaker": "SPEAKER_01",
                "start": 5.5,
                "end": 8.0
            }
        ],
        "structured": {
            "title": "Test Project Discussion",
            "overview": "Conversation about scheduling project meeting"
        }
    }

    print("\nProcessing mock memory webhook...")
    import asyncio
    result = asyncio.run(orchestrator.process_memory_webhook(mock_memory, "test_user_123"))

    print(f"\nPipeline Result:")
    print(f"Success: {result['success']}")
    print(f"Steps Completed: {result['steps_completed']}")
    print(f"Errors: {result['errors']}")

    if 'analysis' in result:
        print(f"\nQuick Analysis:")
        print(f"  ADHD Score: {result['analysis']['adhd_score']}/10")
        print(f"  Anxiety Score: {result['analysis']['anxiety_score']}/10")
        print(f"  Emotion: {result['analysis']['emotional_tone']}")

    orchestrator.close()
    return result['success']

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("OMI-GEMINI INTEGRATION - TEST SUITE")
    print("="*60)

    results = {}

    # Run tests
    try:
        results['transcript_cleaning'] = test_transcript_cleaning()
    except Exception as e:
        logger.error(f"Test 1 failed: {str(e)}")
        results['transcript_cleaning'] = False

    try:
        results['psychological_analysis'] = test_psychological_analysis()
    except Exception as e:
        logger.error(f"Test 2 failed: {str(e)}")
        results['psychological_analysis'] = False

    try:
        results['omi_client'] = test_omi_client()
    except Exception as e:
        logger.error(f"Test 3 failed: {str(e)}")
        results['omi_client'] = False

    try:
        results['full_pipeline'] = test_full_pipeline()
    except Exception as e:
        logger.error(f"Test 4 failed: {str(e)}")
        results['full_pipeline'] = False

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    for test_name, success in results.items():
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status} - {test_name}")

    total_pass = sum(results.values())
    total_tests = len(results)

    print(f"\nTotal: {total_pass}/{total_tests} tests passed")

    if total_pass == total_tests:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n⚠️  Some tests failed. Check logs for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
