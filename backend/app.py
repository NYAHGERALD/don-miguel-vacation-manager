from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from flask_cors import CORS
import os
from datetime import datetime, timedelta
import json
import psycopg2
import psycopg2.extras
import firebase_admin
from firebase_admin import credentials, auth
from functools import wraps
from dotenv import load_dotenv
import logging
import bcrypt
import secrets

import tempfile
import shutil
import base64
from twilio.rest import Client
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='../templates', static_folder='../static')
app.secret_key = os.environ.get('SECRET_KEY', 'j5gXHnC0c&3Vb7Qf@8KpM9wZyT!rLx2Nd4Pq6Rs8Uv0Wx3Yz5Ab7Cd9Ef1Gh3Jk5Mn7')
CORS(app)

# Twilio Configuration
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')

# Initialize Twilio client
twilio_client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    try:
        twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        logger.info("Twilio client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Twilio client: {str(e)}")
else:
    logger.warning("Twilio credentials not found. SMS notifications will be disabled.")

# Initialize scheduler for background notifications
scheduler = BackgroundScheduler()
scheduler.start()
logger.info("Background scheduler started for SMS notifications")

# Firebase Admin SDK initialization
# Initialize Firebase Admin SDK (you'll need to add your service account key)
import os
import sys

# Get the directory where this script is located
current_dir = os.path.dirname(os.path.abspath(__file__))
# Go up one level to the project root
project_root = os.path.dirname(current_dir)
# Path to firebase service account file
#firebase_service_account_path = os.path.join(project_root, 'firebase-service-account.json')
firebase_service_account_path = os.path.join(project_root, '/etc/secrets/firebase-service-account.json')

# Check if the file exists
if not os.path.exists(firebase_service_account_path):
    print(f"Error: Firebase service account file not found at: {firebase_service_account_path}")
    print("Please ensure firebase-service-account.json is in the project root directory.")
    sys.exit(1)

cred = credentials.Certificate(firebase_service_account_path)
firebase_admin.initialize_app(cred)

# Database configuration
#DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://vacation_user:vacation_pass@localhost:5432/vacation_manager')
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://vacation_user:QZgwvm9xM8D9hZcteyfk9RMdcLm5QRzp@dpg-d28iqds9c44c73bcch80-a/vacation_manager_wl7h')

