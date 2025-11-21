"""
Main Orchestrator - Coordinates all components
"""
from typing import Dict, Any, Optional, List, TypedDict, cast
from datetime import datetime, timezone, timedelta
import logging
import asyncio
from functools import lru_cache
import time
import psutil
import os
from contextlib import contextmanager

from .transcript_processor import TranscriptProcessor
from .psychological_analyzer import PsychologicalAnalyzer
from .workspace_automation import WorkspaceAutomation
from .omi_client import OMIClient
from .security import InputValidator
from .modality_processor import ProcessorRegistry, ModalityType
from .concrete_processors import (
    create_text_processor, create_audio_processor, create_image_processor
)
from config.settings import AppSettings, MultimodalConfig, MultilingualConfig, validate_all_configs

class ProcessingResult(TypedDict):
    success: bool
    memory_id: Optional[str]
    uid: str
    steps_completed: List[str]
    errors: List[str]
    warnings: List[str]
    critical_errors: List[str]
    performance_profile: Dict[str, Any]
    status: Optional[str]
    processing_time_seconds: Optional[float]
    model_used: Optional[str]
    analysis: Optional[Dict[str, Any]]
    email_queued: Optional[bool]
    calendar_queued: Optional[bool]
    presentation_queued: Optional[bool]
    workspace_automation_queued: Optional[bool]
    notification_queued: Optional[bool]
    created_memories_count: Optional[int]

# Setup logging if not already configured
if not logging.getLogger().hasHandlers():
    AppSettings.setup_logging()

logger = logging.getLogger(__name__)

@contextmanager
def profile_step(step_name: str, result_dict: Dict[str, Any]):
    """Context manager for profiling individual processing steps"""
    process = psutil.Process(os.getpid())
    start_time = time.time()
    start_memory = process.memory_info().rss / 1024 / 1024  # MB

    try:
        yield
    finally:
        end_time = time.time()
        end_memory = process.memory_info().rss / 1024 / 1024  # MB

        duration = end_time - start_time
        memory_delta = end_memory - start_memory

        result_dict[f"{step_name}_time"] = duration
        result_dict[f"{step_name}_memory_mb"] = memory_delta

        logger.debug(f"Step '{step_name}' completed in {duration:.3f}s, memory delta: {memory_delta:.2f}MB")

