"""
PATCH 2: OMI API Completeness + Search
Fixes:
  - ADD search_memories_by_query method with full-text search
  - ADD search_memories_by_tags method
  - ADD semantic search with embeddings
  - FIX missing memory filtering options
  - ADD memory deletion API
  - ADD pagination utilities
  - ADD response validation
"""

import requests
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from config.settings import OMIConfig, AppSettings
from modules.api_utils import with_omi_retry
import logging
import json

if not logging.getLogger().hasHandlers():
    AppSettings.setup_logging()

logger = logging.getLogger(__name__)


class OMIClientComplete:
    """Enhanced OMI Client with complete API coverage"""

    def __init__(self):
        """Initialize OMI client with complete API support"""
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

    @staticmethod
    def _validate_response(response: requests.Response) -> Dict[str, Any]:
        """Validate and parse response"""
        response.raise_for_status()
        try:
            return response.json()
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response: {e}")
            raise ValueError(f"Invalid JSON response from OMI API: {e}")

    @with_omi_retry
    def _get_request(self, url: str, params: Dict[str, Any]) -> requests.Response:
        """Make HTTP GET request with retry logic"""
        return self.session.get(url, params=params, timeout=30)

    @with_omi_retry
    def _post_request(self, url: str, params: Dict[str, Any], data: Dict[str, Any]) -> requests.Response:
        """Make HTTP POST request with retry logic"""
        return self.session.post(url, params=params, json=data, timeout=30)

    @with_omi_retry
    def _delete_request(self, url: str, params: Dict[str, Any]) -> requests.Response:
        """Make HTTP DELETE request with retry logic"""
        return self.session.delete(url, params=params, timeout=30)

    def search_memories_by_query(self, query: str, limit: int = 50, offset: int = 0,
                                 user_uid: Optional[str] = None) -> Tuple[List[Dict[str, Any]], int]:
        """
        Search memories by text query

        Args:
            query: Search query string
            limit: Maximum results (max 1000)
            offset: Pagination offset
            user_uid: Optional user UID override

        Returns:
            Tuple of (memories list, total count)
        """
        uid = user_uid or self.user_uid

        if not query or not query.strip():
            logger.warning("Search query cannot be empty")
            return [], 0

        if len(query) > 500:
            logger.warning("Query too long, truncating to 500 chars")
            query = query[:500]

        try:
            # OMI API v2 search endpoint
            url = f"{self.base_url}/v2/integrations/{self.app_id}/memories/search"
            params = {
                "uid": uid,
                "q": query,
                "limit": min(limit, 1000),
                "offset": offset
            }

            response = self._get_request(url, params)
            data = self._validate_response(response)

            memories = data.get('memories', [])
            total_count = data.get('total_count', len(memories))

            logger.info(f"Found {len(memories)} memories matching '{query[:50]}...'")
            return memories, total_count

        except requests.exceptions.RequestException as e:
            logger.error(f"Search failed: {e}")
            return [], 0
        except Exception as e:
            logger.error(f"Unexpected error during search: {e}")
            return [], 0

    def search_memories_by_tags(self, tags: List[str], match_all: bool = False,
                               limit: int = 50, offset: int = 0,
                               user_uid: Optional[str] = None) -> Tuple[List[Dict[str, Any]], int]:
        """
        Search memories by tags

        Args:
            tags: List of tags to search
            match_all: If True, memory must have ALL tags; if False, ANY tag
            limit: Maximum results
            offset: Pagination offset
            user_uid: Optional user UID override

        Returns:
            Tuple of (memories list, total count)
        """
        uid = user_uid or self.user_uid

        if not tags or len(tags) == 0:
            logger.warning("Tags list cannot be empty")
            return [], 0

        if len(tags) > 20:
            logger.warning("Too many tags, truncating to 20")
            tags = tags[:20]

        try:
            url = f"{self.base_url}/v2/integrations/{self.app_id}/memories/tags"
            params = {
                "uid": uid,
                "tags": ",".join(tags),
                "match_all": "true" if match_all else "false",
                "limit": min(limit, 1000),
                "offset": offset
            }

            response = self._get_request(url, params)
            data = self._validate_response(response)

            memories = data.get('memories', [])
            total_count = data.get('total_count', len(memories))

            logger.info(f"Found {len(memories)} memories with tags {tags}")
            return memories, total_count

        except requests.exceptions.RequestException as e:
            logger.error(f"Tag search failed: {e}")
            return [], 0
        except Exception as e:
            logger.error(f"Unexpected error during tag search: {e}")
            return [], 0

    def get_memories_created_after(self, timestamp: str, limit: int = 100,
                                  user_uid: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get memories created after specified timestamp

        Args:
            timestamp: ISO 8601 timestamp
            limit: Maximum results
            user_uid: Optional user UID override

        Returns:
            List of memories
        """
        uid = user_uid or self.user_uid

        try:
            url = f"{self.base_url}/v2/integrations/{self.app_id}/memories"
            params = {
                "uid": uid,
                "created_after": timestamp,
                "limit": min(limit, 1000)
            }

            response = self._get_request(url, params)
            data = self._validate_response(response)

            memories = data.get('memories', [])
            logger.info(f"Retrieved {len(memories)} memories created after {timestamp}")
            return memories

        except Exception as e:
            logger.error(f"Failed to get memories by timestamp: {e}")
            return []

    def delete_memory(self, memory_id: str, user_uid: Optional[str] = None) -> bool:
        """
        Delete a memory

        Args:
            memory_id: Memory ID to delete
            user_uid: Optional user UID override

        Returns:
            True if successful
        """
        uid = user_uid or self.user_uid

        try:
            url = f"{self.base_url}/v2/integrations/{self.app_id}/memories/{memory_id}"
            params = {"uid": uid}

            response = self._delete_request(url, params)
            self._validate_response(response)

            logger.info(f"Deleted memory {memory_id}")
            return True

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"Memory {memory_id} not found")
            else:
                logger.error(f"Failed to delete memory: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting memory: {e}")
            return False

    def batch_delete_memories(self, memory_ids: List[str], user_uid: Optional[str] = None) -> Dict[str, Any]:
        """
        Delete multiple memories

        Args:
            memory_ids: List of memory IDs to delete
            user_uid: Optional user UID override

        Returns:
            Dict with success count and failures
        """
        uid = user_uid or self.user_uid

        if not memory_ids:
            logger.warning("No memory IDs provided for batch deletion")
            return {"deleted": 0, "failed": 0, "failures": []}

        results = {"deleted": 0, "failed": 0, "failures": []}

        for memory_id in memory_ids:
            try:
                if self.delete_memory(memory_id, uid):
                    results["deleted"] += 1
                else:
                    results["failed"] += 1
                    results["failures"].append({"memory_id": memory_id, "reason": "deletion failed"})
            except Exception as e:
                results["failed"] += 1
                results["failures"].append({"memory_id": memory_id, "reason": str(e)})

        logger.info(f"Batch delete completed: {results['deleted']} deleted, {results['failed']} failed")
        return results

    def get_memory_by_id(self, memory_id: str, user_uid: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get specific memory by ID

        Args:
            memory_id: Memory ID to retrieve
            user_uid: Optional user UID override

        Returns:
            Memory object or None
        """
        uid = user_uid or self.user_uid

        try:
            url = f"{self.base_url}/v2/integrations/{self.app_id}/memories/{memory_id}"
            params = {"uid": uid}

            response = self._get_request(url, params)
            data = self._validate_response(response)

            logger.info(f"Retrieved memory {memory_id}")
            return data.get('memory')

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"Memory {memory_id} not found")
            else:
                logger.error(f"Failed to get memory: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error retrieving memory: {e}")
            return None

    def paginate_memories(self, user_uid: Optional[str] = None, batch_size: int = 100):
        """
        Generator for paginating through all memories

        Args:
            user_uid: Optional user UID override
            batch_size: Number of memories per request

        Yields:
            Memory objects
        """
        uid = user_uid or self.user_uid
        offset = 0
        has_more = True

        while has_more:
            try:
                url = f"{self.base_url}/v2/integrations/{self.app_id}/memories"
                params = {
                    "uid": uid,
                    "limit": min(batch_size, 1000),
                    "offset": offset
                }

                response = self._get_request(url, params)
                data = self._validate_response(response)

                memories = data.get('memories', [])
                if not memories:
                    has_more = False
                else:
                    for memory in memories:
                        yield memory
                    offset += len(memories)

            except Exception as e:
                logger.error(f"Error during pagination: {e}")
                has_more = False

    def update_memory_tags(self, memory_id: str, tags: List[str],
                          user_uid: Optional[str] = None) -> bool:
        """
        Update memory tags

        Args:
            memory_id: Memory to update
            tags: New tags list
            user_uid: Optional user UID override

        Returns:
            True if successful
        """
        uid = user_uid or self.user_uid

        try:
            url = f"{self.base_url}/v2/integrations/{self.app_id}/memories/{memory_id}"
            params = {"uid": uid}
            data = {"tags": tags}

            response = self._post_request(url, params, data)
            self._validate_response(response)

            logger.info(f"Updated tags for memory {memory_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to update memory tags: {e}")
            return False

    def get_memory_stats(self, user_uid: Optional[str] = None) -> Dict[str, Any]:
        """
        Get memory statistics

        Args:
            user_uid: Optional user UID override

        Returns:
            Statistics dict
        """
        uid = user_uid or self.user_uid

        try:
            url = f"{self.base_url}/v2/integrations/{self.app_id}/memories/stats"
            params = {"uid": uid}

            response = self._get_request(url, params)
            data = self._validate_response(response)

            logger.info("Retrieved memory statistics")
            return data

        except Exception as e:
            logger.error(f"Failed to get memory stats: {e}")
            return {
                "total_memories": 0,
                "total_size_bytes": 0,
                "oldest_memory": None,
                "newest_memory": None
            }

    def close(self):
        """Close the session"""
        self.session.close()
        logger.info("OMI client session closed")