def get_db_connection():
    """Get database connection"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def init_db():
    """Initialize the database with schema"""
    print("Database initialization is handled by the schema.sql file.")
    print("Please run: psql -U postgres -d vacation_manager -f database/schema.sql")
    print("Then run: psql -U postgres -d vacation_manager -f database/grant_permissions.sql")

def get_us_holidays(year):
    """Get US Federal holidays for a given year"""
    holidays = []
    
    # New Year's Day - January 1
    holidays.append(datetime(year, 1, 1))
    
    # Martin Luther King Jr. Day - Third Monday in January
    mlk_day = datetime(year, 1, 1)
    # Find first Monday, then add 14 days to get third Monday
    days_to_monday = (7 - mlk_day.weekday()) % 7
    if days_to_monday == 0:
        days_to_monday = 7
    mlk_day = mlk_day + timedelta(days=days_to_monday + 14)
    holidays.append(mlk_day)
    
    # Presidents' Day - Third Monday in February
    presidents_day = datetime(year, 2, 1)
    days_to_monday = (7 - presidents_day.weekday()) % 7
    if days_to_monday == 0:
        days_to_monday = 7
    presidents_day = presidents_day + timedelta(days=days_to_monday + 14)
    holidays.append(presidents_day)
    
    # Memorial Day - Last Monday in May
    memorial_day = datetime(year, 5, 31)
    days_to_monday = (memorial_day.weekday() + 1) % 7
    memorial_day = memorial_day - timedelta(days=days_to_monday)
    holidays.append(memorial_day)
    
    # Independence Day - July 4
    holidays.append(datetime(year, 7, 4))
    
    # Labor Day - First Monday in September
    labor_day = datetime(year, 9, 1)
    days_to_monday = (7 - labor_day.weekday()) % 7
    if days_to_monday == 0:
        days_to_monday = 7
    labor_day = labor_day + timedelta(days=days_to_monday)
    holidays.append(labor_day)
    
    # Thanksgiving Day - Fourth Thursday in November
    thanksgiving = datetime(year, 11, 1)
    days_to_thursday = (3 - thanksgiving.weekday()) % 7
    thanksgiving = thanksgiving + timedelta(days=days_to_thursday + 21)
    holidays.append(thanksgiving)
    
    # Day After Thanksgiving - Friday after Thanksgiving
    day_after_thanksgiving = thanksgiving + timedelta(days=1)
    holidays.append(day_after_thanksgiving)
    
    # Christmas Eve - December 24
    holidays.append(datetime(year, 12, 24))
    
    # Christmas Day - December 25
    holidays.append(datetime(year, 12, 25))
    
    return holidays

def is_holiday(date):
    """Check if a date is a US Federal holiday"""
    year = date.year
    holidays = get_us_holidays(year)
    
    return any(
        holiday.year == date.year and
        holiday.month == date.month and
        holiday.day == date.day
        for holiday in holidays
    )

def is_business_day(date):
    """Check if a date is a business day (not weekend or holiday)"""
    # Check if it's weekend (Saturday = 5, Sunday = 6)
    if date.weekday() >= 5:
        return False
    # Check if it's a holiday
    if is_holiday(date):
        return False
    return True

def calculate_business_days(start_date, end_date):
    """Calculate business days between two dates, excluding weekends and holidays (INCLUSIVE)"""
    business_days = 0
    current_date = start_date
    
    # Include both start and end dates in the calculation
    while current_date <= end_date:
        if is_business_day(current_date):
            business_days += 1
        current_date += timedelta(days=1)
    
    return business_days

def get_next_business_day_backend(date):
    """Get the next business day after the given date"""
    next_day = date + timedelta(days=1)
    
    while not is_business_day(next_day):
        next_day += timedelta(days=1)
    
    return next_day

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

@app.route('/profile')
def profile():
    """Profile settings page"""
    return render_template('profile.html')

@app.route('/help')
def help_center():
    """Help center page"""
    return render_template('help.html')

@app.route('/admin/login')
def admin_login():
    """Admin login page"""
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    """Admin dashboard page"""
    return render_template('admin_dashboard.html')

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
        supervisor_id = cursor.fetchone()[0]
        
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
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
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

@app.route('/api/supervisor/exists/<firebase_uid>', methods=['GET'])
@verify_firebase_token
def supervisor_exists(firebase_uid):
    """Check if supervisor exists for given Firebase UID"""
    try:
        logger.info(f"Checking supervisor existence for UID: {firebase_uid}")
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed in supervisor_exists")
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT id FROM supervisors WHERE firebase_uid = %s", (firebase_uid,))
        supervisor = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        exists = supervisor is not None
        logger.info(f"Supervisor exists check result for {firebase_uid}: {exists}")
        return jsonify({'exists': exists})
    except Exception as e:
        logger.error(f"Error in supervisor_exists for {firebase_uid}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/employees', methods=['GET', 'POST', 'PUT', 'DELETE'])
@verify_firebase_token
def handle_employees():
    """Handle employee operations"""
    if request.method == 'GET':
        try:
            logger.info("=== GET /api/employees - Starting employee retrieval ===")
            # Get supervisor's department from Firebase UID
            firebase_uid = request.user['uid']
            logger.info(f"Firebase UID: {firebase_uid}")
            
            conn = get_db_connection()
            if not conn:
                logger.error("Database connection failed")
                return jsonify({'error': 'Database connection failed'}), 500
            
            logger.info("Database connection successful")
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Get supervisor info
            logger.info("Looking up supervisor...")
            cursor.execute("SELECT id, department FROM supervisors WHERE firebase_uid = %s", (firebase_uid,))
            supervisor = cursor.fetchone()
            
            if not supervisor:
                logger.error(f"Supervisor not found for firebase_uid: {firebase_uid}")
                cursor.close()
                conn.close()
                return jsonify({'error': 'Supervisor not found'}), 404
            
            logger.info(f"Found supervisor: ID={supervisor['id']}, Department={supervisor['department']}")
            
            # Get employees for this supervisor
            logger.info("Querying employees...")
            cursor.execute("""
                SELECT e.*, wa.name as work_area, wl.name as work_line
                FROM employees e
                LEFT JOIN work_areas wa ON e.work_area_id = wa.id
                LEFT JOIN work_lines wl ON e.work_line_id = wl.id
                WHERE e.supervisor_id = %s
                ORDER BY e.id DESC
            """, (supervisor['id'],))
            
            employees = cursor.fetchall()
            logger.info(f"Found {len(employees)} employees")
            
            # Convert to list of dicts for JSON serialization
            employee_list = [dict(emp) for emp in employees]
            if employee_list:
                logger.info(f"Sample employee: {employee_list[0]}")
            
            cursor.close()
            conn.close()
            logger.info("=== GET /api/employees - Employee retrieval completed successfully ===")
            
            return jsonify(employee_list)
            
        except Exception as e:
            logger.error(f"=== GET /api/employees - Error occurred: {str(e)} ===")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return jsonify({'error': str(e)}), 500
    
    elif request.method == 'POST':
        try:
            logger.info("=== POST /api/employees - Starting employee creation ===")
            data = request.get_json()
            firebase_uid = request.user['uid']
            
            logger.info(f"Received data: {data}")
            logger.info(f"Firebase UID: {firebase_uid}")

            # Check if phone_number is required - it's in required_fields but frontend doesn't mark it as required
            required_fields = ['first_name', 'last_name', 'department', 'shift']
            for field in required_fields:
                if field not in data or not data[field]:
                    logger.error(f"Missing or empty required field: {field}")
                    return jsonify({'error': f'Missing required field: {field}'}), 400

            # Phone number is optional, set to empty string if not provided
            phone_number = data.get('phone_number', '').strip()
            logger.info(f"Phone number: '{phone_number}'")

            work_area_id = data.get('work_area_id')
            work_line_id = data.get('work_line_id')
            
            logger.info(f"Raw work_area_id: {work_area_id} (type: {type(work_area_id)})")
            logger.info(f"Raw work_line_id: {work_line_id} (type: {type(work_line_id)})")

            if work_area_id and work_area_id != '':
                try:
                    work_area_id = int(work_area_id)
                    logger.info(f"Converted work_area_id to: {work_area_id}")
                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to convert work_area_id '{work_area_id}': {e}")
                    work_area_id = None
            else:
                work_area_id = None
                logger.info("work_area_id set to None")

            if work_line_id and work_line_id != '':
                try:
                    work_line_id = int(work_line_id)
                    logger.info(f"Converted work_line_id to: {work_line_id}")
                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to convert work_line_id '{work_line_id}': {e}")
                    work_line_id = None
            else:
                work_line_id = None
                logger.info("work_line_id set to None")

            logger.info("Attempting database connection...")
            conn = get_db_connection()
            if not conn:
                logger.error("Database connection failed")
                return jsonify({'error': 'Database connection failed'}), 500

            logger.info("Database connection successful")
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            logger.info(f"Looking up supervisor for firebase_uid: {firebase_uid}")
            cursor.execute("SELECT id FROM supervisors WHERE firebase_uid = %s", (firebase_uid,))
            supervisor = cursor.fetchone()

            if not supervisor:
                logger.error(f"Supervisor not found for firebase_uid: {firebase_uid}")
                cursor.close()
                conn.close()
                return jsonify({'error': 'Supervisor not found'}), 404

            logger.info(f"Found supervisor with ID: {supervisor['id']}")

            if work_area_id:
                logger.info(f"Validating work_area_id: {work_area_id}")
                cursor.execute("SELECT id FROM work_areas WHERE id = %s", (work_area_id,))
                if not cursor.fetchone():
                    logger.error(f"Invalid work area ID: {work_area_id}")
                    cursor.close()
                    conn.close()
                    return jsonify({'error': 'Invalid work area ID'}), 400
                logger.info("Work area ID validation passed")

            if work_line_id:
                logger.info(f"Validating work_line_id: {work_line_id}")
                cursor.execute("SELECT id FROM work_lines WHERE id = %s", (work_line_id,))
                if not cursor.fetchone():
                    logger.error(f"Invalid work line ID: {work_line_id}")
                    cursor.close()
                    conn.close()
                    return jsonify({'error': 'Invalid work line ID'}), 400
                logger.info("Work line ID validation passed")

            insert_query = '''
                INSERT INTO employees (first_name, last_name, phone_number, department, shift, work_area_id, work_line_id, supervisor_id)
                VALUES (%(first_name)s, %(last_name)s, %(phone_number)s, %(department)s, %(shift)s, %(work_area_id)s, %(work_line_id)s, %(supervisor_id)s)
                RETURNING id
            '''

            employee_data = {
                'first_name': data['first_name'],
                'last_name': data['last_name'],
                'phone_number': phone_number,
                'department': data['department'],
                'shift': data['shift'],
                'work_area_id': work_area_id,
                'work_line_id': work_line_id,
                'supervisor_id': supervisor['id']
            }

            logger.info(f"Final employee data for insertion: {employee_data}")
            logger.info("Executing INSERT query...")
            cursor.execute(insert_query, employee_data)
            result = cursor.fetchone()
            employee_id = result['id']
            logger.info(f"Employee inserted successfully with ID: {employee_id}")

            logger.info("Committing transaction...")
            conn.commit()
            cursor.close()
            conn.close()
            logger.info("=== POST /api/employees - Employee creation completed successfully ===")

            return jsonify({'message': 'Employee added successfully', 'employee_id': employee_id}), 201

        except Exception as e:
            logger.error(f"=== POST /api/employees - Error occurred: {str(e)} ===")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return jsonify({'error': str(e)}), 500

    elif request.method == 'PUT':
        try:
            logger.info("=== PUT /api/employees - Starting employee update ===")
            data = request.get_json()
            firebase_uid = request.user['uid']
            employee_id = data.get('id')
            
            logger.info(f"Received data: {data}")
            logger.info(f"Firebase UID: {firebase_uid}")
            
            # Validate required fields (phone_number is optional)
            required_fields = ['id', 'first_name', 'last_name', 'department', 'shift']
            for field in required_fields:
                if field not in data or not data[field]:
                    logger.error(f"Missing or empty required field: {field}")
                    return jsonify({'error': f'Missing required field: {field}'}), 400
            
            # Phone number is optional, set to empty string if not provided
            phone_number = data.get('phone_number', '').strip()
            logger.info(f"Phone number: '{phone_number}'")
            
            # Get work area and work line IDs if provided
            work_area_id = data.get('work_area_id')
            work_line_id = data.get('work_line_id')
            
            logger.info(f"Raw work_area_id: {work_area_id} (type: {type(work_area_id)})")
            logger.info(f"Raw work_line_id: {work_line_id} (type: {type(work_line_id)})")

            # Convert work area and line IDs to integers if provided
            if work_area_id and work_area_id != '':
                try:
                    work_area_id = int(work_area_id)
                    logger.info(f"Converted work_area_id to: {work_area_id}")
                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to convert work_area_id '{work_area_id}': {e}")
                    work_area_id = None
            else:
                work_area_id = None
                logger.info("work_area_id set to None")

            if work_line_id and work_line_id != '':
                try:
                    work_line_id = int(work_line_id)
                    logger.info(f"Converted work_line_id to: {work_line_id}")
                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to convert work_line_id '{work_line_id}': {e}")
                    work_line_id = None
            else:
                work_line_id = None
                logger.info("work_line_id set to None")
            
            conn = get_db_connection()
            if not conn:
                logger.error("Database connection failed")
                return jsonify({'error': 'Database connection failed'}), 500
            
            logger.info("Database connection successful")
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Get supervisor ID
            logger.info(f"Looking up supervisor for firebase_uid: {firebase_uid}")
            cursor.execute("SELECT id FROM supervisors WHERE firebase_uid = %s", (firebase_uid,))
            supervisor = cursor.fetchone()
            
            if not supervisor:
                logger.error(f"Supervisor not found for firebase_uid: {firebase_uid}")
                cursor.close()
                conn.close()
                return jsonify({'error': 'Supervisor not found'}), 404
            
            logger.info(f"Found supervisor with ID: {supervisor['id']}")
            
            # Validate work area ID if provided
            if work_area_id:
                logger.info(f"Validating work_area_id: {work_area_id}")
                cursor.execute("SELECT id FROM work_areas WHERE id = %s", (work_area_id,))
                if not cursor.fetchone():
                    logger.error(f"Invalid work area ID: {work_area_id}")
                    cursor.close()
                    conn.close()
                    return jsonify({'error': 'Invalid work area ID'}), 400
                logger.info("Work area ID validation passed")
            
            # Validate work line ID if provided
            if work_line_id:
                logger.info(f"Validating work_line_id: {work_line_id}")
                cursor.execute("SELECT id FROM work_lines WHERE id = %s", (work_line_id,))
                if not cursor.fetchone():
                    logger.error(f"Invalid work line ID: {work_line_id}")
                    cursor.close()
                    conn.close()
                    return jsonify({'error': 'Invalid work line ID'}), 400
                logger.info("Work line ID validation passed")
            
            # Update employee
            update_query = """
                UPDATE employees
                SET first_name = %(first_name)s, last_name = %(last_name)s, phone_number = %(phone_number)s,
                    department = %(department)s, shift = %(shift)s, work_area_id = %(work_area_id)s, work_line_id = %(work_line_id)s
                WHERE id = %(id)s AND supervisor_id = %(supervisor_id)s
                RETURNING id, first_name, last_name, phone_number, department, shift, work_area_id, work_line_id
            """
            
            employee_data = {
                'id': data['id'],
                'first_name': data['first_name'],
                'last_name': data['last_name'],
                'phone_number': phone_number,
                'department': data['department'],
                'shift': data['shift'],
                'work_area_id': work_area_id,
                'work_line_id': work_line_id,
                'supervisor_id': supervisor['id']
            }
            
            logger.info(f"Final employee data for update: {employee_data}")
            logger.info("Executing UPDATE query...")
            cursor.execute(update_query, employee_data)
            
            # Check if any rows were updated
            if cursor.rowcount == 0:
                logger.error("No rows updated - employee not found or unauthorized")
                cursor.close()
                conn.close()
                return jsonify({'error': 'Employee not found or unauthorized'}), 404
            
            # Get the updated employee data with work area and line names
            updated_employee = cursor.fetchone()
            logger.info(f"Employee updated successfully: {dict(updated_employee)}")
            
            # Get work area and line names for the response
            cursor.execute("""
                SELECT e.*, wa.name as work_area, wl.name as work_line
                FROM employees e
                LEFT JOIN work_areas wa ON e.work_area_id = wa.id
                LEFT JOIN work_lines wl ON e.work_line_id = wl.id
                WHERE e.id = %s
            """, (data['id'],))
            
            complete_employee = cursor.fetchone()
            
            logger.info("Committing transaction...")
            conn.commit()
            cursor.close()
            conn.close()
            logger.info("=== PUT /api/employees - Employee update completed successfully ===")
            
            return jsonify(dict(complete_employee)), 200
            
        except Exception as e:
            logger.error(f"=== PUT /api/employees - Error occurred: {str(e)} ===")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return jsonify({'error': str(e)}), 500

    elif request.method == 'DELETE':
        try:
            data = request.get_json()
            firebase_uid = request.user['uid']
            employee_id = data.get('id')
            
            if not employee_id:
                return jsonify({'error': 'Missing employee ID'}), 400
            
            conn = get_db_connection()
            if not conn:
                return jsonify({'error': 'Database connection failed'}), 500
            
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Get supervisor ID
            cursor.execute("SELECT id FROM supervisors WHERE firebase_uid = %s", (firebase_uid,))
            supervisor = cursor.fetchone()
            
            if not supervisor:
                return jsonify({'error': 'Supervisor not found'}), 404
            
            # First delete vacation requests for this employee
            cursor.execute("""
                DELETE FROM vacation_requests
                WHERE employee_id = %s AND supervisor_id = %s
            """, (employee_id, supervisor['id']))
            
            # Then delete the employee
            cursor.execute("""
                DELETE FROM employees
                WHERE id = %s AND supervisor_id = %s
            """, (employee_id, supervisor['id']))
            
            # Check if any rows were deleted
            if cursor.rowcount == 0:
                cursor.close()
                conn.close()
                return jsonify({'error': 'Employee not found or unauthorized'}), 404
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return jsonify({'message': 'Employee deleted successfully'}), 200
            
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
            
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Get vacation requests for supervisor's employees
            cursor.execute("""
                SELECT vr.*, e.first_name, e.last_name, e.department, e.shift, wa.name as work_area, wl.name as work_line
                FROM vacation_requests vr
                JOIN employees e ON vr.employee_id = e.id
                LEFT JOIN work_areas wa ON e.work_area_id = wa.id
                LEFT JOIN work_lines wl ON e.work_line_id = wl.id
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
            logger.info("=== POST /api/vacation-requests - Starting vacation request creation ===")
            data = request.get_json()
            firebase_uid = request.user['uid']
            
            logger.info(f"Received data: {data}")
            logger.info(f"Firebase UID: {firebase_uid}")
            
            # Validate required fields
            required_fields = ['employee_id', 'start_date', 'end_date']
            for field in required_fields:
                if field not in data:
                    logger.error(f"Missing required field: {field}")
                    return jsonify({'error': f'Missing required field: {field}'}), 400
            
            logger.info("Attempting database connection...")
            conn = get_db_connection()
            if not conn:
                logger.error("Database connection failed")
                return jsonify({'error': 'Database connection failed'}), 500
            
            logger.info("Database connection successful")
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Get supervisor ID
            logger.info(f"Looking up supervisor for firebase_uid: {firebase_uid}")
            cursor.execute("SELECT id FROM supervisors WHERE firebase_uid = %s", (firebase_uid,))
            supervisor = cursor.fetchone()
            
            if not supervisor:
                logger.error(f"Supervisor not found for firebase_uid: {firebase_uid}")
                cursor.close()
                conn.close()
                return jsonify({'error': 'Supervisor not found'}), 404
            
            logger.info(f"Found supervisor with ID: {supervisor['id']}")
            
            # Validate employee exists and belongs to this supervisor
            logger.info(f"Validating employee_id: {data['employee_id']}")
            cursor.execute("SELECT id, first_name, last_name FROM employees WHERE id = %s AND supervisor_id = %s",
                         (data['employee_id'], supervisor['id']))
            employee = cursor.fetchone()
            
            if not employee:
                logger.error(f"Employee not found or unauthorized: {data['employee_id']}")
                cursor.close()
                conn.close()
                return jsonify({'error': 'Employee not found or unauthorized'}), 404
            
            logger.info(f"Found employee: {employee['first_name']} {employee['last_name']}")
            
            # Parse and validate dates
            try:
                start_date = datetime.strptime(data['start_date'], '%Y-%m-%d')
                end_date = datetime.strptime(data['end_date'], '%Y-%m-%d')
                logger.info(f"=== DATE PROCESSING DEBUG ===")
                logger.info(f"Raw input - start_date: '{data['start_date']}', end_date: '{data['end_date']}'")
                logger.info(f"Parsed datetime objects - Start: {start_date}, End: {end_date}")
                logger.info(f"Date components - Start: {start_date.date()}, End: {end_date.date()}")
                logger.info(f"Weekdays - Start: {start_date.strftime('%A')}, End: {end_date.strftime('%A')}")
            except ValueError as e:
                logger.error(f"Invalid date format: {e}")
                return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
            
            if end_date < start_date:
                logger.error("End date is before start date")
                return jsonify({'error': 'End date must be after start date'}), 400
            
            # Calculate business days excluding weekends and holidays
            logger.info("=== BUSINESS DAY CALCULATION DEBUG ===")
            logger.info("Calculating business days with holiday exclusion...")
            business_days = calculate_business_days(start_date, end_date)
            total_hours = business_days * 8
            return_date = get_next_business_day_backend(end_date)
            
            logger.info(f"Business days calculation result: {business_days} days")
            logger.info(f"Total hours calculation: {business_days} * 8 = {total_hours} hours")
            logger.info(f"End date: {end_date.date()} ({end_date.strftime('%A')})")
            logger.info(f"Return date: {return_date.date()} ({return_date.strftime('%A')})")
            logger.info(f"Return date is business day: {is_business_day(return_date)}")
            
            # Validate return date calculation
            if return_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
                logger.warning(f"WARNING: Return date {return_date.date()} is a weekend day!")
            if is_holiday(return_date):
                logger.warning(f"WARNING: Return date {return_date.date()} is a holiday!")
            
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
            
            logger.info(f"=== DATABASE INSERTION DEBUG ===")
            logger.info(f"Final request data for insertion: {request_data}")
            logger.info(f"Return date string format: '{return_date.strftime('%Y-%m-%d')}'")
            logger.info("Executing INSERT query...")
            cursor.execute(insert_query, request_data)
            result = cursor.fetchone()
            request_id = result['id']
            logger.info(f"Vacation request inserted successfully with ID: {request_id}")
            
            logger.info("Committing transaction...")
            conn.commit()
            cursor.close()
            conn.close()
            logger.info("=== POST /api/vacation-requests - Vacation request creation completed successfully ===")
            
            return jsonify({'message': 'Vacation request created successfully', 'request_id': request_id}), 201
            
        except Exception as e:
            logger.error(f"=== POST /api/vacation-requests - Error occurred: {str(e)} ===")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
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
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
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
            SELECT vr.*, e.first_name, e.last_name, wa.name as work_area, wl.name as work_line
            FROM vacation_requests vr
            JOIN employees e ON vr.employee_id = e.id
            LEFT JOIN work_areas wa ON e.work_area_id = wa.id
            LEFT JOIN work_lines wl ON e.work_line_id = wl.id
            WHERE vr.supervisor_id = %s
            AND vr.status = 'Approved'
            AND vr.start_date >= CURRENT_DATE
            ORDER BY vr.start_date
            LIMIT 10
        """, (supervisor_id,))
        
        upcoming_vacations = [dict(row) for row in cursor.fetchall()]
        
        # Get recent vacation requests
        cursor.execute("""
            SELECT vr.*, e.first_name, e.last_name, wa.name as work_area, wl.name as work_line
            FROM vacation_requests vr
            JOIN employees e ON vr.employee_id = e.id
            LEFT JOIN work_areas wa ON e.work_area_id = wa.id
            LEFT JOIN work_lines wl ON e.work_line_id = wl.id
            WHERE vr.supervisor_id = %s
            ORDER BY vr.created_at DESC
            LIMIT 5
        """, (supervisor_id,))
        
        recent_requests = [dict(row) for row in cursor.fetchall()]
        
        # Get monthly request trends for the current year (January to December)
        cursor.execute("""
            SELECT
                EXTRACT(MONTH FROM created_at) as month,
                COUNT(*) as count
            FROM vacation_requests
            WHERE supervisor_id = %s
            AND EXTRACT(YEAR FROM created_at) = EXTRACT(YEAR FROM CURRENT_DATE)
            GROUP BY EXTRACT(MONTH FROM created_at)
            ORDER BY EXTRACT(MONTH FROM created_at)
        """, (supervisor_id,))
        
        monthly_data = {int(row['month']): row['count'] for row in cursor.fetchall()}
        
        # Create a list of all 12 months (January to December)
        import calendar
        from datetime import datetime
        current_year = datetime.now().year
        month_names = []
        monthly_requests = []
        
        # Generate all 12 months
        for month_num in range(1, 13):
            month_names.append(calendar.month_abbr[month_num])
            monthly_requests.append(monthly_data.get(month_num, 0))
        
        cursor.close()
        conn.close()
        
        stats = {
            'total_employees': total_employees,
            'pending_requests': request_counts.get('Pending', 0),
            'approved_requests': request_counts.get('Approved', 0),
            'denied_requests': request_counts.get('Denied', 0),
            'upcoming_vacations': upcoming_vacations,
            'recent_requests': recent_requests,
            'monthly_trends': {
                'months': month_names,
                'requests': monthly_requests
            }
        }
        
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Work Area Management Endpoints

@app.route('/api/work-areas', methods=['GET'])
@verify_firebase_token
def get_work_areas():
    """Get all work areas"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT id, name FROM work_areas ORDER BY name")
        work_areas = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify([dict(area) for area in work_areas])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/work-areas', methods=['POST'])
