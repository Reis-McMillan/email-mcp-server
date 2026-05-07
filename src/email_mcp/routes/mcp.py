import mcp.types as types
from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.types import Scope, Receive, Send
import logging


import email_mcp.config.config as config
from email_mcp.modules.services.context import current_user
from email_mcp.modules.services.service import Service
from email_mcp.modules.tokens import ReauthRequired
import email_mcp.modules.services.gmail_service  # noqa: F401 – registers provider
import email_mcp.modules.services.microsoft_service  # noqa: F401 – registers provider

logger = logging.getLogger(__name__)


# Define available prompts
PROMPTS = {
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


TOKEN_ID_PROPERTY = {
    "token_id": {
        "type": "integer",
        "description": (
            "Federation `token_id` of the connected account to scope this call to. "
            "Use the `token_id` value returned by a prior tool result or supplied in the user prompt."
        ),
    },
}


def _resolve_services(token_id: int | None, *, required: bool) -> list[tuple[Service, dict]]:
    """Resolve (service, external_token) pairs for the current authenticated user.

    - token_id given: exactly one matching (service, token) or ValueError.
    - token_id None and required: ValueError.
    - token_id None and not required: fan out across all connected tokens.
    """
    user = current_user.get()
    tokens = user.external_tokens or []

    if token_id is not None:
        tokens = [t for t in tokens if t.get("token_id") == token_id]
        if not tokens:
            raise ValueError(f"No connected account for token_id {token_id!r}")
    elif required:
        raise ValueError("Missing required 'token_id' parameter")

    resolved: list[tuple[Service, dict]] = []
    for tok in tokens:
        cls = Service.for_provider(tok.get("provider_id"))
        if cls is None:
            logger.warning("Skipping token with unknown provider_id: %r", tok.get("provider_id"))
            continue
        resolved.append((cls(user_id=user.user_id, subject=tok["subject"]), tok))
    return resolved


def create_server() -> Server:
    server = Server("email-mcp")

    @server.list_prompts()
    async def list_prompts() -> list[types.Prompt]:
        return list(PROMPTS.values())

    @server.get_prompt()
    async def get_prompt(
        name: str, arguments: dict[str, str] | None = None
    ) -> types.GetPromptResult:
        if name not in PROMPTS:
            raise ValueError(f"Prompt not found: {name}")

        if name == "draft-email":
            content = arguments.get("content", "")
            recipient = arguments.get("recipient", "")
            recipient_email = arguments.get("recipient_email", "")

            return types.GetPromptResult(
                messages=[
                    types.PromptMessage(
                        role="user",
                        content=types.TextContent(
                            type="text",
                            text=f"""Please draft and then send an email about {content} for {recipient} ({recipient_email}).
                            Include a subject line starting with 'Subject:' on the first line."""
                        )
                    )
                ]
            )

        elif name == "edit-draft":
            changes = arguments.get("changes", "")
            current_draft = arguments.get("current_draft", "")

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
                description="""Sends email to recipient from the specified account.
                Do not use if user only asked to draft email.
                Drafts must be approved before sending.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        **TOKEN_ID_PROPERTY,
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
                    "required": ["token_id", "recipient_id", "subject", "message"],
                },
                annotations={
                    "consent-required": True
                }
            ),
            types.Tool(
                name="trash-email",
                description="""Moves email to trash. Confirm before moving email to trash.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        **TOKEN_ID_PROPERTY,
                        "email_id": {
                            "type": "string",
                            "description": "Email ID",
                        },
                    },
                    "required": ["token_id", "email_id"],
                },
                annotations={
                    "consent-required": True
                }
            ),
            types.Tool(
                name="get-unread-emails",
                description=(
                    "Retrieve unread emails. If `token_id` is omitted, fans out across "
                    "all of the user's connected email accounts."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        **TOKEN_ID_PROPERTY,
                    },
                    "required": [],
                },
                annotations={
                    "consent-required": False
                }
            ),
            types.Tool(
                name="read-email",
                description="Retrieves given email content from the specified account.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        **TOKEN_ID_PROPERTY,
                        "email_id": {
                            "type": "string",
                            "description": "Email ID",
                        },
                    },
                    "required": ["token_id", "email_id"],
                },
                annotations={
                    "consent-required": False
                }
            ),
            types.Tool(
                name="mark-email-as-read",
                description="Marks given email as read on the specified account.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        **TOKEN_ID_PROPERTY,
                        "email_id": {
                            "type": "string",
                            "description": "Email ID",
                        },
                    },
                    "required": ["token_id", "email_id"],
                },
                annotations={
                    "consent-required": True
                }
            ),
        ]

    @server.call_tool()
    async def handle_call_tool(
        name: str, arguments: dict | None
    ) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
        arguments = arguments or {}
        token_id = arguments.get("token_id")

        try:
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

                email_lines = message.split('\n')
                if email_lines[0].startswith('Subject:'):
                    subject = email_lines[0][8:].strip()
                    message_content = '\n'.join(email_lines[1:]).strip()
                else:
                    message_content = message

                (svc, _), = _resolve_services(token_id, required=True)
                send_response = await svc.send_email(recipient, subject, message_content)

                if send_response["status"] == "success":
                    response_text = f"Email sent successfully. Message ID: {send_response['message_id']}"
                else:
                    response_text = f"Failed to send email: {send_response['error_message']}"
                return [types.TextContent(type="text", text=response_text)]

            elif name == "get-unread-emails":
                services = _resolve_services(token_id, required=False)
                aggregated: list[dict] = []
                reauth_providers: set[str] = set()
                for svc, tok in services:
                    try:
                        msgs = await svc.get_unread_emails()
                    except ReauthRequired as e:
                        reauth_providers.add(e.provider_id)
                        continue
                    except Exception as e:
                        logger.warning("get_unread_emails failed for token_id=%s: %s", tok.get("token_id"), e)
                        continue
                    if not isinstance(msgs, list):
                        logger.warning("get_unread_emails returned non-list for token_id=%s: %s", tok.get("token_id"), msgs)
                        continue
                    for m in msgs:
                        aggregated.append({
                            **m,
                            "token_id": tok.get("token_id"),
                            "account": tok.get("subject"),
                            "provider_id": tok.get("provider_id"),
                        })

                text = str(aggregated)
                if reauth_providers:
                    text += (
                        f"\n\nReauthorization required for: {', '.join(sorted(reauth_providers))}. "
                        f"Visit {config.MONEYPENNY_URL} to complete reauthorization."
                    )
                return [types.TextContent(type="text", text=text)]

            elif name in ("read-email", "trash-email", "mark-email-as-read"):
                email_id = arguments.get("email_id")
                if not email_id:
                    raise ValueError("Missing email ID parameter")

                (svc, _), = _resolve_services(token_id, required=True)

                if name == "read-email":
                    result = await svc.read_email(email_id)
                elif name == "trash-email":
                    result = await svc.trash_email(email_id)
                elif name == "mark-email-as-read":
                    result = await svc.mark_email_as_read(email_id)
                return [types.TextContent(type="text", text=str(result))]

            else:
                logger.error(f"Unknown tool: {name}")
                return [types.TextContent(type="text", text=f"Tool {name} failed: unknown tool")]
        except ReauthRequired as e:
            return [types.TextContent(
                type="text",
                text=(
                    f"Reauthorization required for provider {e.provider_id!r}. "
                    f"Visit {e.moneypenny_url} to complete reauthorization."
                ),
            )]
        except Exception as e:
            logger.exception("Tool %s failed", name)
            return [types.TextContent(type="text", text=f"Tool {name} failed: {e}")]

    return server


async def handle_streamable_http(scope: Scope, receive: Receive, send: Send):
    app = scope.get("app")
    if not app:
        raise RuntimeError("ASGI Scope does not contain the app instance.")

    session_manager: StreamableHTTPSessionManager = app.state.session_manager

    token = current_user.set(scope["user"])
    try:
        await session_manager.handle_request(scope, receive, send)
    finally:
        current_user.reset(token)
