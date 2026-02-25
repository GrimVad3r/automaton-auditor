#!/usr/bin/env bash
# Test runner script for Automaton Auditor
# Provides different test running modes

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

# Test modes
run_all_tests() {
    print_header "Running All Tests"
    uv run pytest tests/ -v
}

run_unit_tests() {
    print_header "Running Unit Tests Only"
    uv run pytest tests/ -v -m "not slow and not integration and not requires_api"
}

run_integration_tests() {
    print_header "Running Integration Tests"
    uv run pytest tests/ -v -m "integration"
}

run_security_tests() {
    print_header "Running Security Tests"
    uv run pytest tests/ -v -m "security"
}

run_fast_tests() {
    print_header "Running Fast Tests"
    uv run pytest tests/ -v -m "not slow"
}

run_with_coverage() {
    print_header "Running Tests with Coverage Report"
    uv run pytest tests/ -v --cov=src --cov-report=html --cov-report=term-missing
    print_success "Coverage report generated at htmlcov/index.html"
}

run_specific_file() {
    print_header "Running Tests in $1"
    uv run pytest "$1" -v
}

run_parallel() {
    print_header "Running Tests in Parallel"
    uv run pytest tests/ -v -n auto
}

show_help() {
    cat << EOF
Automaton Auditor Test Runner

Usage: ./run_tests.sh [COMMAND]

Commands:
  all             Run all tests (default)
  unit            Run only unit tests (fast, no API calls)
  integration     Run integration tests
  security        Run security-focused tests
  fast            Run fast tests only (excludes slow tests)
  coverage        Run tests with coverage report
  parallel        Run tests in parallel
  file <path>     Run tests in specific file
  watch           Run tests in watch mode
  clean           Clean test artifacts

Examples:
  ./run_tests.sh                          # Run all tests
  ./run_tests.sh unit                     # Run unit tests only
  ./run_tests.sh file tests/test_core_state.py
  ./run_tests.sh coverage                 # Generate coverage report

EOF
}

watch_mode() {
    print_header "Watch Mode"
    print_info "Watching for changes... Press Ctrl+C to stop"
    uv run ptw tests/ -- -v -m "not slow"
}

clean_artifacts() {
    print_header "Cleaning Test Artifacts"
    rm -rf .pytest_cache
    rm -rf htmlcov
    rm -f .coverage
    rm -f coverage.xml
    rm -rf .mypy_cache
    rm -rf __pycache__
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    print_success "Cleaned test artifacts"
}

# Main script
main() {
    # Check if uv is installed
    if ! command -v uv &> /dev/null; then
        print_error "uv not found. Install it first: python -m pip install --upgrade uv"
        exit 1
    fi

    # Parse command
    case "${1:-all}" in
        all)
            run_all_tests
            ;;
        unit)
            run_unit_tests
            ;;
        integration)
            run_integration_tests
            ;;
        security)
            run_security_tests
            ;;
        fast)
            run_fast_tests
            ;;
        coverage)
            run_with_coverage
            ;;
        parallel)
            run_parallel
            ;;
        file)
            if [ -z "$2" ]; then
                print_error "Please specify a file path"
                exit 1
            fi
            run_specific_file "$2"
            ;;
        watch)
            watch_mode
            ;;
        clean)
            clean_artifacts
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "Unknown command: $1"
            show_help
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
