-- Don Miguel Vacation Manager Database Schema
-- PostgreSQL Database Schema for Vacation Management System
-- Organized for proper execution order: Functions -> Tables -> Indexes -> Triggers -> Views -> Data -> Permissions

-- =====================================================
-- 1. DROP STATEMENTS (in reverse dependency order)
-- =====================================================

DROP TABLE IF EXISTS notification_history CASCADE;
DROP TABLE IF EXISTS notification_preferences CASCADE;
DROP TABLE IF EXISTS article_ratings CASCADE;
DROP TABLE IF EXISTS announcements CASCADE;
DROP TABLE IF EXISTS support_tickets CASCADE;
DROP TABLE IF EXISTS faq_articles CASCADE;
DROP TABLE IF EXISTS profile_changes CASCADE;
DROP TABLE IF EXISTS feedback CASCADE;
DROP TABLE IF EXISTS legal_document_history CASCADE;
DROP TABLE IF EXISTS legal_documents CASCADE;
DROP TABLE IF EXISTS admin_emails CASCADE;
DROP TABLE IF EXISTS area_limits CASCADE;
DROP TABLE IF EXISTS vacation_requests CASCADE;
DROP TABLE IF EXISTS employees CASCADE;
DROP TABLE IF EXISTS work_lines CASCADE;
DROP TABLE IF EXISTS work_areas CASCADE;
DROP TABLE IF EXISTS supervisors CASCADE;
DROP TABLE IF EXISTS audit_log CASCADE;

-- Drop views
DROP VIEW IF EXISTS dashboard_stats CASCADE;
DROP VIEW IF EXISTS vacation_request_summary CASCADE;

-- Drop functions
DROP FUNCTION IF EXISTS check_area_capacity CASCADE;
DROP FUNCTION IF EXISTS check_vacation_conflicts CASCADE;
DROP FUNCTION IF EXISTS archive_previous_legal_document CASCADE;
DROP FUNCTION IF EXISTS update_updated_at_column CASCADE;

-- =====================================================
-- 2. CREATE FUNCTIONS (before triggers that use them)
-- =====================================================

-- Function for updating updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Function to check vacation conflicts
CREATE OR REPLACE FUNCTION check_vacation_conflicts(
    p_employee_id INTEGER,
    p_start_date DATE,
    p_end_date DATE,
    p_exclude_request_id INTEGER DEFAULT NULL
)
RETURNS TABLE(conflict_count INTEGER, conflicting_requests TEXT[]) AS $$
DECLARE
    conflicts TEXT[];
    conflict_count INTEGER;
BEGIN
    SELECT 
        COUNT(*)::INTEGER,
        ARRAY_AGG('Request #' || id || ' (' || start_date || ' to ' || end_date || ')')
    INTO conflict_count, conflicts
    FROM vacation_requests
    WHERE employee_id = p_employee_id
    AND status IN ('Pending', 'Approved')
    AND (p_exclude_request_id IS NULL OR id != p_exclude_request_id)
    AND (
        (start_date <= p_end_date AND end_date >= p_start_date)
    );
    
    RETURN QUERY SELECT conflict_count, COALESCE(conflicts, ARRAY[]::TEXT[]);
END;
$$ LANGUAGE plpgsql;

-- Function to check area capacity limits
CREATE OR REPLACE FUNCTION check_area_capacity(
    p_department VARCHAR(50),
    p_work_line_id INTEGER,
    p_work_area_id INTEGER,
    p_start_date DATE,
    p_end_date DATE,
    p_exclude_request_id INTEGER DEFAULT NULL
)
RETURNS TABLE(is_over_limit BOOLEAN, current_count INTEGER, max_limit INTEGER) AS $$
DECLARE
    current_requests INTEGER;
    area_limit INTEGER;
