"""
OMI Integration API Client
Handles communication with OMI Import API and Notifications
"""
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime
from config.settings import OMIConfig, AppSettings
from modules.api_utils import with_omi_retry
import logging

# Setup logging if not already configured
if not logging.getLogger().hasHandlers():
    AppSettings.setup_logging()

logger = logging.getLogger(__name__)

class OMIClient:
    """Client for OMI Import API and Notifications"""

    def __init__(self):
        OMIConfig.validate()
        self.app_id = OMIConfig.APP_ID
        self.app_secret = OMIConfig.APP_SECRET
        self.base_url = OMIConfig.BASE_URL
        self.user_uid = OMIConfig.USER_UID

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.app_secret}",
            "Content-Type": "application/json"
        })

    @with_omi_retry
    def _get_conversations_request(self, url: str, params: Dict[str, Any]) -> requests.Response:
        """Make HTTP GET request for conversations with retry logic"""
        return self.session.get(url, params=params)

    def read_conversations(self, limit: int = 100, offset: int = 0,
                           include_discarded: bool = False) -> List[Dict[str, Any]]:
        """
        Read conversations from OMI

        Args:
            limit: Maximum number of conversations (default 100, max 1000)
            offset: Pagination offset
            include_discarded: Include discarded conversations

        Returns:
            List of conversation objects
        """
        url = f"{self.base_url}/v2/integrations/{self.app_id}/conversations"
        params = {
            "uid": self.user_uid,
            "limit": limit,
            "offset": offset
        }

        if include_discarded:
            params["include_discarded"] = "true"

        response = self._get_conversations_request(url, params)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Retrieved {len(data.get('conversations', []))} conversations from OMI")
        return data.get('conversations', [])

    @with_omi_retry
    def _post_conversation_request(self, url: str, params: Dict[str, Any], data: Dict[str, Any]) -> requests.Response:
        """Make HTTP POST request for conversation creation with retry logic"""
        return self.session.post(url, params=params, json=data)

    def create_conversation(self, text: str, started_at: str, finished_at: str,
                            language: str = "en", text_source: str = "other",
                            text_source_spec: Optional[str] = None,
                            geolocation: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """
        Create a new conversation in OMI

        Args:
            text: Full conversation text
            started_at: ISO 8601 timestamp
            finished_at: ISO 8601 timestamp
            language: Language code (default "en")
            text_source: Source type (e.g., "audio_transcript", "email", "other")
            text_source_spec: Additional source specification
            geolocation: Optional dict with "latitude" and "longitude"

        Returns:
            Created conversation object
        """
        url = f"{self.base_url}/v2/integrations/{self.app_id}/user/conversations"
        params = {"uid": self.user_uid}

        data: Dict[str, Any] = {
            "text": text,
            "started_at": started_at,
            "finished_at": finished_at,
            "language": language,
            "text_source": text_source
        }

        if text_source_spec:
            data["text_source_spec"] = text_source_spec
        if geolocation:
            data["geolocation"] = geolocation

        response = self._post_conversation_request(url, params, data)
        response.raise_for_status()
        result = response.json()
        logger.info(f"Created conversation in OMI: {result.get('id', 'unknown')}")
        return result

    @with_omi_retry
    def _post_memories_request(self, url: str, params: Dict[str, Any], data: Dict[str, Any]) -> requests.Response:
        """Make HTTP POST request for memory creation with retry logic"""
        return self.session.post(url, params=params, json=data)

    def create_memories(self, memories: Optional[List[Dict[str, Any]]] = None,
                        text: Optional[str] = None,
                        text_source: str = "other",
                        text_source_spec: Optional[str] = None) -> Dict[str, Any]:
        """
        Create memories in OMI

        Args:
            memories: List of explicit memory objects with "content" and optional "tags"
            text: Text content (required by OMI API, even with explicit memories)
            text_source: Source type (must be "email", "social_post", or "other")
            text_source_spec: Additional source specification

        Returns:
            Response with created memories
        """
        url = f"{self.base_url}/v2/integrations/{self.app_id}/user/memories"
        params = {"uid": self.user_uid}

        data: Dict[str, Any] = {
            "text_source": text_source
        }

        if text_source_spec:
            data["text_source_spec"] = text_source_spec

        # OMI API requires 'text' field even when passing explicit memories
        if text is not None:
            data["text"] = text

        if memories is not None:
            data["memories"] = memories

        # At least text must be provided (OMI API requirement)
        if "text" not in data:
            raise ValueError("'text' field is required by OMI API")

        response = self._post_memories_request(url, params, data)
        response.raise_for_status()
        result = response.json()
        logger.info(f"Created {len(result.get('memories', []))} memories in OMI")
        return result

    @with_omi_retry
    def _get_memories_request(self, url: str, params: Dict[str, Any]) -> requests.Response:
        """Make HTTP GET request for memories with retry logic"""
        return self.session.get(url, params=params)

    def read_memories(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Read memories from OMI

        Args:
            limit: Maximum number of memories (default 100, max 1000)
            offset: Pagination offset

        Returns:
            List of memory objects
        """
        url = f"{self.base_url}/v2/integrations/{self.app_id}/memories"
        params = {
            "uid": self.user_uid,
            "limit": limit,
            "offset": offset
        }

        response = self._get_memories_request(url, params)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Retrieved {len(data.get('memories', []))} memories from OMI")
        return data.get('memories', [])

    @with_omi_retry
    def _post_notification_request(self, url: str, params: Dict[str, Any]) -> requests.Response:
        """Make HTTP POST request for notifications with retry logic"""
        return self.session.post(url, params=params, headers={"Content-Length": "0"})

    def send_notification(self, message: str, user_uid: Optional[str] = None) -> bool:
        """
        Send push notification to OMI app

        Args:
            message: Notification message text
            user_uid: Optional user UID (defaults to configured user)

        Returns:
            True if successful
        """
        uid = user_uid or self.user_uid
        url = f"{self.base_url}/v2/integrations/{self.app_id}/notification"
        params = {
            "uid": uid,
            "message": message
        }

        try:
            response = self._post_notification_request(url, params)
            response.raise_for_status()
            logger.info(f"Sent notification to user {uid}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send notification: {e}")
            return False

    def close(self):
        """Close the session"""
        self.session.close()
