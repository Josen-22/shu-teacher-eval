from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Teacher, Course, Evaluation
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import json
import os
import secrets
import threading
import time
from scraper import run_scraper

app = Flask(__name__)
# Use /tmp for Vercel (writable), instance/ for local/dev
basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
_db_dir = os.environ.get('DB_DIR') or os.path.join(basedir, 'instance')
if not os.path.exists(_db_dir):
    os.makedirs(_db_dir, exist_ok=True)
db_path = os.path.join(_db_dir, 'management_college.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'dev-secret-key'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = os.environ.get('SESSION_COOKIE_SAMESITE') or 'Lax'
app_env = (os.environ.get('APP_ENV') or '').lower()
cookie_secure_env = (os.environ.get('COOKIE_SECURE') or '').lower()
app.config['SESSION_COOKIE_SECURE'] = (app_env == 'production') or (cookie_secure_env in ('1', 'true', 'yes'))
app.config['TEMPLATES_AUTO_RELOAD'] = app_env != 'production'
app.jinja_env.auto_reload = app_env != 'production'

db.init_app(app)
cors_origins_env = os.environ.get('CORS_ORIGINS') or ''
cors_origins = ['*']
if not cors_origins:
    cors_origins = ['*']
CORS(app, supports_credentials=True, origins=cors_origins)

scrape_state = {
    "running": False,
    "last_started_at": None,
    "last_finished_at": None,
    "last_error": None,
}
scrape_lock = threading.Lock()

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_page'
login_manager.login_message = None

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@login_manager.unauthorized_handler
def unauthorized():
    if request.path.startswith('/api/'):
        return jsonify({"error": "Authentication required"}), 401
    next_url = request.full_path if request.query_string else request.path
    return redirect(url_for('login_page', next=next_url))

def serialize_user(user):
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
    }

@app.route('/login')
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    next_url = request.args.get('next') or '/'
    return render_template('login.html', next_url=next_url)

@app.route('/')
@login_required
def index():
    return render_template('index.html')

def load_course_library():
    json_path = os.path.join(basedir, 'courses_catalog_from_text.json')
    if not os.path.exists(json_path):
        return {"all": [], "by_section": {}}
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            payload = json.load(f)
    except Exception:
        return {"all": [], "by_section": {}}
    catalog = payload.get('catalog') or {}
    included = payload.get('included_sections') or []
    by_section = {s: set() for s in included}
    for _, sections in catalog.items():
        for s in included:
            for name in sections.get(s, []) or []:
                if name:
                    by_section[s].add(name)
    all_courses = set()
    for s, items in by_section.items():
        by_section[s] = sorted(items)
        all_courses.update(items)
    return {"all": sorted(all_courses), "by_section": by_section}

def load_external_teacher_names():
    path = os.path.join(os.path.dirname(__file__), "external_teachers.json")
    if not os.path.exists(path):
        return set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return {str(x).strip() for x in data if str(x).strip()}
    except Exception:
        return set()
    return set()

# API Endpoints
@app.route('/api/me', methods=['GET'])
@login_required
def get_current_user():
    return jsonify(serialize_user(current_user))

@app.route('/api/teachers', methods=['GET'])
@login_required
def get_teachers():
    teachers = Teacher.query.all()
    result = []
    for t in teachers:
        result.append({
            "id": t.id,
            "name": t.name,
            "title": t.title,
            "department": t.department,
            "email": t.email,
            "research": t.research,
            "courses": [c.name for c in t.courses]
        })
    return jsonify(result)

@app.route('/api/teachers/<int:id>', methods=['GET'])
@login_required
def get_teacher_detail(id):
    t = Teacher.query.get_or_404(id)
    courses = []
    for c in t.courses:
        evals = Evaluation.query.filter_by(course_id=c.id).all()
        courses.append({
            "id": c.id,
            "name": c.name,
            "evaluations": [{
                "id": e.id,
                "rating": e.rating,
                "comment": e.comment,
                "user": e.user.username,
                "created_at": e.created_at.isoformat()
            } for e in evals]
        })
    return jsonify({
        "id": t.id,
        "name": t.name,
        "title": t.title,
        "department": t.department,
        "email": t.email,
        "research": t.research,
        "bio": t.bio,
        "courses": courses
    })

