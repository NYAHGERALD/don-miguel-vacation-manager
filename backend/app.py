from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
import os
from datetime import datetime, timedelta
import json
import psycopg2
from psycopg2.extras import RealDictCursor
import firebase_admin
from firebase_admin import credentials, auth
from functools import wraps
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, template_folder='../templates', static_folder='../static')
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
CORS(app)

# Firebase Admin SDK initialization
# Initialize Firebase Admin SDK (you'll need to add your service account key)
# cred = credentials.Certificate('path/to/serviceAccountKey.json')
cred = credentials.Certificate('firebase-service-account.json')
# firebase_admin.initialize_app(cred)
firebase_admin.initialize_app(cred)

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://username:password@localhost/vacation_manager')

def get_db_connection():
    """Get database connection"""
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def verify_firebase_token(f):
    """Decorator to verify Firebase token"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'No token provided'}), 401
        
        try:
            # Remove 'Bearer ' prefix if present
            if token.startswith('Bearer '):
                token = token[7:]
            
            # Verify the token with Firebase Admin SDK
            decoded_token = auth.verify_id_token(token)
            request.user = decoded_token
            return f(*args, **kwargs)
        except Exception as e:
            return jsonify({'error': 'Invalid token'}), 401
    
    return decorated_function

@app.route('/')
def index():
    """Main landing page"""
    return render_template('index.html')

@app.route('/login')
def login():
    """Login page"""
    return render_template('login.html')

@app.route('/register')
def register():
    """Registration page"""
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    """Supervisor dashboard"""
    return render_template('dashboard.html')

@app.route('/employees')
def employees():
    """Employee management page"""
    return render_template('employees.html')

@app.route('/vacation-requests')
def vacation_requests():
    """Vacation requests management page"""
    return render_template('vacation_requests.html')

# API Routes

@app.route('/api/register', methods=['POST'])
def api_register():
    """Register a new supervisor"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['firebase_uid', 'email', 'first_name', 'last_name', 'department', 'shift']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor()
        
        # Insert supervisor into database
        insert_query = """
            INSERT INTO supervisors (firebase_uid, email, first_name, last_name, department, shift)
            VALUES (%(firebase_uid)s, %(email)s, %(first_name)s, %(last_name)s, %(department)s, %(shift)s)
            RETURNING id
        """
        
        cursor.execute(insert_query, data)
        supervisor_id = cursor.fetchone()['id']
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'message': 'Supervisor registered successfully', 'supervisor_id': supervisor_id}), 201
        
    except psycopg2.IntegrityError as e:
        return jsonify({'error': 'Email or Firebase UID already exists'}), 409
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/supervisor/<firebase_uid>', methods=['GET'])
@verify_firebase_token
def get_supervisor(firebase_uid):
    """Get supervisor information"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM supervisors WHERE firebase_uid = %s", (firebase_uid,))
        supervisor = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if supervisor:
            return jsonify(dict(supervisor))
        else:
            return jsonify({'error': 'Supervisor not found'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/employees', methods=['GET', 'POST'])
@verify_firebase_token
def handle_employees():
    """Handle employee operations"""
    if request.method == 'GET':
        try:
            # Get supervisor's department from Firebase UID
            firebase_uid = request.user['uid']
            
            conn = get_db_connection()
            if not conn:
                return jsonify({'error': 'Database connection failed'}), 500
            
            cursor = conn.cursor()
            
            # Get supervisor info
            cursor.execute("SELECT department FROM supervisors WHERE firebase_uid = %s", (firebase_uid,))
            supervisor = cursor.fetchone()
            
            if not supervisor:
                return jsonify({'error': 'Supervisor not found'}), 404
            
            # Get employees in supervisor's department
            cursor.execute("""
                SELECT e.* FROM employees e 
                JOIN supervisors s ON e.supervisor_id = s.id 
                WHERE s.firebase_uid = %s
            """, (firebase_uid,))
            
            employees = cursor.fetchall()
            
            cursor.close()
            conn.close()
            
            return jsonify([dict(emp) for emp in employees])
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            firebase_uid = request.user['uid']
            
            # Validate required fields
            required_fields = ['first_name', 'last_name', 'phone_number', 'department', 'shift', 'work_line', 'work_area']
            for field in required_fields:
                if field not in data:
                    return jsonify({'error': f'Missing required field: {field}'}), 400
            
            conn = get_db_connection()
            if not conn:
                return jsonify({'error': 'Database connection failed'}), 500
            
            cursor = conn.cursor()
            
            # Get supervisor ID
            cursor.execute("SELECT id FROM supervisors WHERE firebase_uid = %s", (firebase_uid,))
            supervisor = cursor.fetchone()
            
            if not supervisor:
                return jsonify({'error': 'Supervisor not found'}), 404
            
            # Insert employee
            insert_query = """
                INSERT INTO employees (first_name, last_name, phone_number, department, shift, work_line, work_area, supervisor_id)
                VALUES (%(first_name)s, %(last_name)s, %(phone_number)s, %(department)s, %(shift)s, %(work_line)s, %(work_area)s, %(supervisor_id)s)
                RETURNING id
            """
            
            data['supervisor_id'] = supervisor['id']
            cursor.execute(insert_query, data)
            employee_id = cursor.fetchone()['id']
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return jsonify({'message': 'Employee added successfully', 'employee_id': employee_id}), 201
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500

@app.route('/api/vacation-requests', methods=['GET', 'POST'])
@verify_firebase_token
def handle_vacation_requests():
    """Handle vacation request operations"""
    if request.method == 'GET':
        try:
            firebase_uid = request.user['uid']
            
            conn = get_db_connection()
            if not conn:
                return jsonify({'error': 'Database connection failed'}), 500
            
            cursor = conn.cursor()
            
            # Get vacation requests for supervisor's employees
            cursor.execute("""
                SELECT vr.*, e.first_name, e.last_name, e.department, e.shift, e.work_line, e.work_area
                FROM vacation_requests vr
                JOIN employees e ON vr.employee_id = e.id
                JOIN supervisors s ON vr.supervisor_id = s.id
                WHERE s.firebase_uid = %s
                ORDER BY vr.created_at DESC
            """, (firebase_uid,))
            
            requests = cursor.fetchall()
            
            cursor.close()
            conn.close()
            
            return jsonify([dict(req) for req in requests])
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            firebase_uid = request.user['uid']
            
            # Validate required fields
            required_fields = ['employee_id', 'start_date', 'end_date']
            for field in required_fields:
                if field not in data:
                    return jsonify({'error': f'Missing required field: {field}'}), 400
            
            # Calculate return date and total hours
            start_date = datetime.strptime(data['start_date'], '%Y-%m-%d')
            end_date = datetime.strptime(data['end_date'], '%Y-%m-%d')
            
            # Calculate business days (excluding weekends)
            business_days = 0
            current_date = start_date
            while current_date <= end_date:
                if current_date.weekday() < 5:  # Monday = 0, Sunday = 6
                    business_days += 1
                current_date += timedelta(days=1)
            
            total_hours = business_days * 8
            return_date = end_date + timedelta(days=1)
            
            conn = get_db_connection()
            if not conn:
                return jsonify({'error': 'Database connection failed'}), 500
            
            cursor = conn.cursor()
            
            # Get supervisor ID
            cursor.execute("SELECT id FROM supervisors WHERE firebase_uid = %s", (firebase_uid,))
            supervisor = cursor.fetchone()
            
            if not supervisor:
                return jsonify({'error': 'Supervisor not found'}), 404
            
            # Insert vacation request
            insert_query = """
                INSERT INTO vacation_requests (employee_id, supervisor_id, start_date, end_date, return_date, total_hours, status)
                VALUES (%(employee_id)s, %(supervisor_id)s, %(start_date)s, %(end_date)s, %(return_date)s, %(total_hours)s, 'Pending')
                RETURNING id
            """
            
            request_data = {
                'employee_id': data['employee_id'],
                'supervisor_id': supervisor['id'],
                'start_date': data['start_date'],
                'end_date': data['end_date'],
                'return_date': return_date.strftime('%Y-%m-%d'),
                'total_hours': total_hours
            }
            
            cursor.execute(insert_query, request_data)
            request_id = cursor.fetchone()['id']
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return jsonify({'message': 'Vacation request created successfully', 'request_id': request_id}), 201
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500

@app.route('/api/vacation-requests/<int:request_id>/approve', methods=['PUT'])
@verify_firebase_token
def approve_vacation_request(request_id):
    """Approve a vacation request"""
    try:
        firebase_uid = request.user['uid']
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor()
        
        # Update request status
        cursor.execute("""
            UPDATE vacation_requests 
            SET status = 'Approved' 
            WHERE id = %s AND supervisor_id = (
                SELECT id FROM supervisors WHERE firebase_uid = %s
            )
        """, (request_id, firebase_uid))
        
        if cursor.rowcount == 0:
            return jsonify({'error': 'Vacation request not found or unauthorized'}), 404
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'message': 'Vacation request approved successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/vacation-requests/<int:request_id>/deny', methods=['PUT'])
@verify_firebase_token
def deny_vacation_request(request_id):
    """Deny a vacation request"""
    try:
        firebase_uid = request.user['uid']
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor()
        
        # Update request status
        cursor.execute("""
            UPDATE vacation_requests 
            SET status = 'Denied' 
            WHERE id = %s AND supervisor_id = (
                SELECT id FROM supervisors WHERE firebase_uid = %s
            )
        """, (request_id, firebase_uid))
        
        if cursor.rowcount == 0:
            return jsonify({'error': 'Vacation request not found or unauthorized'}), 404
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'message': 'Vacation request denied successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/dashboard/stats', methods=['GET'])
@verify_firebase_token
def get_dashboard_stats():
    """Get dashboard statistics"""
    try:
        firebase_uid = request.user['uid']
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor()
        
        # Get supervisor ID
        cursor.execute("SELECT id FROM supervisors WHERE firebase_uid = %s", (firebase_uid,))
        supervisor = cursor.fetchone()
        
        if not supervisor:
            return jsonify({'error': 'Supervisor not found'}), 404
        
        supervisor_id = supervisor['id']
        
        # Get total employees
        cursor.execute("SELECT COUNT(*) as total FROM employees WHERE supervisor_id = %s", (supervisor_id,))
        total_employees = cursor.fetchone()['total']
        
        # Get vacation request counts by status
        cursor.execute("""
            SELECT status, COUNT(*) as count 
            FROM vacation_requests 
            WHERE supervisor_id = %s 
            GROUP BY status
        """, (supervisor_id,))
        
        request_counts = {row['status']: row['count'] for row in cursor.fetchall()}
        
        # Get upcoming vacations
        cursor.execute("""
            SELECT vr.*, e.first_name, e.last_name 
            FROM vacation_requests vr
            JOIN employees e ON vr.employee_id = e.id
            WHERE vr.supervisor_id = %s 
            AND vr.status = 'Approved' 
            AND vr.start_date >= CURRENT_DATE
            ORDER BY vr.start_date
            LIMIT 10
        """, (supervisor_id,))
        
        upcoming_vacations = [dict(row) for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        stats = {
            'total_employees': total_employees,
            'pending_requests': request_counts.get('Pending', 0),
            'approved_requests': request_counts.get('Approved', 0),
            'denied_requests': request_counts.get('Denied', 0),
            'upcoming_vacations': upcoming_vacations
        }
        
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)