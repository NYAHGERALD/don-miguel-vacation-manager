# Don Miguel Vacation Manager - Deployment Guide

This guide provides step-by-step instructions for deploying the Don Miguel Vacation Manager application to production.

## Prerequisites

- Node.js 18+ and npm
- Python 3.9+ and pip
- PostgreSQL 12+
- Firebase project with Authentication enabled
- Domain name (optional but recommended)

## Environment Setup

### 1. Clone and Setup Repository

```bash
git clone https://github.com/your-username/don-miguel-vacation-manager.git
cd don-miguel-vacation-manager
```

### 2. Install Dependencies

```bash
# Install Node.js dependencies
npm install

# Install Python dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your actual values
nano .env
```

Required environment variables:
- `SECRET_KEY`: Strong secret key for Flask sessions
- `DATABASE_URL`: PostgreSQL connection string
- `FIREBASE_*`: Firebase service account credentials
- `MAIL_*`: Email configuration for notifications

## Database Setup

### 1. Create PostgreSQL Database

```bash
# Connect to PostgreSQL
psql -U postgres

# Create database and user
CREATE DATABASE vacation_manager;
CREATE USER vacation_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE vacation_manager TO vacation_user;
\q
```

### 2. Run Database Schema

```bash
psql -d vacation_manager -U vacation_user -f database/schema.sql
```

### 3. Verify Database Setup

```bash
psql -d vacation_manager -U vacation_user -c "\dt"
```

## Firebase Configuration

### 1. Create Firebase Project

