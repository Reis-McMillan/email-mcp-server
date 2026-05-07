import os

CLIENT_ID = os.environ.get('CLIENT_ID')
CLIENT_SECRET = os.environ.get('CLIENT_SECRET')
AUTH_URL = os.environ.get('AUTH_URL')
JWKS_URL = os.environ.get('JWKS_URL')
REDIRECT_URI = os.environ.get('REDIRECT_URI')
INIT_URI = os.environ.get('INIT_URI')
MCP_URI = os.environ.get('MCP_URI')
SCOPES = os.environ.get('SCOPES')
HOST = '0.0.0.0'
MONGO_URI = os.environ.get('MONGO_URI')
DB_NAME = 'email-mcp'
MONEYPENNY_URL = os.environ.get('MONEYPENNY_URL')
MONEYPENNY_CLIENT_ID = os.environ.get('MONEYPENNY_CLIENT_ID')
ALLOWED_ORIGINS=['https://moneypenny.mcmlln.dev']
