import argparse
import asyncio
import logging
from contextlib import asynccontextmanager

import mcp.types as types
from mcp.server import Server
import mcp.server.stdio
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.types import Scope, Receive, Send
import uvicorn

from gmail.gmail_service import GmailService


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

EMAIL_ADMIN_PROMPTS = """You are an email administrator.
You can draft, edit, read, trash, open, and send emails.
You've been given access to a specific gmail account.
You have the following tools available:
- Send an email (send-email)
- Retrieve unread emails (get-unread-emails)
- Read email content (read-email)
- Trash email (tras-email)
- Open email in browser (open-email)
Never send an email draft or trash an email unless the user confirms first.
Always ask for approval if not already given.
"""

# Define available prompts
PROMPTS = {
    "manage-email": types.Prompt(
        name="manage-email",
        description="Act like an email administator",
        arguments=None,
    ),
    "draft-email": types.Prompt(
        name="draft-email",
        description="Draft an email with cotent and recipient",
        arguments=[
            types.PromptArgument(
                name="content",
                description="What the email is about",
                required=True
            ),
            types.PromptArgument(
                name="recipient",
                description="Who should the email be addressed to",
                required=True
            ),
            types.PromptArgument(
                name="recipient_email",
                description="Recipient's email address",
                required=True
            ),
        ],
    ),
    "edit-draft": types.Prompt(
        name="edit-draft",
        description="Edit the existing email draft",
        arguments=[
            types.PromptArgument(
                name="changes",
                description="What changes should be made to the draft",
                required=True
            ),
            types.PromptArgument(
                name="current_draft",
                description="The current draft to edit",
                required=True
            ),
        ],
    ),
}


def create_server(gmail_service: GmailService) -> Server:
    server = Server("gmail")

    @server.list_prompts()
    async def list_prompts() -> list[types.Prompt]:
        return list(PROMPTS.values())

    @server.get_prompt()
    async def get_prompt(
        name: str, arguments: dict[str, str] | None = None
    ) -> types.GetPromptResult:
        if name not in PROMPTS:
            raise ValueError(f"Prompt not found: {name}")

        if name == "manage-email":
            return types.GetPromptResult(
                messages=[
                    types.PromptMessage(
                        role="user",
                        content=types.TextContent(
                            type="text",
                            text=EMAIL_ADMIN_PROMPTS,
                        )
                    )
                ]
            )

        if name == "draft-email":
            content = arguments.get("content", "")
            recipient = arguments.get("recipient", "")
            recipient_email = arguments.get("recipient_email", "")

            # First message asks the LLM to create the draft
            return types.GetPromptResult(
                messages=[
                    types.PromptMessage(
                        role="user",
                        content=types.TextContent(
                            type="text",
                            text=f"""Please draft an email about {content} for {recipient} ({recipient_email}).
                            Include a subject line starting with 'Subject:' on the first line.
                            Do not send the email yet, just draft it and ask the user for their thoughts."""
                        )
                    )
                ]
            )

        elif name == "edit-draft":
            changes = arguments.get("changes", "")
            current_draft = arguments.get("current_draft", "")

            # Edit existing draft based on requested changes
            return types.GetPromptResult(
                messages=[
                    types.PromptMessage(
                        role="user",
                        content=types.TextContent(
                            type="text",
                            text=f"""Please revise the current email draft:
                            {current_draft}

                            Requested changes:
                            {changes}

                            Please provide the updated draft."""
                        )
                    )
                ]
            )

        raise ValueError("Prompt implementation not found")

    @server.list_tools()
    async def handle_list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="send-email",
                description="""Sends email to recipient.
                Do not use if user only asked to draft email.
                Drafts must be approved before sending.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "recipient_id": {
                            "type": "string",
                            "description": "Recipient email address",
                        },
                        "subject": {
                            "type": "string",
                            "description": "Email subject",
                        },
                        "message": {
                            "type": "string",
                            "description": "Email content text",
                        },
                    },
                    "required": ["recipient_id", "subject", "message"],
                },
            ),
            types.Tool(
                name="trash-email",
                description="""Moves email to trash.
                Confirm before moving email to trash.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "email_id": {
                            "type": "string",
                            "description": "Email ID",
                        },
                    },
                    "required": ["email_id"],
                },
            ),
            types.Tool(
                name="get-unread-emails",
                description="Retrieve unread emails",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                },
            ),
            types.Tool(
                name="read-email",
                description="Retrieves given email content",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "email_id": {
                            "type": "string",
                            "description": "Email ID",
                        },
                    },
                    "required": ["email_id"],
                },
            ),
            types.Tool(
                name="mark-email-as-read",
                description="Marks given email as read",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "email_id": {
                            "type": "string",
                            "description": "Email ID",
                        },
                    },
                    "required": ["email_id"],
                },
            ),
            types.Tool(
                name="open-email",
                description="Open email in browser",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "email_id": {
                            "type": "string",
                            "description": "Email ID",
                        },
                    },
                    "required": ["email_id"],
                },
            ),
        ]

    @server.call_tool()
    async def handle_call_tool(
        name: str, arguments: dict | None
    ) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:

        if name == "send-email":
            recipient = arguments.get("recipient_id")
            if not recipient:
                raise ValueError("Missing recipient parameter")
            subject = arguments.get("subject")
            if not subject:
                raise ValueError("Missing subject parameter")
            message = arguments.get("message")
            if not message:
                raise ValueError("Missing message parameter")

            # Extract subject and message content
            email_lines = message.split('\n')
            if email_lines[0].startswith('Subject:'):
                subject = email_lines[0][8:].strip()
                message_content = '\n'.join(email_lines[1:]).strip()
            else:
                message_content = message

            send_response = await gmail_service.send_email(recipient, subject, message_content)

            if send_response["status"] == "success":
                response_text = f"Email sent successfully. Message ID: {send_response['message_id']}"
            else:
                response_text = f"Failed to send email: {send_response['error_message']}"
            return [types.TextContent(type="text", text=response_text)]

        if name == "get-unread-emails":

            unread_emails = await gmail_service.get_unread_emails()
            return [types.TextContent(type="text", text=str(unread_emails),artifact={"type": "json", "data": unread_emails} )]

        if name == "read-email":
            email_id = arguments.get("email_id")
            if not email_id:
                raise ValueError("Missing email ID parameter")

            retrieved_email = await gmail_service.read_email(email_id)
            return [types.TextContent(type="text", text=str(retrieved_email),artifact={"type": "dictionary", "data": retrieved_email} )]
        if name == "open-email":
            email_id = arguments.get("email_id")
            if not email_id:
                raise ValueError("Missing email ID parameter")

            msg = await gmail_service.open_email(email_id)
            return [types.TextContent(type="text", text=str(msg))]
        if name == "trash-email":
            email_id = arguments.get("email_id")
            if not email_id:
                raise ValueError("Missing email ID parameter")

            msg = await gmail_service.trash_email(email_id)
            return [types.TextContent(type="text", text=str(msg))]
        if name == "mark-email-as-read":
            email_id = arguments.get("email_id")
            if not email_id:
                raise ValueError("Missing email ID parameter")

            msg = await gmail_service.mark_email_as_read(email_id)
            return [types.TextContent(type="text", text=str(msg))]
        else:
            logger.error(f"Unknown tool: {name}")
            raise ValueError(f"Unknown tool: {name}")

    return server


