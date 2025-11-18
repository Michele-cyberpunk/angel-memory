"""
Google Workspace Automation
Handles Gmail, Calendar, and Slides API interactions
"""
import os
import base64
import pickle
from email.mime.text import MIMEText
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import google.generativeai as genai
from config.settings import GoogleWorkspaceConfig, GeminiConfig
import logging

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
        genai.configure(api_key=GeminiConfig.API_KEY)
        self.gemini_model = genai.GenerativeModel(GeminiConfig.PRIMARY_MODEL)

        logger.info("Initialized WorkspaceAutomation")

    def authenticate(self) -> bool:
        """
        Authenticate with Google Workspace APIs

        Returns:
            True if authentication successful
        """
        try:
            creds = None
            token_file = GoogleWorkspaceConfig.TOKEN_FILE
            client_secret_file = GoogleWorkspaceConfig.CLIENT_SECRET_FILE
            scopes = GoogleWorkspaceConfig.SCOPES

            # Load existing credentials
            if os.path.exists(token_file):
                with open(token_file, 'rb') as token:
                    creds = pickle.load(token)

            # Refresh or get new credentials
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                elif os.path.exists(client_secret_file):
                    flow = InstalledAppFlow.from_client_secrets_file(
                        client_secret_file, scopes)
                    creds = flow.run_local_server(port=0)
                else:
                    logger.error(f"Client secret file not found: {client_secret_file}")
                    return False

                # Save credentials
                with open(token_file, 'wb') as token:
                    pickle.dump(creds, token)

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

    def should_create_email(self, analysis: Dict[str, Any], transcript: str) -> bool:
        """
        Use Gemini to decide if email follow-up is needed

        Args:
            analysis: Psychological analysis results
            transcript: Cleaned transcript

        Returns:
            True if email should be created
        """
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
            response = self.gemini_model.generate_content(prompt)
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
        """Generate email subject and body using Gemini"""

        prompt = f"""Generate a professional email based on this context:

{context}

Create:
1. A clear, concise subject line (max 60 characters)
2. A well-structured email body with:
   - Professional greeting
   - Clear purpose
   - Action items or next steps
   - Professional closing

Format your response as:
SUBJECT: <subject line>

BODY:
<email body>"""

        try:
            response = self.gemini_model.generate_content(prompt)
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
            now = datetime.utcnow().isoformat() + 'Z'
            end_date = (datetime.utcnow() + timedelta(days=days_ahead)).isoformat() + 'Z'

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

    def create_presentation(self, title: str, slides_content: List[Dict[str, Any]]) -> Optional[str]:
        """
        Create a Google Slides presentation

        Args:
            title: Presentation title
            slides_content: List of slide dictionaries with 'title' and 'body'

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

            # Add slides
            requests = []
            for i, slide_data in enumerate(slides_content):
                # Create slide
                slide_id = f'slide_{i}'
                requests.append({
                    'createSlide': {
                        'objectId': slide_id,
                        'slideLayoutReference': {
                            'predefinedLayout': 'TITLE_AND_BODY'
                        }
                    }
                })

            if requests:
                self.slides_service.presentations().batchUpdate(
                    presentationId=presentation_id,
                    body={'requests': requests}
                ).execute()

            logger.info(f"Added {len(slides_content)} slides")
            return presentation_id

        except HttpError as e:
            logger.error(f"Slides API error: {str(e)}")
            return None