BEGIN
    -- Get the area limit
    SELECT max_concurrent_requests INTO area_limit
    FROM area_limits
    WHERE department = p_department
    AND (work_line_id = p_work_line_id OR work_line_id IS NULL)
    AND (work_area_id = p_work_area_id OR work_area_id IS NULL)
    ORDER BY
        CASE WHEN work_line_id = p_work_line_id THEN 1 ELSE 2 END,
        CASE WHEN work_area_id = p_work_area_id THEN 1 ELSE 2 END
    LIMIT 1;
    
    -- If no limit found, default to 1
    IF area_limit IS NULL THEN
        area_limit := 1;
    END IF;
    
    -- Count current approved requests that overlap with the requested period
    SELECT COUNT(*) INTO current_requests
    FROM vacation_requests vr
    JOIN employees e ON vr.employee_id = e.id
    WHERE e.department = p_department
    AND e.work_line_id = p_work_line_id
    AND e.work_area_id = p_work_area_id
    AND vr.status = 'Approved'
    AND (p_exclude_request_id IS NULL OR vr.id != p_exclude_request_id)
    AND (
        (vr.start_date <= p_end_date AND vr.end_date >= p_start_date)
    );
    
    RETURN QUERY SELECT
        (current_requests >= area_limit) AS is_over_limit,
        current_requests,
        area_limit;
END;
$$ LANGUAGE plpgsql;

-- Function to archive old version when creating new active document
CREATE OR REPLACE FUNCTION archive_previous_legal_document()
RETURNS TRIGGER AS $$
BEGIN
    -- If the new document is being set as active
    IF NEW.is_active = true THEN
        -- Archive the currently active document of the same type
        INSERT INTO legal_document_history (
            document_id, document_type, title, content, version,
            effective_date, created_by, archived_by
        )
        SELECT
            id, document_type, title, content, version,
            effective_date, created_by, NEW.created_by
        FROM legal_documents
        WHERE document_type = NEW.document_type
        AND is_active = true
        AND id != NEW.id;
        
        -- Deactivate the old document
        UPDATE legal_documents
        SET is_active = false
        WHERE document_type = NEW.document_type
        AND is_active = true
        AND id != NEW.id;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- 3. CREATE BASE TABLES (no foreign key dependencies)
-- =====================================================

