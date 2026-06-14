"""
Production launcher for 管院教师评价系统
Uses Waitress (Windows-compatible WSGI server)
"""
import os
import sys

# Add backend to path
backend_dir = os.path.join(os.path.dirname(__file__), 'backend')
sys.path.insert(0, backend_dir)
os.chdir(backend_dir)

# Production config
os.environ['APP_ENV'] = 'production'
os.environ['SESSION_COOKIE_SAMESITE'] = 'Lax'
os.environ['COOKIE_SECURE'] = '0'  # Set to 1 if using HTTPS

# Auto-generate or load secret key
secret_file = os.path.join(os.path.dirname(backend_dir), '.secret_key')
if os.environ.get('SECRET_KEY'):
    pass  # Use env var
elif os.path.exists(secret_file):
    with open(secret_file) as f:
        os.environ['SECRET_KEY'] = f.read().strip()
else:
    import secrets
    key = secrets.token_hex(32)
    with open(secret_file, 'w') as f:
        f.write(key)
    os.environ['SECRET_KEY'] = key
    print(f'[INFO] Generated new secret key at {secret_file}')

from app import app

if __name__ == '__main__':
    try:
        from waitress import serve
        print('Starting production server on http://127.0.0.1:5000')
        print('Press Ctrl+C to stop')
        serve(app, host='127.0.0.1', port=5000, threads=4)
    except ImportError:
        print('Waitress not installed. Falling back to Flask dev server.')
        print('Install waitress: pip install waitress')
        app.run(debug=False, host='127.0.0.1', port=5000)
