import os
import time
import datetime
from functools import wraps
from flask import Flask, request, jsonify
import jwt
from sqlalchemy.exc import OperationalError
from dotenv import load_dotenv

load_dotenv()
from db import db, User
from logger import setup_logger

app = Flask(__name__)
auth_logger = setup_logger()

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ['SECRET_KEY']

db.init_app(app)

# Health routes
@app.route('/health', methods=['GET'])
@app.route('/api/health', methods=['GET'])
@app.route('/api/auth/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "service": "auth"}), 200

# Connect & create tables with retry logic (Postgres startup wait)
with app.app_context():
    max_retries = 10
    for attempt in range(max_retries):
        try:
            db.create_all()
            auth_logger.info("System Startup | Status: SUCCESS | Connected to PostgreSQL and verified tables.")
            break
        except OperationalError as e:
            auth_logger.warning(f"Database connection attempt {attempt + 1}/{max_retries} failed. Retrying in 2 seconds...")
            time.sleep(2)
        except Exception as e:
            auth_logger.critical(f"System Startup | Status: CRITICAL | Could not initialize DB: {e}")
            break

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(" ")[1]
        if not token:
            return jsonify({'error': 'Token is missing!'}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = User.query.get(data['user_id'])
            if not current_user:
                return jsonify({'error': 'User not found!'}), 401
        except Exception:
            return jsonify({'error': 'Token is invalid or expired!'}), 401
        return f(current_user, *args, **kwargs)
    return decorated

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    required_fields = ['username', 'password', 're_password', 'email', 'fullName']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'Missing field: {field}'}), 400
            
    if data['password'] != data['re_password']:
        return jsonify({'error': 'Passwords do not match'}), 400
        
    if User.query.filter_by(username=data['username']).first() or User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Username or Email already exists'}), 400
        
    try:
        new_user = User(username=data['username'], email=data['email'], full_name=data['fullName'])
        new_user.set_password(data['password'])
        db.session.add(new_user)
        db.session.commit()
        auth_logger.info(f"REGISTER | SUCCESS | User: {new_user.username}")
        return jsonify({'message': 'User registered successfully'}), 201
    except Exception as e:
        db.session.rollback()
        auth_logger.critical(f"REGISTER | CRITICAL | Error: {e}")
        return jsonify({'error': 'Database error during registration'}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    
    if not data or not username or not data.get('password'):
        return jsonify({'error': 'Missing credentials'}), 400
        
    try:
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(data['password']):
            token = jwt.encode({
                'user_id': user.id,
                'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24)
            }, app.config['SECRET_KEY'], algorithm="HS256")
            
            auth_logger.info(f"LOGIN | SUCCESS | User: {user.username}")
            return jsonify({
                'message': 'Login successful', 'token': token,
                'user': {'username': user.username, 'fullName': user.full_name, 'email': user.email}
            }), 200
            
        auth_logger.warning(f"LOGIN | WARNING | Username: {username} | Invalid credentials.")
        return jsonify({'error': 'Invalid username or password'}), 401
    except Exception as e:
        auth_logger.critical(f"LOGIN | CRITICAL | Error: {e}")
        return jsonify({'error': 'Database error'}), 500

@app.route('/api/auth/logout', methods=['POST'])
@token_required
def logout(current_user):
    auth_logger.info(f"LOGOUT | SUCCESS | User: {current_user.username}")
    return jsonify({'message': 'Logout logged successfully'}), 200

@app.route('/api/auth/user/profile', methods=['GET'])
@token_required
def get_profile(current_user):
    return jsonify({
        'username': current_user.username,
        'fullName': current_user.full_name,
        'email': current_user.email,
        'files': []  # Simplified, no longer tracking file history
    }), 200

@app.route('/api/auth/user/change-password', methods=['POST'])
@token_required
def change_password(current_user):
    data = request.get_json()
    if not current_user.check_password(data.get('oldPassword')):
        return jsonify({'error': 'Incorrect current password'}), 401
    try:
        current_user.set_password(data.get('newPassword'))
        db.session.commit()
        return jsonify({'message': 'Password updated successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Database error'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)