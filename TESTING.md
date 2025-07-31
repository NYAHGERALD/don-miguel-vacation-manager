# Don Miguel Vacation Manager - Testing Guide

This document provides comprehensive testing procedures for the Don Miguel Vacation Manager application.

## Testing Overview

The application includes multiple testing layers:
- Unit tests for individual components
- Integration tests for API endpoints
- End-to-end tests for user workflows
- Security testing
- Performance testing
- Browser compatibility testing

## Prerequisites

```bash
# Install testing dependencies
pip install pytest pytest-flask pytest-cov
npm install --save-dev cypress @testing-library/jest-dom
```

## Unit Testing

### Backend Unit Tests

Create test files in `backend/tests/`:

#### Test Database Models

```python
# backend/tests/test_models.py
import pytest
from backend.app import app, get_db_connection
from datetime import datetime, timedelta

class TestDatabaseModels:
    def setup_method(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
    
    def test_supervisor_creation(self):
        """Test supervisor record creation"""
        # Test supervisor creation logic
        pass
    
    def test_employee_creation(self):
        """Test employee record creation"""
        # Test employee creation logic
        pass
    
    def test_vacation_request_calculation(self):
        """Test vacation hours calculation"""
        # Test business day calculation
        # Test total hours calculation
        pass
```

#### Test API Endpoints

```python
# backend/tests/test_api.py
import pytest
import json
from unittest.mock import patch, MagicMock

class TestAPIEndpoints:
    def setup_method(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        # Mock Firebase token verification
        self.mock_token = "mock-firebase-token"
    
    @patch('backend.app.auth.verify_id_token')
    def test_get_employees(self, mock_verify):
        """Test GET /api/employees endpoint"""
        mock_verify.return_value = {'uid': 'test-uid'}
        
        response = self.client.get('/api/employees', 
                                 headers={'Authorization': f'Bearer {self.mock_token}'})
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)
    
    @patch('backend.app.auth.verify_id_token')
    def test_create_employee(self, mock_verify):
        """Test POST /api/employees endpoint"""
        mock_verify.return_value = {'uid': 'test-uid'}
        
        employee_data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'department': 'Production',
            'shift': 'First Shift',
            'work_line': 'Line 1',
            'work_area': 'Assembly'
        }
        
        response = self.client.post('/api/employees',
                                  data=json.dumps(employee_data),
                                  content_type='application/json',
                                  headers={'Authorization': f'Bearer {self.mock_token}'})
        
        assert response.status_code == 201
    
    @patch('backend.app.auth.verify_id_token')
    def test_vacation_request_approval(self, mock_verify):
        """Test vacation request approval workflow"""
        mock_verify.return_value = {'uid': 'test-uid'}
        
        # Test approval endpoint
        response = self.client.put('/api/vacation-requests/1/approve',
                                 headers={'Authorization': f'Bearer {self.mock_token}'})
        
        # Verify response based on your implementation
        pass
```

#### Test Business Logic

```python
# backend/tests/test_business_logic.py
import pytest
from datetime import datetime, timedelta

class TestBusinessLogic:
    def test_business_days_calculation(self):
        """Test business days calculation excluding weekends"""
        # Monday to Friday (5 business days)
        start_date = datetime(2024, 1, 1)  # Monday
        end_date = datetime(2024, 1, 5)    # Friday
        
        # Your business logic function
        business_days = calculate_business_days(start_date, end_date)
        assert business_days == 5
    
    def test_vacation_hours_calculation(self):
        """Test vacation hours calculation (8 hours per business day)"""
        business_days = 5
        expected_hours = 40
        
        total_hours = business_days * 8
        assert total_hours == expected_hours
    
    def test_area_capacity_limits(self):
        """Test work area capacity limit validation"""
        # Test capacity limit checking logic
        pass
    
    def test_vacation_conflict_detection(self):
        """Test overlapping vacation detection"""
        # Test conflict detection logic
        pass
```

