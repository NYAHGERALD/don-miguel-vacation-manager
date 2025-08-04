# Don Miguel Vacation Manager - Deployment Checklist

## Pre-Deployment Checklist

### 1. Environment Setup
- [ ] Create `.env` file from `.env.example`
- [ ] Configure all required environment variables:
  - [ ] `SECRET_KEY` - Generate secure random key
  - [ ] `DATABASE_URL` - PostgreSQL connection string
  - [ ] `TWILIO_ACCOUNT_SID` - From Twilio Console
  - [ ] `TWILIO_AUTH_TOKEN` - From Twilio Console  
  - [ ] `TWILIO_PHONE_NUMBER` - Your Twilio phone number
- [ ] Place `firebase-service-account.json` in project root

### 2. Database Setup
- [ ] Create PostgreSQL database
- [ ] Run database schema: `psql -U postgres -d vacation_manager -f database/schema.sql`
- [ ] Grant permissions: `psql -U postgres -d vacation_manager -f database/grant_permissions.sql`
- [ ] Create notification tables: `psql -U postgres -d vacation_manager -f database/create_notification_preferences.sql`
- [ ] Set up admin accounts: `python setup_admin_table.py`

### 3. Dependencies
- [ ] Install Python dependencies: `pip install -r requirements.txt`
- [ ] Install Node.js dependencies: `npm install`
- [ ] Build Tailwind CSS: `npm run build-css`

### 4. Firebase Configuration
- [ ] Create Firebase project
- [ ] Enable Authentication with Email/Password
- [ ] Download service account key as `firebase-service-account.json`
- [ ] Configure Firebase web app settings

### 5. Twilio SMS Setup
- [ ] Create Twilio account
- [ ] Purchase phone number
- [ ] Configure webhook URLs (if needed)
- [ ] Test SMS functionality

### 6. Security Configuration
- [ ] Generate secure `SECRET_KEY`
- [ ] Configure CORS settings for production domain
- [ ] Set up HTTPS/SSL certificates
- [ ] Configure firewall rules

### 7. Production Environment
- [ ] Set `FLASK_ENV=production`
- [ ] Configure logging levels
- [ ] Set up error monitoring
- [ ] Configure backup procedures

## Deployment Commands

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt
npm install

# Set up database
psql -U postgres -d vacation_manager -f database/schema.sql
psql -U postgres -d vacation_manager -f database/grant_permissions.sql
psql -U postgres -d vacation_manager -f database/create_notification_preferences.sql

# Build CSS
npm run build-css

# Run application
python backend/app.py
```

### Production Deployment
```bash
# Clone repository
git clone <repository-url>
cd don-miguel-vacation-manager

# Set up virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
npm install

# Configure environment
cp .env.example .env
# Edit .env with production values

# Set up database
# Run database setup commands

# Build assets
npm run build-css

# Start application with production server
gunicorn --bind 0.0.0.0:5000 backend.app:app
```

## File Structure for Deployment

```
don-miguel-vacation-manager/
├── backend/
│   └── app.py                 # Main Flask application
├── database/
│   ├── schema.sql            # Database schema
│   ├── grant_permissions.sql # Database permissions
│   └── create_notification_preferences.sql
├── static/
│   ├── css/
│   ├── js/
│   └── assets/
├── templates/
│   ├── *.html               # All HTML templates
├── docs/
│   └── *.md                 # Documentation
├── requirements.txt         # Python dependencies
├── package.json            # Node.js dependencies
├── .env.example           # Environment template
├── .gitignore            # Git ignore rules
├── README.md             # Project documentation
├── DEPLOYMENT.md         # Deployment guide
└── DEPLOYMENT_CHECKLIST.md # This checklist
```

## Post-Deployment Verification

### 1. Application Health
- [ ] Application starts without errors
- [ ] All routes respond correctly
- [ ] Database connections work
- [ ] Static files load properly

### 2. Authentication
- [ ] User registration works
- [ ] User login works
- [ ] Firebase authentication functions
- [ ] Session management works

### 3. Core Features
- [ ] Employee management
- [ ] Vacation request creation
- [ ] Vacation request approval/denial
- [ ] Dashboard statistics display

### 4. SMS Notifications
- [ ] Test SMS sends successfully
- [ ] Notification preferences save
- [ ] Scheduled notifications work
- [ ] Notification history tracks properly

### 5. Admin Features
- [ ] Admin login works
- [ ] Admin dashboard loads
- [ ] User management functions
- [ ] System statistics display

## Troubleshooting

### Common Issues
1. **Database Connection Errors**
   - Check DATABASE_URL format
   - Verify PostgreSQL is running
   - Check user permissions

2. **Firebase Authentication Issues**
   - Verify service account file exists
   - Check Firebase project configuration
   - Validate API keys

3. **SMS Not Working**
   - Verify Twilio credentials
   - Check phone number format
   - Test Twilio account balance

4. **Static Files Not Loading**
   - Run `npm run build-css`
   - Check file permissions
   - Verify static file paths

### Support
- Check application logs for detailed error messages
- Review database logs for connection issues
- Monitor Twilio logs for SMS delivery status