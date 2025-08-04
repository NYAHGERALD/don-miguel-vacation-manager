# Don Miguel Vacation Manager - Deployment Guide

## Overview
This guide provides step-by-step instructions for deploying the Don Miguel Vacation Manager application, which includes employee vacation management, SMS notifications, and administrative features.

## System Requirements

### Production Environment
- **Python**: 3.8 or higher
- **PostgreSQL**: 12 or higher
- **Node.js**: 14 or higher (for CSS building)
- **Operating System**: Linux (Ubuntu 20.04+ recommended), macOS, or Windows Server

### External Services
- **Firebase**: For user authentication
- **Twilio**: For SMS notifications
- **PostgreSQL Database**: Local or cloud-hosted

## Quick Start

### 1. Clone and Setup
```bash
git clone <your-repository-url>
cd don-miguel-vacation-manager

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
npm install
```

### 2. Environment Configuration
```bash
# Copy environment template
cp .env.example .env

# Edit .env with your configuration
nano .env
```

Required environment variables:
```env
SECRET_KEY=your-secret-key-here
DATABASE_URL=postgresql://username:password@localhost:5432/vacation_manager
TWILIO_ACCOUNT_SID=your-twilio-account-sid
TWILIO_AUTH_TOKEN=your-twilio-auth-token
TWILIO_PHONE_NUMBER=+1234567890
```

### 3. Database Setup
```bash
# Create database
createdb vacation_manager

# Run schema
psql -U postgres -d vacation_manager -f database/schema.sql
psql -U postgres -d vacation_manager -f database/grant_permissions.sql
psql -U postgres -d vacation_manager -f database/create_notification_preferences.sql

# Set up admin accounts
python setup_admin_table.py
```

### 4. Firebase Configuration
1. Create Firebase project at https://console.firebase.google.com
2. Enable Authentication with Email/Password provider
3. Download service account key as `firebase-service-account.json`
4. Place file in project root directory

### 5. Build and Run
```bash
# Build CSS assets
npm run build-css

# Run application
python backend/app.py
```

## Detailed Configuration

### Database Configuration

#### PostgreSQL Setup
```sql
-- Create database and user
CREATE DATABASE vacation_manager;
CREATE USER vacation_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE vacation_manager TO vacation_user;

-- Connect to database and grant schema permissions
\c vacation_manager
GRANT ALL ON SCHEMA public TO vacation_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO vacation_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO vacation_user;
```

#### Database Schema
The application uses the following main tables:
- `employees` - Employee information and authentication
- `vacation_requests` - Vacation request records
- `notification_preferences` - SMS notification settings
- `notification_history` - SMS delivery tracking

### Firebase Authentication Setup

1. **Create Firebase Project**
   - Go to https://console.firebase.google.com
   - Click "Create a project"
   - Follow setup wizard

2. **Enable Authentication**
   - Navigate to Authentication > Sign-in method
   - Enable "Email/Password" provider
   - Configure authorized domains

3. **Generate Service Account**
   - Go to Project Settings > Service accounts
   - Click "Generate new private key"
   - Save as `firebase-service-account.json` in project root

### Twilio SMS Configuration

1. **Create Twilio Account**
   - Sign up at https://www.twilio.com
   - Verify your account

2. **Get Credentials**
   - Find Account SID and Auth Token in Console Dashboard
   - Purchase a phone number for sending SMS

3. **Configure Environment**
   ```env
   TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   TWILIO_AUTH_TOKEN=your_auth_token_here
   TWILIO_PHONE_NUMBER=+1234567890
   ```

## Production Deployment

### Using Gunicorn (Recommended)
```bash
# Install Gunicorn
pip install gunicorn

# Run with Gunicorn
gunicorn --bind 0.0.0.0:5000 --workers 4 backend.app:app
```

### Using Docker
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN npm install && npm run build-css

EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "backend.app:app"]
```

### Nginx Configuration
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /static {
        alias /path/to/your/app/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

## Features Overview

### Core Features
- **Employee Management**: Registration, authentication, profile management
- **Vacation Requests**: Create, submit, approve/deny vacation requests
- **Dashboard**: Overview of vacation statistics and pending requests
- **Admin Panel**: User management and system administration

### SMS Notification System
- **Automated Reminders**: Configurable notifications for upcoming vacations
- **Supervisor Preferences**: Individual notification settings per supervisor
- **Notification History**: Complete tracking of sent messages
- **Twilio Integration**: Reliable SMS delivery with status tracking

### Security Features
- **Firebase Authentication**: Secure user authentication and session management
- **Role-Based Access**: Different permissions for employees, supervisors, and admins
- **Data Validation**: Input sanitization and validation throughout the application

## Monitoring and Maintenance

### Application Logs
```bash
# View application logs
tail -f logs/app.log

# Monitor error logs
tail -f logs/error.log
```

### Database Maintenance
```sql
-- Check notification history size
SELECT COUNT(*) FROM notification_history;

-- Clean old notification history (older than 90 days)
DELETE FROM notification_history 
WHERE created_at < NOW() - INTERVAL '90 days';

-- Vacuum database
VACUUM ANALYZE;
```

### SMS Monitoring
- Monitor Twilio console for delivery status
- Check notification_history table for failed messages
- Review SMS usage and billing

## Troubleshooting

### Common Issues

1. **Database Connection Errors**
   ```
   Error: could not connect to server
   ```
   - Check PostgreSQL is running
   - Verify DATABASE_URL format
   - Check firewall settings

2. **Firebase Authentication Issues**
   ```
   Error: Firebase Admin SDK not initialized
   ```
   - Verify `firebase-service-account.json` exists
   - Check file permissions
   - Validate Firebase project configuration

3. **SMS Not Sending**
   ```
   Error: Unable to create record
   ```
   - Verify Twilio credentials
   - Check account balance
   - Validate phone number format

4. **Static Files Not Loading**
   - Run `npm run build-css`
   - Check file permissions
   - Verify static file paths in templates

### Performance Optimization

1. **Database Indexing**
   ```sql
   CREATE INDEX idx_vacation_requests_employee_id ON vacation_requests(employee_id);
   CREATE INDEX idx_notification_history_created_at ON notification_history(created_at);
   ```

2. **Caching**
   - Implement Redis for session storage
   - Cache frequently accessed data
   - Use CDN for static assets

3. **Background Jobs**
   - Monitor APScheduler job execution
   - Optimize notification checking frequency
   - Implement job failure handling

## Support and Documentation

### Additional Resources
- [Flask Documentation](https://flask.palletsprojects.com/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Firebase Admin SDK](https://firebase.google.com/docs/admin/setup)
- [Twilio SMS API](https://www.twilio.com/docs/sms)

### Getting Help
1. Check application logs for detailed error messages
2. Review database logs for connection issues
3. Monitor Twilio console for SMS delivery status
4. Consult the troubleshooting section above

For additional support, refer to the project documentation or contact the development team.