-- Create supervisors table (base table)
CREATE TABLE supervisors (
    id SERIAL PRIMARY KEY,
    firebase_uid VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone_number VARCHAR(20),
    department VARCHAR(50) NOT NULL CHECK (department IN ('Production', 'Bakery', 'Warehouse')),
    shift VARCHAR(50) NOT NULL CHECK (shift IN ('First Shift', 'Second Shift')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create work_areas table (base table)
CREATE TABLE work_areas (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create work_lines table (base table)
CREATE TABLE work_lines (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create audit_log table (base table)
CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    table_name VARCHAR(50) NOT NULL,
    record_id INTEGER NOT NULL,
    action VARCHAR(20) NOT NULL CHECK (action IN ('INSERT', 'UPDATE', 'DELETE')),
    old_values JSONB,
    new_values JSONB,
    changed_by VARCHAR(255),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create admin_emails table (base table)
CREATE TABLE admin_emails (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 4. CREATE DEPENDENT TABLES (with foreign keys)
-- =====================================================

-- Create employees table (depends on supervisors, work_areas, work_lines)
CREATE TABLE employees (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone_number VARCHAR(20),
    department VARCHAR(50) NOT NULL CHECK (department IN ('Production', 'Bakery', 'Warehouse')),
    shift VARCHAR(50) NOT NULL CHECK (shift IN ('First Shift', 'Second Shift')),
    work_line_id INTEGER REFERENCES work_lines(id) ON DELETE SET NULL,
    work_area_id INTEGER REFERENCES work_areas(id) ON DELETE SET NULL,
    supervisor_id INTEGER NOT NULL REFERENCES supervisors(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create vacation_requests table (depends on employees, supervisors)
CREATE TABLE vacation_requests (
    id SERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    supervisor_id INTEGER NOT NULL REFERENCES supervisors(id) ON DELETE CASCADE,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    return_date DATE NOT NULL,
    total_hours INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Pending' CHECK (status IN ('Pending', 'Approved', 'Denied', 'Cancelled')),
    reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT valid_date_range CHECK (end_date >= start_date),
    CONSTRAINT valid_return_date CHECK (return_date > end_date),
    CONSTRAINT positive_hours CHECK (total_hours > 0)
);

-- Create area_limits table (depends on work_lines, work_areas)
CREATE TABLE area_limits (
    id SERIAL PRIMARY KEY,
    department VARCHAR(50) NOT NULL CHECK (department IN ('Production', 'Bakery', 'Warehouse')),
    work_line_id INTEGER REFERENCES work_lines(id) ON DELETE CASCADE,
    work_area_id INTEGER REFERENCES work_areas(id) ON DELETE CASCADE,
    max_concurrent_requests INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Unique constraint to prevent duplicate limits for same area/line combination
    UNIQUE(department, work_line_id, work_area_id)
);

-- Create feedback table (depends on supervisors)
CREATE TABLE feedback (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) REFERENCES supervisors(firebase_uid) ON DELETE SET NULL,
    category VARCHAR(50) NOT NULL CHECK (category IN ('bug_report', 'feature_request', 'general_feedback')),
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create profile_changes table (depends on supervisors)
CREATE TABLE profile_changes (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) REFERENCES supervisors(firebase_uid) ON DELETE CASCADE,
    field_name VARCHAR(100) NOT NULL,
    old_value TEXT,
    new_value TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'denied')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create faq_articles table (base table for help center)
CREATE TABLE faq_articles (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    category VARCHAR(100) NOT NULL,
    is_published BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create support_tickets table (depends on supervisors)
CREATE TABLE support_tickets (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) REFERENCES supervisors(firebase_uid) ON DELETE SET NULL,
    subject VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    message TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'resolved', 'closed')),
    priority VARCHAR(20) NOT NULL DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create announcements table (base table)
CREATE TABLE announcements (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    is_published BOOLEAN DEFAULT true,
    target_departments TEXT[], -- Array of departments or NULL for all
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create article_ratings table (depends on faq_articles, supervisors)
CREATE TABLE article_ratings (
    id SERIAL PRIMARY KEY,
    article_id INTEGER REFERENCES faq_articles(id) ON DELETE CASCADE,
    user_id VARCHAR(255) REFERENCES supervisors(firebase_uid) ON DELETE SET NULL,
    rating BOOLEAN NOT NULL, -- true for helpful, false for not helpful
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create legal_documents table (depends on admin_emails)
CREATE TABLE legal_documents (
    id SERIAL PRIMARY KEY,
    document_type VARCHAR(50) NOT NULL CHECK (document_type IN ('terms_of_service', 'privacy_policy')),
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    version VARCHAR(20) NOT NULL DEFAULT '1.0',
    is_active BOOLEAN DEFAULT false,
    effective_date DATE,
    created_by VARCHAR(255) REFERENCES admin_emails(email) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure only one active document per type
    UNIQUE(document_type, is_active) DEFERRABLE INITIALLY DEFERRED
);

-- Create legal_document_history table (depends on legal_documents, admin_emails)
CREATE TABLE legal_document_history (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES legal_documents(id) ON DELETE CASCADE,
    document_type VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    version VARCHAR(20) NOT NULL,
    effective_date DATE,
    created_by VARCHAR(255),
    archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    archived_by VARCHAR(255) REFERENCES admin_emails(email) ON DELETE SET NULL
);

-- Create notification_preferences table (depends on supervisors)
CREATE TABLE notification_preferences (
    id SERIAL PRIMARY KEY,
    supervisor_id INTEGER NOT NULL REFERENCES supervisors(id) ON DELETE CASCADE,
    
    -- Notification settings
    sms_enabled BOOLEAN DEFAULT true,
    days_before_vacation INTEGER DEFAULT 2 CHECK (days_before_vacation >= 0 AND days_before_vacation <= 30),
    
    -- Daily notification frequency
    notifications_per_day INTEGER DEFAULT 1 CHECK (notifications_per_day >= 1 AND notifications_per_day <= 10),
    
    -- Notification times (stored as time without timezone)
    notification_times TIME[] DEFAULT ARRAY['09:00:00'::TIME],
    
    -- Phone number override (if different from supervisor table)
    phone_number_override VARCHAR(20),
    
    -- Timezone for the supervisor (default to Central Time)
    timezone VARCHAR(50) DEFAULT 'America/Chicago',
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure unique preferences per supervisor
    UNIQUE(supervisor_id)
);

-- Create notification_history table (depends on supervisors, vacation_requests)
CREATE TABLE notification_history (
    id SERIAL PRIMARY KEY,
    supervisor_id INTEGER NOT NULL REFERENCES supervisors(id) ON DELETE CASCADE,
    vacation_request_id INTEGER NOT NULL REFERENCES vacation_requests(id) ON DELETE CASCADE,
    
    -- Notification details
    notification_type VARCHAR(20) DEFAULT 'sms' CHECK (notification_type IN ('sms', 'email')),
    phone_number VARCHAR(20),
    message_content TEXT NOT NULL,
    
    -- Twilio response data
    twilio_sid VARCHAR(100),
    twilio_status VARCHAR(20),
    twilio_error_code VARCHAR(10),
    twilio_error_message TEXT,
    
    -- Status tracking
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'delivered', 'failed', 'undelivered')),
    sent_at TIMESTAMP,
    delivered_at TIMESTAMP,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 5. CREATE INDEXES (after tables are created)
-- =====================================================

-- Supervisors indexes
CREATE INDEX idx_supervisors_firebase_uid ON supervisors(firebase_uid);
CREATE INDEX idx_supervisors_email ON supervisors(email);
CREATE INDEX idx_supervisors_department ON supervisors(department);

-- Employees indexes
CREATE INDEX idx_employees_supervisor_id ON employees(supervisor_id);
CREATE INDEX idx_employees_department ON employees(department);
CREATE INDEX idx_employees_work_area ON employees(work_area_id, work_line_id);

-- Vacation requests indexes
CREATE INDEX idx_vacation_requests_employee_id ON vacation_requests(employee_id);
CREATE INDEX idx_vacation_requests_supervisor_id ON vacation_requests(supervisor_id);
CREATE INDEX idx_vacation_requests_status ON vacation_requests(status);
CREATE INDEX idx_vacation_requests_dates ON vacation_requests(start_date, end_date);
CREATE INDEX idx_vacation_requests_created_at ON vacation_requests(created_at);

-- Area limits indexes
CREATE INDEX idx_area_limits_department ON area_limits(department);
CREATE INDEX idx_area_limits_work_area ON area_limits(work_area_id, work_line_id);

-- Feedback indexes
CREATE INDEX idx_feedback_user_id ON feedback(user_id);
CREATE INDEX idx_feedback_category ON feedback(category);

-- Profile changes indexes
CREATE INDEX idx_profile_changes_user_id ON profile_changes(user_id);
CREATE INDEX idx_profile_changes_status ON profile_changes(status);

-- FAQ articles indexes
CREATE INDEX idx_faq_articles_category ON faq_articles(category);
CREATE INDEX idx_faq_articles_published ON faq_articles(is_published);

-- Support tickets indexes
CREATE INDEX idx_support_tickets_user_id ON support_tickets(user_id);
CREATE INDEX idx_support_tickets_status ON support_tickets(status);
CREATE INDEX idx_support_tickets_priority ON support_tickets(priority);

-- Article ratings indexes
CREATE INDEX idx_article_ratings_article_id ON article_ratings(article_id);
CREATE INDEX idx_article_ratings_user_id ON article_ratings(user_id);

-- Admin emails indexes
CREATE INDEX idx_admin_emails_email ON admin_emails(email);
CREATE INDEX idx_admin_emails_active ON admin_emails(is_active);
CREATE INDEX idx_admin_emails_password_hash ON admin_emails(password_hash);

-- Legal documents indexes
CREATE INDEX idx_legal_documents_type ON legal_documents(document_type);
CREATE INDEX idx_legal_documents_active ON legal_documents(is_active);
CREATE INDEX idx_legal_documents_effective_date ON legal_documents(effective_date);
CREATE INDEX idx_legal_document_history_document_id ON legal_document_history(document_id);
CREATE INDEX idx_legal_document_history_type ON legal_document_history(document_type);

-- Notification preferences indexes
CREATE INDEX idx_notification_preferences_supervisor_id ON notification_preferences(supervisor_id);

-- Notification history indexes
CREATE INDEX idx_notification_history_supervisor_id ON notification_history(supervisor_id);
CREATE INDEX idx_notification_history_vacation_request_id ON notification_history(vacation_request_id);
CREATE INDEX idx_notification_history_status ON notification_history(status);
CREATE INDEX idx_notification_history_sent_at ON notification_history(sent_at);

-- =====================================================
-- 6. CREATE TRIGGERS (after functions and tables)
-- =====================================================

-- Triggers for updating updated_at timestamps
CREATE TRIGGER update_supervisors_updated_at BEFORE UPDATE ON supervisors
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_employees_updated_at BEFORE UPDATE ON employees
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_vacation_requests_updated_at BEFORE UPDATE ON vacation_requests
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_area_limits_updated_at BEFORE UPDATE ON area_limits
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_profile_changes_updated_at BEFORE UPDATE ON profile_changes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_faq_articles_updated_at BEFORE UPDATE ON faq_articles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_support_tickets_updated_at BEFORE UPDATE ON support_tickets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_announcements_updated_at BEFORE UPDATE ON announcements
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_admin_emails_updated_at BEFORE UPDATE ON admin_emails
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_legal_documents_updated_at BEFORE UPDATE ON legal_documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_notification_preferences_updated_at BEFORE UPDATE ON notification_preferences
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_notification_history_updated_at BEFORE UPDATE ON notification_history
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Trigger for archiving previous legal document versions
CREATE TRIGGER archive_previous_legal_document_trigger
    BEFORE INSERT OR UPDATE ON legal_documents
    FOR EACH ROW
    WHEN (NEW.is_active = true)
    EXECUTE FUNCTION archive_previous_legal_document();

-- =====================================================
-- 7. CREATE VIEWS (after tables and indexes)
-- =====================================================

-- Create a view for vacation request summary
CREATE VIEW vacation_request_summary AS
SELECT
    vr.id,
    vr.start_date,
    vr.end_date,
    vr.return_date,
    vr.total_hours,
    vr.status,
    vr.created_at,
    e.first_name || ' ' || e.last_name AS employee_name,
    e.department,
    e.shift,
    wl.name AS work_line,
    wa.name AS work_area,
    s.first_name || ' ' || s.last_name AS supervisor_name,
    s.email AS supervisor_email
FROM vacation_requests vr
JOIN employees e ON vr.employee_id = e.id
LEFT JOIN work_areas wa ON e.work_area_id = wa.id
LEFT JOIN work_lines wl ON e.work_line_id = wl.id
JOIN supervisors s ON vr.supervisor_id = s.id;

-- Create a view for dashboard statistics
CREATE VIEW dashboard_stats AS
SELECT 
    s.id AS supervisor_id,
    s.department,
    s.shift,
    COUNT(DISTINCT e.id) AS total_employees,
    COUNT(CASE WHEN vr.status = 'Pending' THEN 1 END) AS pending_requests,
    COUNT(CASE WHEN vr.status = 'Approved' THEN 1 END) AS approved_requests,
    COUNT(CASE WHEN vr.status = 'Denied' THEN 1 END) AS denied_requests,
    COUNT(CASE WHEN vr.status = 'Cancelled' THEN 1 END) AS cancelled_requests,
    SUM(CASE WHEN vr.status = 'Approved' THEN vr.total_hours ELSE 0 END) AS total_approved_hours
FROM supervisors s
LEFT JOIN employees e ON s.id = e.supervisor_id
LEFT JOIN vacation_requests vr ON e.id = vr.employee_id
GROUP BY s.id, s.department, s.shift;

-- =====================================================
-- 8. INSERT SAMPLE DATA (after all structures are created)
-- =====================================================

-- Insert initial admin email with secure password
-- Default admin login credentials:
-- Email: nyah.gerard@gmail.com
-- Password: AdminSecure2025!
INSERT INTO admin_emails (email, password_hash) VALUES 
('nyah.gerard@gmail.com', '$2b$12$Kcu.TXmYNnEoz3H.gBhrHuv4y.60L74AD35zz8WUshHVWDb5bRxH6');

-- Insert sample FAQ articles for testing
INSERT INTO faq_articles (title, content, category) VALUES
('How do I request vacation time?', 'To request vacation time, navigate to the Vacation Requests page and click "New Request". Fill in your desired start and end dates, and your supervisor will review the request.', 'Vacation Requests'),
('What is the maximum vacation time I can request?', 'The maximum vacation time depends on your department and work area capacity limits. Generally, you can request up to 2 weeks at a time, subject to approval.', 'Vacation Requests'),
('How far in advance should I request vacation?', 'We recommend submitting vacation requests at least 2 weeks in advance to ensure proper coverage and approval processing.', 'Vacation Requests'),
('Can I cancel my vacation request?', 'Yes, you can contact your supervisor to cancel a pending vacation request. Approved requests may require additional approval to cancel.', 'Vacation Requests'),
('How do I update my profile information?', 'Go to Profile Settings from the user menu. You can update your name and phone number. Department and shift changes require administrator approval.', 'Profile Management'),
('How do I change my password?', 'In Profile Settings, go to the Security tab and use the Change Password form. You will need to enter your current password and a new secure password.', 'Profile Management'),
('What should I do if I forgot my password?', 'Use the "Forgot Password" link on the login page to reset your password via email through Firebase Authentication.', 'Account Access'),
('How do I enable two-factor authentication?', 'Two-factor authentication can be enabled in the Security section of your Profile Settings for enhanced account security.', 'Account Security'),
('Who can I contact for technical support?', 'Use the Contact Support form in the Help Center or email your system administrator for technical assistance.', 'Technical Support'),
('How do I report a bug or request a feature?', 'Use the Feedback tab in either Profile Settings or Help Center to report bugs or request new features.', 'Technical Support');

-- Insert sample announcements for testing
INSERT INTO announcements (title, content, target_departments) VALUES
('System Maintenance Scheduled', 'The vacation management system will undergo scheduled maintenance on Sunday from 2:00 AM to 4:00 AM. The system will be temporarily unavailable during this time.', NULL),
('New Feature: Mobile Access', 'We are pleased to announce that the vacation management system is now optimized for mobile devices. You can access all features from your smartphone or tablet.', NULL),
('Holiday Schedule Reminder', 'Please remember to submit your holiday vacation requests early as these periods have high demand. Requests are processed on a first-come, first-served basis.', NULL),
('Production Department Update', 'New work area limits have been implemented for the Production department. Please check with your supervisor for updated capacity information.', ARRAY['Production']),
('Bakery Department Training', 'Mandatory training sessions for the new equipment will be held next week. Please coordinate with your supervisor for scheduling.', ARRAY['Bakery']);

-- Insert default Terms of Service and Privacy Policy
INSERT INTO legal_documents (document_type, title, content, version, is_active, effective_date, created_by) VALUES
('terms_of_service', 'Terms of Service',
'# Terms of Service

## 1. Acceptance of Terms
By accessing and using the Don Miguel Foods Vacation Management System, you agree to be bound by these Terms of Service.

## 2. Description of Service
The Vacation Management System is designed to facilitate vacation request submissions, approvals, and management for Don Miguel Foods employees and supervisors.

## 3. User Responsibilities
- Provide accurate and complete information
- Maintain the confidentiality of your account credentials
- Use the system only for legitimate business purposes
- Comply with all company policies and procedures

## 4. System Usage
- The system is available 24/7 with scheduled maintenance windows
- Users are responsible for timely submission of vacation requests
- Supervisors must review and respond to requests in a timely manner

## 5. Data Privacy
Your personal information is protected according to our Privacy Policy and applicable data protection laws.

## 6. Limitation of Liability
Don Miguel Foods is not liable for any indirect, incidental, or consequential damages arising from system use.

## 7. Modifications
These terms may be updated periodically. Users will be notified of significant changes.

## 8. Contact Information
For questions about these terms, contact your system administrator or HR department.

Last updated: ' || CURRENT_DATE,
'1.0', true, CURRENT_DATE, 'nyah.gerard@gmail.com'),

('privacy_policy', 'Privacy Policy',
'# Privacy Policy

## 1. Information We Collect
We collect information necessary for vacation management including:
- Employee identification and contact information
- Vacation request details and dates
- Supervisor approval decisions
- System usage logs for security and performance

## 2. How We Use Your Information
Your information is used to:
- Process vacation requests and approvals
- Maintain accurate employee records
- Generate reports for management
- Ensure system security and compliance

## 3. Information Sharing
We do not share your personal information with third parties except:
- As required by law or legal process
- With your explicit consent
- For legitimate business operations within Don Miguel Foods

## 4. Data Security
We implement appropriate security measures to protect your information:
- Encrypted data transmission and storage
- Access controls and authentication
- Regular security audits and updates
- Employee training on data protection

## 5. Data Retention
We retain your information for as long as necessary for business operations and legal compliance.

## 6. Your Rights
You have the right to:
- Access your personal information
- Request corrections to inaccurate data
- Request deletion of your data (subject to legal requirements)
- Opt-out of non-essential communications

## 7. Cookies and Tracking
We use cookies and similar technologies for:
- Authentication and session management
- System functionality and user preferences
- Security monitoring and fraud prevention

## 8. Changes to This Policy
We may update this privacy policy periodically. Significant changes will be communicated to users.

## 9. Contact Us
For privacy-related questions or concerns, contact:
- System Administrator: nyah.gerard@gmail.com
- HR Department: hr@donmiguelfoods.com

Last updated: ' || CURRENT_DATE,
'1.0', true, CURRENT_DATE, 'nyah.gerard@gmail.com');

-- =====================================================
-- 9. GRANT PERMISSIONS (must be run as superuser)
-- =====================================================

-- Grant permissions to vacation_user for all tables
GRANT ALL PRIVILEGES ON TABLE supervisors TO vacation_user;
GRANT ALL PRIVILEGES ON TABLE employees TO vacation_user;
GRANT ALL PRIVILEGES ON TABLE work_areas TO vacation_user;
GRANT ALL PRIVILEGES ON TABLE work_lines TO vacation_user;
GRANT ALL PRIVILEGES ON TABLE vacation_requests TO vacation_user;
GRANT ALL PRIVILEGES ON TABLE area_limits TO vacation_user;
GRANT ALL PRIVILEGES ON TABLE audit_log TO vacation_user;
GRANT ALL PRIVILEGES ON TABLE feedback TO vacation_user;
GRANT ALL PRIVILEGES ON TABLE profile_changes TO vacation_user;
GRANT ALL PRIVILEGES ON TABLE faq_articles TO vacation_user;
GRANT ALL PRIVILEGES ON TABLE support_tickets TO vacation_user;
GRANT ALL PRIVILEGES ON TABLE announcements TO vacation_user;
GRANT ALL PRIVILEGES ON TABLE article_ratings TO vacation_user;
GRANT ALL PRIVILEGES ON TABLE admin_emails TO vacation_user;
GRANT ALL PRIVILEGES ON TABLE legal_documents TO vacation_user;
GRANT ALL PRIVILEGES ON TABLE legal_document_history TO vacation_user;
GRANT ALL PRIVILEGES ON TABLE notification_preferences TO vacation_user;
GRANT ALL PRIVILEGES ON TABLE notification_history TO vacation_user;

-- Grant permissions to sequences
GRANT ALL PRIVILEGES ON SEQUENCE supervisors_id_seq TO vacation_user;
GRANT ALL PRIVILEGES ON SEQUENCE employees_id_seq TO vacation_user;
GRANT ALL PRIVILEGES ON SEQUENCE work_areas_id_seq TO vacation_user;
GRANT ALL PRIVILEGES ON SEQUENCE work_lines_id_seq TO vacation_user;
GRANT ALL PRIVILEGES ON SEQUENCE vacation_requests_id_seq TO vacation_user;
GRANT ALL PRIVILEGES ON SEQUENCE area_limits_id_seq TO vacation_user;
GRANT ALL PRIVILEGES ON SEQUENCE audit_log_id_seq TO vacation_user;
GRANT ALL PRIVILEGES ON SEQUENCE feedback_id_seq TO vacation_user;
GRANT ALL PRIVILEGES ON SEQUENCE profile_changes_id_seq TO vacation_user;
GRANT ALL PRIVILEGES ON SEQUENCE faq_articles_id_seq TO vacation_user;
GRANT ALL PRIVILEGES ON SEQUENCE support_tickets_id_seq TO vacation_user;
GRANT ALL PRIVILEGES ON SEQUENCE announcements_id_seq TO vacation_user;
GRANT ALL PRIVILEGES ON SEQUENCE article_ratings_id_seq TO vacation_user;
GRANT ALL PRIVILEGES ON SEQUENCE admin_emails_id_seq TO vacation_user;
GRANT ALL PRIVILEGES ON SEQUENCE legal_documents_id_seq TO vacation_user;
GRANT ALL PRIVILEGES ON SEQUENCE legal_document_history_id_seq TO vacation_user;
GRANT ALL PRIVILEGES ON SEQUENCE notification_preferences_id_seq TO vacation_user;
GRANT ALL PRIVILEGES ON SEQUENCE notification_history_id_seq TO vacation_user;

-- Grant permissions to views
GRANT SELECT ON vacation_request_summary TO vacation_user;
GRANT SELECT ON dashboard_stats TO vacation_user;

-- =====================================================
-- 10. TABLE COMMENTS (for documentation)
-- =====================================================

COMMENT ON TABLE supervisors IS 'Stores supervisor information linked to Firebase Authentication';
COMMENT ON TABLE employees IS 'Stores employee information managed by supervisors';
COMMENT ON TABLE vacation_requests IS 'Stores vacation requests with approval workflow';
COMMENT ON TABLE area_limits IS 'Defines maximum concurrent vacation limits per work area';
COMMENT ON TABLE audit_log IS 'Tracks all changes for compliance and auditing';
COMMENT ON TABLE feedback IS 'Stores user feedback and feature requests';
COMMENT ON TABLE profile_changes IS 'Tracks profile change requests requiring approval';
COMMENT ON TABLE faq_articles IS 'Stores help center FAQ articles';
COMMENT ON TABLE support_tickets IS 'Stores support tickets from contact form';
COMMENT ON TABLE announcements IS 'Stores system announcements for users';
COMMENT ON TABLE article_ratings IS 'Stores user ratings for FAQ articles';
COMMENT ON TABLE admin_emails IS 'Stores admin email addresses for authentication';
COMMENT ON TABLE legal_documents IS 'Stores Terms of Service and Privacy Policy documents with version control';
COMMENT ON TABLE legal_document_history IS 'Archives previous versions of legal documents for audit trail';
COMMENT ON TABLE notification_preferences IS 'Stores SMS notification preferences for each supervisor';
COMMENT ON TABLE notification_history IS 'Tracks all sent SMS notifications for audit and delivery status';

-- Column comments for key fields
COMMENT ON COLUMN supervisors.firebase_uid IS 'Unique identifier from Firebase Authentication';
COMMENT ON COLUMN vacation_requests.total_hours IS 'Calculated as 8 hours per business day';
COMMENT ON COLUMN vacation_requests.return_date IS 'First day back to work after vacation';
COMMENT ON COLUMN legal_documents.document_type IS 'Type of legal document: terms_of_service or privacy_policy';
COMMENT ON COLUMN legal_documents.is_active IS 'Only one document per type can be active at a time';
COMMENT ON COLUMN legal_documents.version IS 'Version number for tracking document revisions';
COMMENT ON COLUMN legal_documents.effective_date IS 'Date when the document becomes effective';
COMMENT ON COLUMN notification_preferences.days_before_vacation IS 'Number of days before vacation start date to send notifications';
COMMENT ON COLUMN notification_preferences.notifications_per_day IS 'How many times per day to send notifications';
COMMENT ON COLUMN notification_preferences.notification_times IS 'Array of times during the day to send notifications';
COMMENT ON COLUMN notification_preferences.phone_number_override IS 'Override phone number if different from supervisor table';
COMMENT ON COLUMN notification_history.twilio_sid IS 'Twilio message SID for tracking';
COMMENT ON COLUMN notification_history.twilio_status IS 'Status returned by Twilio API';

-- =====================================================
-- SCHEMA SETUP COMPLETE
-- =====================================================
-- 
-- This schema file is organized for proper execution order:
-- 1. Drop statements (reverse dependency order)
-- 2. Functions (before triggers)
-- 3. Base tables (no foreign keys)
-- 4. Dependent tables (with foreign keys)
-- 5. Indexes (for performance)
-- 6. Triggers (after functions and tables)
-- 7. Views (after tables and indexes)
-- 8. Sample data (after all structures)
-- 9. Permissions (must be run as superuser)
-- 10. Documentation comments
--
-- To execute this schema:
-- 1. Connect as PostgreSQL superuser (postgres)
-- 2. Create database: CREATE DATABASE vacation_manager;
-- 3. Create user: CREATE USER vacation_user WITH PASSWORD 'your_password';
-- 4. Run this schema file: \i database/schema.sql
--
-- The schema includes all necessary tables, indexes, triggers, views,
-- functions, sample data, and permissions for the Don Miguel Vacation
-- Manager application to function properly.