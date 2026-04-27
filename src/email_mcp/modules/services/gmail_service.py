import asyncio
import base64
import logging
import webbrowser
from email.header import decode_header
from email.message import EmailMessage
from email import message_from_bytes
from base64 import urlsafe_b64decode

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from email_mcp.modules.services.service import Service


logger = logging.getLogger(__name__)


def decode_mime_header(header: str) -> str:
    """Helper function to decode encoded email headers"""
    decoded_parts = decode_header(header)
    decoded_string = ''
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            decoded_string += part.decode(encoding or 'utf-8')
        else:
            decoded_string += part
    return decoded_string


class GmailService(Service):
    provider_id = "google"
    _service = None

    async def _ensure_service(self):
        if self._service is None:
            token_data = await self.get_token()
            creds = Credentials(token=token_data['access_token'])
            self._service = build('gmail', 'v1', credentials=creds)
        return self._service

    async def send_email(self, recipient_id: str, subject: str, message: str) -> dict:
        """Creates and sends an email message"""
        try:
            service = await self._ensure_service()
            profile = await asyncio.to_thread(
                service.users().getProfile(userId='me').execute
            )
            user_email = profile.get('emailAddress', '')

            message_obj = EmailMessage()
            message_obj.set_content(message)
            message_obj['To'] = recipient_id
            message_obj['From'] = user_email
            message_obj['Subject'] = subject

            encoded_message = base64.urlsafe_b64encode(message_obj.as_bytes()).decode()
            create_message = {'raw': encoded_message}

            send_message = await asyncio.to_thread(
                service.users().messages().send(userId="me", body=create_message).execute
            )
            logger.info(f"Message sent: {send_message['id']}")
            return {"status": "success", "message_id": send_message["id"]}
        except HttpError as error:
            return {"status": "error", "error_message": str(error)}

    async def open_email(self, email_id: str) -> str:
        """Opens email in browser given ID."""
        try:
            url = f"https://mail.google.com/#all/{email_id}"
            webbrowser.open(url, new=0, autoraise=True)
            return "Email opened in browser successfully."
        except HttpError as error:
            return f"An HttpError occurred: {str(error)}"

    async def get_unread_emails(self) -> list[dict[str, str]] | str:
        """Retrieves unread messages from mailbox."""
        try:
            service = await self._ensure_service()
            user_id = 'me'
            query = 'in:inbox is:unread category:primary'

            response = service.users().messages().list(userId=user_id, q=query).execute()
            messages = []
            if 'messages' in response:
                messages.extend(response['messages'])

            while 'nextPageToken' in response:
                page_token = response['nextPageToken']
                response = service.users().messages().list(
                    userId=user_id, q=query, pageToken=page_token
                ).execute()
                messages.extend(response['messages'])
            return messages
        except HttpError as error:
            return f"An HttpError occurred: {str(error)}"

    async def read_email(self, email_id: str) -> dict[str, str] | str:
        """Retrieves email contents including to, from, subject, and contents."""
        try:
            service = await self._ensure_service()
            msg = service.users().messages().get(userId="me", id=email_id, format='raw').execute()
            email_metadata = {}

            raw_data = msg['raw']
            decoded_data = urlsafe_b64decode(raw_data)
            mime_message = message_from_bytes(decoded_data)

            body = None
            if mime_message.is_multipart():
                for part in mime_message.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode()
                        break
            else:
                body = mime_message.get_payload(decode=True).decode()
            email_metadata['content'] = body

            email_metadata['subject'] = decode_mime_header(mime_message.get('subject', ''))
            email_metadata['from'] = mime_message.get('from', '')
            email_metadata['to'] = mime_message.get('to', '')
            email_metadata['date'] = mime_message.get('date', '')

            logger.info(f"Email read: {email_id}")
            await self.mark_email_as_read(email_id)

            return email_metadata
        except HttpError as error:
            return f"An HttpError occurred: {str(error)}"

    async def trash_email(self, email_id: str) -> str:
        """Moves email to trash given ID."""
        try:
            service = await self._ensure_service()
            service.users().messages().trash(userId="me", id=email_id).execute()
            logger.info(f"Email moved to trash: {email_id}")
            return "Email moved to trash successfully."
        except HttpError as error:
            return f"An HttpError occurred: {str(error)}"

    async def mark_email_as_read(self, email_id: str) -> str:
        """Marks email as read given ID."""
        try:
            service = await self._ensure_service()
            service.users().messages().modify(
                userId="me", id=email_id, body={'removeLabelIds': ['UNREAD']}
            ).execute()
            logger.info(f"Email marked as read: {email_id}")
            return "Email marked as read."
        except HttpError as error:
            return f"An HttpError occurred: {str(error)}"
