import os
import subprocess
import html
import re
import json
import datetime
from functools import wraps
from flask import Flask, request, jsonify
from pydantic import ValidationError
import jwt
from dotenv import load_dotenv

from Src.logger import setup_loggers
from Src.defs import load_os_data, generate_reservation_model, save_configuration

load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
f_logger, c_logger = setup_loggers()

SHARED_DIR = os.getenv('SHARED_DIR', '/shared_files')

# Health routes
@app.route('/health', methods=['GET'])
@app.route('/api/health', methods=['GET'])
@app.route('/api/backend/health', methods=['GET'])
@app.route('/api/provision/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "service": "backend"}), 200

@app.route('/api/log_error', methods=['POST'])
def log_frontend_error():
    error_data = request.get_json()
    f_logger.error(f"[Frontend Validation Error]: {error_data}")
    return jsonify({"status": "logged"}), 200

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
            current_user_id = data['user_id']
        except Exception as e:
            f_logger.error(f"JWT Verification failed: {e}")
            return jsonify({'error': 'Token is invalid or expired!'}), 401
        return f(current_user_id, *args, **kwargs)
    return decorated

def save_to_shared_volume(file_content, file_name, user_id):
    user_dir = os.path.join(SHARED_DIR, str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    file_path = os.path.join(user_dir, file_name)
    try:
        with open(file_path, 'w') as f:
            f.write(file_content)
        f_logger.info(f"Successfully saved {file_name} locally at {file_path}")
        return file_path
    except Exception as e:
        f_logger.error(f"Save Error for {file_name}: {e}")
        return None

def is_malicious_payload(input_string):
    malicious_pattern = re.compile(r'(<|>|<script>|javascript:|onload=|eval\()', re.IGNORECASE)
    return bool(malicious_pattern.search(str(input_string)))

def sanitize_and_validate_payload(data):
    errors = []
    clean_data = {}
    
    # Active Malicious Payload Scanner
    for key, value in data.items():
        if isinstance(value, str) and is_malicious_payload(value):
            errors.append(f"Validation Error: Malicious content detected in '{key}'.")
            
    raw_count = data.get('count')
    if raw_count is None:
        errors.append("Validation Error: 'count' is missing.")
    else:
        try:
            count = int(raw_count)
            if 1 <= count <= 10:
                clean_data['count'] = count
            else:
                errors.append("Validation Error: 'count' must be between 1 and 10.")
        except (ValueError, TypeError):
            errors.append("Validation Error: 'count' must be a valid number.")
            
    clean_data['osKey'] = data.get('osKey')
    clean_data['typeChoice'] = data.get('typeChoice')
    clean_data['installScript'] = data.get('installScript', 'none')
    clean_data['infraType'] = data.get('infraType', 'json')
    clean_data['baseName'] = html.escape(str(data.get('baseName', '')))
    
    return clean_data, errors

def run_bash_installation(os_key: str) -> bool:
    script_path = os.path.join("./Scripts/", f"{os_key}_install.sh")
    if not os.path.exists(script_path):
        f_logger.error(f"Script not found: {script_path}")
        return False
    try:
        process = subprocess.Popen(
            ["bash", script_path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
        )
        for line in process.stdout:
            clean_line = line.strip()
            if clean_line:
                f_logger.info(f"[Bash]: {clean_line}")
        process.wait()
        return process.returncode == 0
    except Exception as e:
        f_logger.critical(f"Error running bash script: {e}")
        return False

@app.route('/api/provision', methods=['POST'])
@token_required
def provision(current_user_id):
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400
        
    raw_data = request.get_json()
    clean_data, validation_errors = sanitize_and_validate_payload(raw_data)
    
    if validation_errors:
        return jsonify({"error": "Validation failed", "details": validation_errors}), 400
        
    count = clean_data.get('count')
    base_name = clean_data.get('baseName')
    os_key = clean_data.get('osKey')
    type_choice = clean_data.get('typeChoice')
    install_script = clean_data.get('installScript')
    infraType = clean_data.get('infraType')
    
    os_data = load_os_data(f_logger, c_logger)
    try:
        final_model = generate_reservation_model(count, base_name, os_key, type_choice, os_data)
    except ValidationError:
        return jsonify({"error": "Data validation failed at model generation"}), 400
        
    response_payload = None
    save_success = False
    
    if infraType == 'terraform':
        from Src.tf_generator import generate_tf_file
        save_success, tf_content = generate_tf_file(final_model, f_logger, count, base_name, os_key)
        if save_success:
            response_payload = tf_content
    else:
        try:
            save_configuration(final_model, f_logger, c_logger, count)
            save_success = True
            response_payload = final_model.model_dump()
        except Exception:
            save_success = False
            
    if not save_success:
        return jsonify({"error": "Failed to generate infrastructure config"}), 500
        
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    extension = 'tf' if infraType == 'terraform' else 'json'
    file_name = f"{base_name}_{timestamp}.{extension}"
    content_to_save = response_payload if isinstance(response_payload, str) else json.dumps(response_payload, indent=2)
    
    # Save a backup copy locally
    save_to_shared_volume(content_to_save, file_name, current_user_id)
    
    if install_script != 'none':
        deployment_success = run_bash_installation(os_key)
        if not deployment_success:
            return jsonify({"error": "Deployment failed. Check app.log"}), 500
            
    return jsonify({"message": "Success", "config": response_payload}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)