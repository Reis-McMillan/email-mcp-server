from . import server
import asyncio
import argparse

def main():
    """Main entry point for the package."""
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
    asyncio.run(server.main(
        creds_file_path=args.creds_file_path,
        token_path=args.token_path,
        transport=args.transport,
        host=args.host,
        port=args.port,
    ))

# Optionally expose other important items at package level
__all__ = ['main', 'server']