class OMIGeminiOrchestrator:
    """Main orchestrator coordinating OMI, Gemini, and Google Workspace"""

    def __init__(self):
        # Validate configurations
        try:
            validate_all_configs()
            logger.debug("Configuration validation successful")
        except Exception as e:
            logger.error("Configuration validation failed", extra={
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise

        try:
            self.transcript_processor = TranscriptProcessor()
            logger.debug("Transcript processor initialized")
        except Exception as e:
            logger.error("Failed to initialize transcript processor", exc_info=True, extra={
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise

        try:
            self.psychological_analyzer = PsychologicalAnalyzer()
            logger.debug("Psychological analyzer initialized")
        except Exception as e:
            logger.error("Failed to initialize psychological analyzer", exc_info=True, extra={
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise

        try:
            self.workspace_automation = WorkspaceAutomation()
            logger.debug("Workspace automation initialized")
        except Exception as e:
            logger.error("Failed to initialize workspace automation", exc_info=True, extra={
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise

        try:
            self.omi_client = OMIClient()
            logger.debug("OMI client initialized")
        except Exception as e:
            logger.error("Failed to initialize OMI client", exc_info=True, extra={
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise

        # Initialize modality processor registry
        try:
            self.processor_registry = ProcessorRegistry()

            # Register concrete processors based on configuration
            if True:  # Always enable text processing for now
                self.processor_registry.register_processor(ModalityType.TEXT, create_text_processor())

            if MultimodalConfig.ENABLE_AUDIO_PROCESSING:
                self.processor_registry.register_processor(ModalityType.AUDIO, create_audio_processor())

            if MultimodalConfig.ENABLE_IMAGE_ANALYSIS:
                self.processor_registry.register_processor(ModalityType.IMAGE, create_image_processor())

            logger.debug("Modality processors registered")
        except Exception as e:
            logger.error("Failed to initialize modality processors", exc_info=True, extra={
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise

        # Performance tracking
        self.processing_stats = {
            "total_processed": 0,
            "average_processing_time": 0,
            "success_rate": 0
        }

        logger.info("OMI-Gemini Orchestrator initialized successfully", extra={
            "components": ["transcript_processor", "psychological_analyzer", "workspace_automation", "omi_client", "modality_processors"],
            "supported_modalities": [m.value for m in self.processor_registry.list_modalities()]
        })

    async def process_memory_webhook(self, memory_data: Dict[str, Any], uid: str) -> ProcessingResult:
        """
        Process memory creation webhook from OMI app

        This is the main entry point when OMI app triggers the webhook

        Args:
            memory_data: Memory object from OMI webhook
            uid: User unique identifier

        Returns:
            Processing result dictionary
        """
        start_time = time.time()

        # Input validation and sanitization
        if not InputValidator.validate_uid(uid):
            logger.error("Invalid uid parameter", extra={
                "uid": uid,
                "uid_type": type(uid).__name__
            })
            raise ValueError("uid must be a valid non-empty string")

        try:
            memory_data = InputValidator.validate_memory_data(memory_data)
        except ValueError as e:
            logger.error("Invalid memory_data", extra={
                "uid": uid,
                "error": str(e)
            })
            raise

        logger.info("Starting memory webhook processing", extra={
            "uid": uid,
            "memory_id": memory_data.get('id'),
            "memory_keys": list(memory_data.keys()),
            "processing_start_time": start_time
        })

        result: ProcessingResult = {
            "success": False,
            "memory_id": memory_data.get("id"),
            "uid": uid,
            "steps_completed": [],
            "errors": [],
            "warnings": [],
            "critical_errors": [],
            "performance_profile": {},
            "status": None,
            "processing_time_seconds": None,
            "model_used": None,
            "analysis": None,
            "email_queued": False,
            "calendar_queued": False,
            "presentation_queued": False,
            "workspace_automation_queued": False,
            "notification_queued": False,
            "created_memories_count": 0
        }

        try:
            # Step 1: Extract transcript from memory
            with profile_step("transcript_extraction", result["performance_profile"]):
                transcript_raw = self._extract_transcript(memory_data)
                if not transcript_raw:
                    logger.warning("No transcript found in memory data", extra={
                        "uid": uid,
                        "memory_id": memory_data.get('id'),
                        "memory_keys": list(memory_data.keys())
                    })
                    result["errors"].append("No transcript available")
                    return result

                result["steps_completed"].append("transcript_extracted")
                logger.debug("Transcript extracted successfully", extra={
                    "uid": uid,
                    "transcript_length": len(transcript_raw)
                })

                # Early return for very short transcripts (optimize for <1s response)
                if len(transcript_raw.strip()) < 20:
                    logger.info("Very short transcript detected, skipping full processing for speed", extra={
                        "uid": uid,
                        "transcript_length": len(transcript_raw)
                    })
                    result["success"] = True
                    result["status"] = "success"
                    result["processing_time_seconds"] = time.time() - start_time
                    return result

            # Step 2: Clean transcript with Gemini
            with profile_step("transcript_cleaning", result["performance_profile"]):
                cleaned_result = self.transcript_processor.process_transcript(transcript_raw)

                if not cleaned_result["success"]:
                    logger.error("Transcript cleaning failed", extra={
                        "uid": uid,
                        "memory_id": memory_data.get('id'),
                        "error": cleaned_result.get('error'),
                        "model_used": cleaned_result.get('model_used'),
                        "attempts_used": cleaned_result.get('attempts_used')
                    })
                    result["errors"].append(f"Cleaning failed: {cleaned_result.get('error')}")
                    return result

                cleaned_transcript = cleaned_result["cleaned_text"]
                result["model_used"] = cleaned_result.get("model_used")
                result["steps_completed"].append("transcript_cleaned")

                logger.debug("Transcript cleaned successfully", extra={
                    "uid": uid,
                    "model_used": cleaned_result.get("model_used"),
                    "processing_time": cleaned_result.get("processing_time"),
                    "cleaned_length": len(cleaned_transcript)
                })

            # Step 3: Psychological analysis
            with profile_step("psychological_analysis", result["performance_profile"]):
                analysis = self.psychological_analyzer.analyze(cleaned_transcript, include_details=True)

                if "error" in analysis:
                    error_msg = f"Psychological analysis failed: {analysis['error']}"
                    logger.warning(error_msg)
                    result["warnings"].append(error_msg)
                    # Continue processing even if analysis fails
                    analysis = self.psychological_analyzer._empty_analysis()  # Use empty analysis
                else:
                    result["steps_completed"].append("psychological_analysis")

            result["analysis"] = {
                "adhd_score": analysis.get("adhd_indicators", {}).get("score", 0),
                "anxiety_score": analysis.get("anxiety_patterns", {}).get("score", 0),
                "bias_score": analysis.get("cognitive_biases", {}).get("score", 0),
                "emotional_tone": analysis.get("emotional_tone", {}).get("primary_emotion", "unknown")
            }

            # Step 4: Save analysis as memory in OMI
            with profile_step("memory_save", result["performance_profile"]):
                memory_content = self._format_analysis_for_memory(analysis, cleaned_result)

                # Use direct OMI client API for memory creation
                memory_result = self.omi_client.create_memories(
                    text=memory_content,
                    memories=[{
                        "content": memory_content,
                        "tags": ["gemini_analysis", "psychological_insight"]
                    }],
                    text_source="other"
                )

                result["steps_completed"].append("memory_saved")
                result["created_memories_count"] = len(memory_result.get("memories", []))

            # Step 5: Workspace automation (run in background for performance)
            # Check what should be created but don't wait for completion
            email_created = False
            calendar_created = False
            slides_created = False

            if self.workspace_automation.credentials:
                # Quick checks for what should be automated
                should_email = self.workspace_automation.should_create_email(
                    analysis, cleaned_transcript
                )
                should_schedule = self._should_schedule_meeting(analysis, cleaned_transcript)
                should_present = self._should_create_presentation(analysis, cleaned_transcript)

                # Schedule background tasks
                if should_email or should_schedule or should_present:
                    # Create background task for workspace automation
                    memory_id = memory_data.get("id")
                    if memory_id:
                        asyncio.create_task(self._run_workspace_automation_background(
                            analysis, cleaned_transcript, str(memory_id), uid
                        ))

                    # Mark as queued (not completed yet)
                    result["workspace_automation_queued"] = True
                    if should_email:
                        result["email_queued"] = True
                    if should_schedule:
                        result["calendar_queued"] = True
                    if should_present:
                        result["presentation_queued"] = True

            # Step 6: Send notification to OMI app (background for performance)
            notification_msg = self._build_notification_message(
                analysis, 
                result.get("email_queued") or False, 
                result.get("calendar_queued") or False,
                result.get("presentation_queued") or False, 
                len(result["steps_completed"])
            )

            # Send notification asynchronously to not block response
            asyncio.create_task(self._send_notification_background(notification_msg, uid))
            result["notification_queued"] = True

            # Mark as successful if core steps completed (transcript cleaning is essential)
            core_success = "transcript_cleaned" in result["steps_completed"]
            result["success"] = core_success

            # Overall status based on error severity
            if result["critical_errors"]:
                result["status"] = "critical_failure"
            elif result["errors"] and not core_success:
                result["status"] = "failure"
            elif result["errors"] or result["warnings"]:
                result["status"] = "partial_success"
            else:
                result["status"] = "success"

            # Performance tracking
            processing_time = time.time() - start_time
            result["processing_time_seconds"] = processing_time

            # Add overall memory usage to profile
            process = psutil.Process(os.getpid())
            result["performance_profile"]["total_memory_mb"] = process.memory_info().rss / 1024 / 1024

            # Update stats
            self.processing_stats["total_processed"] += 1
            self.processing_stats["average_processing_time"] = (
                (self.processing_stats["average_processing_time"] * (self.processing_stats["total_processed"] - 1)) + processing_time
            ) / self.processing_stats["total_processed"]

            success_count = 1 if result["success"] else 0
            self.processing_stats["success_rate"] = (
                (self.processing_stats["success_rate"] * (self.processing_stats["total_processed"] - 1)) + success_count
            ) / self.processing_stats["total_processed"]

            # Track step performance for optimization insights
            if "performance_profile" not in self.processing_stats:
                self.processing_stats["performance_profile"] = {}

            for step_name, step_time in result["performance_profile"].items():
                if step_name.endswith("_time"):
                    if step_name not in self.processing_stats["performance_profile"]:
                        self.processing_stats["performance_profile"][step_name] = []
                    self.processing_stats["performance_profile"][step_name].append(step_time)
                    # Keep only last 100 measurements for rolling average
                    if len(self.processing_stats["performance_profile"][step_name]) > 100:
                        self.processing_stats["performance_profile"][step_name] = self.processing_stats["performance_profile"][step_name][-100:]

            logger.info(f"Memory processing completed in {processing_time:.2f}s. Status: {result['status']}, Steps: {len(result['steps_completed'])}, Warnings: {len(result['warnings'])}, Errors: {len(result['errors'])}, Critical: {len(result['critical_errors'])}")

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
        # Input validation
        if not InputValidator.validate_session_id(session_id):
            raise ValueError("Invalid session_id")
        if not InputValidator.validate_uid(uid):
            raise ValueError("Invalid uid")

        try:
            segments = InputValidator.validate_transcript_segments(segments)
        except ValueError as e:
            raise ValueError(f"Invalid segments: {str(e)}")

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
            limit: Number of recent conversations to process (max 50)

        Returns:
            List of analysis results
        """
        # Validate limit
        if not isinstance(limit, int) or limit < 1 or limit > 50:
            raise ValueError("limit must be an integer between 1 and 50")

        logger.info(f"Manual analysis of {limit} recent conversations")

        try:
            # Use direct OMI client to get conversations
            conversations = self.omi_client.read_conversations(limit=limit)

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

    def _should_schedule_meeting(self, analysis: Dict[str, Any], transcript: str) -> bool:
        """Determine if a calendar meeting should be scheduled based on analysis"""
        # Simple heuristic: schedule if high anxiety or ADHD scores, or if transcript mentions follow-up
        adhd_score = analysis.get("adhd_indicators", {}).get("score", 0)
        anxiety_score = analysis.get("anxiety_patterns", {}).get("score", 0)

        follow_up_keywords = ["follow up", "follow-up", "meeting", "schedule", "appointment", "discuss later"]
        has_follow_up = any(keyword in transcript.lower() for keyword in follow_up_keywords)

        return (adhd_score >= 6 or anxiety_score >= 6 or has_follow_up)

    def _should_create_presentation(self, analysis: Dict[str, Any], transcript: str) -> bool:
        """Determine if a presentation should be created based on analysis"""
        # Create presentation for important professional discussions or high-scoring analyses
        adhd_score = analysis.get("adhd_indicators", {}).get("score", 0)
        anxiety_score = analysis.get("anxiety_patterns", {}).get("score", 0)

        professional_keywords = ["meeting", "presentation", "project", "business", "work", "professional"]
        is_professional = any(keyword in transcript.lower() for keyword in professional_keywords)

        return is_professional and (adhd_score >= 4 or anxiety_score >= 4)

    def _generate_slide_content(self, section_type: str, analysis: Dict[str, Any], transcript: str, prompt_instruction: str) -> str:
        """Generate content for a specific slide section using Gemini"""
        try:
            # Create context from analysis
            analysis_summary = self.psychological_analyzer.generate_summary(analysis)

            full_prompt = f"""You are creating content for a presentation slide about a conversation analysis.

Section: {section_type.replace('_', ' ').title()}
Instructions: {prompt_instruction}

Conversation Transcript:
{transcript[:2000]}... (truncated for brevity)

Psychological Analysis Summary:
{analysis_summary}

Please generate concise, well-formatted content suitable for a presentation slide. Keep it under 200 words, use bullet points where appropriate, and focus on the most important information.

Format your response as clean text that will look good on a slide."""

            # Use workspace automation's Gemini client for consistency
            response = self.workspace_automation.client.models.generate_content(
                model=self.workspace_automation.gemini_model_name,
                contents=full_prompt
            )

            content = response.text.strip()

            # Ensure content isn't too long for a slide
            if len(content) > 500:
                content = content[:497] + "..."

            return content

        except Exception as e:
            logger.error(f"Error generating slide content for {section_type}: {str(e)}")
            return f"Error generating content for {section_type.replace('_', ' ').title()}"

    def _generate_slides_content(self, analysis: Dict[str, Any], transcript: str) -> List[Dict[str, Any]]:
        """Generate template-based slides content for presentation with structured sections"""
        try:
            # Generate content for each section using Gemini
            slides_data = []

            # Title slide
            slides_data.append({
                "layout": "TITLE",
                "title": "Meeting Analysis & Insights",
                "body": f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\nPowered by Gemini AI"
            })

            # Key Points slide
            key_points_content = self._generate_slide_content(
                "key_points",
                analysis,
                transcript,
                "Extract and summarize the 3-5 most important key points from this conversation. Focus on main topics, decisions made, and critical information discussed."
            )
            slides_data.append({
                "layout": "TITLE_AND_BODY",
                "title": "Key Points",
                "body": key_points_content
            })

            # Action Items slide
            action_items_content = self._generate_slide_content(
                "action_items",
                analysis,
                transcript,
                "Identify all action items, tasks, follow-ups, or commitments mentioned in the conversation. List them clearly with responsible parties if mentioned."
            )
            slides_data.append({
                "layout": "TITLE_AND_BODY",
                "title": "Action Items",
                "body": action_items_content
            })

            # Psychological Insights slide
            psychological_insights = self._generate_slide_content(
                "psychological_insights",
                analysis,
                transcript,
                f"Based on the psychological analysis (ADHD: {analysis.get('adhd_indicators', {}).get('score', 0)}/10, Anxiety: {analysis.get('anxiety_patterns', {}).get('score', 0)}/10), provide insights about communication patterns, emotional dynamics, and recommendations for future interactions."
            )
            slides_data.append({
                "layout": "TITLE_AND_BODY",
                "title": "Psychological Insights",
                "body": psychological_insights
            })

            # Conclusions slide
            conclusions_content = self._generate_slide_content(
                "conclusions",
                analysis,
                transcript,
                "Provide overall conclusions about the conversation, including outcomes achieved, areas for improvement, and recommendations for follow-up actions."
            )
            slides_data.append({
                "layout": "TITLE_AND_BODY",
                "title": "Conclusions",
                "body": conclusions_content
            })

            logger.info(f"Generated {len(slides_data)} slides for presentation")
            return slides_data

        except Exception as e:
            logger.error(f"Error generating slides content: {str(e)}")
            # Fallback to basic slides
            summary = self.psychological_analyzer.generate_summary(analysis)
            return [
                {
                    "layout": "TITLE_AND_BODY",
                    "title": "Conversation Analysis Summary",
                    "body": f"Analysis generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n{summary}"
                },
                {
                    "layout": "TITLE_AND_BODY",
                    "title": "Key Findings",
                    "body": f"ADHD Indicators: {analysis.get('adhd_indicators', {}).get('score', 0)}/10\n"
                           f"Anxiety Patterns: {analysis.get('anxiety_patterns', {}).get('score', 0)}/10\n"
                           f"Cognitive Biases: {analysis.get('cognitive_biases', {}).get('score', 0)}/10\n"
                           f"Emotional Tone: {analysis.get('emotional_tone', {}).get('primary_emotion', 'unknown')}"
                },
                {
                    "layout": "TITLE_AND_BODY",
                    "title": "Transcript Excerpt",
                    "body": transcript[:1000] + ("..." if len(transcript) > 1000 else "")
                }
            ]

    async def _run_workspace_automation_background(self, analysis: Dict[str, Any], cleaned_transcript: str,
                                                  memory_id: str, uid: str):
        """Run workspace automation in background after webhook response"""

        try:
            logger.info(f"Starting background workspace automation for memory {memory_id}, uid {uid}")

            email_created = False
            calendar_created = False
            slides_created = False

            # Email automation
            should_email = self.workspace_automation.should_create_email(analysis, cleaned_transcript)
            if should_email:
                draft_id = self.workspace_automation.create_email_draft(
                    context=f"Analysis Summary:\n{self.psychological_analyzer.generate_summary(analysis)}\n\nTranscript:\n{cleaned_transcript}"
                )
                if draft_id:
                    email_created = True
                    logger.info(f"Background email draft created for memory {memory_id}")

            # Calendar integration
            should_schedule = self._should_schedule_meeting(analysis, cleaned_transcript)
            if should_schedule:
                event_id = self.workspace_automation.create_calendar_event(
                    summary=f"Follow-up: {analysis.get('overall_assessment', 'Discussion')[:50]}",
                    start_time=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
                    end_time=(datetime.now(timezone.utc) + timedelta(days=1, hours=1)).isoformat(),
                    description=f"Analysis: {self.psychological_analyzer.generate_summary(analysis)}"
                )
                if event_id:
                    calendar_created = True
                    logger.info(f"Background calendar event created for memory {memory_id}")

            # Slides integration
            should_present = self._should_create_presentation(analysis, cleaned_transcript)
            if should_present:
                slides_content = self._generate_slides_content(analysis, cleaned_transcript)
                presentation_id = self.workspace_automation.create_presentation(
                    title=f"Analysis: {datetime.now().strftime('%Y-%m-%d')}",
                    slides_content=slides_content
                )
                if presentation_id:
                    slides_created = True
                    logger.info(f"Background presentation created for memory {memory_id}")

            # Send completion notification
            if email_created or calendar_created or slides_created:
                notification_msg = f"Workspace automation completed - Email: {email_created}, Calendar: {calendar_created}, Slides: {slides_created}"
                self.omi_client.send_notification(notification_msg, uid)
                logger.info(f"Background automation completed for memory {memory_id}")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Background workspace automation failed for memory {memory_id}: {error_msg}")
            # Send error notification
            try:
                self.omi_client.send_notification(f"Workspace automation failed: {error_msg}", uid)
            except:
                pass  # Don't let notification failure crash the background task

    async def _send_notification_background(self, message: str, uid: str):
        """Send notification asynchronously"""
        try:
            notification_sent = self.omi_client.send_notification(message, uid)
            if not notification_sent:
                logger.warning(f"Background notification failed to send for uid {uid}")
        except Exception as e:
            logger.error(f"Background notification error for uid {uid}: {str(e)}")

    def _build_notification_message(self, analysis: Dict[str, Any], email_created: bool, calendar_created: bool, slides_created: bool, steps_count: int) -> str:
        """Build notification message for OMI app"""

        adhd_score = analysis.get("adhd_indicators", {}).get("score", 0)
        anxiety_score = analysis.get("anxiety_patterns", {}).get("score", 0)
        bias_score = analysis.get("cognitive_biases", {}).get("score", 0)

        msg = f"Gemini analysis complete ({steps_count} steps)"

        if adhd_score >= 5 or anxiety_score >= 5 or bias_score >= 5:
            scores = []
            if adhd_score >= 5:
                scores.append(f"ADHD:{adhd_score}")
            if anxiety_score >= 5:
                scores.append(f"Anxiety:{anxiety_score}")
            if bias_score >= 5:
                scores.append(f"Biases:{bias_score}")
            msg += f" - Patterns detected ({'/'.join(scores)}/10)"

        automation_items = []
        if email_created:
            automation_items.append("email")
        if calendar_created:
            automation_items.append("calendar")
        if slides_created:
            automation_items.append("slides")

        if automation_items:
            msg += f" - Created: {', '.join(automation_items)}"

        return msg

    def process_multimodal_input(self, input_data: Any, modality: ModalityType, uid: str, **kwargs) -> Dict[str, Any]:
        """
        Process multimodal input (text, audio, image) using registered processors

        Args:
            input_data: The input data to process
            modality: The type of input modality
            uid: User identifier
            **kwargs: Additional processing parameters

        Returns:
            Processing result dictionary
        """
        # Input validation
        if not InputValidator.validate_uid(uid):
            raise ValueError("Invalid uid")

        start_time = time.time()
        logger.info(f"Processing {modality.value} input for user {uid}")

        try:
            # Get the appropriate processor
            processor = self.processor_registry.get_processor(modality)
            if not processor:
                return {
                    "success": False,
                    "error": f"No processor available for modality: {modality.value}",
                    "modality": modality.value,
                    "processing_time_seconds": time.time() - start_time
                }

            # Process the input
            result = processor.process(input_data, **kwargs)

            # Convert to dictionary format for consistency
            response = result.to_dict()
            response["processing_time_seconds"] = time.time() - start_time

            if result.success:
                logger.info(f"Successfully processed {modality.value} input for user {uid}")
            else:
                logger.warning(f"Failed to process {modality.value} input for user {uid}: {result.error}")

            return response

        except Exception as e:
            logger.error(f"Multimodal processing failed for {modality.value}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "modality": modality.value,
                "processing_time_seconds": time.time() - start_time
            }

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
        # Input validation
        if not InputValidator.validate_uid(uid):
            raise ValueError("Invalid uid")
        if not isinstance(audio_bytes, bytes):
            raise ValueError("audio_bytes must be bytes")
        if len(audio_bytes) > 10 * 1024 * 1024:  # 10MB limit
            raise ValueError("Audio data too large")

        try:
            sample_rate = InputValidator.validate_sample_rate(sample_rate)
        except ValueError:
            raise

        logger.info(f"Processing audio stream for user {uid}, {len(audio_bytes)} bytes at {sample_rate}Hz")

        # Use the new multimodal processing system
        return self.process_multimodal_input(
            audio_bytes, ModalityType.AUDIO, uid,
            sample_rate=sample_rate
        )

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get current performance statistics"""
        stats = self.processing_stats.copy()

        # Calculate averages for step performance
        if "performance_profile" in stats:
            for step_name, times in stats["performance_profile"].items():
                if times:
                    stats[f"avg_{step_name}"] = sum(times) / len(times)
                    stats[f"max_{step_name}"] = max(times)
                    stats[f"min_{step_name}"] = min(times)

        return stats

    async def close(self):
        """Cleanup resources"""
        self.omi_client.close()
        logger.info("Orchestrator closed")
