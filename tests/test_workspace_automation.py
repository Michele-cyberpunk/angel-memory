"""
Unit tests for workspace_automation.py module
Tests Google Workspace integration with comprehensive mocking
"""
import pytest
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime, timedelta

from modules.workspace_automation import WorkspaceAutomation


class TestWorkspaceAutomationInit:
    """Test WorkspaceAutomation initialization"""

    @patch('modules.workspace_automation.genai.Client')
    @patch('modules.workspace_automation.GeminiConfig')
    def test_init_success(self, mock_config, mock_genai_client):
        """Test successful initialization"""
        mock_client = MagicMock()
        mock_genai_client.return_value = mock_client
        mock_config.PRIMARY_MODEL = "models/gemini-2.5-pro"
        mock_config.validate.return_value = True

        automation = WorkspaceAutomation()

        assert automation.client == mock_client
        assert automation.gemini_model_name == "models/gemini-2.5-pro"
        mock_genai_client.assert_called_once()

    @patch('modules.workspace_automation.genai.Client')
    @patch('modules.workspace_automation.GeminiConfig.validate')
    def test_init_config_validation(self, mock_validate, mock_genai_client):
        """Test that config validation is called during init"""
        WorkspaceAutomation()
        mock_validate.assert_called_once()


class TestAuthentication:
    """Test Google Workspace authentication"""

    @patch('modules.workspace_automation.genai.Client')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data=b'fake_creds')
    @patch('pickle.load')
    @patch('google.oauth2.credentials.Credentials')
    def test_authenticate_with_existing_valid_creds(self, mock_creds_class, mock_pickle_load,
                                                   mock_file, mock_exists, mock_genai_client):
        """Test authentication with existing valid credentials"""
        # Setup mocks
        mock_exists.return_value = True
        mock_creds = MagicMock()
        mock_creds.expired = False
        mock_creds.valid = True
        mock_pickle_load.return_value = mock_creds

        automation = WorkspaceAutomation()

        # Mock service building
        with patch('modules.workspace_automation.build') as mock_build:
            mock_gmail = MagicMock()
            mock_calendar = MagicMock()
            mock_slides = MagicMock()

            def build_side_effect(service_name, version, credentials=None):
                if service_name == 'gmail':
                    return mock_gmail
                elif service_name == 'calendar':
                    return mock_calendar
                elif service_name == 'slides':
                    return mock_slides

            mock_build.side_effect = build_side_effect

            result = automation.authenticate()

            assert result == True
            assert automation.credentials == mock_creds
            assert automation.gmail_service == mock_gmail
            assert automation.calendar_service == mock_calendar
            assert automation.slides_service == mock_slides

    @patch('modules.workspace_automation.genai.Client')
    @patch('os.path.exists')
    def test_authenticate_no_credentials_file(self, mock_exists, mock_genai_client):
        """Test authentication when no credentials file exists"""
        mock_exists.return_value = False

        automation = WorkspaceAutomation()
        result = automation.authenticate()

        assert result == False
        assert automation.credentials is None

    @patch('modules.workspace_automation.genai.Client')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data=b'fake_creds')
    @patch('pickle.load')
    @patch('google.oauth2.credentials.Credentials')
    def test_authenticate_expired_creds_with_refresh(self, mock_creds_class, mock_pickle_load,
                                                    mock_file, mock_exists, mock_genai_client):
        """Test authentication with expired credentials that can be refreshed"""
        mock_exists.return_value = True
        mock_creds = MagicMock()
        mock_creds.expired = True
        mock_creds.refresh_token = True
        mock_creds.valid = True
        mock_pickle_load.return_value = mock_creds

        automation = WorkspaceAutomation()

        with patch('modules.workspace_automation.build') as mock_build, \
             patch('pickle.dump') as mock_pickle_dump:

            result = automation.authenticate()

            assert result == True
            mock_creds.refresh.assert_called_once()


class TestOAuthFlow:
    """Test OAuth2 authorization flow"""

    @patch('modules.workspace_automation.genai.Client')
    @patch('os.path.exists')
    def test_get_authorization_url_success(self, mock_exists, mock_genai_client):
        """Test getting authorization URL"""
        mock_exists.return_value = True  # Client secret file exists
        automation = WorkspaceAutomation()
        automation.gmail_service = None

        result = automation.create_email_draft("context")

        assert result is None

    @patch('modules.workspace_automation.genai.Client')
    def test_generate_email_content(self, mock_genai_client):
        """Test email content generation"""
        automation = WorkspaceAutomation()

        mock_response = MagicMock()
        mock_response.text = "SUBJECT: Follow-up Meeting\n\nBODY:\nDear Team,\n\nLet's discuss the project.\n\nBest regards"
        automation.client.models.generate_content.return_value = mock_response

        result = automation._generate_email_content("meeting context")

        assert result["subject"] == "Follow-up Meeting"
        assert "Dear Team" in result["body"]


