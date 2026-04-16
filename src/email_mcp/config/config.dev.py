import os

CLIENT_ID = os.environ.get('EMAIL_MCP_CLIENT_ID')
CLIENT_SECRET = os.environ.get('EMAIL_MCP_CLIENT_SECRET')
AUTH_URL = os.environ.get('AUTH_URL')
JWKS_URL = os.environ.get('JWKS_URL')
REDIRECT_URI = 'http://localhost:8000/auth/callback'
SCOPES = 'openid google'
HOST = '0.0.0.0'
MONGO_URI = 'mongodb://mongodb:27017'
DB_NAME = 'email-mcp'