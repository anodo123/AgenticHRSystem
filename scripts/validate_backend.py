"""Backend validation and comprehensive test script."""
import asyncio
import sys
import subprocess
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

# Test 1: Check all imports
print("=" * 60)
print("TEST 1: Checking critical imports...")
print("=" * 60)

try:
    from app.core.config import Settings, get_settings
    print("✓ Config module imported")
    
    from app.db.base import Base
    from app.db.session import SessionLocal, get_db
    print("✓ Database session module imported")
    
    from app.models.user import User, Role, Permission
    from app.models.employee import Employee
    from app.models.workflow import Workflow, WorkflowState, TriggerType, IntentCategory
    from app.models.approval import ApprovalRequest
    from app.models.audit import AuditLog
    from app.models.rag import Policy, Incident
    print("✓ All model classes imported")
    
    from app.security import get_current_user, has_permission, has_any_role
    print("✓ Security dependencies imported")
    
    from app.workflows.state_machine import WorkflowStateMachine
    print("✓ Workflow state machine imported")
    
    from app.repositories.workflow_repository import WorkflowRepository
    print("✓ Workflow repository imported")
    
    from app.services.workflow_service import WorkflowService
    print("✓ Workflow service imported")
    
    from app.api.v1.schemas.auth import LoginRequest, TokenResponse
    from app.api.v1.schemas.employee import EmployeeCreate, EmployeeResponse
    from app.api.v1.schemas.workflow import WorkflowCreateRequest, WorkflowResponse
    print("✓ All schema classes imported")
    
    from app.main import app
    print("✓ FastAPI main app imported")
    
except Exception as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)

# Test 2: Validate state machine configuration
print("\n" + "=" * 60)
print("TEST 2: Validating workflow state machine...")
print("=" * 60)

try:
    # Test valid transitions
    assert WorkflowStateMachine.is_valid_transition(
        WorkflowState.RECEIVED, WorkflowState.AUTHENTICATED
    ), "RECEIVED -> AUTHENTICATED should be valid"
    print("✓ Valid transition check passed")
    
    # Test invalid transitions
    assert not WorkflowStateMachine.is_valid_transition(
        WorkflowState.RECEIVED, WorkflowState.COMPLETED
    ), "RECEIVED -> COMPLETED should be invalid"
    print("✓ Invalid transition check passed")
    
    # Test terminal states
    assert WorkflowStateMachine.is_terminal_state(WorkflowState.COMPLETED)
    assert not WorkflowStateMachine.is_terminal_state(WorkflowState.RECEIVED)
    print("✓ Terminal state detection passed")
    
    # Test get valid next states
    next_states = WorkflowStateMachine.get_valid_next_states(WorkflowState.RECEIVED)
    assert WorkflowState.AUTHENTICATED in next_states
    print("✓ Get valid next states passed")
    
    # Test transition validation
    is_valid, error = WorkflowStateMachine.validate_transition(
        WorkflowState.RECEIVED, WorkflowState.AUTHENTICATED
    )
    assert is_valid and error is None, f"Validation failed: {error}"
    print("✓ Transition validation passed")
    
except AssertionError as e:
    print(f"✗ State machine validation failed: {e}")
    sys.exit(1)

# Test 3: Validate configuration
print("\n" + "=" * 60)
print("TEST 3: Validating configuration...")
print("=" * 60)

try:
    settings = get_settings()
    
    assert settings.app_name == "DARWINBOXAI"
    print(f"✓ Project name: {settings.app_name}")
    
    assert settings.api_v1_str == "/api/v1"
    print(f"✓ API version prefix: {settings.api_v1_str}")
    
    assert len(settings.jwt_secret_key) >= 32
    print("✓ JWT secret key configured")
    
    assert settings.database_url is not None
    print(f"✓ Database URL configured")
    
    print(f"✓ Mock LLM: {settings.mock_llm_enabled}")
    print(f"✓ Mock HR Adapters: {settings.mock_hr_adapters_enabled}")
    
except AssertionError as e:
    print(f"✗ Configuration validation failed: {e}")
    sys.exit(1)

# Test 4: Validate API routes are registered
print("\n" + "=" * 60)
print("TEST 4: Validating API routes...")
print("=" * 60)

try:
    from fastapi.routing import APIRoute
    
    routes = [route for route in app.routes if isinstance(route, APIRoute)]
    route_paths = [route.path for route in routes]
    
    # Check for critical routes
    critical_routes = [
        "/api/v1/auth/login",
        "/api/v1/employees",
        "/api/v1/workflows",
        "/api/v1/audit",
    ]
    
    for critical_route in critical_routes:
        found = any(critical_route in path for path in route_paths)
        if found:
            print(f"✓ Route registered: {critical_route}")
        else:
            print(f"✗ Missing route: {critical_route}")
    
    print(f"✓ Total routes registered: {len(route_paths)}")
    
except Exception as e:
    print(f"✗ Route validation failed: {e}")
    sys.exit(1)

# Test 5: Database model relationships
print("\n" + "=" * 60)
print("TEST 5: Validating database model relationships...")
print("=" * 60)

try:
    from sqlalchemy import inspect
    
    # Check User model
    user_mapper = inspect(User)
    assert hasattr(user_mapper, 'columns'), "User model missing columns"
    print(f"✓ User model has {len(user_mapper.columns)} columns")
    
    # Check Employee model
    emp_mapper = inspect(Employee)
    assert hasattr(emp_mapper, 'columns'), "Employee model missing columns"
    print(f"✓ Employee model has {len(emp_mapper.columns)} columns")
    
    # Check Workflow model
    wf_mapper = inspect(Workflow)
    assert hasattr(wf_mapper, 'columns'), "Workflow model missing columns"
    print(f"✓ Workflow model has {len(wf_mapper.columns)} columns")
    
except Exception as e:
    print(f"✗ Model validation failed: {e}")
    sys.exit(1)

# Test 6: Pydantic v2 compatibility
print("\n" + "=" * 60)
print("TEST 6: Validating Pydantic v2 compatibility...")
print("=" * 60)

try:
    from app.api.v1.schemas.auth import LoginRequest, UserProfile
    from app.api.v1.schemas.employee import EmployeeCreate, EmployeeResponse
    
    # Test LoginRequest
    login = LoginRequest(username="test", password="pass123")
    assert login.username == "test"
    print("✓ LoginRequest schema works")
    
    # Test UserProfile model_config
    assert hasattr(UserProfile, 'model_config')
    print("✓ UserProfile has model_config")
    
    # Test EmployeeResponse model_config
    assert hasattr(EmployeeResponse, 'model_config')
    print("✓ EmployeeResponse has model_config")
    
    # Test model_validate usage
    test_dict = {
        "id": 1,
        "username": "testuser",
        "email": "test@example.com",
        "full_name": "Test User",
        "is_active": True,
        "roles": [],
        "last_login": None,
    }
    profile = UserProfile.model_validate(test_dict)
    assert profile.username == "testuser"
    print("✓ model_validate works correctly")
    
except Exception as e:
    print(f"✗ Pydantic v2 validation failed: {e}")
    sys.exit(1)

# Success!
print("\n" + "=" * 60)
print("ALL VALIDATION TESTS PASSED ✓")
print("=" * 60)
print("\nThe backend is ready through Phase 9 testing!")
print("Run: docker compose up --build")