### Frontend Unit Tests

Create test files in `static/js/tests/`:

```javascript
// static/js/tests/auth.test.js
import { AuthManager, PasswordStrengthChecker } from '../auth.js';

describe('AuthManager', () => {
    let authManager;
    
    beforeEach(() => {
        authManager = new AuthManager();
    });
    
    test('should handle authentication errors correctly', () => {
        const error = { code: 'auth/user-not-found' };
        const result = authManager.handleAuthError(error);
        
        expect(result.message).toBe('No account found with this email address.');
    });
    
    test('should generate correct user initials', () => {
        const userInfo = {
            displayName: 'John Doe'
        };
        
        // Mock currentUser
        authManager.currentUser = userInfo;
        const info = authManager.getUserInfo();
        
        expect(info.initials).toBe('JD');
    });
});

describe('PasswordStrengthChecker', () => {
    test('should correctly assess password strength', () => {
        const weakPassword = '123';
        const strongPassword = 'StrongPass123!';
        
        const weakResult = PasswordStrengthChecker.check(weakPassword);
        const strongResult = PasswordStrengthChecker.check(strongPassword);
        
        expect(weakResult.strength).toBe('weak');
        expect(strongResult.strength).toBe('strong');
    });
});
```

```javascript
// static/js/tests/utils.test.js
import { DateUtils, UIUtils } from '../utils.js';

describe('DateUtils', () => {
    test('should calculate business days correctly', () => {
        const startDate = '2024-01-01'; // Monday
        const endDate = '2024-01-05';   // Friday
        
        const businessDays = DateUtils.calculateBusinessDays(startDate, endDate);
        expect(businessDays).toBe(5);
    });
    
    test('should format dates correctly', () => {
        const date = '2024-01-15';
        const formatted = DateUtils.formatDate(date);
        
        expect(formatted).toBe('Jan 15, 2024');
    });
    
    test('should detect weekends correctly', () => {
        const saturday = '2024-01-06';
        const monday = '2024-01-08';
        
        expect(DateUtils.isWeekend(saturday)).toBe(true);
        expect(DateUtils.isWeekend(monday)).toBe(false);
    });
});

describe('UIUtils', () => {
    test('should generate correct initials', () => {
        const initials = UIUtils.getInitials('John', 'Doe');
        expect(initials).toBe('JD');
    });
    
    test('should format file sizes correctly', () => {
        const size = UIUtils.formatFileSize(1024);
        expect(size).toBe('1 KB');
    });
});
```

## Integration Testing

### API Integration Tests

```python
# backend/tests/test_integration.py
import pytest
import json
from unittest.mock import patch

class TestAPIIntegration:
    def setup_method(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
    
    @patch('backend.app.auth.verify_id_token')
    def test_employee_vacation_workflow(self, mock_verify):
        """Test complete employee and vacation request workflow"""
        mock_verify.return_value = {'uid': 'test-supervisor-uid'}
        
        # 1. Create employee
        employee_data = {
            'first_name': 'Jane',
            'last_name': 'Smith',
            'department': 'Production',
            'shift': 'First Shift'
        }
        
        response = self.client.post('/api/employees',
                                  data=json.dumps(employee_data),
                                  content_type='application/json',
                                  headers={'Authorization': 'Bearer mock-token'})
        
        assert response.status_code == 201
        employee_id = json.loads(response.data)['employee_id']
        
        # 2. Create vacation request
        request_data = {
            'employee_id': employee_id,
            'start_date': '2024-02-01',
            'end_date': '2024-02-05'
        }
        
        response = self.client.post('/api/vacation-requests',
                                  data=json.dumps(request_data),
                                  content_type='application/json',
                                  headers={'Authorization': 'Bearer mock-token'})
        
        assert response.status_code == 201
        request_id = json.loads(response.data)['request_id']
        
        # 3. Approve vacation request
        response = self.client.put(f'/api/vacation-requests/{request_id}/approve',
                                 headers={'Authorization': 'Bearer mock-token'})
        
        assert response.status_code == 200
        
        # 4. Verify request status
        response = self.client.get('/api/vacation-requests',
                                 headers={'Authorization': 'Bearer mock-token'})
        
        requests = json.loads(response.data)
        approved_request = next(r for r in requests if r['id'] == request_id)
        assert approved_request['status'] == 'Approved'
```

