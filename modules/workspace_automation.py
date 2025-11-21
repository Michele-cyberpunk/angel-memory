"""
Google Workspace Automation
Handles Gmail, Calendar, and Slides API interactions
"""
import os
import base64
import pickle
import re
from email.mime.text import MIMEText
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone

from dateutil import parser as date_parser

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from google import genai
from config.settings import GoogleWorkspaceConfig, GeminiConfig, AppSettings
import logging

# Setup logging if not already configured
if not logging.getLogger().hasHandlers():
    AppSettings.setup_logging()

logger = logging.getLogger(__name__)

class WorkspaceAutomation:
    """Automate Google Workspace tasks based on Gemini analysis"""

    def __init__(self):
        self.credentials = None
        self.gmail_service = None
        self.calendar_service = None
        self.slides_service = None

        # Initialize Gemini for decision-making
        GeminiConfig.validate()
        self.client = genai.Client(api_key=GeminiConfig.API_KEY)
        self.gemini_model_name = GeminiConfig.PRIMARY_MODEL

        logger.info("Initialized WorkspaceAutomation")

    def authenticate(self) -> bool:
        """
        Authenticate with Google Workspace APIs using existing tokens

        Returns:
            True if authentication successful
        """
        try:
            creds = None
            token_file = GoogleWorkspaceConfig.TOKEN_FILE

            # Load existing credentials
            if os.path.exists(token_file):
                with open(token_file, 'rb') as token:
                    creds = pickle.load(token)

            # Refresh if expired
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                # Save refreshed credentials
                with open(token_file, 'wb') as token:
                    pickle.dump(creds, token)

            if not creds or not creds.valid:
                logger.warning("No valid credentials found. Use get_authorization_url() and complete_authentication() for OAuth2 flow")
                return False

            self.credentials = creds

            # Build services
            self.gmail_service = build('gmail', 'v1', credentials=creds)
            self.calendar_service = build('calendar', 'v3', credentials=creds)
            self.slides_service = build('slides', 'v1', credentials=creds)

            logger.info("Successfully authenticated with Google Workspace")
            return True

        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}")
            return False

    def get_authorization_url(self) -> Optional[str]:
        """
        Get Google OAuth2 authorization URL for web-based authentication

        Returns:
            Authorization URL to redirect user to, or None if error
        """
        try:
            client_secret_file = GoogleWorkspaceConfig.CLIENT_SECRET_FILE
            redirect_uri = GoogleWorkspaceConfig.REDIRECT_URI
            scopes = GoogleWorkspaceConfig.SCOPES

            if not os.path.exists(client_secret_file):
                logger.error(f"Client secret file not found: {client_secret_file}")
                return None

            flow = InstalledAppFlow.from_client_secrets_file(
                client_secret_file,
                scopes=scopes
            )

            auth_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true'
            )

            # Store flow state for later use
            self._auth_flow = flow
            self._auth_state = state

            logger.info("Generated authorization URL for OAuth2")
            return auth_url

        except Exception as e:
            logger.error(f"Failed to generate authorization URL: {str(e)}")
            return None

    def complete_authentication(self, code: str, state: str) -> bool:
        """
        Complete OAuth2 authentication with authorization code

        Args:
            code: Authorization code from callback
            state: State parameter from callback

        Returns:
            True if authentication successful
        """
        try:
            if not hasattr(self, '_auth_flow') or not hasattr(self, '_auth_state'):
                logger.error("Authorization flow not initialized. Call get_authorization_url() first")
                return False

            if state != self._auth_state:
                logger.error("State parameter mismatch - possible CSRF attack")
                return False

            flow = self._auth_flow
            flow.fetch_token(code=code)

            creds = flow.credentials
            self.credentials = creds

            # Save credentials
            token_file = GoogleWorkspaceConfig.TOKEN_FILE
            with open(token_file, 'wb') as token:
                pickle.dump(creds, token)

            # Build services
            self.gmail_service = build('gmail', 'v1', credentials=creds)
            self.calendar_service = build('calendar', 'v3', credentials=creds)
            self.slides_service = build('slides', 'v1', credentials=creds)

            # Clean up
            delattr(self, '_auth_flow')
            delattr(self, '_auth_state')

            logger.info("Successfully completed OAuth2 authentication")
            return True

        except Exception as e:
            logger.error(f"Failed to complete authentication: {str(e)}")
            return False

    def should_create_email(self, analysis: Dict[str, Any], transcript: str) -> bool:
        """
        Use Gemini to decide if email follow-up is needed

        Args:
            analysis: Psychological analysis results
            transcript: Cleaned transcript

        Returns:
            True if email should be created
        """
        # Input validation
        if not isinstance(analysis, dict):
            raise ValueError("analysis must be a dictionary")

        if not isinstance(transcript, str):
            raise ValueError("transcript must be a string")

        if not transcript.strip():
            logger.warning("Empty transcript provided for email decision")
            return False
        prompt = f"""Based on this conversation analysis, determine if a follow-up email would be helpful.

Conversation transcript excerpt:
{transcript[:500]}...

Analysis summary:
- ADHD indicators: {analysis.get('adhd_indicators', {}).get('score', 0)}/10
- Anxiety patterns: {analysis.get('anxiety_patterns', {}).get('score', 0)}/10
- Overall: {analysis.get('overall_assessment', 'N/A')}

Consider:
1. Are there action items that need written confirmation?
2. Is there important information to document?
3. Would an email help with organization or follow-through?
4. Is this a professional context requiring formal communication?

Respond with ONLY "YES" or "NO" and a brief one-sentence reason.
Format: YES|NO: <reason>"""

        try:
            response = self.client.models.generate_content(
                model=self.gemini_model_name,
                contents=prompt
            )
            decision_text = response.text.strip().upper()

            should_create = decision_text.startswith("YES")
            logger.info(f"Email creation decision: {decision_text}")

            return should_create

        except Exception as e:
            logger.error(f"Error in email decision: {str(e)}")
            return False

    def create_email_draft(self, context: str, recipient: Optional[str] = None) -> Optional[str]:
        """
        Create Gmail draft based on context

        Args:
            context: Context for email generation
            recipient: Optional recipient email

        Returns:
            Draft ID if successful, None otherwise
        """
        # Input validation
        if not isinstance(context, str) or not context.strip():
            raise ValueError("context must be a non-empty string")

        if recipient is not None and (not isinstance(recipient, str) or not recipient.strip()):
            raise ValueError("recipient must be a non-empty string or None")

        if not self.gmail_service:
            logger.error("Gmail service not initialized")
            return None

        try:
            # Generate email content with Gemini
            email_content = self._generate_email_content(context)

            if not email_content:
                return None

            # Create message
            message = MIMEText(email_content['body'])
            message['to'] = recipient or ''
            message['subject'] = email_content['subject']

            # Encode message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')

            # Create draft
            draft_body = {
                'message': {
                    'raw': raw_message
                }
            }

            draft = self.gmail_service.users().drafts().create(
                userId='me',
                body=draft_body
            ).execute()

            draft_id = draft['id']
            logger.info(f"Created email draft: {draft_id}")

            return draft_id

        except HttpError as e:
            logger.error(f"Gmail API error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error creating email draft: {str(e)}")
            return None

    def _generate_email_content(self, context: str) -> Optional[Dict[str, str]]:
        """Generate email subject and body using Gemini with conversation insights"""

        prompt = f"""Generate a professional follow-up email based on this conversation analysis and transcript:

{context}

IMPORTANT: Consider the psychological analysis when crafting the email:
- If anxiety scores are high (>6), use calming, supportive language
- If ADHD indicators are high (>6), keep it concise and structured
- If cognitive biases are detected, be clear and factual
- Tailor the tone to the emotional context of the conversation

Create:
1. A clear, concise subject line (max 60 characters) that reflects the conversation's purpose
2. A well-structured email body with:
   - Appropriate greeting based on context
   - Clear purpose referencing key discussion points
   - Action items or next steps mentioned in the conversation
   - Supportive closing that acknowledges the conversation's emotional tone
   - Professional sign-off

Format your response as:
SUBJECT: <subject line>

BODY:
<email body>"""

        try:
            response = self.client.models.generate_content(
                model=self.gemini_model_name,
                contents=prompt
            )
            text = response.text.strip()

            # Parse subject and body
            if "SUBJECT:" in text and "BODY:" in text:
                parts = text.split("BODY:", 1)
                subject = parts[0].replace("SUBJECT:", "").strip()
                body = parts[1].strip()

                return {
                    'subject': subject,
                    'body': body
                }
            else:
                logger.warning("Could not parse email format from Gemini response")
                return None

        except Exception as e:
            logger.error(f"Error generating email content: {str(e)}")
            return None

    def read_recent_emails(self, max_results: int = 10, query: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Read recent emails from inbox

        Args:
            max_results: Maximum number of emails to retrieve
            query: Optional Gmail search query

        Returns:
            List of email objects with id, subject, snippet, from
        """
        if not self.gmail_service:
            logger.error("Gmail service not initialized")
            return []

        try:
            # Get message list
            results = self.gmail_service.users().messages().list(
                userId='me',
                maxResults=max_results,
                q=query or ''
            ).execute()

            messages = results.get('messages', [])

            email_list = []
            for msg in messages:
                # Get full message details
                message = self.gmail_service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='metadata',
                    metadataHeaders=['From', 'Subject', 'Date']
                ).execute()

                headers = {h['name']: h['value'] for h in message['payload']['headers']}

                email_list.append({
                    'id': msg['id'],
                    'subject': headers.get('Subject', '(no subject)'),
                    'from': headers.get('From', ''),
                    'date': headers.get('Date', ''),
                    'snippet': message.get('snippet', '')
                })

            logger.info(f"Retrieved {len(email_list)} emails")
            return email_list

        except HttpError as e:
            logger.error(f"Gmail API error: {str(e)}")
            return []

    def list_calendar_events(self, days_ahead: int = 7) -> List[Dict[str, Any]]:
        """
        List upcoming calendar events

        Args:
            days_ahead: Number of days to look ahead

        Returns:
            List of calendar events
        """
        if not self.calendar_service:
            logger.error("Calendar service not initialized")
            return []

        try:
            now = datetime.now(timezone.utc).isoformat()
            end_date = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).isoformat()

            events_result = self.calendar_service.events().list(
                calendarId='primary',
                timeMin=now,
                timeMax=end_date,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])
            logger.info(f"Retrieved {len(events)} calendar events")

            return events

        except HttpError as e:
            logger.error(f"Calendar API error: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Error listing calendar events: {str(e)}")
            return []

    def create_calendar_event(self, summary: str, start_time: str, end_time: str,
                             description: Optional[str] = None) -> Optional[str]:
        """
        Create a calendar event

        Args:
            summary: Event title
            start_time: ISO format datetime
            end_time: ISO format datetime
            description: Optional event description

        Returns:
            Event ID if successful
        """
        if not self.calendar_service:
            logger.error("Calendar service not initialized")
            return None

        try:
            event = {
                'summary': summary,
                'start': {'dateTime': start_time, 'timeZone': 'UTC'},
                'end': {'dateTime': end_time, 'timeZone': 'UTC'},
            }

            if description:
                event['description'] = description

            created_event = self.calendar_service.events().insert(
                calendarId='primary',
                body=event
            ).execute()

            event_id = created_event['id']
            logger.info(f"Created calendar event: {event_id}")

            return event_id

        except HttpError as e:
            logger.error(f"Calendar API error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error creating calendar event: {str(e)}")
            return None

    def extract_calendar_events(self, transcript: str) -> List[Dict[str, Any]]:
        """
        Extract potential calendar events from transcript using Gemini AI

        Args:
            transcript: Cleaned transcript text

        Returns:
            List of event dictionaries with title, start_time, end_time, description
        """
        if not isinstance(transcript, str) or not transcript.strip():
            logger.warning("Invalid or empty transcript provided for event extraction")
            return []

        prompt = f"""Analyze this conversation transcript and extract any scheduling information, appointments, meetings, or time-sensitive commitments.

Transcript:
{transcript}

Look for:
- Explicit meeting or appointment scheduling
- Time/date references for future events
- Commitments to specific times or deadlines
- Recurring events or reminders

For each event found, extract:
- Title/Summary: Brief description of the event
- Start Time: When the event begins (use ISO format if possible, or natural language)
- End Time: When the event ends (estimate if not specified)
- Description: Additional context from the conversation

Format each event as:
EVENT: <title>
START: <start_time>
END: <end_time>
DESCRIPTION: <description>

Separate multiple events with ---

If no events are found, respond with "NO_EVENTS"

Only extract events that are clearly scheduled or committed to."""

        try:
            response = self.client.models.generate_content(
                model=self.gemini_model_name,
                contents=prompt
            )
            text = response.text.strip()

            if text == "NO_EVENTS" or not text:
                logger.info("No calendar events found in transcript")
                return []

            # Parse the response
            events = []
            event_blocks = text.split("---")

            for block in event_blocks:
                block = block.strip()
                if not block or "EVENT:" not in block:
                    continue

                event_data = {}
                lines = block.split('\n')
                for line in lines:
                    line = line.strip()
                    if line.startswith("EVENT:"):
                        event_data['title'] = line.replace("EVENT:", "").strip()
                    elif line.startswith("START:"):
                        event_data['start_time'] = line.replace("START:", "").strip()
                    elif line.startswith("END:"):
                        event_data['end_time'] = line.replace("END:", "").strip()
                    elif line.startswith("DESCRIPTION:"):
                        event_data['description'] = line.replace("DESCRIPTION:", "").strip()

                if 'title' in event_data and 'start_time' in event_data:
                    events.append(event_data)

            logger.info(f"Extracted {len(events)} potential calendar events")
            return events

        except Exception as e:
            logger.error(f"Error extracting calendar events: {str(e)}")
            return []

    def parse_event_times(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse natural language times into ISO format datetimes

        Args:
            event: Event dictionary with start_time and end_time strings

        Returns:
            Event with parsed start and end datetime strings
        """
        parsed_event = event.copy()

        try:
            # Parse start time
            if 'start_time' in event:
                start_str = event['start_time']
                # Try to parse as datetime, if fails, assume it's relative to now
                try:
                    start_dt = date_parser.parse(start_str, fuzzy=True)
                    # If no year specified and it's in the past, assume next occurrence
                    now = datetime.now()
                    if start_dt < now and start_dt.year == now.year:
                        # For months, add a year if past
                        if start_dt.month < now.month or (start_dt.month == now.month and start_dt.day < now.day):
                            start_dt = start_dt.replace(year=now.year + 1)
                        elif start_dt.month == now.month and start_dt.day == now.day and start_dt.hour < now.hour:
                            start_dt = start_dt.replace(year=now.year + 1)
                    parsed_event['start_datetime'] = start_dt.isoformat()
                except:
                    logger.warning(f"Could not parse start time: {start_str}")
                    parsed_event['start_datetime'] = None

            # Parse end time
            if 'end_time' in event:
                end_str = event['end_time']
                try:
                    end_dt = date_parser.parse(end_str, fuzzy=True)
                    # If same logic as start
                    now = datetime.now()
                    if 'start_datetime' in parsed_event and parsed_event['start_datetime']:
                        start_dt = datetime.fromisoformat(parsed_event['start_datetime'])
                        if end_dt < start_dt:
                            # If end is before start, assume next day or add duration
                            end_dt = start_dt + timedelta(hours=1)  # Default 1 hour
                    parsed_event['end_datetime'] = end_dt.isoformat()
                except:
                    # Default to 1 hour after start
                    if 'start_datetime' in parsed_event and parsed_event['start_datetime']:
                        start_dt = datetime.fromisoformat(parsed_event['start_datetime'])
                        end_dt = start_dt + timedelta(hours=1)
                        parsed_event['end_datetime'] = end_dt.isoformat()
                    else:
                        logger.warning(f"Could not parse end time: {end_str}")
                        parsed_event['end_datetime'] = None

        except Exception as e:
            logger.error(f"Error parsing event times: {str(e)}")

        return parsed_event

    def create_events_from_transcript(self, transcript: str) -> List[str]:
        """
        Extract and create calendar events from transcript

        Args:
            transcript: Cleaned transcript text

        Returns:
            List of created event IDs
        """
        if not self.calendar_service:
            logger.error("Calendar service not initialized")
            return []

        # Extract potential events
        raw_events = self.extract_calendar_events(transcript)
        if not raw_events:
            return []

        created_event_ids = []

        for event in raw_events:
            # Parse times
            parsed_event = self.parse_event_times(event)

            if not parsed_event.get('start_datetime') or not parsed_event.get('end_datetime'):
                logger.warning(f"Skipping event due to invalid times: {event}")
                continue

            # Create the event
            event_id = self.create_calendar_event(
                summary=parsed_event['title'],
                start_time=parsed_event['start_datetime'],
                end_time=parsed_event['end_datetime'],
                description=parsed_event.get('description', '')
            )

            if event_id:
                created_event_ids.append(event_id)

        logger.info(f"Created {len(created_event_ids)} calendar events from transcript")
        return created_event_ids

    def create_presentation(self, title: str, slides_content: List[Dict[str, Any]]) -> Optional[str]:
        """
        Create a Google Slides presentation with template-based slides

        Args:
            title: Presentation title
            slides_content: List of slide dictionaries with 'layout', 'title', and 'body'

        Returns:
            Presentation ID if successful
        """
        if not self.slides_service:
            logger.error("Slides service not initialized")
            return None

        try:
            # Create presentation
            presentation = self.slides_service.presentations().create(
                body={'title': title}
            ).execute()

            presentation_id = presentation['presentationId']
            logger.info(f"Created presentation: {presentation_id}")

            # Create slides first
            create_requests = []
            for i, slide_data in enumerate(slides_content):
                slide_id = f'slide_{i}'
                layout = slide_data.get('layout', 'TITLE_AND_BODY')

                # Map layout names to Google Slides predefined layouts
                layout_mapping = {
                    'TITLE': 'TITLE',
                    'TITLE_ONLY': 'TITLE_ONLY',
                    'TITLE_AND_BODY': 'TITLE_AND_BODY',
                    'BLANK': 'BLANK',
                    'SECTION_HEADER': 'SECTION_HEADER',
                    'SECTION_TITLE_AND_DESCRIPTION': 'SECTION_TITLE_AND_DESCRIPTION'
                }

                predefined_layout = layout_mapping.get(layout, 'TITLE_AND_BODY')

                create_requests.append({
                    'createSlide': {
                        'objectId': slide_id,
                        'slideLayoutReference': {
                            'predefinedLayout': predefined_layout
                        }
                    }
                })

            # Execute slide creation
            if create_requests:
                self.slides_service.presentations().batchUpdate(
                    presentationId=presentation_id,
                    body={'requests': create_requests}
                ).execute()

            # Now populate slides with content
            # Get the presentation to find the page elements
            presentation_data = self.slides_service.presentations().get(
                presentationId=presentation_id
            ).execute()

            content_requests = []
            for i, slide_data in enumerate(slides_content):
                slide_id = f'slide_{i}'
                title_text = slide_data.get('title', '')
                body_text = slide_data.get('body', '')

                # Find the slide in presentation data
                slide_page = None
                for page in presentation_data.get('slides', []):
                    if page.get('objectId') == slide_id:
                        slide_page = page
                        break

                if not slide_page:
                    continue

                # Find text elements on the slide
                page_elements = slide_page.get('pageElements', [])
                title_element_id = None
                body_element_id = None

                for element in page_elements:
                    if element.get('shape', {}).get('shapeType') == 'TEXT_BOX':
                        # Check if it's a title or body based on position/size (simplified)
                        element_id = element.get('objectId')
                        if title_element_id is None:
                            title_element_id = element_id
                        elif body_element_id is None:
                            body_element_id = element_id

                # Update title text
                if title_element_id and title_text:
                    content_requests.append({
                        'deleteText': {
                            'objectId': title_element_id,
                            'textRange': {'type': 'ALL'}
                        }
                    })
                    content_requests.append({
                        'insertText': {
                            'objectId': title_element_id,
                            'insertionIndex': 0,
                            'text': title_text
                        }
                    })

                # Update body text
                if body_element_id and body_text:
                    content_requests.append({
                        'deleteText': {
                            'objectId': body_element_id,
                            'textRange': {'type': 'ALL'}
                        }
                    })
                    content_requests.append({
                        'insertText': {
                            'objectId': body_element_id,
                            'insertionIndex': 0,
                            'text': body_text
                        }
                    })

            # Execute content updates
            if content_requests:
                self.slides_service.presentations().batchUpdate(
                    presentationId=presentation_id,
                    body={'requests': content_requests}
                ).execute()

            logger.info(f"Created presentation with {len(slides_content)} slides and populated content")
            return presentation_id

        except HttpError as e:
            logger.error(f"Slides API error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error creating presentation: {str(e)}")
            return None