@app.route('/api/course-catalog', methods=['GET'])
@login_required
def get_course_catalog():
    return jsonify(load_course_library())

@app.route('/api/teachers/<int:teacher_id>/courses', methods=['POST'])
@login_required
def add_teacher_course(teacher_id):
    t = Teacher.query.get_or_404(teacher_id)
    data = request.json or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({"error": "Course name is required"}), 400
    if len(name) > 100:
        return jsonify({"error": "Course name too long"}), 400

    exists = Course.query.filter_by(teacher_id=t.id, name=name).first()
    if exists:
        return jsonify({
            "id": exists.id,
            "name": exists.name,
            "teacher_id": t.id
        }), 200

    course = Course(name=name, teacher_id=t.id)
    db.session.add(course)
    db.session.commit()
    return jsonify({
        "id": course.id,
        "name": course.name,
        "teacher_id": t.id
    }), 201

@app.route('/api/evaluate', methods=['POST'])
@login_required
def post_evaluation():
    data = request.json or {}
    course_id = data.get('course_id')
    teacher_id = data.get('teacher_id')
    course_name = (data.get('course_name') or '').strip()
    rating = data.get('rating')
    comment = (data.get('comment') or '').strip()
    
    if rating is None:
        return jsonify({"error": "Missing required fields"}), 400
    try:
        rating = int(rating)
    except Exception:
        return jsonify({"error": "Invalid rating"}), 400
    if rating < 1 or rating > 5:
        return jsonify({"error": "Invalid rating"}), 400
    if len(comment) > 2000:
        return jsonify({"error": "Comment too long"}), 400

    if course_id is not None and course_id != '':
        try:
            course_id = int(course_id)
        except Exception:
            return jsonify({"error": "Invalid course"}), 400
    else:
        course_id = None

    if course_id is None:
        if teacher_id is None or teacher_id == '' or not course_name:
            return jsonify({"error": "Missing required fields"}), 400
        try:
            teacher_id = int(teacher_id)
        except Exception:
            return jsonify({"error": "Teacher not found"}), 404
        t = Teacher.query.get(teacher_id)
        if not t:
            return jsonify({"error": "Teacher not found"}), 404
        if len(course_name) > 100:
            return jsonify({"error": "Course name too long"}), 400
        c = Course.query.filter_by(teacher_id=t.id, name=course_name).first()
        if not c:
            c = Course(name=course_name, teacher_id=t.id)
            db.session.add(c)
            db.session.flush()
        course_id = c.id
        
    existing = Evaluation.query.filter_by(course_id=course_id, user_id=current_user.id).first()
    if existing:
        existing.rating = rating
        existing.comment = comment
        existing.created_at = datetime.utcnow()
        db.session.commit()
        return jsonify({"message": "Evaluation updated successfully"})

    evaluation = Evaluation(course_id=course_id, user_id=current_user.id, rating=rating, comment=comment)
    db.session.add(evaluation)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = Evaluation.query.filter_by(course_id=course_id, user_id=current_user.id).first()
        if existing:
            existing.rating = rating
            existing.comment = comment
            existing.created_at = datetime.utcnow()
            db.session.commit()
            return jsonify({"message": "Evaluation updated successfully"})
        return jsonify({"error": "Failed to submit evaluation"}), 500
    return jsonify({"message": "Evaluation submitted successfully"})

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    
    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400
    if len(username) > 80:
        return jsonify({"error": "Username too long"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password too short"}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already exists"}), 400
        
    user = User(username=username, password_hash=generate_password_hash(password))
    db.session.add(user)
    db.session.commit()
    login_user(user)
    return jsonify({
        "message": "User registered successfully",
        **serialize_user(user),
    })

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    
    user = User.query.filter_by(username=username).first()
    ok = False
    if user:
        try:
            ok = check_password_hash(user.password_hash, password)
        except Exception:
            ok = False
        if not ok and user.password_hash == password:
            user.password_hash = generate_password_hash(password)
            db.session.commit()
            ok = True

    if ok:
        login_user(user)
        return jsonify({
            "message": "Login successful",
            **serialize_user(user),
        })
    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/api/logout', methods=['POST'])