async def main(
    creds_file_path: str,
    token_path: str,
    transport: str = "stdio",
    host: str = "localhost",
    port: int = 8000,
):
    gmail_service = GmailService(creds_file_path, token_path)
    server = create_server(gmail_service)

    if transport == "stdio":
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
    elif transport == "http":
        session_manager = StreamableHTTPSessionManager(app=server)

        async def handle_streamable_http(scope: Scope, receive: Receive, send: Send):
            await session_manager.handle_request(scope, receive, send)

        @asynccontextmanager
        async def lifespan(app):
            async with session_manager.run():
                yield

        starlette_app = Starlette(
            routes=[Route("/mcp", endpoint=handle_streamable_http)],
            lifespan=lifespan,
        )

        logger.info(f"Starting HTTP server on {host}:{port}")
        config = uvicorn.Config(starlette_app, host=host, port=port, log_level="info")
        uv_server = uvicorn.Server(config)
        await uv_server.serve()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Gmail API MCP Server')
    parser.add_argument('--creds-file-path',
                        required=True,
                       help='OAuth 2.0 credentials file path')
    parser.add_argument('--token-path',
                        required=True,
                       help='File location to store and retrieve access and refresh tokens for application')
    parser.add_argument('--transport',
                        choices=['stdio', 'http'],
                        default='stdio',
                        help='Transport type (default: stdio)')
    parser.add_argument('--host',
                        default='localhost',
                        help='Host for HTTP transport (default: localhost)')
    parser.add_argument('--port',
                        type=int,
                        default=8000,
                        help='Port for HTTP transport (default: 8000)')

    args = parser.parse_args()
    asyncio.run(main(args.creds_file_path, args.token_path,
                     args.transport, args.host, args.port))