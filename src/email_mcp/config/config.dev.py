import os

CLIENT_ID = os.environ.get('EMAIL_MCP_CLIENT_ID')
CLIENT_SECRET = os.environ.get('EMAIL_MCP_CLIENT_SECRET')
AUTH_URL = os.environ.get('AUTH_URL')
JWKS_URL = os.environ.get('JWKS_URL')
REDIRECT_URI = 'http://localhost:8000/auth/callback'
INIT_URI = 'http://localhost:8000/auth/initialize'
MCP_URI = 'http://localhost:8000/mcp'
SCOPES = 'openid google'
HOST = '0.0.0.0'
MONGO_URI = 'mongodb://localhost:27017?directConnection=true'
DB_NAME = 'email-mcp'
ALLOWED_ORIGINS=['http://localhost:5173']
