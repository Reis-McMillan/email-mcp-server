import logging
import time
import webbrowser

from azure.core.credentials import AccessToken
from azure.core.credentials_async import AsyncTokenCredential
from msgraph import GraphServiceClient
from msgraph.generated.users.item.send_mail.send_mail_post_request_body import SendMailPostRequestBody
from msgraph.generated.models.message import Message
from msgraph.generated.models.item_body import ItemBody
from msgraph.generated.models.body_type import BodyType
from msgraph.generated.models.recipient import Recipient
from msgraph.generated.models.email_address import EmailAddress

from email_mcp.modules.services.service import Service


logger = logging.getLogger(__name__)


class _ExternalTokenCredential(AsyncTokenCredential):
    """Credential wrapper that delegates to Service.get_token()."""

    def __init__(self, service: Service):
        self._service = service

    async def get_token(self, *scopes, **kwargs) -> AccessToken:
        token_data = await self._service.get_token()
        expires_on = token_data.get('expires_on', int(time.time()) + 3600)
        return AccessToken(token_data['access_token'], expires_on)

    async def close(self):
        pass


class MicrosoftService(Service):
    provider_id = "microsoft"
    _client: GraphServiceClient | None = None

    @property
    def client(self) -> GraphServiceClient:
        if self._client is None:
            self._client = GraphServiceClient(
                credentials=_ExternalTokenCredential(self),
                scopes=["https://graph.microsoft.com/.default"],
            )
        return self._client

    async def send_email(self, recipient_id: str, subject: str, message: str) -> dict:
        """Creates and sends an email message via Microsoft Graph."""
        try:
            msg = Message(
                subject=subject,
                body=ItemBody(content=message, content_type=BodyType.Text),
                to_recipients=[
                    Recipient(
                        email_address=EmailAddress(address=recipient_id)
                    )
                ],
            )
            request_body = SendMailPostRequestBody(
                message=msg,
                save_to_sent_items=True,
            )
            await self.client.me.send_mail.post(request_body)
            logger.info(f"Email sent to {recipient_id}")
            return {"status": "success", "message_id": "sent"}
        except Exception as error:
            return {"status": "error", "error_message": str(error)}

    async def open_email(self, email_id: str) -> str:
        """Opens email in Outlook web given ID."""
        try:
            msg = await self.client.me.messages.by_message_id(email_id).get()
            web_link = msg.web_link if msg and msg.web_link else f"https://outlook.office.com/mail/id/{email_id}"
            webbrowser.open(web_link, new=0, autoraise=True)
            return "Email opened in browser successfully."
        except Exception as error:
            return f"An error occurred: {str(error)}"

    async def get_unread_emails(self) -> list[dict[str, str]] | str:
        """Retrieves unread messages from inbox."""
        try:
            from msgraph.generated.users.item.mail_folders.item.messages.messages_request_builder import MessagesRequestBuilder

            query_params = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
                filter="isRead eq false",
                select=["id", "subject", "from", "receivedDateTime"],
                top=25,
            )
            config = MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
                query_parameters=query_params,
            )

            result = await self.client.me.mail_folders.by_mail_folder_id("inbox").messages.get(
                request_configuration=config,
            )

            messages = []
            if result and result.value:
                for msg in result.value:
                    messages.append({"id": msg.id})

                while result.odata_next_link:
                    result = await self.client.me.mail_folders.by_mail_folder_id("inbox").messages.get()
                    if result and result.value:
                        messages.extend({"id": msg.id} for msg in result.value)
                    else:
                        break

            return messages
        except Exception as error:
            return f"An error occurred: {str(error)}"

    async def read_email(self, email_id: str) -> dict[str, str] | str:
        """Retrieves email contents including to, from, subject, and contents."""
        try:
            msg = await self.client.me.messages.by_message_id(email_id).get()

            email_metadata = {}
            email_metadata["content"] = msg.body.content if msg.body else ""
            email_metadata["subject"] = msg.subject or ""
            email_metadata["from"] = (
                msg.from_.email_address.address
                if msg.from_ and msg.from_.email_address
                else ""
            )
            email_metadata["to"] = (
                ", ".join(
                    r.email_address.address
                    for r in (msg.to_recipients or [])
                    if r.email_address
                )
            )
            email_metadata["date"] = str(msg.received_date_time or "")

            logger.info(f"Email read: {email_id}")
            await self.mark_email_as_read(email_id)

            return email_metadata
        except Exception as error:
            return f"An error occurred: {str(error)}"

    async def trash_email(self, email_id: str) -> str:
        """Moves email to deleted items."""
        try:
            from msgraph.generated.users.item.messages.item.move.move_post_request_body import MovePostRequestBody

            request_body = MovePostRequestBody(
                destination_id="deleteditems",
            )
            await self.client.me.messages.by_message_id(email_id).move.post(request_body)
            logger.info(f"Email moved to trash: {email_id}")
            return "Email moved to trash successfully."
        except Exception as error:
            return f"An error occurred: {str(error)}"

    async def mark_email_as_read(self, email_id: str) -> str:
        """Marks email as read."""
        try:
            msg = Message(is_read=True)
            await self.client.me.messages.by_message_id(email_id).patch(msg)
            logger.info(f"Email marked as read: {email_id}")
            return "Email marked as read."
        except Exception as error:
            return f"An error occurred: {str(error)}"