@verify_firebase_token
def add_work_area():
    """Add a new work area"""
    try:
        data = request.get_json()
        name = data.get('name')
        
        if not name:
            return jsonify({'error': 'Missing required field: name'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Insert new work area
        cursor.execute("INSERT INTO work_areas (name) VALUES (%s) RETURNING id, name", (name,))
        new_area = cursor.fetchone()
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify(dict(new_area)), 201
    except psycopg2.IntegrityError:
        return jsonify({'error': 'Work area already exists'}), 409
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/work-areas/<int:area_id>', methods=['DELETE'])
@verify_firebase_token
def delete_work_area(area_id):
    """Delete a work area"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor()
        
        # Delete work area
        cursor.execute("DELETE FROM work_areas WHERE id = %s", (area_id,))
        
        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Work area not found'}), 404
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'message': 'Work area deleted successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Work Line Management Endpoints

@app.route('/api/work-lines', methods=['GET'])
@verify_firebase_token
def get_work_lines():
    """Get all work lines"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT id, name FROM work_lines ORDER BY name")
        work_lines = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify([dict(line) for line in work_lines])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/work-lines', methods=['POST'])
@verify_firebase_token
def add_work_line():
    """Add a new work line"""
    try:
        data = request.get_json()
        name = data.get('name')
        
        if not name:
            return jsonify({'error': 'Missing required field: name'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Insert new work line
        cursor.execute("INSERT INTO work_lines (name) VALUES (%s) RETURNING id, name", (name,))
        new_line = cursor.fetchone()
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify(dict(new_line)), 201
    except psycopg2.IntegrityError:
        return jsonify({'error': 'Work line already exists'}), 409
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/work-lines/<int:line_id>', methods=['DELETE'])
@verify_firebase_token
def delete_work_line(line_id):
    """Delete a work line"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor()
        
        # Delete work line
        cursor.execute("DELETE FROM work_lines WHERE id = %s", (line_id,))
        
        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Work line not found'}), 404
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'message': 'Work line deleted successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Profile Settings API Endpoints

@app.route('/api/profile/<firebase_uid>', methods=['GET'])
@verify_firebase_token
def get_profile(firebase_uid):
    """Get supervisor profile information"""
    try:
        # Verify that the user is requesting their own profile
        if request.user['uid'] != firebase_uid:
            return jsonify({'error': 'Unauthorized access to profile'}), 403
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
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

@app.route('/api/profile/<firebase_uid>', methods=['PUT'])
@verify_firebase_token
def update_profile(firebase_uid):
    """Update supervisor profile information"""
    try:
        logger.info("=== PUT /api/profile - Starting profile update ===")
        logger.info(f"Firebase UID from URL: {firebase_uid}")
        logger.info(f"Firebase UID from token: {request.user['uid']}")
        
        # Verify that the user is updating their own profile
        if request.user['uid'] != firebase_uid:
            logger.error(f"Unauthorized profile update attempt: token UID {request.user['uid']} != URL UID {firebase_uid}")
            return jsonify({'error': 'Unauthorized access to profile'}), 403
        
        data = request.get_json()
        logger.info(f"Received profile update data: {data}")
        
        # Only allow updating first_name, last_name, and phone_number
        # Department and shift are read-only
        update_fields = {}
        if 'first_name' in data:
            update_fields['first_name'] = data['first_name']
            logger.info(f"Updating first_name: {data['first_name']}")
        if 'last_name' in data:
            update_fields['last_name'] = data['last_name']
            logger.info(f"Updating last_name: {data['last_name']}")
        if 'phone_number' in data:
            update_fields['phone_number'] = data['phone_number']
            logger.info(f"Updating phone_number: {data['phone_number']}")
        
        logger.info(f"Final update fields: {update_fields}")
        
        # If no fields to update, return success
        if not update_fields:
            logger.info("No fields to update, returning success")
            return jsonify({'message': 'No fields to update'}), 200
        
        logger.info("Attempting database connection...")
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            return jsonify({'error': 'Database connection failed'}), 500
        
        logger.info("Database connection successful")
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Build dynamic update query
        set_clause = ', '.join([f"{field} = %({field})s" for field in update_fields])
        update_fields['firebase_uid'] = firebase_uid
        
        update_query = f"""
            UPDATE supervisors
            SET {set_clause}
            WHERE firebase_uid = %(firebase_uid)s
        """
        
        logger.info(f"Update query: {update_query}")
        logger.info(f"Query parameters: {update_fields}")
        
        cursor.execute(update_query, update_fields)
        logger.info(f"Query executed, rows affected: {cursor.rowcount}")
        
        # Check if any rows were updated
        if cursor.rowcount == 0:
            logger.error("No rows updated - supervisor not found")
            cursor.close()
            conn.close()
            return jsonify({'error': 'Supervisor not found'}), 404
        
        logger.info("Committing transaction...")
        conn.commit()
        cursor.close()
        conn.close()
        logger.info("=== PUT /api/profile - Profile update completed successfully ===")
        
        return jsonify({'message': 'Profile updated successfully'}), 200
        
    except Exception as e:
        logger.error(f"=== PUT /api/profile - Error occurred: {str(e)} ===")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/profile/change-password', methods=['POST'])
@verify_firebase_token
def change_password():
    """Change user password using Firebase Authentication"""
    try:
        logger.info("=== POST /api/profile/change-password - Starting password change ===")
        data = request.get_json()
        firebase_uid = request.user['uid']
        
        logger.info(f"Password change request for user: {firebase_uid}")
        logger.info(f"Request data keys: {list(data.keys()) if data else 'No data'}")
        
        # Validate required fields
        if 'current_password' not in data or 'new_password' not in data:
            logger.error("Missing required fields in password change request")
            return jsonify({'error': 'Missing required fields: current_password, new_password'}), 400
        
        new_password = data['new_password']
        
        # Validate new password strength
        if len(new_password) < 6:
            logger.error("New password too short")
            return jsonify({'error': 'New password must be at least 6 characters long'}), 400
        
        logger.info("Attempting to update password using Firebase Admin SDK...")
        
        # Update password using Firebase Admin SDK
        try:
            auth.update_user(firebase_uid, password=new_password)
            logger.info(f"Password updated successfully for user: {firebase_uid}")
            
            return jsonify({'message': 'Password changed successfully'}), 200
            
        except Exception as firebase_error:
            logger.error(f"Firebase Admin SDK error: {str(firebase_error)}")
            logger.error(f"Firebase error type: {type(firebase_error).__name__}")
            
            # Handle specific Firebase errors
            error_message = 'Failed to change password'
            if 'WEAK_PASSWORD' in str(firebase_error):
                error_message = 'Password is too weak. Please choose a stronger password.'
            elif 'INVALID_PASSWORD' in str(firebase_error):
                error_message = 'Invalid password format.'
            elif 'USER_NOT_FOUND' in str(firebase_error):
                error_message = 'User account not found.'
            
            return jsonify({'error': error_message}), 400
        
    except Exception as e:
        logger.error(f"=== POST /api/profile/change-password - Error occurred: {str(e)} ===")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': 'An unexpected error occurred while changing password'}), 500

@app.route('/api/profile/feedback', methods=['POST'])
@verify_firebase_token
def submit_profile_feedback():
    """Submit feedback from profile settings"""
    try:
        data = request.get_json()
        firebase_uid = request.user['uid']
        
        # Validate required fields
        required_fields = ['category', 'message']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Validate category
        valid_categories = ['bug_report', 'feature_request', 'general_feedback']
        if data['category'] not in valid_categories:
            return jsonify({'error': f'Invalid category. Must be one of: {", ".join(valid_categories)}'}), 400
        
        # Validate rating if provided
        rating = data.get('rating')
        if rating is not None:
            if not isinstance(rating, int) or rating < 1 or rating > 5:
                return jsonify({'error': 'Rating must be an integer between 1 and 5'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Insert feedback
        insert_query = """
            INSERT INTO feedback (user_id, category, rating, message)
            VALUES (%(user_id)s, %(category)s, %(rating)s, %(message)s)
            RETURNING id
        """
        
        feedback_data = {
            'user_id': firebase_uid,
            'category': data['category'],
            'rating': rating,
            'message': data['message']
        }
        
        cursor.execute(insert_query, feedback_data)
        feedback_id = cursor.fetchone()[0]
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'message': 'Feedback submitted successfully', 'feedback_id': feedback_id}), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Help Center API Endpoints

@app.route('/api/help/faq', methods=['GET'])
@verify_firebase_token
def get_faq_articles():
    """Get all published FAQ articles"""
    try:
        firebase_uid = request.user['uid']
        logger.info(f"Loading FAQ articles for user: {firebase_uid}")
        
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed in get_faq_articles")
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT id, title, content, category, created_at, updated_at
            FROM faq_articles
            WHERE is_published = true
            ORDER BY category, title
        """)
        faq_articles = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        logger.info(f"Found {len(faq_articles)} FAQ articles for {firebase_uid}")
        return jsonify([dict(article) for article in faq_articles])
    except Exception as e:
        logger.error(f"Error in get_faq_articles for {firebase_uid}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/help/faq/search', methods=['GET'])
@verify_firebase_token
def search_faq_articles():
    """Search FAQ articles by query"""
    try:
        query = request.args.get('q', '')
        if not query:
            return jsonify({'error': 'Search query parameter "q" is required'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        # Search in title and content
        search_query = """
            SELECT id, title, content, category, created_at, updated_at
            FROM faq_articles
            WHERE is_published = true
            AND (title ILIKE %s OR content ILIKE %s)
            ORDER BY category, title
        """
        search_param = f"%{query}%"
        cursor.execute(search_query, (search_param, search_param))
        faq_articles = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify([dict(article) for article in faq_articles])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/help/ticket', methods=['POST'])
@verify_firebase_token
def submit_support_ticket():
    """Submit a support ticket"""
    try:
        logger.info("=== POST /api/help/ticket - Starting support ticket submission ===")
        data = request.get_json()
        firebase_uid = request.user['uid']
        
        logger.info(f"Support ticket submission for user: {firebase_uid}")
        logger.info(f"Request data: {data}")
        
        # Validate required fields
        required_fields = ['subject', 'category', 'message']
        for field in required_fields:
            if field not in data:
                logger.error(f"Missing required field: {field}")
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        logger.info("Attempting database connection...")
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            return jsonify({'error': 'Database connection failed'}), 500
        
        logger.info("Database connection successful")
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Insert support ticket
        insert_query = """
            INSERT INTO support_tickets (user_id, subject, category, message)
            VALUES (%(user_id)s, %(subject)s, %(category)s, %(message)s)
            RETURNING id
        """
        
        ticket_data = {
            'user_id': firebase_uid,
            'subject': data['subject'],
            'category': data['category'],
            'message': data['message']
        }
        
        logger.info(f"Executing INSERT query with data: {ticket_data}")
        cursor.execute(insert_query, ticket_data)
        result = cursor.fetchone()
        ticket_id = result['id']
        logger.info(f"Support ticket inserted successfully with ID: {ticket_id}")
        
        logger.info("Committing transaction...")
        conn.commit()
        cursor.close()
        conn.close()
        logger.info("=== POST /api/help/ticket - Support ticket submission completed successfully ===")
        
        return jsonify({'message': 'Support ticket submitted successfully', 'ticket_id': ticket_id}), 201
        
    except Exception as e:
        logger.error(f"=== POST /api/help/ticket - Error occurred: {str(e)} ===")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/help/feedback', methods=['POST'])
@verify_firebase_token
def submit_help_feedback():
    """Submit feedback from help center"""
    try:
        logger.info("=== POST /api/help/feedback - Starting feedback submission ===")
        data = request.get_json()
        firebase_uid = request.user['uid']
        
        logger.info(f"Feedback submission for user: {firebase_uid}")
        logger.info(f"Request data: {data}")
        
        # Validate required fields
        required_fields = ['category', 'message']
        for field in required_fields:
            if field not in data:
                logger.error(f"Missing required field: {field}")
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Validate category
        valid_categories = ['bug_report', 'feature_request', 'general_feedback']
        if data['category'] not in valid_categories:
            logger.error(f"Invalid category: {data['category']}")
            return jsonify({'error': f'Invalid category. Must be one of: {", ".join(valid_categories)}'}), 400
        
        # Validate rating if provided
        rating = data.get('rating')
        if rating is not None:
            if not isinstance(rating, int) or rating < 1 or rating > 5:
                logger.error(f"Invalid rating: {rating}")
                return jsonify({'error': 'Rating must be an integer between 1 and 5'}), 400
        
        logger.info("Attempting database connection...")
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            return jsonify({'error': 'Database connection failed'}), 500
        
        logger.info("Database connection successful")
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Insert feedback
        insert_query = """
            INSERT INTO feedback (user_id, category, rating, message)
            VALUES (%(user_id)s, %(category)s, %(rating)s, %(message)s)
            RETURNING id
        """
        
        feedback_data = {
            'user_id': firebase_uid,
            'category': data['category'],
            'rating': rating,
            'message': data['message']
        }
        
        logger.info(f"Executing INSERT query with data: {feedback_data}")
        cursor.execute(insert_query, feedback_data)
        result = cursor.fetchone()
        feedback_id = result['id']
        logger.info(f"Feedback inserted successfully with ID: {feedback_id}")
        
        logger.info("Committing transaction...")
        conn.commit()
        cursor.close()
        conn.close()
        logger.info("=== POST /api/help/feedback - Feedback submission completed successfully ===")
        
        return jsonify({'message': 'Feedback submitted successfully', 'feedback_id': feedback_id}), 201
        
    except Exception as e:
        logger.error(f"=== POST /api/help/feedback - Error occurred: {str(e)} ===")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/help/announcements', methods=['GET'])
@verify_firebase_token
def get_announcements():
    """Get system announcements"""
    try:
        firebase_uid = request.user['uid']
        logger.info(f"Loading announcements for user: {firebase_uid}")
        
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed in get_announcements")
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get supervisor department for filtering
        cursor.execute("SELECT department FROM supervisors WHERE firebase_uid = %s", (firebase_uid,))
        supervisor = cursor.fetchone()
        
        if not supervisor:
            logger.error(f"Supervisor not found for UID: {firebase_uid}")
            cursor.close()
            conn.close()
            return jsonify({'error': 'Supervisor not found'}), 404
        
        department = supervisor['department']
        logger.info(f"Loading announcements for department: {department}")
        
        # Get announcements that are either for all departments (NULL) or for this department
        cursor.execute("""
            SELECT id, title, content, created_at, updated_at
            FROM announcements
            WHERE is_published = true
            AND (target_departments IS NULL OR %s = ANY(target_departments))
            ORDER BY created_at DESC
        """, (department,))
        announcements = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        logger.info(f"Found {len(announcements)} announcements for {firebase_uid}")
        return jsonify([dict(announcement) for announcement in announcements])
    except Exception as e:
        logger.error(f"Error in get_announcements for {firebase_uid}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/help/rate-article', methods=['POST'])
@verify_firebase_token
def rate_faq_article():
    """Rate a FAQ article as helpful or not helpful"""
    try:
        data = request.get_json()
        firebase_uid = request.user['uid']
        
        # Validate required fields
        if 'article_id' not in data or 'rating' not in data:
            return jsonify({'error': 'Missing required fields: article_id, rating'}), 400
        
        # Validate rating
        if data['rating'] not in [True, False]:
            return jsonify({'error': 'Rating must be true (helpful) or false (not helpful)'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Check if article exists
        cursor.execute("SELECT id FROM faq_articles WHERE id = %s", (data['article_id'],))
        article = cursor.fetchone()
        
        if not article:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Article not found'}), 404
        
        # Insert or update rating
        upsert_query = """
            INSERT INTO article_ratings (article_id, user_id, rating)
            VALUES (%(article_id)s, %(user_id)s, %(rating)s)
            ON CONFLICT (article_id, user_id)
            DO UPDATE SET rating = EXCLUDED.rating
            RETURNING id
        """
        
        rating_data = {
            'article_id': data['article_id'],
            'user_id': firebase_uid,
            'rating': data['rating']
        }
        
        cursor.execute(upsert_query, rating_data)
        rating_id = cursor.fetchone()[0]
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'message': 'Article rating submitted successfully', 'rating_id': rating_id}), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Test endpoint without authentication for debugging
@app.route('/api/test-employees', methods=['POST'])
def test_handle_employees():
    """Test employee creation without authentication"""
    try:
        logger.info("=== POST /api/test-employees - Starting test employee creation ===")
        data = request.get_json()
        
        logger.info(f"Received data: {data}")

        # Check required fields
        required_fields = ['first_name', 'last_name', 'department', 'shift']
        for field in required_fields:
            if field not in data or not data[field]:
                logger.error(f"Missing or empty required field: {field}")
                return jsonify({'error': f'Missing required field: {field}'}), 400

        # Phone number is optional, set to empty string if not provided
        phone_number = data.get('phone_number', '').strip()
        logger.info(f"Phone number: '{phone_number}'")

        work_area_id = data.get('work_area_id')
        work_line_id = data.get('work_line_id')
        
        logger.info(f"Raw work_area_id: {work_area_id} (type: {type(work_area_id)})")
        logger.info(f"Raw work_line_id: {work_line_id} (type: {type(work_line_id)})")

        if work_area_id and work_area_id != '':
            try:
                work_area_id = int(work_area_id)
                logger.info(f"Converted work_area_id to: {work_area_id}")
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to convert work_area_id '{work_area_id}': {e}")
                work_area_id = None
        else:
            work_area_id = None
            logger.info("work_area_id set to None")

        if work_line_id and work_line_id != '':
            try:
                work_line_id = int(work_line_id)
                logger.info(f"Converted work_line_id to: {work_line_id}")
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to convert work_line_id '{work_line_id}': {e}")
                work_line_id = None
        else:
            work_line_id = None
            logger.info("work_line_id set to None")

        logger.info("Attempting database connection...")
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            return jsonify({'error': 'Database connection failed'}), 500

        logger.info("Database connection successful")
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # For testing, use supervisor_id = 1 (assuming it exists)
        supervisor_id = 1
        logger.info(f"Using test supervisor_id: {supervisor_id}")

        if work_area_id:
            logger.info(f"Validating work_area_id: {work_area_id}")
            cursor.execute("SELECT id FROM work_areas WHERE id = %s", (work_area_id,))
            if not cursor.fetchone():
                logger.error(f"Invalid work area ID: {work_area_id}")
                cursor.close()
                conn.close()
                return jsonify({'error': 'Invalid work area ID'}), 400
            logger.info("Work area ID validation passed")

        if work_line_id:
            logger.info(f"Validating work_line_id: {work_line_id}")
            cursor.execute("SELECT id FROM work_lines WHERE id = %s", (work_line_id,))
            if not cursor.fetchone():
                logger.error(f"Invalid work line ID: {work_line_id}")
                cursor.close()
                conn.close()
                return jsonify({'error': 'Invalid work line ID'}), 400
            logger.info("Work line ID validation passed")

        insert_query = '''
            INSERT INTO employees (first_name, last_name, phone_number, department, shift, work_area_id, work_line_id, supervisor_id)
            VALUES (%(first_name)s, %(last_name)s, %(phone_number)s, %(department)s, %(shift)s, %(work_area_id)s, %(work_line_id)s, %(supervisor_id)s)
            RETURNING id
        '''

        employee_data = {
            'first_name': data['first_name'],
            'last_name': data['last_name'],
            'phone_number': phone_number,
            'department': data['department'],
            'shift': data['shift'],
            'work_area_id': work_area_id,
            'work_line_id': work_line_id,
            'supervisor_id': supervisor_id
        }

        logger.info(f"Final employee data for insertion: {employee_data}")
        logger.info("Executing INSERT query...")
        cursor.execute(insert_query, employee_data)
        result = cursor.fetchone()
        employee_id = result['id']
        logger.info(f"Employee inserted successfully with ID: {employee_id}")

        logger.info("Committing transaction...")
        conn.commit()
        cursor.close()
        conn.close()
        logger.info("=== POST /api/test-employees - Employee creation completed successfully ===")

        return jsonify({'message': 'Employee added successfully', 'employee_id': employee_id}), 201

    except Exception as e:
        logger.error(f"=== POST /api/test-employees - Error occurred: {str(e)} ===")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

# Test endpoint for GET employees without authentication
@app.route('/api/test-employees-get', methods=['GET'])
def test_get_employees():
    """Test employee retrieval without authentication"""
    try:
        logger.info("=== GET /api/test-employees-get - Starting test employee retrieval ===")
        
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            return jsonify({'error': 'Database connection failed'}), 500

        logger.info("Database connection successful")
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # For testing, use supervisor_id = 1
        supervisor_id = 1
        logger.info(f"Using test supervisor_id: {supervisor_id}")
        
        # Get employees for supervisor
        cursor.execute("""
            SELECT e.*, wa.name as work_area, wl.name as work_line
            FROM employees e
            LEFT JOIN work_areas wa ON e.work_area_id = wa.id
            LEFT JOIN work_lines wl ON e.work_line_id = wl.id
            WHERE e.supervisor_id = %s
            ORDER BY e.id DESC
        """, (supervisor_id,))
        
        employees = cursor.fetchall()
        logger.info(f"Found {len(employees)} employees")
        
        # Convert to list of dicts for JSON serialization
        employee_list = [dict(emp) for emp in employees]
        logger.info(f"Sample employee data: {employee_list[0] if employee_list else 'No employees'}")
        
        cursor.close()
        conn.close()
        logger.info("=== GET /api/test-employees-get - Employee retrieval completed successfully ===")
        
        return jsonify(employee_list)
        
    except Exception as e:
        logger.error(f"=== GET /api/test-employees-get - Error occurred: {str(e)} ===")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

# Test endpoint for vacation requests without authentication
@app.route('/api/test-vacation-requests', methods=['POST'])
def test_vacation_request_creation():
    """Test vacation request creation without authentication"""
    try:
        logger.info("=== POST /api/test-vacation-requests - Starting test vacation request creation ===")
        data = request.get_json()
        
        logger.info(f"Received data: {data}")
        
        # Validate required fields
        required_fields = ['employee_id', 'start_date', 'end_date']
        for field in required_fields:
            if field not in data:
                logger.error(f"Missing required field: {field}")
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        logger.info("Attempting database connection...")
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            return jsonify({'error': 'Database connection failed'}), 500
        
        logger.info("Database connection successful")
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # For testing, use supervisor_id = 1
        supervisor_id = 1
        logger.info(f"Using test supervisor_id: {supervisor_id}")
        
        # Validate employee exists and belongs to this supervisor
        logger.info(f"Validating employee_id: {data['employee_id']}")
        cursor.execute("SELECT id, first_name, last_name FROM employees WHERE id = %s AND supervisor_id = %s",
                     (data['employee_id'], supervisor_id))
        employee = cursor.fetchone()
        
        if not employee:
            logger.error(f"Employee not found or unauthorized: {data['employee_id']}")
            cursor.close()
            conn.close()
            return jsonify({'error': 'Employee not found or unauthorized'}), 404
        
        logger.info(f"Found employee: {employee['first_name']} {employee['last_name']}")
        
        # Parse and validate dates
        try:
            start_date = datetime.strptime(data['start_date'], '%Y-%m-%d')
            end_date = datetime.strptime(data['end_date'], '%Y-%m-%d')
            logger.info(f"Parsed dates - Start: {start_date.date()}, End: {end_date.date()}")
        except ValueError as e:
            logger.error(f"Invalid date format: {e}")
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        if end_date < start_date:
            logger.error("End date is before start date")
            return jsonify({'error': 'End date must be after start date'}), 400
        
        # Calculate business days excluding weekends and holidays
        logger.info("Calculating business days with holiday exclusion...")
        business_days = calculate_business_days(start_date, end_date)
        total_hours = business_days * 8
        return_date = get_next_business_day_backend(end_date)
        
        logger.info(f"Calculated - Business days: {business_days}, Total hours: {total_hours}, Return date: {return_date.date()}")
        
        # Insert vacation request
        insert_query = """
            INSERT INTO vacation_requests (employee_id, supervisor_id, start_date, end_date, return_date, total_hours, status)
            VALUES (%(employee_id)s, %(supervisor_id)s, %(start_date)s, %(end_date)s, %(return_date)s, %(total_hours)s, 'Pending')
            RETURNING id
        """
        
        request_data = {
            'employee_id': data['employee_id'],
            'supervisor_id': supervisor_id,
            'start_date': data['start_date'],
            'end_date': data['end_date'],
            'return_date': return_date.strftime('%Y-%m-%d'),
            'total_hours': total_hours
        }
        
        logger.info(f"Final request data for insertion: {request_data}")
        logger.info("Executing INSERT query...")
        cursor.execute(insert_query, request_data)
        result = cursor.fetchone()
        request_id = result['id']
        logger.info(f"Vacation request inserted successfully with ID: {request_id}")
        
        logger.info("Committing transaction...")
        conn.commit()
        cursor.close()
        conn.close()
        logger.info("=== POST /api/test-vacation-requests - Vacation request creation completed successfully ===")
        
        return jsonify({
            'message': 'Vacation request created successfully',
            'request_id': request_id,
            'calculated_business_days': business_days,
            'calculated_total_hours': total_hours,
            'calculated_return_date': return_date.strftime('%Y-%m-%d')
        }), 201
        
    except Exception as e:
        logger.error(f"=== POST /api/test-vacation-requests - Error occurred: {str(e)} ===")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

# Test endpoint for vacation request retrieval without authentication
@app.route('/api/test-vacation-requests-get', methods=['GET'])
def test_get_vacation_requests():
    """Test vacation request retrieval without authentication"""
    try:
        logger.info("=== GET /api/test-vacation-requests-get - Starting test vacation request retrieval ===")
        
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            return jsonify({'error': 'Database connection failed'}), 500
        
        logger.info("Database connection successful")
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # For testing, use supervisor_id = 1
        supervisor_id = 1
        logger.info(f"Using test supervisor_id: {supervisor_id}")
        
        # Get vacation requests for supervisor's employees
        cursor.execute("""
            SELECT vr.*, e.first_name, e.last_name, e.department, e.shift, wa.name as work_area, wl.name as work_line
            FROM vacation_requests vr
            JOIN employees e ON vr.employee_id = e.id
            LEFT JOIN work_areas wa ON e.work_area_id = wa.id
            LEFT JOIN work_lines wl ON e.work_line_id = wl.id
            WHERE vr.supervisor_id = %s
            ORDER BY vr.created_at DESC
        """, (supervisor_id,))
        
        requests = cursor.fetchall()
        logger.info(f"Found {len(requests)} vacation requests")
        
        # Convert to list of dicts for JSON serialization
        request_list = [dict(req) for req in requests]
        if request_list:
            logger.info(f"Sample request: {request_list[0]}")
        
        cursor.close()
        conn.close()
        logger.info("=== GET /api/test-vacation-requests-get - Vacation request retrieval completed successfully ===")
        
        return jsonify(request_list)
        
    except Exception as e:
        logger.error(f"=== GET /api/test-vacation-requests-get - Error occurred: {str(e)} ===")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

# Test endpoint for profile update without authentication
@app.route('/api/test-profile-update/<firebase_uid>', methods=['PUT'])
def test_update_profile(firebase_uid):
    """Test profile update without authentication"""
    try:
        logger.info("=== PUT /api/test-profile-update - Starting test profile update ===")
        logger.info(f"Firebase UID from URL: {firebase_uid}")
        
        data = request.get_json()
        logger.info(f"Received profile update data: {data}")
        
        # Only allow updating first_name, last_name, and phone_number
        update_fields = {}
        if 'first_name' in data:
            update_fields['first_name'] = data['first_name']
            logger.info(f"Updating first_name: {data['first_name']}")
        if 'last_name' in data:
            update_fields['last_name'] = data['last_name']
            logger.info(f"Updating last_name: {data['last_name']}")
        if 'phone_number' in data:
            update_fields['phone_number'] = data['phone_number']
            logger.info(f"Updating phone_number: {data['phone_number']}")
        
        logger.info(f"Final update fields: {update_fields}")
        
        # If no fields to update, return success
        if not update_fields:
            logger.info("No fields to update, returning success")
            return jsonify({'message': 'No fields to update'}), 200
        
        logger.info("Attempting database connection...")
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            return jsonify({'error': 'Database connection failed'}), 500
        
        logger.info("Database connection successful")
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Build dynamic update query
        set_clause = ', '.join([f"{field} = %({field})s" for field in update_fields])
        update_fields['firebase_uid'] = firebase_uid
        
        update_query = f"""
            UPDATE supervisors
            SET {set_clause}
            WHERE firebase_uid = %(firebase_uid)s
        """
        
        logger.info(f"Update query: {update_query}")
        logger.info(f"Query parameters: {update_fields}")
        
        cursor.execute(update_query, update_fields)
        logger.info(f"Query executed, rows affected: {cursor.rowcount}")
        
        # Check if any rows were updated
        if cursor.rowcount == 0:
            logger.error("No rows updated - supervisor not found")
            cursor.close()
            conn.close()
            return jsonify({'error': 'Supervisor not found'}), 404
        
        logger.info("Committing transaction...")
        conn.commit()
        cursor.close()
        conn.close()
        logger.info("=== PUT /api/test-profile-update - Profile update completed successfully ===")
        
        return jsonify({'message': 'Profile updated successfully'}), 200
        
    except Exception as e:
        logger.error(f"=== PUT /api/test-profile-update - Error occurred: {str(e)} ===")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

# Admin API Endpoints

def verify_admin_token(f):
    """Decorator to verify admin token and check admin email"""
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
            
            # Check if email is in admin_emails table
            email = decoded_token.get('email')
            if not email:
                return jsonify({'error': 'No email in token'}), 401
            
            conn = get_db_connection()
            if not conn:
                return jsonify({'error': 'Database connection failed'}), 500
            
            cursor = conn.cursor()
            cursor.execute("SELECT is_active FROM admin_emails WHERE email = %s", (email,))
            admin_record = cursor.fetchone()
            
            cursor.close()
            conn.close()
            
            if not admin_record or not admin_record[0]:
                return jsonify({'error': 'Access denied. Not an authorized admin.'}), 403
            
            return f(*args, **kwargs)
        except Exception as e:
            return jsonify({'error': 'Invalid token'}), 401
    
    return decorated_function

# Secure Backend-Only Admin Authentication System
def verify_admin_session(f):
    """Decorator to verify admin session"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session or not session['admin_logged_in']:
            return jsonify({'error': 'Admin authentication required'}), 401
        
        if 'admin_email' not in session:
            return jsonify({'error': 'Invalid admin session'}), 401
            
        # Verify admin is still active in database
        try:
            conn = get_db_connection()
            if not conn:
                return jsonify({'error': 'Database connection failed'}), 500
            
            cursor = conn.cursor()
            cursor.execute("SELECT is_active FROM admin_emails WHERE email = %s", (session['admin_email'],))
            admin_record = cursor.fetchone()
            
            cursor.close()
            conn.close()
            
            if not admin_record or not admin_record[0]:
                session.clear()
                return jsonify({'error': 'Admin access revoked'}), 403
                
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Admin session verification error: {str(e)}")
            return jsonify({'error': 'Session verification failed'}), 500
    
    return decorated_function

@app.route('/api/admin/login', methods=['POST'])
def admin_login_api():
    """Secure admin login with email and password"""
    try:
        logger.info("=== Admin login attempt started ===")
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        logger.info(f"Admin login attempt for email: {email}")
        
        if not email or not password:
            logger.warning("Missing email or password in admin login")
            return jsonify({'error': 'Email and password are required'}), 400
        
        logger.info("Attempting database connection...")
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            return jsonify({'error': 'Database connection failed'}), 500
        
        logger.info("Database connection successful")
        cursor = conn.cursor()
        
        # Get admin record with password hash
        logger.info(f"Querying admin_emails table for email: {email}")
        cursor.execute("SELECT email, password_hash, is_active FROM admin_emails WHERE email = %s", (email,))
        admin_record = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if not admin_record:
            logger.warning(f"No admin record found for email: {email}")
            return jsonify({'error': 'Invalid email or password'}), 401
        
        admin_email, password_hash, is_active = admin_record
        
        if not is_active:
            logger.warning(f"Admin account is inactive: {email}")
            return jsonify({'error': 'Admin account is inactive'}), 401
        
        if not password_hash:
            logger.error(f"No password hash found for admin: {email}")
            return jsonify({'error': 'Admin account not properly configured'}), 500
        
        # Verify password
        logger.info("Verifying password...")
        if not bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8')):
            logger.warning(f"Invalid password for admin: {email}")
            return jsonify({'error': 'Invalid email or password'}), 401
        
        # Create secure admin session
        session.permanent = True
        session['admin_logged_in'] = True
        session['admin_email'] = admin_email
        session['admin_login_time'] = datetime.now().isoformat()
        session['csrf_token'] = secrets.token_hex(16)
        
        logger.info(f"Admin login successful for: {email}")
        return jsonify({
            'message': 'Admin login successful',
            'email': admin_email,
            'csrf_token': session['csrf_token']
        }), 200
        
    except Exception as e:
        logger.error(f"Admin login error: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': 'Login failed. Please try again.'}), 500

@app.route('/api/admin/logout', methods=['POST'])
@verify_admin_session
def admin_logout():
    """Secure admin logout"""
    try:
        logger.info(f"Admin logout for: {session.get('admin_email')}")
        session.clear()
        return jsonify({'message': 'Admin logout successful'}), 200
    except Exception as e:
        logger.error(f"Admin logout error: {str(e)}")
        return jsonify({'error': 'Logout failed'}), 500

@app.route('/api/admin/session-check', methods=['GET'])
@verify_admin_session
def admin_session_check():
    """Check if admin session is valid"""
    try:
        return jsonify({
            'authenticated': True,
            'email': session.get('admin_email'),
            'login_time': session.get('admin_login_time')
        }), 200
    except Exception as e:
        logger.error(f"Admin session check error: {str(e)}")
        return jsonify({'error': 'Session check failed'}), 500

@app.route('/api/admin/change-password', methods=['POST'])
@verify_admin_session
def admin_change_password():
    """Change admin password with current password verification"""
    try:
        logger.info("=== Admin password change attempt started ===")
        data = request.get_json()
        current_admin_email = session.get('admin_email')
        
        logger.info(f"Password change request for admin: {current_admin_email}")
        
        # Validate required fields
        required_fields = ['email', 'current_password', 'new_password']
        for field in required_fields:
            if field not in data or not data[field]:
                logger.error(f"Missing required field: {field}")
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Verify the email matches the current session
        if data['email'] != current_admin_email:
            logger.error(f"Email mismatch: session={current_admin_email}, request={data['email']}")
            return jsonify({'error': 'Email does not match current session'}), 403
        
        # Validate new password strength
        new_password = data['new_password']
        if len(new_password) < 6:
            logger.error("New password too short")
            return jsonify({'error': 'New password must be at least 6 characters long'}), 400
        
        # Verify current password and get admin record
        logger.info("Attempting database connection...")
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            return jsonify({'error': 'Database connection failed'}), 500
        
        logger.info("Database connection successful")
        cursor = conn.cursor()
        
        # Get current admin record
        logger.info(f"Querying admin record for email: {current_admin_email}")
        cursor.execute("SELECT email, password_hash, is_active FROM admin_emails WHERE email = %s", (current_admin_email,))
        admin_record = cursor.fetchone()
        
        if not admin_record:
            logger.error(f"Admin record not found for email: {current_admin_email}")
            cursor.close()
            conn.close()
            return jsonify({'error': 'Admin account not found'}), 404
        
        admin_email, current_password_hash, is_active = admin_record
        
        if not is_active:
            logger.error(f"Admin account is inactive: {current_admin_email}")
            cursor.close()
            conn.close()
            return jsonify({'error': 'Admin account is inactive'}), 403
        
        # Verify current password
        logger.info("Verifying current password...")
        if not bcrypt.checkpw(data['current_password'].encode('utf-8'), current_password_hash.encode('utf-8')):
            logger.error(f"Invalid current password for admin: {current_admin_email}")
            cursor.close()
            conn.close()
            return jsonify({'error': 'Current password is incorrect'}), 401
        
        # Check if new password is different from current
        if bcrypt.checkpw(new_password.encode('utf-8'), current_password_hash.encode('utf-8')):
            logger.error("New password is same as current password")
            cursor.close()
            conn.close()
            return jsonify({'error': 'New password must be different from current password'}), 400
        
        # Hash new password
        logger.info("Hashing new password...")
        new_password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Update password in database
        logger.info("Updating password in database...")
        cursor.execute("""
            UPDATE admin_emails
            SET password_hash = %s, updated_at = CURRENT_TIMESTAMP
            WHERE email = %s
        """, (new_password_hash, current_admin_email))
        
        if cursor.rowcount == 0:
            logger.error("No rows updated - admin record not found")
            cursor.close()
            conn.close()
            return jsonify({'error': 'Failed to update password'}), 500
        
        logger.info("Committing password change...")
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"Password changed successfully for admin: {current_admin_email}")
        
        # Clear the current session to force re-login
        session.clear()
        
        return jsonify({'message': 'Password changed successfully. Please log in again.'}), 200
        
    except Exception as e:
        logger.error(f"Admin password change error: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': 'Password change failed. Please try again.'}), 500

@app.route('/api/admin/check-email', methods=['POST'])
def check_admin_email():
    """Check if email is authorized for admin access"""
    try:
        logger.info("=== Admin email check started ===")
        data = request.get_json()
        email = data.get('email')
        logger.info(f"Checking admin access for email: {email}")
        
        if not email:
            logger.error("No email provided in request")
            return jsonify({'error': 'Email is required'}), 400
        
        logger.info("Attempting database connection...")
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            return jsonify({'error': 'Database connection failed'}), 500
        
        logger.info("Database connection successful")
        cursor = conn.cursor()
        
        # First check if admin_emails table exists
        logger.info("Checking if admin_emails table exists...")
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'admin_emails'
            );
        """)
        table_exists = cursor.fetchone()[0]
        logger.info(f"admin_emails table exists: {table_exists}")
        
        if not table_exists:
            logger.error("admin_emails table does not exist")
            cursor.close()
            conn.close()
            return jsonify({'error': 'Admin system not properly configured'}), 500
        
        # Check for admin email
        logger.info(f"Querying admin_emails table for email: {email}")
        cursor.execute("SELECT is_active FROM admin_emails WHERE email = %s", (email,))
        admin_record = cursor.fetchone()
        logger.info(f"Admin record found: {admin_record}")
        
        # If no record found, let's see what emails are in the table
        if not admin_record:
            logger.info("No admin record found, checking all admin emails...")
            cursor.execute("SELECT email, is_active FROM admin_emails")
            all_admins = cursor.fetchall()
            logger.info(f"All admin emails in database: {all_admins}")
        
        cursor.close()
        conn.close()
        
        is_admin = admin_record is not None and admin_record[0]
        logger.info(f"Final admin check result: {is_admin}")
        return jsonify({'isAdmin': is_admin})
        
    except Exception as e:
        logger.error(f"Error in check_admin_email: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/verify', methods=['POST'])
@verify_admin_token
def verify_admin():
    """Verify admin access"""
    try:
        data = request.get_json()
        email = data.get('email')
        
        # Additional verification if needed
        return jsonify({'message': 'Admin access verified', 'email': email})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/overview', methods=['GET'])
@verify_admin_session
def get_admin_overview():
    """Get admin dashboard overview statistics"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get total supervisors
        cursor.execute("SELECT COUNT(*) as count FROM supervisors")
        total_supervisors = cursor.fetchone()['count']
        
        # Get total employees
        cursor.execute("SELECT COUNT(*) as count FROM employees")
        total_employees = cursor.fetchone()['count']
        
        # Get total vacation requests
        cursor.execute("SELECT COUNT(*) as count FROM vacation_requests")
        total_vacation_requests = cursor.fetchone()['count']
        
        # Get total active announcements
        cursor.execute("SELECT COUNT(*) as count FROM announcements WHERE is_published = true")
        total_announcements = cursor.fetchone()['count']
        
        # Get recent activity (last 10 activities)
        cursor.execute("""
            SELECT
                'New vacation request from ' || e.first_name || ' ' || e.last_name as description,
                vr.created_at
            FROM vacation_requests vr
            JOIN employees e ON vr.employee_id = e.id
            ORDER BY vr.created_at DESC
            LIMIT 5
        """)
        recent_activity = [dict(row) for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'totalSupervisors': total_supervisors,
            'totalEmployees': total_employees,
            'totalVacationRequests': total_vacation_requests,
            'totalAnnouncements': total_announcements,
            'recentActivity': recent_activity
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/announcements', methods=['GET', 'POST', 'PUT', 'DELETE'])
@verify_admin_session
def handle_admin_announcements():
    """Handle admin announcements management"""
    if request.method == 'GET':
        try:
            conn = get_db_connection()
            if not conn:
                return jsonify({'error': 'Database connection failed'}), 500
            
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("""
                SELECT id, title, content, is_published, target_departments, created_at, updated_at
                FROM announcements
                ORDER BY created_at DESC
            """)
            announcements = [dict(row) for row in cursor.fetchall()]
            
            cursor.close()
            conn.close()
            
            return jsonify(announcements)
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            
            required_fields = ['title', 'content']
            for field in required_fields:
                if field not in data:
                    return jsonify({'error': f'Missing required field: {field}'}), 400
            
            conn = get_db_connection()
            if not conn:
                return jsonify({'error': 'Database connection failed'}), 500
            
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            target_departments = data.get('target_departments')
            if target_departments and isinstance(target_departments, list):
                target_departments = target_departments
            else:
                target_departments = None
            
            cursor.execute("""
                INSERT INTO announcements (title, content, target_departments)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (data['title'], data['content'], target_departments))
            
            announcement_id = cursor.fetchone()['id']
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return jsonify({'message': 'Announcement created successfully', 'id': announcement_id}), 201
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500

# Get single announcement endpoint
@app.route('/api/admin/announcements/<int:announcement_id>', methods=['GET'])
@verify_admin_session
def get_single_announcement(announcement_id):
    """Get a single announcement by ID"""
    try:
        logger.info(f"Getting announcement with ID: {announcement_id}")
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT id, title, content, is_published, target_departments, created_at, updated_at
            FROM announcements
            WHERE id = %s
        """, (announcement_id,))
        
        announcement = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if not announcement:
            logger.warning(f"Announcement not found with ID: {announcement_id}")
            return jsonify({'error': 'Announcement not found'}), 404
        
        logger.info(f"Successfully retrieved announcement: {announcement['title']}")
        return jsonify(dict(announcement))
        
    except Exception as e:
        logger.error(f"Error getting announcement {announcement_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Update announcement endpoint
@app.route('/api/admin/announcements/<int:announcement_id>', methods=['PUT'])
@verify_admin_session
def update_announcement(announcement_id):
    """Update an announcement"""
    try:
        logger.info(f"Updating announcement with ID: {announcement_id}")
        data = request.get_json()
        logger.info(f"Update data received: {data}")
        
        required_fields = ['title', 'content']
        for field in required_fields:
            if field not in data:
                logger.error(f"Missing required field: {field}")
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        target_departments = data.get('target_departments')
        if target_departments and isinstance(target_departments, list):
            target_departments = target_departments
        else:
            target_departments = None
        
        is_published = data.get('is_published', True)
        
        logger.info(f"Executing update with: title={data['title']}, content={data['content'][:50]}..., target_departments={target_departments}, is_published={is_published}")
        
        cursor.execute("""
            UPDATE announcements
            SET title = %s, content = %s, target_departments = %s, is_published = %s
            WHERE id = %s
            RETURNING id, title, content, is_published, target_departments, created_at, updated_at
        """, (data['title'], data['content'], target_departments, is_published, announcement_id))
        
        updated_announcement = cursor.fetchone()
        
        if not updated_announcement:
            logger.warning(f"Announcement not found with ID: {announcement_id}")
            cursor.close()
            conn.close()
            return jsonify({'error': 'Announcement not found'}), 404
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"Successfully updated announcement: {updated_announcement['title']}")
        return jsonify(dict(updated_announcement))
        
    except Exception as e:
        logger.error(f"Error updating announcement {announcement_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Delete announcement endpoint
@app.route('/api/admin/announcements/<int:announcement_id>', methods=['DELETE'])
@verify_admin_session
def delete_announcement(announcement_id):
    """Delete an announcement"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor()
        cursor.execute("DELETE FROM announcements WHERE id = %s", (announcement_id,))
        
        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Announcement not found'}), 404
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'message': 'Announcement deleted successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/faq', methods=['GET', 'POST', 'PUT', 'DELETE'])
@verify_admin_session
def handle_admin_faq():
    """Handle admin FAQ articles management"""
    if request.method == 'GET':
        try:
            conn = get_db_connection()
            if not conn:
                return jsonify({'error': 'Database connection failed'}), 500
            
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("""
                SELECT id, title, content, category, is_published, created_at, updated_at
                FROM faq_articles
                ORDER BY category, title
            """)
            articles = [dict(row) for row in cursor.fetchall()]
            
            cursor.close()
            conn.close()
            
            return jsonify(articles)
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            
            required_fields = ['title', 'content', 'category']
            for field in required_fields:
                if field not in data:
                    return jsonify({'error': f'Missing required field: {field}'}), 400
            
            conn = get_db_connection()
            if not conn:
                return jsonify({'error': 'Database connection failed'}), 500
            
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            cursor.execute("""
                INSERT INTO faq_articles (title, content, category)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (data['title'], data['content'], data['category']))
            
            article_id = cursor.fetchone()['id']
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return jsonify({'message': 'FAQ article created successfully', 'id': article_id}), 201
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500

# Get single FAQ article endpoint
@app.route('/api/admin/faq/<int:article_id>', methods=['GET'])
@verify_admin_session
def get_single_faq_article(article_id):
    """Get a single FAQ article by ID"""
    try:
        logger.info(f"Getting FAQ article with ID: {article_id}")
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT id, title, content, category, is_published, created_at, updated_at
            FROM faq_articles
            WHERE id = %s
        """, (article_id,))
        
        article = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if not article:
            logger.warning(f"FAQ article not found with ID: {article_id}")
            return jsonify({'error': 'FAQ article not found'}), 404
        
        logger.info(f"Successfully retrieved FAQ article: {article['title']}")
        return jsonify(dict(article))
        
    except Exception as e:
        logger.error(f"Error getting FAQ article {article_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Update FAQ article endpoint
@app.route('/api/admin/faq/<int:article_id>', methods=['PUT'])
@verify_admin_session
def update_faq_article(article_id):
    """Update a FAQ article"""
    try:
        logger.info(f"Updating FAQ article with ID: {article_id}")
        data = request.get_json()
        logger.info(f"Update data received: {data}")
        
        required_fields = ['title', 'content', 'category']
        for field in required_fields:
            if field not in data:
                logger.error(f"Missing required field: {field}")
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        is_published = data.get('is_published', True)
        
        logger.info(f"Executing update with: title={data['title']}, content={data['content'][:50]}..., category={data['category']}, is_published={is_published}")
        
        cursor.execute("""
            UPDATE faq_articles
            SET title = %s, content = %s, category = %s, is_published = %s
            WHERE id = %s
            RETURNING id, title, content, category, is_published, created_at, updated_at
        """, (data['title'], data['content'], data['category'], is_published, article_id))
        
        updated_article = cursor.fetchone()
        
        if not updated_article:
            logger.warning(f"FAQ article not found with ID: {article_id}")
            cursor.close()
            conn.close()
            return jsonify({'error': 'FAQ article not found'}), 404
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"Successfully updated FAQ article: {updated_article['title']}")
        return jsonify(dict(updated_article))
        
    except Exception as e:
        logger.error(f"Error updating FAQ article {article_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Delete FAQ article endpoint
@app.route('/api/admin/faq/<int:article_id>', methods=['DELETE'])
@verify_admin_session
def delete_faq_article(article_id):
    """Delete a FAQ article"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor()
        cursor.execute("DELETE FROM faq_articles WHERE id = %s", (article_id,))
        
        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            return jsonify({'error': 'FAQ article not found'}), 404
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'message': 'FAQ article deleted successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/feedback', methods=['GET'])
@verify_admin_session
def get_admin_feedback():
    """Get all user feedback for admin review"""
    try:
        category = request.args.get('category')
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        query = """
            SELECT f.*, s.email as user_email
            FROM feedback f
            LEFT JOIN supervisors s ON f.user_id = s.firebase_uid
            WHERE 1=1
        """
        params = []
        
        if category:
            query += " AND f.category = %s"
            params.append(category)
        
        query += " ORDER BY f.created_at DESC"
        
        cursor.execute(query, params)
        feedback = [dict(row) for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        return jsonify(feedback)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/support-tickets', methods=['GET'])
@verify_admin_session
def get_admin_support_tickets():
    """Get all support tickets for admin review"""
    try:
        status = request.args.get('status')
        priority = request.args.get('priority')
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        query = """
            SELECT st.*, s.email as user_email
            FROM support_tickets st
            LEFT JOIN supervisors s ON st.user_id = s.firebase_uid
            WHERE 1=1
        """
        params = []
        
        if status:
            query += " AND st.status = %s"
            params.append(status)
        
        if priority:
            query += " AND st.priority = %s"
            params.append(priority)
        
        query += " ORDER BY st.created_at DESC"
        
        cursor.execute(query, params)
        tickets = [dict(row) for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        return jsonify(tickets)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Get single support ticket endpoint
@app.route('/api/admin/support-tickets/<int:ticket_id>', methods=['GET'])
@verify_admin_session
def get_single_support_ticket(ticket_id):
    """Get a single support ticket by ID"""
    try:
        logger.info(f"Getting support ticket with ID: {ticket_id}")
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT st.*, s.email as user_email
            FROM support_tickets st
            LEFT JOIN supervisors s ON st.user_id = s.firebase_uid
            WHERE st.id = %s
        """, (ticket_id,))
        
        ticket = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if not ticket:
            logger.warning(f"Support ticket not found with ID: {ticket_id}")
            return jsonify({'error': 'Support ticket not found'}), 404
        
        logger.info(f"Successfully retrieved support ticket: {ticket['subject']}")
        return jsonify(dict(ticket))
        
    except Exception as e:
        logger.error(f"Error getting support ticket {ticket_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Update support ticket status endpoint
@app.route('/api/admin/support-tickets/<int:ticket_id>', methods=['PUT'])
@verify_admin_session
def update_support_ticket(ticket_id):
    """Update support ticket status"""
    try:
        data = request.get_json()
        status = data.get('status')
        
        if not status:
            return jsonify({'error': 'Status is required'}), 400
        
        valid_statuses = ['open', 'in_progress', 'resolved', 'closed']
        if status not in valid_statuses:
            return jsonify({'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE support_tickets
            SET status = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (status, ticket_id))
        
        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Support ticket not found'}), 404
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'message': 'Support ticket updated successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/supervisors', methods=['GET'])
@verify_admin_session
def get_admin_supervisors():
    """Get all supervisors for admin management"""
    try:
        department = request.args.get('department')
        shift = request.args.get('shift')
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        query = """
            SELECT s.*, COUNT(e.id) as employee_count
            FROM supervisors s
            LEFT JOIN employees e ON s.id = e.supervisor_id
            WHERE 1=1
        """
        params = []
        
        if department:
            query += " AND s.department = %s"
            params.append(department)
        
        if shift:
            query += " AND s.shift = %s"
            params.append(shift)
        
        query += " GROUP BY s.id ORDER BY s.last_name, s.first_name"
        
        cursor.execute(query, params)
        supervisors = [dict(row) for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        return jsonify(supervisors)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/vacation-requests', methods=['GET'])
@verify_admin_session
def get_admin_vacation_requests():
    """Get all vacation requests for admin review"""
    try:
        supervisor = request.args.get('supervisor')
        shift = request.args.get('shift')
        department = request.args.get('department')
        status = request.args.get('status')
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        query = """
            SELECT vr.*,
                   e.first_name || ' ' || e.last_name as employee_name,
                   e.department, e.shift,
                   s.first_name || ' ' || s.last_name as supervisor_name,
                   wa.name as work_area, wl.name as work_line
            FROM vacation_requests vr
            JOIN employees e ON vr.employee_id = e.id
            JOIN supervisors s ON vr.supervisor_id = s.id
            LEFT JOIN work_areas wa ON e.work_area_id = wa.id
            LEFT JOIN work_lines wl ON e.work_line_id = wl.id
            WHERE 1=1
        """
        params = []
        
        if supervisor:
            query += " AND s.id = %s"
            params.append(supervisor)
        
        if shift:
            query += " AND e.shift = %s"
            params.append(shift)
        
        if department:
            query += " AND e.department = %s"
            params.append(department)
        
        if status:
            query += " AND vr.status = %s"
            params.append(status)
        
        query += " ORDER BY vr.created_at DESC"
        
        cursor.execute(query, params)
        requests = [dict(row) for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        return jsonify(requests)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/employees', methods=['GET'])
@verify_admin_session
def get_admin_employees():
    """Get all employees for admin review"""
    try:
        supervisor = request.args.get('supervisor')
        department = request.args.get('department')
        shift = request.args.get('shift')
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        query = """
            SELECT e.*,
                   s.first_name || ' ' || s.last_name as supervisor_name,
                   wa.name as work_area, wl.name as work_line
            FROM employees e
            JOIN supervisors s ON e.supervisor_id = s.id
            LEFT JOIN work_areas wa ON e.work_area_id = wa.id
            LEFT JOIN work_lines wl ON e.work_line_id = wl.id
            WHERE 1=1
        """
        params = []
        
        if supervisor:
            query += " AND (s.first_name || ' ' || s.last_name) = %s"
            params.append(supervisor)
        
        if department:
            query += " AND e.department = %s"
            params.append(department)
        
        if shift:
            query += " AND e.shift = %s"
            params.append(shift)
        
        query += " ORDER BY e.last_name, e.first_name"
        
        logger.info(f"Final SQL query: {query}")
        logger.info(f"Query parameters: {params}")
        
        cursor.execute(query, params)
        employees = [dict(row) for row in cursor.fetchall()]
        
        logger.info(f"Found {len(employees)} employees matching filters")
        
        cursor.close()
        conn.close()
        
        return jsonify(employees)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/admin-emails', methods=['GET', 'POST'])
@verify_admin_session
def handle_admin_emails():
    """Handle admin email management"""
    if request.method == 'GET':
        try:
            conn = get_db_connection()
            if not conn:
                return jsonify({'error': 'Database connection failed'}), 500
            
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("""
                SELECT id, email, is_active, created_at, updated_at
                FROM admin_emails
                ORDER BY created_at DESC
            """)
            emails = [dict(row) for row in cursor.fetchall()]
            
            cursor.close()
            conn.close()
            
            return jsonify(emails)
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            email = data.get('email')
            password = data.get('password')
            
            if not email:
                return jsonify({'error': 'Email is required'}), 400
            
            if not password:
                return jsonify({'error': 'Password is required'}), 400
            
            # Hash the password
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            conn = get_db_connection()
            if not conn:
                return jsonify({'error': 'Database connection failed'}), 500
            
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            cursor.execute("""
                INSERT INTO admin_emails (email, password_hash)
                VALUES (%s, %s)
                RETURNING id
            """, (email, password_hash))
            
            email_id = cursor.fetchone()['id']
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return jsonify({'message': 'Admin email added successfully', 'id': email_id}), 201
            
        except psycopg2.IntegrityError:
            return jsonify({'error': 'Email already exists'}), 409
        except Exception as e:
            return jsonify({'error': str(e)}), 500

@app.route('/api/admin/admin-emails/<int:email_id>', methods=['PUT', 'DELETE'])
@verify_admin_session
def handle_admin_email_actions(email_id):
    """Handle individual admin email actions"""
    if request.method == 'PUT':
        try:
            data = request.get_json()
            is_active = data.get('is_active')
            
            if is_active is None:
                return jsonify({'error': 'is_active field is required'}), 400
            
            conn = get_db_connection()
            if not conn:
                return jsonify({'error': 'Database connection failed'}), 500
            
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE admin_emails
                SET is_active = %s
                WHERE id = %s
            """, (is_active, email_id))
            
            if cursor.rowcount == 0:
                cursor.close()
                conn.close()
                return jsonify({'error': 'Admin email not found'}), 404
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return jsonify({'message': 'Admin email updated successfully'})
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    elif request.method == 'DELETE':
        try:
            conn = get_db_connection()
            if not conn:
                return jsonify({'error': 'Database connection failed'}), 500
            
            cursor = conn.cursor()
            cursor.execute("DELETE FROM admin_emails WHERE id = %s", (email_id,))
            
            if cursor.rowcount == 0:
                cursor.close()
                conn.close()
                return jsonify({'error': 'Admin email not found'}), 404
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return jsonify({'message': 'Admin email deleted successfully'})
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500

# Delete admin email by email address endpoint
@app.route('/api/admin/admin-emails/<path:email>', methods=['DELETE'])
@verify_admin_session
def delete_admin_email_by_email(email):
    """Delete admin email by email address"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor()
        cursor.execute("DELETE FROM admin_emails WHERE email = %s", (email,))
        
        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Admin email not found'}), 404
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'message': 'Admin email deleted successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Legal Documents Management API Endpoints

@app.route('/api/admin/legal-documents', methods=['GET'])
@verify_admin_session
def get_legal_documents():
    """Get all active legal documents"""
    try:
        logger.info("Getting all active legal documents")
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT id, document_type, title, content, version, is_active,
                   effective_date, created_at, updated_at
            FROM legal_documents
            WHERE is_active = true
            ORDER BY document_type, version DESC
        """)
        
        documents = [dict(row) for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        logger.info(f"Found {len(documents)} active legal documents")
        return jsonify(documents)
        
    except Exception as e:
        logger.error(f"Error getting legal documents: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/legal-documents/history', methods=['GET'])
@verify_admin_session
def get_legal_documents_history():
    """Get all legal documents including archived versions"""
    try:
        logger.info("Getting legal documents history")
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT id, document_type, title, content, version, is_active,
                   effective_date, created_at, updated_at
            FROM legal_documents
            ORDER BY document_type, version DESC, created_at DESC
        """)
        
        documents = [dict(row) for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        logger.info(f"Found {len(documents)} legal documents in history")
        return jsonify(documents)
        
    except Exception as e:
        logger.error(f"Error getting legal documents history: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/legal-documents/<document_type>', methods=['GET'])
@verify_admin_session
def get_legal_document_by_type(document_type):
    """Get active legal document by type"""
    try:
        logger.info(f"Getting legal document by type: {document_type}")
        
        # Validate document type
        valid_types = ['terms_of_service', 'privacy_policy']
        if document_type not in valid_types:
            logger.error(f"Invalid document type: {document_type}")
            return jsonify({'error': f'Invalid document type. Must be one of: {", ".join(valid_types)}'}), 400
        
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT id, document_type, title, content, version, is_active,
                   effective_date, created_at, updated_at
            FROM legal_documents
            WHERE document_type = %s AND is_active = true
            ORDER BY version DESC
            LIMIT 1
        """, (document_type,))
        
        document = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if not document:
            logger.warning(f"No active legal document found for type: {document_type}")
            return jsonify({'error': 'Legal document not found'}), 404
        
        logger.info(f"Successfully retrieved legal document: {document['title']}")
        return jsonify(dict(document))
        
    except Exception as e:
        logger.error(f"Error getting legal document {document_type}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/legal-documents/by-id/<int:document_id>', methods=['GET'])
@verify_admin_session
def get_legal_document_by_id(document_id):
    """Get legal document by ID (for viewing archived versions)"""
    try:
        logger.info(f"Getting legal document by ID: {document_id}")
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT id, document_type, title, content, version, is_active,
                   effective_date, created_at, updated_at
            FROM legal_documents
            WHERE id = %s
        """, (document_id,))
        
        document = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if not document:
            logger.warning(f"Legal document not found with ID: {document_id}")
            return jsonify({'error': 'Legal document not found'}), 404
        
        logger.info(f"Successfully retrieved legal document: {document['title']}")
        return jsonify(dict(document))
        
    except Exception as e:
        logger.error(f"Error getting legal document {document_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/legal-documents/<document_type>', methods=['PUT'])
@verify_admin_session
def update_legal_document(document_type):
    """Update legal document (creates new version and archives old one)"""
    try:
        logger.info(f"Updating legal document: {document_type}")
        data = request.get_json()
        logger.info(f"Update data received: {data}")
        
        # Validate document type
        valid_types = ['terms_of_service', 'privacy_policy']
        if document_type not in valid_types:
            logger.error(f"Invalid document type: {document_type}")
            return jsonify({'error': f'Invalid document type. Must be one of: {", ".join(valid_types)}'}), 400
        
        # Validate required fields
        required_fields = ['title', 'content', 'effective_date']
        for field in required_fields:
            if field not in data or not data[field]:
                logger.error(f"Missing required field: {field}")
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Validate effective date format
        try:
            from datetime import datetime
            effective_date = datetime.strptime(data['effective_date'], '%Y-%m-%d').date()
            logger.info(f"Parsed effective date: {effective_date}")
        except ValueError as e:
            logger.error(f"Invalid effective date format: {e}")
            return jsonify({'error': 'Invalid effective date format. Use YYYY-MM-DD'}), 400
        
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
            # First check if legal_documents table exists
            logger.info("Checking if legal_documents table exists")
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'legal_documents'
                );
            """)
            result = cursor.fetchone()
            table_exists = result['exists'] if result else False
            logger.info(f"legal_documents table exists: {table_exists}")
            
            if not table_exists:
                logger.error("legal_documents table does not exist")
                cursor.close()
                conn.close()
                return jsonify({'error': 'Legal documents system not properly configured. Please run database migrations.'}), 500
            
            # Get current active document to determine next version
            logger.info("Getting current active document version")
            cursor.execute("""
                SELECT version FROM legal_documents
                WHERE document_type = %s AND is_active = true
                ORDER BY created_at DESC
                LIMIT 1
            """, (document_type,))
            
            current_doc = cursor.fetchone()
            if current_doc:
                try:
                    # Try to parse version as integer
                    current_version = int(current_doc['version'])
                    next_version = current_version + 1
                except (ValueError, TypeError):
                    # If version is not a number, try to extract number or default to 2
                    version_str = str(current_doc['version'])
                    import re
                    version_match = re.search(r'\d+', version_str)
                    if version_match:
                        current_version = int(version_match.group())
                        next_version = current_version + 1
                    else:
                        next_version = 2
            else:
                next_version = 1
            logger.info(f"Next version will be: {next_version}")
            
            # Archive current active document (if exists)
            if current_doc:
                logger.info("Archiving current active document")
                cursor.execute("""
                    UPDATE legal_documents
                    SET is_active = false
                    WHERE document_type = %s AND is_active = true
                """, (document_type,))
                logger.info(f"Archived {cursor.rowcount} existing documents")
            
            # Insert new version as active
            logger.info("Inserting new document version")
            cursor.execute("""
                INSERT INTO legal_documents (document_type, title, content, version, is_active, effective_date)
                VALUES (%s, %s, %s, %s, true, %s)
                RETURNING id, document_type, title, content, version, is_active, effective_date, created_at, updated_at
            """, (document_type, data['title'], data['content'], str(next_version), effective_date))
            
            new_document = cursor.fetchone()
            if not new_document:
                logger.error("Failed to insert new document - no result returned")
                cursor.close()
                conn.close()
                return jsonify({'error': 'Failed to create new document version'}), 500
                
            logger.info(f"Created new document with ID: {new_document['id']}")
            
            # Commit transaction
            conn.commit()
            
            cursor.close()
            conn.close()
            
            logger.info(f"Successfully updated legal document: {new_document['title']}")
            return jsonify(dict(new_document))
            
        except psycopg2.Error as db_error:
            # Database-specific error handling
            logger.error(f"Database error: {str(db_error)}")
            logger.error(f"Database error code: {db_error.pgcode}")
            conn.rollback()
            cursor.close()
            conn.close()
            return jsonify({'error': f'Database error: {str(db_error)}'}), 500
            
        except Exception as e:
            # Rollback transaction on error
            logger.error(f"General error in transaction: {str(e)}")
            conn.rollback()
            cursor.close()
            conn.close()
            raise e
        
    except Exception as e:
        logger.error(f"Error updating legal document {document_type}: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

# Public endpoints for legal documents (no authentication required)

@app.route('/api/legal/terms-of-service', methods=['GET'])
def get_public_terms_of_service():
    """Get current Terms of Service for public access"""
    try:
        logger.info("Getting public Terms of Service")
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT title, content, version, effective_date, updated_at
            FROM legal_documents
            WHERE document_type = 'terms_of_service' AND is_active = true
            ORDER BY version DESC
            LIMIT 1
        """)
        
        document = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if not document:
            logger.warning("No active Terms of Service found")
            return jsonify({'error': 'Terms of Service not available'}), 404
        
        logger.info("Successfully retrieved public Terms of Service")
        return jsonify(dict(document))
        
    except Exception as e:
        logger.error(f"Error getting public Terms of Service: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/legal/privacy-policy', methods=['GET'])
def get_public_privacy_policy():
    """Get current Privacy Policy for public access"""
    try:
        logger.info("Getting public Privacy Policy")
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT title, content, version, effective_date, updated_at
            FROM legal_documents
            WHERE document_type = 'privacy_policy' AND is_active = true
            ORDER BY version DESC
            LIMIT 1
        """)
        
        document = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if not document:
            logger.warning("No active Privacy Policy found")
            return jsonify({'error': 'Privacy Policy not available'}), 404
        
        logger.info("Successfully retrieved public Privacy Policy")
        return jsonify(dict(document))
        
    except Exception as e:
        logger.error(f"Error getting public Privacy Policy: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Public support ticket endpoint for index.html (no authentication required)
@app.route('/api/public/support-ticket', methods=['POST'])
def submit_public_support_ticket():
    """Submit a support ticket from public pages (no authentication required)"""
    try:
        logger.info("=== POST /api/public/support-ticket - Starting public support ticket submission ===")
        data = request.get_json()
        
        logger.info(f"Public support ticket submission")
        logger.info(f"Request data: {data}")
        
        # Validate required fields
        required_fields = ['subject', 'category', 'message']
        for field in required_fields:
            if field not in data or not data[field].strip():
                logger.error(f"Missing required field: {field}")
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        logger.info("Attempting database connection...")
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            return jsonify({'error': 'Database connection failed'}), 500
        
        logger.info("Database connection successful")
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # For public submissions, use a guest email if no user is authenticated
        user_email = data.get('email', '').strip()
        if not user_email:
            user_email = 'guest@email.com'
        
        # Insert support ticket with email instead of user_id
        insert_query = """
            INSERT INTO support_tickets (user_id, subject, category, message)
            VALUES (%(user_id)s, %(subject)s, %(category)s, %(message)s)
            RETURNING id
        """
        
        ticket_data = {
            'user_id': user_email,  # Store email in user_id field for public tickets
            'subject': data['subject'].strip(),
            'category': data['category'],
            'message': data['message'].strip()
        }
        
        logger.info(f"Executing INSERT query with data: {ticket_data}")
        cursor.execute(insert_query, ticket_data)
        result = cursor.fetchone()
        ticket_id = result['id']
        logger.info(f"Public support ticket inserted successfully with ID: {ticket_id}")
        
        logger.info("Committing transaction...")
        conn.commit()
        cursor.close()
        conn.close()
        logger.info("=== POST /api/public/support-ticket - Public support ticket submission completed successfully ===")
        
        return jsonify({'message': 'Support ticket submitted successfully', 'ticket_id': ticket_id}), 201
        
    except Exception as e:
        logger.error(f"=== POST /api/public/support-ticket - Error occurred: {str(e)} ===")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

        
        # Create temporary files
        temp_excel = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
        temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        
        try:
            # Copy template to temp file
            shutil.copy2(excel_path, temp_excel.name)
            
            # VALIDATION LOG #2: Excel Template Structure Analysis
            logger.info(f"=== VALIDATION LOG #2: Excel Template Structure Analysis ===")
            workbook = load_workbook(temp_excel.name)
            logger.info(f"Available worksheets: {workbook.sheetnames}")
            
            if 'vacation' not in workbook.sheetnames:
                logger.error("'vacation' sheet not found in Excel template")
                return jsonify({'error': 'Excel template format error'}), 500
            
            sheet = workbook['vacation']
            logger.info(f"Vacation sheet loaded successfully")
            
            # VALIDATION LOG #3: Check current cell contents at required positions
            logger.info(f"=== VALIDATION LOG #3: Current Cell Contents Analysis ===")
            required_cells = ['A10', 'F10', 'A12', 'B11', 'E12', 'D18', 'F19']
            for cell_ref in required_cells:
                current_value = sheet[cell_ref].value
                logger.info(f"Cell {cell_ref} current value: '{current_value}' (type: {type(current_value)})")
            
            # VALIDATION LOG #4: Vacation data preparation
            logger.info(f"=== VALIDATION LOG #4: Vacation Data Preparation ===")
            employee_name = f"{vacation['first_name']} {vacation['last_name']}"
            logger.info(f"Employee name: {employee_name}")
            logger.info(f"Created at: {vacation['created_at']}")
            logger.info(f"Total hours: {vacation['total_hours']}")
            
            # Fill in vacation data with logging
            logger.info(f"=== VALIDATION LOG #5: Cell Population Process ===")
            sheet['A10'] = employee_name
            logger.info(f"Set A10 (Employee Name) to: {employee_name}")
            
            submitted_date = vacation['created_at'].strftime('%m/%d/%Y') if vacation['created_at'] else ''
            sheet['F10'] = submitted_date
            logger.info(f"Set F10 (Submitted Date) to: {submitted_date}")
            
            sheet['A12'] = vacation['total_hours']
            logger.info(f"Set A12 (Total Hours) to: {vacation['total_hours']}")
            
            # Calculate total days (business days)
            start_date = vacation['start_date']
            end_date = vacation['end_date']
            if isinstance(start_date, str):
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            if isinstance(end_date, str):
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            total_days = calculate_business_days(
                datetime.combine(start_date, datetime.min.time()),
                datetime.combine(end_date, datetime.min.time())
            )
            sheet['B11'] = total_days
            logger.info(f"Set B11 (Total Days) to: {total_days}")
            
            # Format dates
            start_date_str = start_date.strftime('%m/%d/%Y')
            end_date_str = end_date.strftime('%m/%d/%Y')
            date_range = f"{start_date_str} to {end_date_str}"
            sheet['E12'] = date_range
            logger.info(f"Set E12 (Start and End Date) to: {date_range}")
            
            # Return date information
            return_date = vacation['return_date']
            if isinstance(return_date, str):
                return_date = datetime.strptime(return_date, '%Y-%m-%d').date()
            
            # Calculate return day of week
            return_day = return_date.strftime('%A')
            sheet['D18'] = return_day
            logger.info(f"Set D18 (Return Day) to: {return_day}")
            
            return_date_str = return_date.strftime('%m/%d/%Y')
            sheet['F19'] = return_date_str
            logger.info(f"Set F19 (Return Date) to: {return_date_str}")
            
            # VALIDATION LOG #6: Verify cell population
            logger.info(f"=== VALIDATION LOG #6: Post-Population Cell Verification ===")
            for cell_ref in required_cells:
                new_value = sheet[cell_ref].value
                logger.info(f"Cell {cell_ref} after population: '{new_value}' (type: {type(new_value)})")
            
            # Save the Excel file
            workbook.save(temp_excel.name)
            logger.info(f"Excel file saved to: {temp_excel.name}")
            workbook.close()
            
            # Generate HTML content for PDF display
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>Employee Vacation Request</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        margin: 40px;
                        line-height: 1.6;
                        color: #333;
                    }}
                    .header {{
                        text-align: center;
                        border-bottom: 2px solid #333;
                        padding-bottom: 20px;
                        margin-bottom: 30px;
                    }}
                    .header h1 {{
                        margin: 0;
                        font-size: 24px;
                        color: #2c3e50;
                    }}
                    .section {{
                        margin-bottom: 25px;
                        padding: 15px;
                        border: 1px solid #ddd;
                        border-radius: 5px;
                        background-color: #f9f9f9;
                    }}
                    .section h2 {{
                        margin-top: 0;
                        color: #34495e;
                        font-size: 18px;
                        border-bottom: 1px solid #bdc3c7;
                        padding-bottom: 5px;
                    }}
                    .info-row {{
                        display: flex;
                        justify-content: space-between;
                        margin-bottom: 10px;
                        padding: 5px 0;
                    }}
                    .info-label {{
                        font-weight: bold;
                        color: #2c3e50;
                        min-width: 150px;
                    }}
                    .info-value {{
                        color: #34495e;
                    }}
                    .vacation-period {{
                        background-color: #e8f4f8;
                        padding: 15px;
                        border-left: 4px solid #3498db;
                        margin: 15px 0;
                    }}
                    .return-info {{
                        background-color: #f0f8e8;
                        padding: 15px;
                        border-left: 4px solid #27ae60;
                        margin: 15px 0;
                    }}
                    @media print {{
                        body {{ margin: 20px; }}
                        .section {{ break-inside: avoid; }}
                    }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>Employee Vacation Request</h1>
                    <p>Don Miguel Vacation Manager</p>
                </div>
                
                <div class="section">
                    <h2>Employee Information</h2>
                    <div class="info-row">
                        <span class="info-label">Employee Name:</span>
                        <span class="info-value">{employee_name}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Department:</span>
                        <span class="info-value">{vacation['department']}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Shift:</span>
                        <span class="info-value">{vacation['shift']}</span>
                    </div>
                    {f'''<div class="info-row">
                        <span class="info-label">Work Area:</span>
                        <span class="info-value">{vacation['work_area']}</span>
                    </div>''' if vacation['work_area'] else ''}
                    {f'''<div class="info-row">
                        <span class="info-label">Work Line:</span>
                        <span class="info-value">{vacation['work_line']}</span>
                    </div>''' if vacation['work_line'] else ''}
                </div>
                
                <div class="section">
                    <h2>Vacation Details</h2>
                    <div class="info-row">
                        <span class="info-label">Submitted Date:</span>
                        <span class="info-value">{vacation['created_at'].strftime('%m/%d/%Y') if vacation['created_at'] else 'N/A'}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Total Hours:</span>
                        <span class="info-value">{vacation['total_hours']}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Total Days:</span>
                        <span class="info-value">{total_days}</span>
                    </div>
                    
                    <div class="vacation-period">
                        <h3 style="margin-top: 0; color: #2980b9;">Vacation Period</h3>
                        <div class="info-row">
                            <span class="info-label">From:</span>
                            <span class="info-value">{start_date_str}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">To:</span>
                            <span class="info-value">{end_date_str}</span>
                        </div>
                    </div>
                </div>
                
                <div class="section">
                    <h2>Return Information</h2>
                    <div class="return-info">
                        <div class="info-row">
                            <span class="info-label">Return Day:</span>
                            <span class="info-value">{return_day}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Return Date:</span>
                            <span class="info-value">{return_date.strftime('%m/%d/%Y')}</span>
                        </div>
                    </div>
                </div>
                
                <div class="section">
                    <h2>Supervisor Approval</h2>
                    <div class="info-row">
                        <span class="info-label">Status:</span>
                        <span class="info-value" style="color: #27ae60; font-weight: bold;">APPROVED</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Generated:</span>
                        <span class="info-value">{datetime.now().strftime('%m/%d/%Y %I:%M %p')}</span>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Write HTML content to temp file for potential future use
            with open(temp_pdf.name.replace('.pdf', '.html'), 'w', encoding='utf-8') as html_file:
                html_file.write(html_content)
            
            # Clean up Excel data (restore template)
            workbook = load_workbook(temp_excel.name)
            sheet = workbook['vacation']
            sheet['A10'] = None
            sheet['F10'] = None
            sheet['A12'] = None
            sheet['B11'] = None
            sheet['E12'] = None
            sheet['D18'] = None
            sheet['F19'] = None
            workbook.save(excel_path)  # Save back to original template
            workbook.close()
            
            logger.info("HTML content generated successfully")
            
            # VALIDATION LOG #7: Final Response Analysis
            logger.info(f"=== VALIDATION LOG #7: Final Response Analysis ===")
            import base64
            html_base64 = base64.b64encode(html_content.encode('utf-8')).decode('utf-8')
            logger.info(f"HTML content encoded to base64, length: {len(html_base64)} characters")
            
            filename = f"vacation_request_{employee_name.replace(' ', '_')}_{start_date_str.replace('/', '_')}.html"
            logger.info(f"Generated filename: {filename}")
            logger.info("CRITICAL ISSUE CONFIRMED: System generates HTML instead of PDF from Excel")
            logger.info("DIAGNOSIS COMPLETE: Validation logs added successfully")
            
            return jsonify({
                'message': 'Vacation print document generated successfully',
                'html_data': html_base64,
                'filename': filename
            })
            
        finally:
            # Clean up temporary files
            try:
                os.unlink(temp_excel.name)
                os.unlink(temp_pdf.name)
            except:
                pass
        
    except Exception as e:
        logger.error(f"=== POST /api/vacation-print/{vacation_id} - Error occurred: {str(e)} ===")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

# SMS Notification System Functions

def send_sms_notification(phone_number, message_text, supervisor_id=None, vacation_request_id=None):
    """Send SMS notification using Twilio"""
    try:
        if not twilio_client:
            logger.error("Twilio client not initialized. Cannot send SMS.")
            return False, "Twilio not configured"
        
        if not TWILIO_PHONE_NUMBER:
            logger.error("Twilio phone number not configured")
            return False, "Twilio phone number not configured"
        
        # Format phone number (ensure it starts with +1 for US numbers)
        if not phone_number.startswith('+'):
            if phone_number.startswith('1'):
                phone_number = '+' + phone_number
            else:
                phone_number = '+1' + phone_number.replace('-', '').replace('(', '').replace(')', '').replace(' ', '')
        
        logger.info(f"Sending SMS to {phone_number}: {message_text[:50]}...")
        
        # Send SMS via Twilio
        twilio_message = twilio_client.messages.create(
            body=message_text,
            from_=TWILIO_PHONE_NUMBER,
            to=phone_number
        )
        
        logger.info(f"SMS sent successfully. Twilio SID: {twilio_message.sid}")
        
        # Log to notification history
        if supervisor_id and vacation_request_id:
            log_notification_history(
                supervisor_id=supervisor_id,
                vacation_request_id=vacation_request_id,
                phone_number=phone_number,
                message_content=message_text,
                twilio_sid=twilio_message.sid,
                twilio_status=twilio_message.status,
                status='sent'
            )
        
        return True, twilio_message.sid
        
    except Exception as e:
        logger.error(f"Failed to send SMS to {phone_number}: {str(e)}")
        
        # Log failed notification
        if supervisor_id and vacation_request_id:
            log_notification_history(
                supervisor_id=supervisor_id,
                vacation_request_id=vacation_request_id,
                phone_number=phone_number,
                message_content=message_text,
                twilio_error_message=str(e),
                status='failed'
            )
        
        return False, str(e)

def log_notification_history(supervisor_id, vacation_request_id, phone_number, message_content,
                           twilio_sid=None, twilio_status=None, twilio_error_code=None,
                           twilio_error_message=None, status='pending'):
    """Log notification to history table"""
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed for notification logging")
            return
        
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO notification_history
            (supervisor_id, vacation_request_id, phone_number, message_content,
             twilio_sid, twilio_status, twilio_error_code, twilio_error_message, status, sent_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (supervisor_id, vacation_request_id, phone_number, message_content,
              twilio_sid, twilio_status, twilio_error_code, twilio_error_message,
              status, datetime.now() if status in ['sent', 'failed'] else None))
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"Failed to log notification history: {str(e)}")

def check_upcoming_vacations():
    """Check for upcoming vacations and send notifications"""
    try:
        logger.info("Checking for upcoming vacations requiring notifications...")
        
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed for vacation check")
            return
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get all notification preferences with upcoming vacations
        query = """
            SELECT DISTINCT
                np.supervisor_id,
                np.sms_enabled,
                np.days_before_vacation,
                np.notifications_per_day,
                np.notification_times,
                np.phone_number_override,
                np.timezone,
                s.phone_number as supervisor_phone,
                s.first_name as supervisor_first_name,
                s.last_name as supervisor_last_name,
                vr.id as vacation_request_id,
                vr.start_date,
                vr.end_date,
                vr.return_date,
                vr.total_hours,
                e.first_name as employee_first_name,
                e.last_name as employee_last_name,
                e.department,
                e.shift
            FROM notification_preferences np
            JOIN supervisors s ON np.supervisor_id = s.id
            JOIN vacation_requests vr ON vr.supervisor_id = s.id
            JOIN employees e ON vr.employee_id = e.id
            WHERE np.sms_enabled = true
            AND vr.status = 'Approved'
            AND vr.start_date > CURRENT_DATE
            AND vr.start_date <= CURRENT_DATE + INTERVAL '%s days'
        """
        
        # Check for vacations within the next 30 days (we'll filter by individual preferences)
        cursor.execute(query, (30,))
        upcoming_vacations = cursor.fetchall()
        
        logger.info(f"Found {len(upcoming_vacations)} potential vacation notifications to process")
        
        for vacation in upcoming_vacations:
            try:
                # Calculate days until vacation
                start_date = vacation['start_date']
                if isinstance(start_date, str):
                    start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                
                days_until_vacation = (start_date - datetime.now().date()).days
                
                # Check if this vacation falls within the notification window
                if days_until_vacation <= vacation['days_before_vacation'] and days_until_vacation >= 0:
                    
                    # Check if we've already sent notifications today for this vacation
                    cursor.execute("""
                        SELECT COUNT(*) as count FROM notification_history
                        WHERE supervisor_id = %s
                        AND vacation_request_id = %s
                        AND DATE(sent_at) = CURRENT_DATE
                        AND status = 'sent'
                    """, (vacation['supervisor_id'], vacation['vacation_request_id']))
                    
                    notifications_sent_today = cursor.fetchone()['count']
                    
                    if notifications_sent_today < vacation['notifications_per_day']:
                        # Send notification
                        phone_number = vacation['phone_number_override'] or vacation['supervisor_phone']
                        
                        if phone_number:
                            message = create_vacation_notification_message(vacation, days_until_vacation)
                            
                            success, result = send_sms_notification(
                                phone_number=phone_number,
                                message=message,
                                supervisor_id=vacation['supervisor_id'],
                                vacation_request_id=vacation['vacation_request_id']
                            )
                            
                            if success:
                                logger.info(f"Sent vacation notification for {vacation['employee_first_name']} {vacation['employee_last_name']} to supervisor {vacation['supervisor_first_name']} {vacation['supervisor_last_name']}")
                            else:
                                logger.error(f"Failed to send notification: {result}")
                        else:
                            logger.warning(f"No phone number available for supervisor {vacation['supervisor_first_name']} {vacation['supervisor_last_name']}")
            
            except Exception as e:
                logger.error(f"Error processing vacation notification: {str(e)}")
                continue
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error in check_upcoming_vacations: {str(e)}")

def create_vacation_notification_message(vacation, days_until):
    """Create SMS message for vacation notification"""
    employee_name = f"{vacation['employee_first_name']} {vacation['employee_last_name']}"
    start_date = vacation['start_date']
    end_date = vacation['end_date']
    
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    start_date_str = start_date.strftime('%m/%d/%Y')
    end_date_str = end_date.strftime('%m/%d/%Y')
    
    if days_until == 0:
        message = f"🏖️ VACATION ALERT: {employee_name} starts vacation TODAY ({start_date_str} to {end_date_str}). Total: {vacation['total_hours']} hours. - Don Miguel Vacation Manager"
    elif days_until == 1:
        message = f"🏖️ VACATION REMINDER: {employee_name} starts vacation TOMORROW ({start_date_str} to {end_date_str}). Total: {vacation['total_hours']} hours. - Don Miguel Vacation Manager"
    else:
        message = f"🏖️ VACATION REMINDER: {employee_name} starts vacation in {days_until} days ({start_date_str} to {end_date_str}). Total: {vacation['total_hours']} hours. - Don Miguel Vacation Manager"
    
    return message

def schedule_notification_jobs():
    """Schedule notification jobs based on supervisor preferences"""
    try:
        logger.info("Scheduling notification jobs...")
        
        # Clear existing jobs
        scheduler.remove_all_jobs()
        
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed for job scheduling")
            return
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get all unique notification times from preferences
        cursor.execute("""
            SELECT DISTINCT unnest(notification_times) as notification_time
            FROM notification_preferences
            WHERE sms_enabled = true
        """)
        
        notification_times = cursor.fetchall()
        
        for time_row in notification_times:
            notification_time = time_row['notification_time']
            hour = notification_time.hour
            minute = notification_time.minute
            
            # Schedule job for this time
            scheduler.add_job(
                func=check_upcoming_vacations,
                trigger=CronTrigger(hour=hour, minute=minute),
                id=f'vacation_check_{hour:02d}_{minute:02d}',
                name=f'Vacation Check at {hour:02d}:{minute:02d}',
                replace_existing=True
            )
            
            logger.info(f"Scheduled vacation check job for {hour:02d}:{minute:02d}")
        
        cursor.close()
        conn.close()
        
        # If no specific times are set, schedule a default check at 9 AM
        if not notification_times:
            scheduler.add_job(
                func=check_upcoming_vacations,
                trigger=CronTrigger(hour=9, minute=0),
                id='vacation_check_default',
                name='Default Vacation Check at 09:00',
                replace_existing=True
            )
            logger.info("Scheduled default vacation check job for 09:00")
        
    except Exception as e:
        logger.error(f"Error scheduling notification jobs: {str(e)}")

# API Endpoints for Notification Preferences

@app.route('/api/notification-preferences', methods=['GET'])
@verify_firebase_token
def get_notification_preferences():
    """Get supervisor's notification preferences"""
    try:
        firebase_uid = request.user['uid']
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get supervisor ID
        cursor.execute("SELECT id FROM supervisors WHERE firebase_uid = %s", (firebase_uid,))
        supervisor = cursor.fetchone()
        
        if not supervisor:
            return jsonify({'error': 'Supervisor not found'}), 404
        
        # Get notification preferences
        cursor.execute("""
            SELECT * FROM notification_preferences
            WHERE supervisor_id = %s
        """, (supervisor['id'],))
        
        preferences = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if preferences:
            # Convert time array to strings for JSON serialization
            prefs_dict = dict(preferences)
            if prefs_dict['notification_times']:
                # Convert time objects to HH:MM format strings
                prefs_dict['notification_times'] = [t.strftime('%H:%M') if hasattr(t, 'strftime') else str(t) for t in prefs_dict['notification_times']]
            return jsonify(prefs_dict)
        else:
            # Return default preferences
            return jsonify({
                'supervisor_id': supervisor['id'],
                'sms_enabled': True,
                'days_before_vacation': 2,
                'notifications_per_day': 1,
                'notification_times': ['09:00'],
                'phone_number_override': None,
                'timezone': 'America/Chicago'
            })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/notification-preferences', methods=['PUT'])
@verify_firebase_token
def update_notification_preferences():
    """Update supervisor's notification preferences"""
    try:
        firebase_uid = request.user['uid']
        data = request.get_json()
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get supervisor ID
        cursor.execute("SELECT id FROM supervisors WHERE firebase_uid = %s", (firebase_uid,))
        supervisor = cursor.fetchone()
        
        if not supervisor:
            return jsonify({'error': 'Supervisor not found'}), 404
        
        # Validate input data
        sms_enabled = data.get('sms_enabled', True)
        days_before_vacation = data.get('days_before_vacation', 2)
        notifications_per_day = data.get('notifications_per_day', 1)
        notification_times = data.get('notification_times', ['09:00:00'])
        phone_number_override = data.get('phone_number_override')
        timezone = data.get('timezone', 'America/Chicago')
        
        # Validate ranges
        if not (0 <= days_before_vacation <= 30):
            return jsonify({'error': 'Days before vacation must be between 0 and 30'}), 400
        
        if not (1 <= notifications_per_day <= 10):
            return jsonify({'error': 'Notifications per day must be between 1 and 10'}), 400
        
        if not notification_times or len(notification_times) == 0:
            notification_times = ['09:00:00']
        
        # Convert time strings to time objects for database storage
        time_objects = []
        for time_str in notification_times:
            try:
                # Parse time string (HH:MM format)
                from datetime import datetime
                time_obj = datetime.strptime(time_str, '%H:%M').time()
                time_objects.append(time_obj)
            except ValueError:
                # If parsing fails, try HH:MM:SS format
                try:
                    time_obj = datetime.strptime(time_str, '%H:%M:%S').time()
                    time_objects.append(time_obj)
                except ValueError:
                    logger.error(f"Invalid time format: {time_str}")
                    return jsonify({'error': f'Invalid time format: {time_str}'}), 400

        # Update or insert preferences
        cursor.execute("""
            INSERT INTO notification_preferences
            (supervisor_id, sms_enabled, days_before_vacation, notifications_per_day,
             notification_times, phone_number_override, timezone)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (supervisor_id)
            DO UPDATE SET
                sms_enabled = EXCLUDED.sms_enabled,
                days_before_vacation = EXCLUDED.days_before_vacation,
                notifications_per_day = EXCLUDED.notifications_per_day,
                notification_times = EXCLUDED.notification_times,
                phone_number_override = EXCLUDED.phone_number_override,
                timezone = EXCLUDED.timezone,
                updated_at = CURRENT_TIMESTAMP
            RETURNING *
        """, (supervisor['id'], sms_enabled, days_before_vacation, notifications_per_day,
              time_objects, phone_number_override, timezone))
        
        updated_preferences = cursor.fetchone()
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Reschedule notification jobs with new preferences
        schedule_notification_jobs()
        
        # Convert time array to strings for JSON serialization
        prefs_dict = dict(updated_preferences)
        if prefs_dict['notification_times']:
            # Convert time objects to HH:MM format strings
            prefs_dict['notification_times'] = [t.strftime('%H:%M') if hasattr(t, 'strftime') else str(t) for t in prefs_dict['notification_times']]
        
        return jsonify(prefs_dict)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/notification-history', methods=['GET'])
@verify_firebase_token
def get_notification_history():
    """Get supervisor's notification history"""
    try:
        firebase_uid = request.user['uid']
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get supervisor ID
        cursor.execute("SELECT id FROM supervisors WHERE firebase_uid = %s", (firebase_uid,))
        supervisor = cursor.fetchone()
        
        if not supervisor:
            return jsonify({'error': 'Supervisor not found'}), 404
        
        # Get notification history with vacation details
        cursor.execute("""
            SELECT nh.*,
                   e.first_name || ' ' || e.last_name as employee_name,
                   vr.start_date, vr.end_date
            FROM notification_history nh
            JOIN vacation_requests vr ON nh.vacation_request_id = vr.id
            JOIN employees e ON vr.employee_id = e.id
            WHERE nh.supervisor_id = %s
            ORDER BY nh.created_at DESC
            LIMIT 50
        """, (supervisor['id'],))
        
        history = [dict(row) for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        return jsonify(history)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/test-sms', methods=['POST'])
@verify_firebase_token
def test_sms_notification():
    """Test SMS notification functionality"""
    try:
        firebase_uid = request.user['uid']
        
        # Handle both JSON and form data, or no data at all
        data = {}
        try:
            if request.is_json and request.get_json():
                data = request.get_json()
        except Exception:
            # If JSON parsing fails, continue with empty data
            pass
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get supervisor details
        cursor.execute("SELECT * FROM supervisors WHERE firebase_uid = %s", (firebase_uid,))
        supervisor = cursor.fetchone()
        
        if not supervisor:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Supervisor not found'}), 404
        
        cursor.close()
        conn.close()
        
        # Get phone number from request or supervisor record
        phone_number = data.get('phone_number') if data else None
        if not phone_number:
            phone_number = supervisor['phone_number']
        
        if not phone_number:
            return jsonify({'error': 'No phone number available. Please add a phone number to your profile or notification preferences.'}), 400
        
        # Send test message
        test_message = f"🧪 Test SMS from Don Miguel Vacation Manager for {supervisor['first_name']} {supervisor['last_name']}. SMS notifications are working correctly!"
        
        success, result = send_sms_notification(phone_number, test_message)
        
        if success:
            return jsonify({
                'message': 'Test SMS sent successfully',
                'twilio_sid': result,
                'phone_number': phone_number
            })
        else:
            return jsonify({'error': f'Failed to send test SMS: {result}'}), 500
        
    except Exception as e:
        logger.error(f"Error in test SMS: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Initialize notification jobs on startup
try:
    schedule_notification_jobs()
    logger.info("Notification system initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize notification system: {str(e)}")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5006)
