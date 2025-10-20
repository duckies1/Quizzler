#!/bin/bash

# Quizzler Backend Test Runner Script
# This script runs different types of tests based on the waterfall testing methodology

set -e  # Exit on any error

echo "🧪 Quizzler Backend Testing Suite"
echo "================================="

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if virtual environment is activated
if [[ "$VIRTUAL_ENV" == "" ]]; then
    print_warning "Virtual environment not detected. Please activate your venv first."
    print_warning "Run: source venv/bin/activate (Linux/Mac) or venv\\Scripts\\activate (Windows)"
fi

# Install test dependencies
print_status "Installing test dependencies..."
pip install -r requirements-test.txt

# Create reports directory
mkdir -p reports

# Function to run specific test types
run_unit_tests() {
    print_status "Running Unit Tests..."
    pytest tests/unit/ -v --tb=short -m "unit or not (integration or e2e or performance)"
}

run_integration_tests() {
    print_status "Running Integration Tests..."
    pytest tests/integration/ -v --tb=short -m "integration"
}

run_e2e_tests() {
    print_status "Running End-to-End Tests..."
    pytest tests/e2e/ -v --tb=short -m "e2e"
}

run_performance_tests() {
    print_status "Running Performance Tests..."
    pytest tests/performance/ -v --tb=short -m "performance"
}

run_security_tests() {
    print_status "Running Security Tests..."
    pytest tests/e2e/test_security.py -v --tb=short -m "security or not performance"
}

run_all_tests() {
    print_status "Running All Tests..."
    pytest tests/ -v --tb=short --cov=app --cov-report=html --cov-report=term-missing
}

# Check command line arguments
case "${1:-all}" in
    "unit")
        run_unit_tests
        ;;
    "integration")
        run_integration_tests
        ;;
    "e2e")
        run_e2e_tests
        ;;
    "performance")
        run_performance_tests
        ;;
    "security")
        run_security_tests
        ;;
    "all")
        print_status "Running complete test suite (Waterfall Testing Phase)..."
        echo ""
        
        print_status "📋 Test Plan Overview:"
        echo "1. Unit Tests - Test individual components"
        echo "2. Integration Tests - Test component interactions"
        echo "3. End-to-End Tests - Test complete user workflows"
        echo "4. Performance Tests - Test system performance"
        echo "5. Security Tests - Test security measures"
        echo ""
        
        # Run tests in waterfall order
        print_status "Phase 1: Unit Testing"
        run_unit_tests
        echo ""
        
        print_status "Phase 2: Integration Testing"
        run_integration_tests
        echo ""
        
        print_status "Phase 3: End-to-End Testing"
        run_e2e_tests
        echo ""
        
        print_status "Phase 4: Performance Testing"
        run_performance_tests
        echo ""
        
        print_status "Phase 5: Security Testing"
        run_security_tests
        echo ""
        
        print_status "📊 Generating comprehensive test report..."
        pytest tests/ --cov=app --cov-report=html --cov-report=term-missing --html=reports/complete_test_report.html --self-contained-html
        ;;
    "help"|"-h"|"--help")
        echo "Usage: ./run_tests.sh [test_type]"
        echo ""
        echo "Test types:"
        echo "  unit         - Run unit tests only"
        echo "  integration  - Run integration tests only"
        echo "  e2e          - Run end-to-end tests only"
        echo "  performance  - Run performance tests only"
        echo "  security     - Run security tests only"
        echo "  all          - Run complete test suite (default)"
        echo "  help         - Show this help message"
        echo ""
        echo "Examples:"
        echo "  ./run_tests.sh unit"
        echo "  ./run_tests.sh all"
        exit 0
        ;;
    *)
        print_error "Unknown test type: $1"
        print_error "Run './run_tests.sh help' for usage information"
        exit 1
        ;;
esac

print_status "✅ Testing completed!"
echo ""
echo "📁 Test reports generated in:"
echo "   - HTML Coverage Report: htmlcov/index.html"
echo "   - Test Report: reports/"
echo ""
print_status "Check the reports for detailed test results and coverage information."