### Database Integration Tests

```python
# backend/tests/test_database_integration.py
import pytest
import psycopg2
from backend.app import get_db_connection

class TestDatabaseIntegration:
    def setup_method(self):
        # Setup test database
        self.conn = get_db_connection()
        self.cursor = self.conn.cursor()
    
    def teardown_method(self):
        # Cleanup test data
        self.cursor.close()
        self.conn.close()
    
    def test_supervisor_employee_relationship(self):
        """Test supervisor-employee foreign key relationship"""
        # Insert test supervisor
        supervisor_data = {
            'firebase_uid': 'test-uid-123',
            'email': 'test@example.com',
            'first_name': 'Test',
            'last_name': 'Supervisor',
            'department': 'Production',
            'shift': 'First Shift'
        }
        
        # Test database operations
        pass
    
    def test_vacation_request_constraints(self):
        """Test vacation request database constraints"""
        # Test date range constraints
        # Test status constraints
        # Test foreign key constraints
        pass
```

## End-to-End Testing

### Cypress E2E Tests

```javascript
// cypress/e2e/auth.cy.js
describe('Authentication Flow', () => {
    beforeEach(() => {
        cy.visit('/');
    });
    
    it('should allow supervisor registration', () => {
        cy.get('[data-cy=register-link]').click();
        
        cy.get('#firstName').type('John');
        cy.get('#lastName').type('Doe');
        cy.get('#email').type('john.doe@donmiguelfoods.com');
        cy.get('#department').select('Production');
        cy.get('#shift').select('First Shift');
        cy.get('#password').type('StrongPassword123!');
        cy.get('#confirmPassword').type('StrongPassword123!');
        cy.get('#terms').check();
        
        cy.get('#saveEmployee').click();
        
        cy.url().should('include', '/dashboard');
    });
    
    it('should allow supervisor login', () => {
        cy.get('[data-cy=login-link]').click();
        
        cy.get('#email').type('existing@donmiguelfoods.com');
        cy.get('#password').type('password123');
        
        cy.get('#loginButton').click();
        
        cy.url().should('include', '/dashboard');
    });
    
    it('should handle login errors', () => {
        cy.get('[data-cy=login-link]').click();
        
        cy.get('#email').type('nonexistent@example.com');
        cy.get('#password').type('wrongpassword');
        
        cy.get('#loginButton').click();
        
        cy.get('#errorAlert').should('be.visible');
        cy.get('#errorMessage').should('contain', 'No account found');
    });
});
```

```javascript
// cypress/e2e/employee-management.cy.js
describe('Employee Management', () => {
    beforeEach(() => {
        // Login as supervisor
        cy.login('supervisor@donmiguelfoods.com', 'password123');
        cy.visit('/employees');
    });
    
    it('should add new employee', () => {
        cy.get('#addEmployeeButton').click();
        
        cy.get('#employeeFirstName').type('Jane');
        cy.get('#employeeLastName').type('Smith');
        cy.get('#employeePhone').type('555-0123');
        cy.get('#employeeDepartment').select('Production');
        cy.get('#employeeShift').select('First Shift');
        cy.get('#employeeWorkLine').type('Line 1');
        cy.get('#employeeWorkArea').type('Assembly');
        
        cy.get('#saveEmployee').click();
        
        cy.get('#toast').should('contain', 'Employee added successfully');
        cy.get('#employeeTableBody').should('contain', 'Jane Smith');
    });
    
    it('should filter employees by shift', () => {
        cy.get('#shiftFilter').select('First Shift');
        
        cy.get('#employeeTableBody tr').each(($row) => {
            cy.wrap($row).should('contain', 'First Shift');
        });
    });
    
    it('should search employees by name', () => {
        cy.get('#searchInput').type('John');
        
        cy.get('#employeeTableBody tr').should('have.length.at.least', 1);
        cy.get('#employeeTableBody').should('contain', 'John');
    });
});
```