1. Go to [Firebase Console](https://console.firebase.google.com)
2. Create a new project
3. Enable Authentication with Email/Password and Google providers
4. Generate service account key

### 2. Update Firebase Configuration

1. Download service account JSON file
2. Update `firebase-config.js` with your project configuration
3. Set Firebase environment variables in `.env`

### 3. Configure Authentication

1. Set up authorized domains in Firebase Console
2. Configure OAuth redirect URIs
3. Set up email templates (optional)

## Build and Compile Assets

### 1. Build CSS

```bash
# Development build
npm run build-css

# Production build (minified)
npm run build-css-prod
```

### 2. Optimize Images and Assets

```bash
# Create optimized favicon
# Add any image optimization steps here
```

## Local Testing

### 1. Start Development Server

```bash
# Start Flask development server
python backend/app.py

# Or use npm script
npm run dev
```

### 2. Test Application

1. Open browser to `http://localhost:5000`
2. Test registration and login
3. Test all major features
4. Verify database connections
5. Test email notifications (if configured)

## Production Deployment Options

### Option 1: Railway Deployment

#### Backend Deployment

1. **Create Railway Account**
   - Sign up at [railway.app](https://railway.app)
   - Connect your GitHub repository

2. **Deploy Backend**
   ```bash
   # Install Railway CLI
   npm install -g @railway/cli
   
   # Login and deploy
   railway login
   railway init
   railway up
   ```

3. **Configure Environment Variables**
   - Add all environment variables from `.env`
   - Set `PORT` to Railway's provided port
   - Update `DATABASE_URL` to Railway PostgreSQL

4. **Setup Database**
   ```bash
   # Add PostgreSQL service
   railway add postgresql
   
   # Run migrations
   railway run python -c "import psycopg2; # run schema"
   ```

#### Frontend Deployment (Vercel)

1. **Deploy to Vercel**
   ```bash
   # Install Vercel CLI
   npm install -g vercel
   
   # Deploy
   vercel --prod
   ```

2. **Configure Build Settings**
   - Build Command: `npm run build-css-prod`
   - Output Directory: `static`
   - Install Command: `npm install`

### Option 2: DigitalOcean Droplet

#### 1. Create and Configure Droplet

```bash
# Create Ubuntu 22.04 droplet
# SSH into droplet
ssh root@your-droplet-ip

# Update system
apt update && apt upgrade -y

# Install dependencies
apt install -y python3 python3-pip nodejs npm postgresql postgresql-contrib nginx certbot python3-certbot-nginx
```

#### 2. Setup Application

```bash
# Clone repository
git clone https://github.com/your-username/don-miguel-vacation-manager.git
cd don-miguel-vacation-manager

# Install dependencies
pip3 install -r requirements.txt
npm install

# Build assets
npm run build-css-prod

# Setup systemd service
sudo cp deployment/vacation-manager.service /etc/systemd/system/
sudo systemctl enable vacation-manager
sudo systemctl start vacation-manager
```

#### 3. Configure Nginx

```bash
# Copy nginx configuration
sudo cp deployment/nginx.conf /etc/nginx/sites-available/vacation-manager
sudo ln -s /etc/nginx/sites-available/vacation-manager /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default

# Test and reload nginx
sudo nginx -t
sudo systemctl reload nginx
```

#### 4. Setup SSL Certificate

```bash
# Get SSL certificate
sudo certbot --nginx -d vacationmanager.donmiguelfoods.com

# Test auto-renewal
sudo certbot renew --dry-run
```

### Option 3: Heroku Deployment

#### 1. Prepare for Heroku

```bash
# Install Heroku CLI
# Create Procfile
echo "web: gunicorn backend.app:app" > Procfile

# Create runtime.txt
echo "python-3.9.16" > runtime.txt
```

#### 2. Deploy to Heroku

```bash
# Login and create app
heroku login
heroku create don-miguel-vacation-manager

# Add PostgreSQL addon
heroku addons:create heroku-postgresql:hobby-dev

# Set environment variables
heroku config:set SECRET_KEY=your-secret-key
heroku config:set FLASK_ENV=production
# ... set all other environment variables

# Deploy
git push heroku main

# Run database migrations
heroku run python -c "exec(open('database/schema.sql').read())"
```

## Post-Deployment Configuration

### 1. Domain Configuration

```bash
# Configure custom domain (if using)
# Update DNS records to point to your deployment
# Update Firebase authorized domains
# Update CORS settings if needed
```

### 2. SSL/TLS Setup

```bash
# Ensure HTTPS is enforced
# Configure security headers
# Test SSL configuration
```

### 3. Monitoring Setup

```bash
# Setup application monitoring
# Configure error tracking (Sentry, etc.)
# Setup uptime monitoring
# Configure log aggregation
```

### 4. Backup Configuration

```bash
# Setup automated database backups
# Configure file backup if needed
# Test backup restoration process
```

## Security Checklist

- [ ] All environment variables are set securely
- [ ] Database connections are encrypted
- [ ] HTTPS is enforced
- [ ] Firebase security rules are configured
- [ ] Rate limiting is enabled
- [ ] Input validation is implemented
- [ ] CORS is properly configured
- [ ] Security headers are set
- [ ] Regular security updates are planned

## Performance Optimization

### 1. Database Optimization

```sql
-- Add database indexes for better performance
CREATE INDEX CONCURRENTLY idx_vacation_requests_status_date 
ON vacation_requests(status, start_date);

CREATE INDEX CONCURRENTLY idx_employees_supervisor_department 
ON employees(supervisor_id, department);
```

### 2. Caching Setup

```python
# Add Redis caching for frequently accessed data
# Configure Flask-Caching
# Implement query result caching
```

### 3. CDN Configuration

```bash
# Setup CDN for static assets
# Configure asset versioning
# Implement asset compression
```

## Monitoring and Maintenance

### 1. Application Monitoring

- Setup health check endpoints
- Monitor response times
- Track error rates
- Monitor database performance

### 2. Log Management

```bash
# Configure structured logging
# Setup log rotation
# Implement log analysis
```

### 3. Regular Maintenance

- Database maintenance and optimization
- Security updates
- Dependency updates
- Performance monitoring
- Backup verification

## Troubleshooting

### Common Issues

1. **Database Connection Issues**
   ```bash
   # Check database connectivity
   psql $DATABASE_URL -c "SELECT 1;"
   
   # Verify environment variables
   echo $DATABASE_URL
   ```

2. **Firebase Authentication Issues**
   ```bash
   # Verify Firebase configuration
   # Check authorized domains
   # Validate service account credentials
   ```

3. **Static Asset Issues**
   ```bash
   # Rebuild CSS
   npm run build-css-prod
   
   # Check file permissions
   ls -la static/css/
   ```

4. **Email Notification Issues**
   ```bash
   # Test SMTP configuration
   # Check email credentials
   # Verify firewall settings
   ```

### Debug Mode

```bash
# Enable debug mode for troubleshooting
export FLASK_DEBUG=True
export LOG_LEVEL=DEBUG

# Run with verbose logging
python backend/app.py
```

## Support and Documentation

- **Technical Documentation**: See README.md
- **API Documentation**: Available at `/api/docs` (if implemented)
- **User Guide**: Create user documentation for supervisors
- **Support Contact**: support@donmiguelfoods.com

## Rollback Procedures

### 1. Application Rollback

```bash
# Rollback to previous version
git checkout previous-stable-tag
# Redeploy using your chosen method
```

### 2. Database Rollback

```bash
# Restore from backup
pg_restore -d vacation_manager backup_file.sql
```

### 3. Configuration Rollback

```bash
# Restore previous environment variables
# Rollback nginx/web server configuration
# Restore previous SSL certificates if needed
```

---

## Quick Deployment Commands

### Railway + Vercel (Recommended)

```bash
# Backend (Railway)
railway login
railway init
railway add postgresql
railway up

# Frontend (Vercel)
vercel --prod
```

### DigitalOcean Droplet

```bash
# One-time setup script
curl -sSL https://raw.githubusercontent.com/your-repo/deployment/setup.sh | bash
```

### Heroku

```bash
# Quick Heroku deployment
heroku create don-miguel-vacation-manager
heroku addons:create heroku-postgresql:hobby-dev
git push heroku main
```

---

**Note**: Always test deployments in a staging environment before deploying to production. Keep backups of your database and configuration files.