# Don Miguel Vacation Manager

A professional-grade vacation management web application designed for workplace supervisors to manage employee vacation requests efficiently and securely.

## 🌟 Features

### Core Functionality
- **Secure Authentication**: Firebase Authentication with email/password and Google OAuth
- **Supervisor Dashboard**: Comprehensive metrics and analytics
- **Employee Management**: Add, view, and manage employees by department
- **Vacation Request System**: Create, approve, deny, and track vacation requests
- **Approval Workflow**: Streamlined approval process with business rule validation
- **Data Filtering & Sorting**: Advanced filtering by status, dates, employees, and more
- **Visual Analytics**: Charts and graphs for vacation trends and statistics
- **Notifications**: Email alerts for approvals, denials, and reminders

### Advanced Features
- **Access Control**: Role-based permissions scoped by department
- **Conflict Detection**: Automatic detection of overlapping vacation requests
- **Capacity Management**: Configurable limits for concurrent vacations per work area
- **Audit Logging**: Complete audit trail for compliance
- **Responsive Design**: Mobile-friendly interface using Tailwind CSS
- **Real-time Updates**: Dynamic dashboard updates

## 🏗️ Architecture

### Technology Stack
- **Frontend**: HTML5, Tailwind CSS v4, JavaScript ES6+, Chart.js
- **Backend**: Python Flask with RESTful API design
- **Database**: PostgreSQL with advanced schema design
- **Authentication**: Firebase Authentication
- **Styling**: Tailwind CSS v4 with custom Don Miguel Foods branding
- **Charts**: Chart.js for data visualization

### Project Structure
```
vacation-manager-app/
├── backend/
│   └── app.py                 # Flask application with API endpoints
├── database/
│   └── schema.sql            # PostgreSQL database schema
├── templates/                # HTML templates
│   ├── index.html           # Landing page
│   ├── login.html           # Login page
│   ├── register.html        # Registration page
│   ├── dashboard.html       # Supervisor dashboard
│   ├── employees.html       # Employee management
│   └── vacation_requests.html # Vacation request management
├── static/
│   ├── css/
│   │   ├── input.css        # Tailwind input file
│   │   └── output.css       # Compiled Tailwind CSS
│   └── js/
│       ├── auth.js          # Authentication logic
│       ├── dashboard.js     # Dashboard functionality
│       ├── employees.js     # Employee management
│       └── vacation.js      # Vacation request handling
├── firebase-config.js       # Firebase configuration
├── tailwind.config.js       # Tailwind CSS configuration
├── package.json            # Node.js dependencies
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variables template
└── README.md              # This file
```

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Node.js 18+
- PostgreSQL 12+
- Firebase project with Authentication enabled

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/don-miguel-vacation-manager.git
   cd don-miguel-vacation-manager
   ```

2. **Set up Python environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Install Node.js dependencies**
   ```bash
   npm install
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your actual configuration values
   ```

5. **Set up PostgreSQL database**
   ```bash
   createdb vacation_manager
   psql -d vacation_manager -f database/schema.sql
   ```

6. **Configure Firebase**
   - Create a Firebase project at https://console.firebase.google.com
   - Enable Authentication with Email/Password and Google providers
   - Download service account key and update firebase-config.js
   - Update .env with Firebase configuration

7. **Build CSS**
   ```bash
   npm run build-css
   ```

8. **Start the application**
   ```bash
   npm run dev
   ```

The application will be available at `http://localhost:5000`

## 📊 Database Schema

### Core Tables
- **supervisors**: Supervisor profiles linked to Firebase Authentication
- **employees**: Employee information managed by supervisors
- **vacation_requests**: Vacation requests with approval workflow
- **area_limits**: Configurable limits for concurrent vacations
- **audit_log**: Complete audit trail for compliance

### Key Features
- Foreign key relationships ensuring data integrity
- Check constraints for data validation
- Indexes for optimal query performance
- Triggers for automatic timestamp updates
- Views for complex queries and reporting

## 🔐 Security Features

- **Firebase Authentication**: Secure user authentication and session management
- **JWT Token Validation**: Server-side token verification
- **Role-Based Access Control**: Department-scoped data access
- **SQL Injection Prevention**: Parameterized queries
- **CORS Protection**: Configured cross-origin resource sharing
- **Environment Variables**: Sensitive data stored securely

## 🎨 UI/UX Features

- **Responsive Design**: Mobile-first approach with Tailwind CSS
- **Accessibility**: ARIA roles and semantic HTML
- **Custom Branding**: Don Miguel Foods color scheme and typography
- **Interactive Components**: Modals, dropdowns, and form validation
- **Loading States**: User feedback during async operations
- **Error Handling**: Graceful error messages and recovery

## 📈 Analytics & Reporting

### Dashboard Metrics
- Total employees managed
- Vacation request breakdown by status
- Upcoming vacations timeline
- Monthly vacation statistics
- Department and shift analytics

### Visualizations
- Bar charts for monthly request trends
- Pie charts for status distribution
- Gantt charts for vacation timelines
- Heat maps for peak vacation periods

## 🔧 API Endpoints

### Authentication
- `POST /api/register` - Register new supervisor
- `GET /api/supervisor/<firebase_uid>` - Get supervisor profile

### Employee Management
- `GET /api/employees` - List employees
- `POST /api/employees` - Add new employee

### Vacation Requests
- `GET /api/vacation-requests` - List vacation requests
- `POST /api/vacation-requests` - Create vacation request
- `PUT /api/vacation-requests/<id>/approve` - Approve request
- `PUT /api/vacation-requests/<id>/deny` - Deny request

### Dashboard
- `GET /api/dashboard/stats` - Get dashboard statistics

## 🚀 Deployment

### Production Setup
1. **Environment Configuration**
   - Set `FLASK_ENV=production`
   - Configure production database
   - Set secure secret keys

2. **Database Migration**
   ```bash
   psql -d production_db -f database/schema.sql
   ```

3. **Build Assets**
   ```bash
   npm run build-css-prod
   ```

4. **Deploy with Gunicorn**
   ```bash
   gunicorn -w 4 -b 0.0.0.0:8000 backend.app:app
   ```

### Recommended Hosting
- **Frontend**: Vercel or Netlify
- **Backend**: Railway, Heroku, or DigitalOcean
- **Database**: Supabase, Railway, or managed PostgreSQL
- **Domain**: `vacationmanager.donmiguelfoods.com`

## 🧪 Testing

### Run Tests
```bash
pytest backend/tests/
```

### Test Coverage
- Unit tests for API endpoints
- Integration tests for database operations
- Frontend tests for user interactions

## 📝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🏢 Company Information

**Don Miguel Foods**
- Application Name: Don Miguel Vacation Manager
- Created by: Gerald Nyah
- Support: support@donmiguelfoods.com
- Website: https://vacationmanager.donmiguelfoods.com

## 🆘 Support

For technical support or questions:
- Email: support@donmiguelfoods.com
- Documentation: [Project Wiki](https://github.com/your-username/don-miguel-vacation-manager/wiki)
- Issues: [GitHub Issues](https://github.com/your-username/don-miguel-vacation-manager/issues)

---

© 2025 Don Miguel Foods. All rights reserved.