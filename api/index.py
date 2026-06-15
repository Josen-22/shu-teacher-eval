import os, sys, json
from pathlib import Path

# Vercel puts /tmp as writable; use it for SQLite
os.environ.setdefault('DB_DIR', '/tmp')
os.environ.setdefault('APP_ENV', 'production')

# Add backend to path
backend_dir = os.path.join(os.path.dirname(__file__), '..', 'backend')
sys.path.insert(0, backend_dir)

from app import app as application

# Export for Vercel
app = application