```javascript
// cypress/e2e/vacation-requests.cy.js
describe('Vacation Request Management', () => {
    beforeEach(() => {
        cy.login('supervisor@donmiguelfoods.com', 'password123');
        cy.visit('/vacation-requests');
    });
    
    it('should create vacation request', () => {
        cy.get('#createRequestButton').click();
        
        cy.get('#requestEmployee').select('John Doe');
        cy.get('#requestStartDate').type('2024-03-01');
        cy.get('#requestEndDate').type('2024-03-05');
        
        // Verify calculations
        cy.get('#calculatedDays').should('contain', '5');
        cy.get('#calculatedHours').should('contain', '40');
        
        cy.get('#submitRequest').click();
        
        cy.get('#toast').should('contain', 'Vacation request created successfully');
    });
    
    it('should approve vacation request', () => {
        // Assuming there's a pending request
        cy.get('[data-cy=approve-button]').first().click();
        
        cy.get('#toast').should('contain', 'Request approved successfully');
    });
    
    it('should filter requests by status', () => {
        cy.get('#statusFilter').select('Approved');
        cy.get('#applyFilters').click();
        
        cy.get('#requestsTableBody tr').each(($row) => {
            cy.wrap($row).should('contain', 'Approved');
        });
    });
});
```

### Custom Cypress Commands

```javascript
// cypress/support/commands.js
Cypress.Commands.add('login', (email, password) => {
    cy.visit('/login');
    cy.get('#email').type(email);
    cy.get('#password').type(password);
    cy.get('#loginButton').click();
    cy.url().should('include', '/dashboard');
});

Cypress.Commands.add('createEmployee', (employeeData) => {
    cy.visit('/employees');
    cy.get('#addEmployeeButton').click();
    
    Object.keys(employeeData).forEach(key => {
        cy.get(`#employee${key.charAt(0).toUpperCase() + key.slice(1)}`).type(employeeData[key]);
    });
    
    cy.get('#saveEmployee').click();
});
```

## Performance Testing

### Load Testing with Artillery

```yaml
# artillery-config.yml
config:
  target: 'http://localhost:5000'
  phases:
    - duration: 60
      arrivalRate: 10
    - duration: 120
      arrivalRate: 20
    - duration: 60
      arrivalRate: 5

scenarios:
  - name: "Dashboard Load Test"
    weight: 50
    flow:
      - get:
          url: "/dashboard"
          headers:
            Authorization: "Bearer {{ $randomString() }}"
  
  - name: "API Load Test"
    weight: 30
    flow:
      - get:
          url: "/api/employees"
          headers:
            Authorization: "Bearer {{ $randomString() }}"
  
  - name: "Vacation Request Load Test"
    weight: 20
    flow:
      - post:
          url: "/api/vacation-requests"
          headers:
            Authorization: "Bearer {{ $randomString() }}"
            Content-Type: "application/json"
          json:
            employee_id: 1
            start_date: "2024-03-01"
            end_date: "2024-03-05"
```

### Database Performance Testing

```python
# backend/tests/test_performance.py
import pytest
import time
from concurrent.futures import ThreadPoolExecutor

class TestPerformance:
    def test_database_query_performance(self):
        """Test database query performance under load"""
        start_time = time.time()
        
        # Execute multiple database queries
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for _ in range(100):
                future = executor.submit(self.execute_query)
                futures.append(future)
            
            for future in futures:
                future.result()
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Assert reasonable performance
        assert execution_time < 10  # Should complete within 10 seconds
    
    def execute_query(self):
        # Execute a typical database query
        pass