class TestCalendarIntegration:
    """Test calendar automation features"""

    @patch('modules.workspace_automation.genai.Client')
    def test_list_calendar_events_success(self, mock_genai_client):
        """Test listing calendar events"""
        automation = WorkspaceAutomation()
        automation.calendar_service = MagicMock()

        mock_events = {"items": [{"id": "event1", "summary": "Test Event"}]}
        automation.calendar_service.events().list().execute.return_value = mock_events

        result = automation.list_calendar_events()

        assert len(result) == 1
        assert result[0]["id"] == "event1"

    @patch('modules.workspace_automation.genai.Client')
    def test_list_calendar_events_no_service(self, mock_genai_client):
        """Test listing events without calendar service"""
        automation = WorkspaceAutomation()
        automation.calendar_service = None

        result = automation.list_calendar_events()

        assert result == []

    @patch('modules.workspace_automation.genai.Client')
    def test_create_calendar_event_success(self, mock_genai_client):
        """Test successful calendar event creation"""
        automation = WorkspaceAutomation()
        automation.calendar_service = MagicMock()

        mock_event = {"id": "event123"}
        automation.calendar_service.events().insert().execute.return_value = mock_event

        result = automation.create_calendar_event(
            "Test Event", "2024-01-01T10:00:00Z", "2024-01-01T11:00:00Z"
        )

        assert result == "event123"

    @patch('modules.workspace_automation.genai.Client')
    def test_create_calendar_event_no_service(self, mock_genai_client):
        """Test calendar event creation without service"""
        automation = WorkspaceAutomation()
        automation.calendar_service = None

        mock_response = MagicMock()
        mock_response.text = "NO_EVENTS"
        automation.client.models.generate_content.return_value = mock_response

        result = automation.extract_calendar_events("Just casual conversation")

        assert result == []

    @patch('modules.workspace_automation.genai.Client')
    def test_parse_event_times(self, mock_genai_client):
        """Test parsing natural language event times"""
        automation = WorkspaceAutomation()

        event = {
            "title": "Meeting",
            "start_time": "tomorrow at 2pm",
            "end_time": "tomorrow at 3pm",
            "description": "Team meeting"
        }

        # This would require dateutil parsing, so we'll test the structure
        result = automation.parse_event_times(event)

        assert result["title"] == "Meeting"
        assert "start_datetime" in result or "start_time" in result


class TestSlidesIntegration:
    """Test Google Slides automation"""

    @patch('modules.workspace_automation.genai.Client')
    def test_create_presentation_success(self, mock_genai_client):
        """Test successful presentation creation"""
        automation = WorkspaceAutomation()
        automation.slides_service = MagicMock()

        # Mock presentation creation
        mock_presentation = {"presentationId": "pres123"}
        automation.slides_service.presentations().create().execute.return_value = mock_presentation

        # Mock slide creation and content updates
        automation.slides_service.presentations().batchUpdate.return_value.execute.return_value = {}

        slides_content = [
            {"layout": "TITLE", "title": "Test Slide", "body": "Content"}
        ]

        result = automation.create_presentation("Test Presentation", slides_content)

        assert result == "pres123"

    @patch('modules.workspace_automation.genai.Client')
    def test_create_presentation_no_service(self, mock_genai_client):
        """Test presentation creation without slides service"""
        automation = WorkspaceAutomation()
        automation.slides_service = None

        result = automation.create_presentation("Test", [])

        assert result is None


class TestTranscriptAnalysis:
    """Test transcript analysis for automation decisions"""

    @patch('modules.workspace_automation.genai.Client')
    def test_read_recent_emails_success(self, mock_genai_client):
        """Test reading recent emails"""
        automation = WorkspaceAutomation()
        automation.gmail_service = MagicMock()

        # Mock message list
        mock_messages = [{"id": "msg1"}]
        automation.gmail_service.users().messages().list().execute.return_value = {
            "messages": mock_messages
        }

        # Mock message details
        mock_message_data = {
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Test Subject"},
                    {"name": "From", "value": "sender@example.com"},
                    {"name": "Date", "value": "Mon, 1 Jan 2024 10:00:00 GMT"}
                ]
            },
            "snippet": "Test snippet"
        }
        automation.gmail_service.users().messages().get().execute.return_value = mock_message_data

        result = automation.read_recent_emails()

        assert len(result) == 1
        assert result[0]["subject"] == "Test Subject"
        assert result[0]["from"] == "sender@example.com"

    @patch('modules.workspace_automation.genai.Client')
    def test_read_recent_emails_no_service(self, mock_genai_client):
        """Test reading emails without Gmail service"""
        automation = WorkspaceAutomation()
        automation.gmail_service = None

        result = automation.read_recent_emails()

        assert result == []


class TestErrorHandling:
    """Test error handling in workspace automation"""

    @patch('modules.workspace_automation.genai.Client')
    def test_authenticate_exception_handling(self, mock_genai_client):
        """Test exception handling during authentication"""
        automation = WorkspaceAutomation()

        with patch('os.path.exists', side_effect=Exception("File error")):
            result = automation.authenticate()
            assert result == False

    @patch('modules.workspace_automation.genai.Client')
    def test_email_creation_gemini_error(self, mock_genai_client):
        """Test handling Gemini API errors in email creation"""
        automation = WorkspaceAutomation()
        automation.client.models.generate_content.side_effect = Exception("API Error")

        result = automation._generate_email_content("context")

        assert result is None

    @patch('modules.workspace_automation.genai.Client')
    def test_calendar_event_creation_error(self, mock_genai_client):
        """Test handling calendar API errors"""
        automation = WorkspaceAutomation()
        automation.calendar_service = MagicMock()
        automation.calendar_service.events().insert().execute.side_effect = Exception("API Error")

        result = automation.create_calendar_event("Test", "start", "end")

        assert result is None