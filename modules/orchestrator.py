"""
Main Orchestrator - Coordinates all components
"""
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import logging

from .mcp_integration import MCPIntegration
from .transcript_processor import TranscriptProcessor
from .psychological_analyzer import PsychologicalAnalyzer
from .workspace_automation import WorkspaceAutomation

logger = logging.getLogger(__name__)

class OMIGeminiOrchestrator:
    """Main orchestrator coordinating OMI, Gemini, and Google Workspace"""

    def __init__(self):
        self.mcp_client = MCPIntegration()
        self.transcript_processor = TranscriptProcessor()
        self.psychological_analyzer = PsychologicalAnalyzer()
        self.workspace_automation = WorkspaceAutomation()

        logger.info("OMI-Gemini Orchestrator initialized")

    async def process_memory_webhook(self, memory_data: Dict[str, Any], uid: str) -> Dict[str, Any]:
        """
        Process memory creation webhook from OMI app

        This is the main entry point when OMI app triggers the webhook

        Args:
            memory_data: Memory object from OMI webhook
            uid: User unique identifier

        Returns:
            Processing result dictionary
        """
        logger.info(f"Processing memory webhook for user {uid}, memory ID: {memory_data.get('id')}")

        result = {
            "success": False,
            "memory_id": memory_data.get("id"),
            "uid": uid,
            "steps_completed": [],
            "errors": []
        }

        try:
            # Step 1: Extract transcript from memory
            transcript_raw = self._extract_transcript(memory_data)
            if not transcript_raw:
                logger.warning("No transcript found in memory data")
                result["errors"].append("No transcript available")
                return result

            result["steps_completed"].append("transcript_extracted")

            # Step 2: Clean transcript with Gemini
            cleaned_result = self.transcript_processor.process_transcript(transcript_raw)

            if not cleaned_result["success"]:
                logger.error(f"Transcript cleaning failed: {cleaned_result.get('error')}")
                result["errors"].append(f"Cleaning failed: {cleaned_result.get('error')}")
                return result

            cleaned_transcript = cleaned_result["cleaned_text"]
            result["model_used"] = cleaned_result.get("model_used")
            result["steps_completed"].append("transcript_cleaned")

            # Step 3: Psychological analysis
            analysis = self.psychological_analyzer.analyze(cleaned_transcript, include_details=True)

            if "error" in analysis:
                logger.warning(f"Psychological analysis had issues: {analysis['error']}")
                result["errors"].append(f"Analysis warning: {analysis['error']}")
            else:
                result["steps_completed"].append("psychological_analysis")

            result["analysis"] = {
                "adhd_score": analysis.get("adhd_indicators", {}).get("score", 0),
                "anxiety_score": analysis.get("anxiety_patterns", {}).get("score", 0),
                "emotional_tone": analysis.get("emotional_tone", {}).get("primary_emotion", "unknown")
            }

            # Step 4: Save analysis as memory in OMI
            try:
                memory_content = self._format_analysis_for_memory(analysis, cleaned_result)

                # OMI API requires both 'text' and 'memories' fields
                # Using MCP tool 'create_memory'
                await self.mcp_client.call_tool("create_memory", {
                    "memory_content": memory_content,
                    "structured": {
                        "category": "analysis",
                        "tags": ["gemini_analysis", "psychological_insight"]
                    }
                })

                result["steps_completed"].append("memory_saved")
                result["created_memories"] = 1 # MCP doesn't return count easily

            except Exception as e:
                logger.error(f"Failed to save memory: {str(e)}")
                result["errors"].append(f"Memory save failed: {str(e)}")

            # Step 5: Check if email automation needed (if authenticated)
            email_created = False
            try:
                if self.workspace_automation.credentials:
                    should_email = self.workspace_automation.should_create_email(
                        analysis, cleaned_transcript
                    )

                    if should_email:
                        draft_id = self.workspace_automation.create_email_draft(
                            context=f"Analysis Summary:\n{self.psychological_analyzer.generate_summary(analysis)}\n\nTranscript:\n{cleaned_transcript}"
                        )

                        if draft_id:
                            result["email_draft_id"] = draft_id
                            result["steps_completed"].append("email_draft_created")
                            email_created = True
            except Exception as e:
                logger.error(f"Email automation failed: {str(e)}")
                result["errors"].append(f"Email automation: {str(e)}")

            # Step 6: Send notification to OMI app
            try:
                notification_msg = self._build_notification_message(
                    analysis, email_created, len(result["steps_completed"])
                )

                # Notification via MCP not yet supported, skipping or using fallback
                # notification_sent = self.omi_client.send_notification(notification_msg, uid)
                notification_sent = False  # Default to False when notification is disabled

                if notification_sent:
                    result["steps_completed"].append("notification_sent")

            except Exception as e:
                logger.error(f"Notification failed: {str(e)}")
                result["errors"].append(f"Notification: {str(e)}")

            # Mark as successful if core steps completed
            result["success"] = "transcript_cleaned" in result["steps_completed"]

            logger.info(f"Memory processing completed. Steps: {len(result['steps_completed'])}, Errors: {len(result['errors'])}")

            return result

        except Exception as e:
            logger.error(f"Unexpected error in memory processing: {str(e)}", exc_info=True)
            result["errors"].append(f"Unexpected error: {str(e)}")
            return result

    async def process_realtime_transcript(self, segments: list[Dict[str, Any]], session_id: str, uid: str) -> Dict[str, Any]:
        """
        Process real-time transcript segments from OMI

        Args:
            segments: List of transcript segments
            session_id: Session identifier for deduplication
            uid: User identifier

        Returns:
            Processing result
        """
        logger.info(f"Processing realtime transcript, session: {session_id}, segments: {len(segments)}")

        # Combine segments into full text
        full_text = " ".join([seg.get("text", "") for seg in segments])

        if not full_text.strip():
            return {"success": False, "error": "Empty transcript"}

        # For real-time, we might do lightweight processing
        # Full analysis can wait for memory creation
        return {
            "success": True,
            "session_id": session_id,
            "segments_processed": len(segments),
            "note": "Real-time processing - full analysis on memory creation"
        }

    async def manual_conversation_analysis(self, limit: int = 5) -> list[Dict[str, Any]]:
        """
        Manually process recent conversations from OMI

        Args:
            limit: Number of recent conversations to process

        Returns:
            List of analysis results
        """
        logger.info(f"Manual analysis of {limit} recent conversations")

        try:
            # Use MCP to get conversations
            conversations_data = await self.mcp_client.call_tool("get_conversations", {})
            # MCP returns a list of conversations directly or wrapped?
            # Based on test output: get_conversations: Retrieve a list of conversation metadata.
            
            # We need to handle the format returned by MCP
            conversations = []
            if isinstance(conversations_data, list):
                conversations = conversations_data
            elif isinstance(conversations_data, dict):
                # Try to find list in common keys
                if "conversations" in conversations_data and isinstance(conversations_data["conversations"], list):
                    conversations = conversations_data["conversations"]
                elif "data" in conversations_data and isinstance(conversations_data["data"], list):
                    conversations = conversations_data["data"]
                elif "items" in conversations_data and isinstance(conversations_data["items"], list):
                    conversations = conversations_data["items"]
            
            # Limit locally since MCP tool might not support limit param
            conversations = conversations[:limit]

            results = []
            for conv in conversations:
                logger.info(f"Analyzing conversation {conv.get('id')}")

                # Extract text
                text = conv.get("text", "")
                if not text:
                    continue

                # Process
                cleaned = self.transcript_processor.process_transcript(text)
                if not cleaned["success"]:
                    continue

                analysis = self.psychological_analyzer.analyze(cleaned["cleaned_text"])

                results.append({
                    "conversation_id": conv.get("id"),
                    "analysis": analysis,
                    "cleaned_transcript": cleaned["cleaned_text"],
                    "model_used": cleaned["model_used"]
                })

            logger.info(f"Completed analysis of {len(results)} conversations")
            return results

        except Exception as e:
            logger.error(f"Manual analysis failed: {str(e)}")
            return []

    def _extract_transcript(self, memory_data: Dict[str, Any]) -> Optional[str]:
        """Extract transcript text from memory data"""

        # Try multiple possible locations
        if "transcript_segments" in memory_data:
            segments = memory_data["transcript_segments"]
            return " ".join([seg.get("text", "") for seg in segments])

        if "text" in memory_data:
            return memory_data["text"]

        if "structured" in memory_data and "overview" in memory_data["structured"]:
            return memory_data["structured"]["overview"]

        return None

    def _format_analysis_for_memory(self, analysis: Dict[str, Any], cleaned_result: Dict[str, Any]) -> str:
        """Format analysis results as memory content"""

        summary = self.psychological_analyzer.generate_summary(analysis)

        memory_text = f"""Gemini AI Analysis (Model: {cleaned_result.get('model_used', 'unknown')})

{summary}

Generated: {datetime.now(timezone.utc).isoformat()}

This analysis is generated automatically and should not replace professional evaluation."""

        return memory_text

    def _build_notification_message(self, analysis: Dict[str, Any], email_created: bool, steps_count: int) -> str:
        """Build notification message for OMI app"""

        adhd_score = analysis.get("adhd_indicators", {}).get("score", 0)
        anxiety_score = analysis.get("anxiety_patterns", {}).get("score", 0)

        msg = f"Gemini analysis complete ({steps_count} steps)"

        if adhd_score >= 5 or anxiety_score >= 5:
            msg += f" - Patterns detected (ADHD:{adhd_score}/10, Anxiety:{anxiety_score}/10)"

        if email_created:
            msg += " - Email draft created"

        return msg

    def process_audio_stream(self, audio_bytes: bytes, sample_rate: int, uid: str) -> Dict[str, Any]:
        """
        Process raw audio stream from OMI device

        Args:
            audio_bytes: Raw PCM audio bytes
            sample_rate: Audio sample rate
            uid: User identifier

        Returns:
            Processing result with buffer info
        """
        logger.info(f"Processing audio stream for user {uid}, {len(audio_bytes)} bytes at {sample_rate}Hz")

        # For now, we acknowledge receipt
        # Future: Could buffer audio for offline transcription or analysis
        return {
            "buffered": True,
            "buffer_size": len(audio_bytes),
            "sample_rate": sample_rate,
            "note": "Audio stream received - OMI handles transcription"
        }

    async def close(self):
        """Cleanup resources"""
        await self.mcp_client.close()
        logger.info("Orchestrator closed")