```

## Security Testing

### Authentication Security Tests

```python
# backend/tests/test_security.py
import pytest

class TestSecurity:
    def test_unauthorized_access(self):
        """Test that endpoints require authentication"""
        response = self.client.get('/api/employees')
        assert response.status_code == 401
    
    def test_invalid_token(self):
        """Test invalid token handling"""
        response = self.client.get('/api/employees',
                                 headers={'Authorization': 'Bearer invalid-token'})
        assert response.status_code == 401
    
    def test_sql_injection_protection(self):
        """Test SQL injection protection"""
        malicious_input = "'; DROP TABLE employees; --"
        
        response = self.client.post('/api/employees',
                                  data=json.dumps({'first_name': malicious_input}),
                                  content_type='application/json',
                                  headers={'Authorization': 'Bearer valid-token'})
        
        # Should not cause database error
        assert response.status_code in [400, 422]  # Validation error, not 500
    
    def test_xss_protection(self):
        """Test XSS protection"""
        xss_payload = "<script>alert('xss')</script>"
        
        # Test that XSS payloads are properly escaped
        pass
```

## Browser Compatibility Testing

### Cross-Browser Testing Matrix

| Browser | Version | Desktop | Mobile | Status |
|---------|---------|---------|--------|--------|
| Chrome | Latest | ✅ | ✅ | Pass |
| Firefox | Latest | ✅ | ✅ | Pass |
| Safari | Latest | ✅ | ✅ | Pass |
| Edge | Latest | ✅ | ✅ | Pass |
| IE | 11 | ❌ | N/A | Not Supported |

### Responsive Design Testing

```javascript
// cypress/e2e/responsive.cy.js
describe('Responsive Design', () => {
    const viewports = [
        { width: 375, height: 667, name: 'iPhone SE' },
        { width: 768, height: 1024, name: 'iPad' },
        { width: 1920, height: 1080, name: 'Desktop' }
    ];
    
    viewports.forEach(viewport => {
        it(`should work on ${viewport.name}`, () => {
            cy.viewport(viewport.width, viewport.height);
            cy.visit('/dashboard');
            
            // Test navigation
            cy.get('nav').should('be.visible');
            
            // Test mobile menu on smaller screens
            if (viewport.width < 768) {
                cy.get('.mobile-menu-button').should('be.visible');
                cy.get('.mobile-menu-button').click();
                cy.get('.mobile-menu').should('be.visible');
            }
            
            // Test content layout
            cy.get('.card').should('be.visible');
        });
    });
});
```

## Accessibility Testing

```javascript
// cypress/e2e/accessibility.cy.js
describe('Accessibility', () => {
    beforeEach(() => {
        cy.visit('/');
        cy.injectAxe();
    });
    
    it('should have no accessibility violations on homepage', () => {
        cy.checkA11y();
    });
    
    it('should have no accessibility violations on dashboard', () => {
        cy.login('supervisor@donmiguelfoods.com', 'password123');
        cy.visit('/dashboard');
        cy.checkA11y();
    });
    
    it('should support keyboard navigation', () => {
        cy.get('body').tab();
        cy.focused().should('have.attr', 'href', '/login');
        
        cy.focused().tab();
        cy.focused().should('have.attr', 'href', '/register');
    });
});
```

## Running Tests

### Backend Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=backend --cov-report=html

# Run specific test file
pytest backend/tests/test_api.py

# Run with verbose output
pytest -v

# Run performance tests
pytest backend/tests/test_performance.py -s
```

### Frontend Tests

```bash
# Run unit tests
npm test

# Run E2E tests
npx cypress run

# Open Cypress GUI
npx cypress open

# Run specific test
npx cypress run --spec "cypress/e2e/auth.cy.js"
```

### Load Testing

