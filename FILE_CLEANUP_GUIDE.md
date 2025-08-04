# File Cleanup Guide for GitHub Deployment

## Files to KEEP (Production Files) ✅

### Core Application Files
- `backend/app.py` - Main Flask application
- `requirements.txt` - Python dependencies
- `package.json` - Node.js dependencies
- `package-lock.json` - Node.js lock file

### Database Files
- `database/schema.sql` - Main database schema
- `database/create_notification_preferences.sql` - SMS notification tables
- `database/grant_permissions.sql` - Database permissions (if exists)
- `setup_admin_table.py` - Admin setup script

### Templates (All HTML files in templates/ directory)
- `templates/index.html`
- `templates/dashboard.html` 
- `templates/profile.html`
- `templates/admin.html`
- `templates/help.html`
- All other `.html` files in templates/

### Static Assets
- `static/` directory (entire folder)
- `tailwind.config.js` (if exists)

### Configuration & Documentation
- `.env.example` - Environment template
- `.gitignore` - Git ignore rules
- `README.md` - Project documentation
- `DEPLOYMENT.md` - Deployment guide
- `DEPLOYMENT_CHECKLIST.md` - Deployment checklist
- `PROJECT_STATUS.md` - Project status
- `DATABASE_SETUP.md` - Database setup guide

## Files to DELETE (Test/Development Files) ❌

### Test Files (All should be deleted)
- `test_employee_creation.py`
- `test_db_connection_debug.py`
- `test_employee_retrieval.py`
- `test_db_connection.py`
- `test_excel_pdf_implementation.py`
- `test_profile_api.py`
- `test_profile_update.py`
- `test_support_ticket.py`
- `test_vacation_print_validation.py`
- `test_vacation_print.py`
- `test_vacation_request.py`

### Test HTML Files
- `test_dashboard_chart.html`
- `test_date_calculation.html`
- `test_date_formatting_debug.html`
- `test_responsive_admin.html`
- `test_toast_display.html`
- `test_toast.html`
- `test_vacation_complete_fix.html`
- `test_vacation_fixed.html`
- `test_vacation_frontend.html`

### Development/Temporary Files
- `create_excel_template.py` - Excel functionality was removed
- `TESTING.md` - Development testing notes
- `firebase_config.py` - Should be excluded (contains credentials)
- `firebase-config.js` - Should be excluded (contains credentials)
- `firebase-service-account.json` - Should be excluded (sensitive credentials)

### Database Development Files
- `database/add_password_hash_column.sql` - Development migration, likely not needed
- `setup_legal_documents_table.py` - If not used in production

## Quick Cleanup Commands

### Delete Test Files
```bash
# Delete Python test files
rm test_*.py
rm *_test.py

# Delete HTML test files  
rm test_*.html

# Delete development files
rm create_excel_template.py
rm TESTING.md
rm firebase_config.py
rm firebase-config.js

# Delete sensitive files (these should already be in .gitignore)
rm firebase-service-account.json
rm .env
```

### Verify Clean Structure
After cleanup, your project should look like:
```
don-miguel-vacation-manager/
├── backend/
│   └── app.py
├── database/
│   ├── schema.sql
│   ├── create_notification_preferences.sql
│   └── grant_permissions.sql (if exists)
├── static/
│   ├── css/
│   ├── js/
│   └── assets/
├── templates/
│   ├── index.html
│   ├── dashboard.html
│   ├── profile.html
│   ├── admin.html
│   ├── help.html
│   └── [other .html files]
├── docs/ (if you want to organize documentation)
├── requirements.txt
├── package.json
├── package-lock.json
├── setup_admin_table.py
├── .env.example
├── .gitignore
├── README.md
├── DEPLOYMENT.md
├── DEPLOYMENT_CHECKLIST.md
├── PROJECT_STATUS.md
└── DATABASE_SETUP.md
```

## Files That Will Be Automatically Ignored

These files don't need to be manually deleted because `.gitignore` will exclude them:
- `.env` (your actual environment file)
- `node_modules/`
- `__pycache__/`
- `*.pyc`
- `venv/`
- `.DS_Store`
- `logs/`

## Summary

**DELETE**: All files starting with `test_`, development utilities, and credential files
**KEEP**: Core application files, templates, database schemas, documentation, and configuration templates

After cleanup, you'll have a clean, production-ready codebase suitable for GitHub deployment.