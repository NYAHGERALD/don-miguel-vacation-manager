# Don Miguel Vacation Manager

A comprehensive web-based vacation management system with SMS notifications, built with Flask, PostgreSQL, Firebase Authentication, and Twilio SMS integration.

## Features

### 🏢 Employee Management
- User registration and authentication via Firebase
- Role-based access control (Employee, Supervisor, Admin)
- Profile management with personal information
- Secure session management

### 📅 Vacation Request System
- Create and submit vacation requests
- Supervisor approval/denial workflow
- Request status tracking and history
- Calendar integration and conflict detection

### 📊 Dashboard & Analytics
- Real-time vacation statistics
- Pending requests overview
- Employee vacation balance tracking
- Administrative reporting tools

### 📱 SMS Notification System
- Automated vacation reminders via Twilio
- Configurable notification preferences per supervisor
- Customizable notification timing and frequency
- Complete notification history tracking
- Test SMS functionality

### 👨‍💼 Administrative Features
- User management and role assignment
- System configuration and settings
- Vacation policy management
- Comprehensive audit logging

## Technology Stack

- **Backend**: Flask (Python)
- **Database**: PostgreSQL
- **Authentication**: Firebase Admin SDK
- **SMS**: Twilio API
- **Frontend**: HTML5, Tailwind CSS, JavaScript
- **Scheduling**: APScheduler
- **Deployment**: Gunicorn, Nginx

## Quick Start

### Prerequisites
- Python 3.8+
- PostgreSQL 12+
- Node.js 14+ (for CSS building)
- Firebase project
- Twilio account

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd don-miguel-vacation-manager
   ```

2. **Set up virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   npm install
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Set up database**
   ```bash
   createdb vacation_manager
   psql -U postgres -d vacation_manager -f database/schema.sql
   psql -U postgres -d vacation_manager -f database/grant_permissions.sql
   psql -U postgres -d vacation_manager -f database/create_notification_preferences.sql
   ```

6. **Configure Firebase**
   - Place `firebase-service-account.json` in project root
   - Configure Firebase Authentication

7. **Build and run**
   ```bash
   npm run build-css
   python backend/app.py
   ```

Visit `http://localhost:5000` to access the application.

## Configuration

### Environment Variables

Create a `.env` file with the following variables:

```env
# Application
SECRET_KEY=your-secret-key-here
FLASK_ENV=development

# Database
DATABASE_URL=postgresql://username:password@localhost:5432/vacation_manager

# Twilio SMS
TWILIO_ACCOUNT_SID=your-twilio-account-sid
TWILIO_AUTH_TOKEN=your-twilio-auth-token
TWILIO_PHONE_NUMBER=+1234567890
```

### Firebase Setup

1. Create a Firebase project
2. Enable Email/Password authentication
3. Download service account key as `firebase-service-account.json`
4. Place in project root directory

### Twilio Setup

1. Create Twilio account
2. Purchase a phone number
3. Get Account SID and Auth Token from console
4. Configure environment variables

## Project Structure

```
don-miguel-vacation-manager/
├── backend/
│   └── app.py                 # Main Flask application
├── database/
│   ├── schema.sql            # Database schema
│   ├── grant_permissions.sql # Database permissions
│   └── create_notification_preferences.sql
├── static/
│   ├── css/                  # Compiled CSS files
│   ├── js/                   # JavaScript files
│   └── assets/               # Images and other assets
├── templates/
│   ├── index.html           # Landing page
│   ├── dashboard.html       # Main dashboard
│   ├── profile.html         # User profile with SMS settings
│   ├── admin.html           # Admin panel
│   └── *.html               # Other templates
├── docs/
│   └── *.md                 # Documentation files
├── requirements.txt         # Python dependencies
├── package.json            # Node.js dependencies
├── tailwind.config.js      # Tailwind CSS configuration
├── .env.example           # Environment template
├── .gitignore            # Git ignore rules
├── README.md             # This file
├── DEPLOYMENT.md         # Deployment guide
└── DEPLOYMENT_CHECKLIST.md # Deployment checklist
```

## API Endpoints

### Authentication
- `POST /api/login` - User login
- `POST /api/register` - User registration
- `POST /api/logout` - User logout

### Vacation Management
- `GET /api/vacation-requests` - Get user's vacation requests
- `POST /api/vacation-requests` - Create new vacation request
- `PUT /api/vacation-requests/<id>` - Update vacation request status

### SMS Notifications
- `GET /api/notification-preferences` - Get notification settings
- `PUT /api/notification-preferences` - Update notification settings
- `GET /api/notification-history` - Get notification history
- `POST /api/test-sms` - Send test SMS

### Administration
- `GET /api/admin/users` - Get all users (admin only)
- `PUT /api/admin/users/<id>` - Update user role (admin only)

## SMS Notification System

### Features
- **Automated Reminders**: Configurable notifications for upcoming vacations
- **Individual Preferences**: Each supervisor can configure their own settings
- **Flexible Scheduling**: Choose notification days, times, and frequency
- **Phone Number Override**: Use different phone numbers for notifications
- **Complete History**: Track all sent messages with Twilio status

### Configuration Options
- Enable/disable notifications
- Days before vacation to notify (1-30 days)
- Notification times (multiple times per day)
- Phone number override
- Notification frequency settings

### Usage
1. Navigate to Profile → SMS Notifications tab
2. Configure your notification preferences
3. Test SMS functionality
4. View notification history

## Development

### Running in Development Mode
```bash
export FLASK_ENV=development
python backend/app.py
```

### Building CSS
```bash
npm run build-css
```

### Database Migrations
```bash
# Run new migration
psql -U postgres -d vacation_manager -f database/new_migration.sql
```

### Testing SMS
Use the test SMS endpoint or the profile page test button to verify SMS functionality.

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for comprehensive deployment instructions.

### Quick Production Deployment
```bash
# Install production dependencies
pip install gunicorn

# Set production environment
export FLASK_ENV=production

# Run with Gunicorn
gunicorn --bind 0.0.0.0:5000 --workers 4 backend.app:app
```

## Security

### Authentication
- Firebase Admin SDK for secure authentication
- Session-based user management
- Role-based access control

### Data Protection
- Input validation and sanitization
- SQL injection prevention
- CSRF protection
- Secure password handling

### SMS Security
- Twilio secure API integration
- Phone number validation
- Rate limiting for SMS sending

## Monitoring

### Application Logs
Monitor application performance and errors through structured logging.

### SMS Monitoring
- Track SMS delivery status via Twilio console
- Monitor notification history in the application
- Review SMS usage and billing

### Database Monitoring
- Monitor connection pool usage
- Track query performance
- Regular database maintenance

## Troubleshooting

### Common Issues

1. **Database Connection Errors**
   - Verify PostgreSQL is running
   - Check DATABASE_URL format
   - Ensure user permissions are correct

2. **Firebase Authentication Issues**
   - Verify service account file exists
   - Check Firebase project configuration
   - Validate API keys and permissions

3. **SMS Not Working**
   - Verify Twilio credentials
   - Check account balance and phone number
   - Review notification preferences

4. **Static Files Not Loading**
   - Run `npm run build-css`
   - Check file permissions
   - Verify static file paths

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
1. Check the troubleshooting section
2. Review the deployment guide
3. Check application logs for detailed error messages
4. Contact the development team

## Changelog

### Version 2.0.0
- Added comprehensive SMS notification system
- Implemented Twilio integration
- Added notification preferences and history
- Enhanced supervisor dashboard
- Improved security and error handling

### Version 1.0.0
- Initial release
- Basic vacation management system
- Firebase authentication
- Admin panel functionality