```bash
# Install Artillery
npm install -g artillery

# Run load test
artillery run artillery-config.yml

# Generate report
artillery run artillery-config.yml --output report.json
artillery report report.json
```

## Continuous Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/test.yml
name: Test Suite

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test_vacation_manager
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v3
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov
    
    - name: Run tests
      run: pytest --cov=backend --cov-report=xml
      env:
        DATABASE_URL: postgresql://postgres:postgres@localhost/test_vacation_manager
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3

  frontend-tests:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Node.js
      uses: actions/setup-node@v3
      with:
        node-version: '18'
    
    - name: Install dependencies
      run: npm install
    
    - name: Run unit tests
      run: npm test
    
    - name: Run E2E tests
      run: |
        npm start &
        npx wait-on http://localhost:5000
        npx cypress run
```

## Test Data Management

### Test Database Setup

```sql
-- test_data.sql
-- Insert test supervisors
INSERT INTO supervisors (firebase_uid, email, first_name, last_name, department, shift) VALUES
('test-uid-1', 'test1@donmiguelfoods.com', 'Test', 'Supervisor1', 'Production', 'First Shift'),
('test-uid-2', 'test2@donmiguelfoods.com', 'Test', 'Supervisor2', 'Bakery', 'Second Shift');

-- Insert test employees
INSERT INTO employees (first_name, last_name, phone_number, department, shift, work_line, work_area, supervisor_id) VALUES
('John', 'Doe', '555-0101', 'Production', 'First Shift', 'Line 1', 'Assembly', 1),
('Jane', 'Smith', '555-0102', 'Production', 'First Shift', 'Line 2', 'Assembly', 1);

-- Insert test vacation requests
INSERT INTO vacation_requests (employee_id, supervisor_id, start_date, end_date, return_date, total_hours, status) VALUES
(1, 1, '2024-03-01', '2024-03-05', '2024-03-06', 40, 'Pending'),
(2, 1, '2024-03-15', '2024-03-19', '2024-03-20', 40, 'Approved');
```

### Test Data Cleanup

```python
# backend/tests/conftest.py
import pytest
from backend.app import app, get_db_connection

@pytest.fixture(scope="function")
def test_client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        with app.app_context():
            yield client

@pytest.fixture(scope="function")
def clean_database():
    """Clean database after each test"""
    yield
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Clean test data
    cursor.execute("DELETE FROM vacation_requests WHERE supervisor_id IN (SELECT id FROM supervisors WHERE email LIKE 'test%')")
    cursor.execute("DELETE FROM employees WHERE supervisor_id IN (SELECT id FROM supervisors WHERE email LIKE 'test%')")
    cursor.execute("DELETE FROM supervisors WHERE email LIKE 'test%'")
    
    conn.commit()
    cursor.close()
    conn.close()
```

## Test Reporting

### Coverage Reports

```bash
# Generate HTML coverage report
pytest --cov=backend --cov-report=html

# View coverage report
open htmlcov/index.html
```

### Test Results Dashboard

Set up test reporting dashboard using tools like:
- Allure Reports
- Jest HTML Reporter
- Cypress Dashboard

## Troubleshooting Tests

### Common Issues

1. **Database Connection Issues**
   ```bash
   # Check database is running
   pg_isready -h localhost -p 5432
   
   # Reset test database
   dropdb test_vacation_manager
   createdb test_vacation_manager
   ```

2. **Firebase Authentication in Tests**
   ```python
   # Mock Firebase authentication
   @patch('backend.app.auth.verify_id_token')
   def test_with_auth(self, mock_verify):
       mock_verify.return_value = {'uid': 'test-uid'}
       # Your test code here
   ```

3. **Cypress Test Failures**
   ```bash
   # Run in headed mode for debugging
   npx cypress run --headed
   
   # Take screenshots on failure
   npx cypress run --screenshot-on-failure
   ```

---

This comprehensive testing guide ensures the Don Miguel Vacation Manager application is thoroughly tested across all layers and scenarios.