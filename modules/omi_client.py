"""
OMI Integration API Client
Handles communication with OMI Import API and Notifications
"""
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime
from config.settings import OMIConfig
import logging

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

        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            logger.info(f"Retrieved {len(data)} conversations from OMI")
            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to read conversations: {e}")
            raise

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

        data = {
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

        try:
            response = self.session.post(url, params=params, json=data)
            response.raise_for_status()
            result = response.json()
            logger.info(f"Created conversation in OMI: {result.get('id', 'unknown')}")
            return result
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create conversation: {e}")
            raise

    def create_memories(self, memories: Optional[List[Dict[str, Any]]] = None,
                       text: Optional[str] = None,
                       text_source: str = "other",
                       text_source_spec: Optional[str] = None) -> Dict[str, Any]:
        """
        Create memories in OMI

        Args:
            memories: List of explicit memory objects with "content" and optional "tags"
            text: Alternative: text from which memories will be extracted
            text_source: Source type
            text_source_spec: Additional source specification

        Returns:
            Response with created memories
        """
        url = f"{self.base_url}/v2/integrations/{self.app_id}/user/memories"
        params = {"uid": self.user_uid}

        data = {
            "text_source": text_source
        }

        if text_source_spec:
            data["text_source_spec"] = text_source_spec

        if memories is not None:
            data["memories"] = memories
        elif text is not None:
            data["text"] = text
        else:
            raise ValueError("Either 'memories' or 'text' must be provided")

        try:
            response = self.session.post(url, params=params, json=data)
            response.raise_for_status()
            result = response.json()
            logger.info(f"Created {len(result.get('memories', []))} memories in OMI")
            return result
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create memories: {e}")
            raise

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

        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            logger.info(f"Retrieved {len(data)} memories from OMI")
            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to read memories: {e}")
            raise

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
            # Notifications API uses POST with empty body and message in query params
            response = self.session.post(url, params=params, headers={
                "Content-Length": "0"
            })
            response.raise_for_status()
            logger.info(f"Sent notification to user {uid}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send notification: {e}")
            return False

    def close(self):
        """Close the session"""
        self.session.close()
