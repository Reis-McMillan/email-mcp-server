import os

CLIENT_ID = os.environ.get('EMAIL_MCP_CLIENT_ID')
CLIENT_SECRET = os.environ.get('EMAIL_MCP_CLIENT_SECRET')
AUTH_URL = os.environ.get('AUTH_URL')
JWKS_URL = os.environ.get('JWKS_URL')
REDIRECT_URI = os.environ.get('EMAIL_MCP_REDIRECT_URI')
SCOPES = os.environ.get('SCOPES')
HOST = '0.0.0.0'
MONGO_URI = 'mongodb://localhost:27017'
DB_NAME = 'email-mcp'