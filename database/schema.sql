-- Don Miguel Vacation Manager Database Schema
-- PostgreSQL Database Schema for Vacation Management System

-- Drop tables if they exist (for development/testing)
DROP TABLE IF EXISTS area_limits CASCADE;
DROP TABLE IF EXISTS vacation_requests CASCADE;
DROP TABLE IF EXISTS employees CASCADE;
DROP TABLE IF EXISTS supervisors CASCADE;

-- Create supervisors table
CREATE TABLE supervisors (
    id SERIAL PRIMARY KEY,
    firebase_uid VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    department VARCHAR(50) NOT NULL CHECK (department IN ('Production', 'Bakery', 'Warehouse')),
    shift VARCHAR(50) NOT NULL CHECK (shift IN ('First Shift', 'Second Shift')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create employees table
CREATE TABLE employees (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone_number VARCHAR(20),
    department VARCHAR(50) NOT NULL CHECK (department IN ('Production', 'Bakery', 'Warehouse')),
    shift VARCHAR(50) NOT NULL CHECK (shift IN ('First Shift', 'Second Shift')),
    work_line VARCHAR(100),
    work_area VARCHAR(100),
    supervisor_id INTEGER NOT NULL REFERENCES supervisors(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create vacation_requests table
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

-- Create area_limits table for managing concurrent vacation limits
CREATE TABLE area_limits (
    id SERIAL PRIMARY KEY,
    department VARCHAR(50) NOT NULL CHECK (department IN ('Production', 'Bakery', 'Warehouse')),
    work_line VARCHAR(100),
    work_area VARCHAR(100),
    max_concurrent_requests INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Unique constraint to prevent duplicate limits for same area/line combination
    UNIQUE(department, work_line, work_area)
);

-- Create audit_log table for tracking changes
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

-- Create indexes for better performance
CREATE INDEX idx_supervisors_firebase_uid ON supervisors(firebase_uid);
CREATE INDEX idx_supervisors_email ON supervisors(email);
CREATE INDEX idx_supervisors_department ON supervisors(department);

CREATE INDEX idx_employees_supervisor_id ON employees(supervisor_id);
CREATE INDEX idx_employees_department ON employees(department);
CREATE INDEX idx_employees_work_area ON employees(work_area, work_line);

CREATE INDEX idx_vacation_requests_employee_id ON vacation_requests(employee_id);
CREATE INDEX idx_vacation_requests_supervisor_id ON vacation_requests(supervisor_id);
CREATE INDEX idx_vacation_requests_status ON vacation_requests(status);
CREATE INDEX idx_vacation_requests_dates ON vacation_requests(start_date, end_date);
CREATE INDEX idx_vacation_requests_created_at ON vacation_requests(created_at);

CREATE INDEX idx_area_limits_department ON area_limits(department);
CREATE INDEX idx_area_limits_work_area ON area_limits(work_area, work_line);

-- Create triggers for updating updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_supervisors_updated_at BEFORE UPDATE ON supervisors
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_employees_updated_at BEFORE UPDATE ON employees
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_vacation_requests_updated_at BEFORE UPDATE ON vacation_requests
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_area_limits_updated_at BEFORE UPDATE ON area_limits
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert default area limits
INSERT INTO area_limits (department, work_line, work_area, max_concurrent_requests) VALUES
('Production', 'Line 1', 'Assembly', 2),
('Production', 'Line 2', 'Assembly', 2),
('Production', 'Line 3', 'Assembly', 1),
('Bakery', 'Mixing Line', 'Mixing Area', 1),
('Bakery', 'Baking Line', 'Oven Area', 1),
('Bakery', 'Packaging Line', 'Packaging Area', 2),
('Warehouse', 'Receiving', 'Dock Area', 1),
('Warehouse', 'Shipping', 'Dock Area', 1),
('Warehouse', 'Storage', 'Main Floor', 2);

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
    e.work_line,
    e.work_area,
    s.first_name || ' ' || s.last_name AS supervisor_name,
    s.email AS supervisor_email
FROM vacation_requests vr
JOIN employees e ON vr.employee_id = e.id
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
    p_work_line VARCHAR(100),
    p_work_area VARCHAR(100),
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
    AND (work_line = p_work_line OR work_line IS NULL)
    AND (work_area = p_work_area OR work_area IS NULL)
    ORDER BY 
        CASE WHEN work_line = p_work_line THEN 1 ELSE 2 END,
        CASE WHEN work_area = p_work_area THEN 1 ELSE 2 END
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
    AND e.work_line = p_work_line
    AND e.work_area = p_work_area
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

-- Sample data for testing (optional - remove in production)
-- INSERT INTO supervisors (firebase_uid, email, first_name, last_name, department, shift) VALUES
-- ('test-uid-1', 'supervisor1@donmiguelfoods.com', 'John', 'Smith', 'Production', 'First Shift'),
-- ('test-uid-2', 'supervisor2@donmiguelfoods.com', 'Jane', 'Doe', 'Bakery', 'Second Shift'),
-- ('test-uid-3', 'supervisor3@donmiguelfoods.com', 'Mike', 'Johnson', 'Warehouse', 'First Shift');

-- INSERT INTO employees (first_name, last_name, phone_number, department, shift, work_line, work_area, supervisor_id) VALUES
-- ('Alice', 'Brown', '555-0101', 'Production', 'First Shift', 'Line 1', 'Assembly', 1),
-- ('Bob', 'Wilson', '555-0102', 'Production', 'First Shift', 'Line 2', 'Assembly', 1),
-- ('Carol', 'Davis', '555-0103', 'Bakery', 'Second Shift', 'Mixing Line', 'Mixing Area', 2),
-- ('David', 'Miller', '555-0104', 'Warehouse', 'First Shift', 'Receiving', 'Dock Area', 3);

COMMENT ON TABLE supervisors IS 'Stores supervisor information linked to Firebase Authentication';
COMMENT ON TABLE employees IS 'Stores employee information managed by supervisors';
COMMENT ON TABLE vacation_requests IS 'Stores vacation requests with approval workflow';
COMMENT ON TABLE area_limits IS 'Defines maximum concurrent vacation limits per work area';
COMMENT ON TABLE audit_log IS 'Tracks all changes for compliance and auditing';

COMMENT ON COLUMN supervisors.firebase_uid IS 'Unique identifier from Firebase Authentication';
COMMENT ON COLUMN vacation_requests.total_hours IS 'Calculated as 8 hours per business day';
COMMENT ON COLUMN vacation_requests.return_date IS 'First day back to work after vacation';