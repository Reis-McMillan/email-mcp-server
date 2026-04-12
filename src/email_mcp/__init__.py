from . import server
import asyncio
import argparse

def main():
    parser = argparse.ArgumentParser(description='Email MCP Server')
    parser.add_argument('--host', default='localhost',
                        help='Host to bind to (default: localhost)')
    parser.add_argument('--port', type=int, default=8000,
                        help='Port to bind to (default: 8000)')

    args = parser.parse_args()
    asyncio.run(server.main(host=args.host, port=args.port))

__all__ = ['main', 'server']
