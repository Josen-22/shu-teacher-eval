import os, sys

# Setup paths BEFORE importing Flask
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

os.environ['DB_DIR'] = '/tmp'
os.environ['APP_ENV'] = 'production'

# Prepend backend to ensure models.py is found
from backend.app import app as application
app = application