def api_logout():
    if current_user.is_authenticated:
        logout_user()
    return jsonify({"message": "Logout successful"})

@app.route('/api/scrape', methods=['POST'])
@login_required
def trigger_scrape():
    include_courses = request.args.get('include_courses') in ('1', 'true', 'True')

    with scrape_lock:
        if scrape_state["running"]:
            return jsonify({"message": "Scrape already running"}), 202
        scrape_state["running"] = True
        scrape_state["last_started_at"] = int(time.time())
        scrape_state["last_finished_at"] = None
        scrape_state["last_error"] = None

    def job():
        try:
            run_scraper()
            seed_database(include_courses=include_courses)
        except Exception as e:
            with scrape_lock:
                scrape_state["last_error"] = str(e)
        finally:
            with scrape_lock:
                scrape_state["running"] = False
                scrape_state["last_finished_at"] = int(time.time())

    threading.Thread(target=job, daemon=True).start()
    return jsonify({"message": "Scrape started"}), 202

@app.route('/api/scrape/status', methods=['GET'])
@login_required
def scrape_status():
    with scrape_lock:
        return jsonify(dict(scrape_state))

def seed_database(include_courses=False):
    json_path = os.path.join(os.path.dirname(__file__), 'teachers.json')
    if not os.path.exists(json_path):
        return
        
    with open(json_path, 'r', encoding='utf-8') as f:
        teachers_data = json.load(f)

    external_names = load_external_teacher_names()
        
    for data in teachers_data:
        if not data.get('name'):
            continue
        if data.get('name') in external_names:
            continue
            
        # Try to find existing teacher by URL or Name
        teacher = Teacher.query.filter((Teacher.url == data['url']) | (Teacher.name == data['name'])).first()
        
        if not teacher:
            teacher = Teacher(
                name=data['name'],
                url=data['url'],
                title=data['title'],
                department=data['department'],
                email=data['email'],
                research=data['research'],
                bio=data['bio']
            )
            db.session.add(teacher)
            db.session.flush() 
        else:
            # Update existing teacher if the new data has more info
            if not teacher.email and data.get('email'):
                teacher.email = data['email']
            if not teacher.research and data.get('research'):
                teacher.research = data['research']
            if (not teacher.bio or len(teacher.bio) < 20) and data.get('bio'):
                teacher.bio = data['bio']
            if not teacher.department and data.get('department'):
                teacher.department = data['department']
            # Always update title if it's more descriptive
            if len(data.get('title', '')) > len(teacher.title or ''):
                teacher.title = data['title']
            
        if include_courses:
            existing_courses = {c.name for c in teacher.courses}
            for course_name in data.get('courses', []):
                if course_name not in existing_courses:
                    course = Course(name=course_name, teacher_id=teacher.id)
                    db.session.add(course)
            
    db.session.commit()

# Create tables
with app.app_context():
    db.create_all()
    external_names = load_external_teacher_names()
    if external_names:
        teachers = Teacher.query.filter(Teacher.name.in_(list(external_names))).all()
        for t in teachers:
            db.session.delete(t)
    # Auto-seed teacher data on every startup
    teacher_count = Teacher.query.count()
    if teacher_count == 0:
        seed_database(include_courses=True)
        print(f'[SEED] Database seeded with {Teacher.query.count()} teachers')
        db.session.commit()
    # Auto-create admin account if not exists
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(username='admin', role='admin',
                 password_hash=generate_password_hash('admin123'))
        db.session.add(admin)
        db.session.commit()
        print('[SEED] Admin account created: admin / admin123')
    seen = set()
    dups = []
    for e in Evaluation.query.order_by(Evaluation.course_id, Evaluation.user_id, Evaluation.created_at.desc()).all():
        key = (e.course_id, e.user_id)
        if key in seen:
            dups.append(e)
            continue
        seen.add(key)
    if dups:
        for e in dups:
            db.session.delete(e)
        db.session.commit()

if __name__ == '__main__':
    import os as _os
    _port = int(_os.environ.get('PORT', 5000))
    _host = '0.0.0.0' if app_env == 'production' else '127.0.0.1'
    app.run(debug=(app_env != 'production'), host=_host, port=_port)
