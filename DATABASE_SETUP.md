# PostgreSQL Database Setup Guide

This guide will help you set up the PostgreSQL database for the Don Miguel Vacation Manager application.

## Prerequisites

- PostgreSQL 12 or higher installed on your system
- Python 3.8 or higher
- Access to PostgreSQL with superuser privileges (for initial setup)

## Installation Steps

### 1. Install PostgreSQL

#### macOS (using Homebrew)
```bash
brew install postgresql
brew services start postgresql
```

#### Ubuntu/Debian
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

#### Windows
Download and install from [PostgreSQL official website](https://www.postgresql.org/download/windows/)

### 2. Create Database and User

Connect to PostgreSQL as superuser:
```bash
sudo -u postgres psql
```

Or on macOS with Homebrew:
```bash
psql postgres
```

Run the following SQL commands:
```sql
-- Create the database
CREATE DATABASE vacation_manager;

-- Create the user
CREATE USER vacation_user WITH PASSWORD 'vacation_pass';

-- Grant privileges to the user
GRANT ALL PRIVILEGES ON DATABASE vacation_manager TO vacation_user;

-- Connect to the database
\c vacation_manager

-- Grant schema privileges
GRANT ALL ON SCHEMA public TO vacation_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO vacation_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO vacation_user;

-- Exit psql
\q
```

### 3. Initialize Database Schema

From the project root directory, run:
```bash
# Create tables and initial data
psql -U postgres -d vacation_manager -f database/schema.sql

# Grant permissions to vacation_user
psql -U postgres -d vacation_manager -f database/grant_permissions.sql
```

### 4. Configure Environment Variables

Create or update your `.env` file in the project root:
```env
# Database Configuration
DATABASE_URL=postgresql://vacation_user:vacation_pass@localhost:5432/vacation_manager

# Flask Configuration
SECRET_KEY=your-secret-key-here
FLASK_ENV=development
FLASK_DEBUG=True
```

### 5. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 6. Test Database Connection

Run the test script to verify everything is working:
```bash
python test_db_connection.py
```

You should see output similar to:
```
🔍 Testing PostgreSQL Database Connection...
==================================================
Testing connection to: localhost:5432/vacation_manager
✅ Database connection successful!
PostgreSQL version: PostgreSQL 14.x ...

📋 Found 13 tables:
  - announcements
  - area_limits
  - article_ratings
  - audit_log
  - employees
  - faq_articles
  - feedback
  - profile_changes
  - supervisors
  - support_tickets
  - vacation_requests
  - work_areas
  - work_lines

👥 Supervisors table has 0 records

==================================================
✅ Database test completed successfully!
```

## Database Schema Overview

The database includes the following main tables:

- **supervisors**: Store supervisor information linked to Firebase Authentication
- **employees**: Store employee information managed by supervisors
- **vacation_requests**: Store vacation requests with approval workflow
- **work_areas** & **work_lines**: Define work organization structure
- **area_limits**: Define maximum concurrent vacation limits per work area
- **faq_articles**: FAQ content for the help center
- **support_tickets**: Support requests from users
- **announcements**: System announcements
- **feedback**: User feedback collection
- **audit_log**: Track all changes for compliance

## Troubleshooting

### Connection Issues

1. **"Connection refused"**: Make sure PostgreSQL is running
   ```bash
   # Check status
   sudo systemctl status postgresql  # Linux
   brew services list | grep postgresql  # macOS
   ```

2. **"Database does not exist"**: Create the database following step 2

3. **"Authentication failed"**: Check username/password in DATABASE_URL

4. **"Permission denied"**: Run the grant_permissions.sql script

### Performance Optimization

For production environments, consider:

1. **Connection Pooling**: Use pgbouncer or similar
2. **Indexes**: The schema includes optimized indexes
3. **Backup Strategy**: Set up regular backups
4. **Monitoring**: Use tools like pg_stat_statements

## Production Deployment

For production deployment:

1. Use strong passwords and secure connection strings
2. Enable SSL connections
3. Set up regular backups
4. Configure connection pooling
5. Monitor database performance
6. Use environment-specific configuration

## Maintenance Commands

```bash
# Backup database
pg_dump -U vacation_user vacation_manager > backup.sql

# Restore database
psql -U vacation_user vacation_manager < backup.sql

# Check database size
psql -U vacation_user -d vacation_manager -c "SELECT pg_size_pretty(pg_database_size('vacation_manager'));"

# View active connections
psql -U vacation_user -d vacation_manager -c "SELECT * FROM pg_stat_activity WHERE datname = 'vacation_manager';"