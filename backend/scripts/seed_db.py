"""Database seed script."""
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from app.db.session import SessionLocal, engine
from app.db.base import Base
from app.models import (
    Permission,
    Role,
    User,
    Employee,
    EmploymentStatus,
    EmployeeType,
    PayrollRecord,
)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def seed_permissions(db: Session):
    """Seed permissions."""
    permissions_data = [
        ("view_workflows", "View workflows"),
        ("create_workflow", "Create new workflow"),
        ("view_approvals", "View approval requests"),
        ("approve_request", "Approve requests"),
        ("reject_request", "Reject requests"),
        ("manage_policies", "Manage HR policies"),
        ("manage_tasks", "Manage scheduled tasks"),
        ("view_audit", "View audit logs"),
        ("manage_users", "Manage users"),
        ("manage_roles", "Manage roles"),
        ("view_employees", "View employee directory"),
        ("modify_employee_data", "Modify employee data"),
        ("view_payroll", "View payroll data"),
        ("process_payroll", "Process payroll"),
    ]

    for name, desc in permissions_data:
        if not db.query(Permission).filter(Permission.name == name).first():
            perm = Permission(name=name, description=desc)
            db.add(perm)

    db.commit()


def seed_roles(db: Session):
    """Seed roles with permissions."""
    roles_config = {
        "EMPLOYEE": ["view_workflows", "create_workflow"],
        "MANAGER": ["view_workflows", "view_approvals", "view_employees"],
        "HR_OPERATIONS": [
            "view_workflows",
            "view_approvals",
            "view_employees",
            "modify_employee_data",
            "view_audit",
        ],
        "PAYROLL_SPECIALIST": [
            "view_workflows",
            "view_approvals",
            "approve_request",
            "view_payroll",
            "process_payroll",
        ],
        "COMPLIANCE_OFFICER": [
            "view_workflows",
            "view_approvals",
            "approve_request",
            "view_audit",
        ],
        "HR_ADMIN": [
            "view_workflows",
            "create_workflow",
            "view_approvals",
            "approve_request",
            "reject_request",
            "manage_policies",
            "manage_tasks",
            "view_employees",
            "modify_employee_data",
            "view_audit",
        ],
        "SYSTEM_ADMIN": [
            "view_workflows",
            "view_approvals",
            "approve_request",
            "manage_policies",
            "manage_tasks",
            "view_employees",
            "modify_employee_data",
            "view_audit",
            "manage_users",
            "manage_roles",
            "view_payroll",
        ],
        "AUDITOR": ["view_workflows", "view_audit"],
    }

    for role_name, perm_names in roles_config.items():
        role = db.query(Role).filter(Role.name == role_name).first()
        if not role:
            role = Role(name=role_name, description=f"{role_name} Role")
            db.add(role)
            db.flush()

        # Add permissions
        for perm_name in perm_names:
            perm = db.query(Permission).filter(Permission.name == perm_name).first()
            if perm and perm not in role.permissions:
                role.permissions.append(perm)

    db.commit()


def seed_users(db: Session):
    """Seed demo users."""
    roles = {
        "EMPLOYEE": db.query(Role).filter(Role.name == "EMPLOYEE").first(),
        "MANAGER": db.query(Role).filter(Role.name == "MANAGER").first(),
        "PAYROLL_SPECIALIST": db.query(Role).filter(Role.name == "PAYROLL_SPECIALIST").first(),
        "COMPLIANCE_OFFICER": db.query(Role).filter(Role.name == "COMPLIANCE_OFFICER").first(),
        "HR_ADMIN": db.query(Role).filter(Role.name == "HR_ADMIN").first(),
        "SYSTEM_ADMIN": db.query(Role).filter(Role.name == "SYSTEM_ADMIN").first(),
    }

    users_data = [
        {
            "username": "employee",
            "email": "employee@darwinboxai.local",
            "full_name": "John Smith",
            "role_key": "EMPLOYEE",
            "password": "demo123!",
        },
        {
            "username": "manager",
            "email": "manager@darwinboxai.local",
            "full_name": "Sarah Johnson",
            "role_key": "MANAGER",
            "password": "demo123!",
        },
        {
            "username": "payroll",
            "email": "payroll@darwinboxai.local",
            "full_name": "Mike Davis",
            "role_key": "PAYROLL_SPECIALIST",
            "password": "demo123!",
        },
        {
            "username": "compliance",
            "email": "compliance@darwinboxai.local",
            "full_name": "Emma Wilson",
            "role_key": "COMPLIANCE_OFFICER",
            "password": "demo123!",
        },
        {
            "username": "admin",
            "email": "admin@darwinboxai.local",
            "full_name": "Alex Brown",
            "role_key": "HR_ADMIN",
            "password": "demo123!",
        },
        {
            "username": "sysadmin",
            "email": "sysadmin@darwinboxai.local",
            "full_name": "System Administrator",
            "role_key": "SYSTEM_ADMIN",
            "password": "demo123!",
            "is_superuser": True,
        },
    ]

    for user_data in users_data:
        if not db.query(User).filter(User.username == user_data["username"]).first():
            user = User(
                username=user_data["username"],
                email=user_data["email"],
                full_name=user_data["full_name"],
                hashed_password=hash_password(user_data["password"]),
                is_superuser=user_data.get("is_superuser", False),
            )
            user.roles.append(roles[user_data["role_key"]])
            db.add(user)

    db.commit()


def seed_employees(db: Session):
    """Seed sample employees."""
    employees_data = [
        {
            "employee_number": "EMP001",
            "first_name": "John",
            "last_name": "Smith",
            "email": "john.smith@darwinboxai.local",
            "department": "Engineering",
            "business_unit": "Platform",
            "country": "US",
            "role": "Senior Engineer",
            "hire_date": datetime.utcnow() - timedelta(days=365*3),
            "salary": 120000,
        },
        {
            "employee_number": "EMP002",
            "first_name": "Sarah",
            "last_name": "Johnson",
            "email": "sarah.johnson@darwinboxai.local",
            "department": "HR",
            "business_unit": "Operations",
            "country": "US",
            "role": "HR Manager",
            "hire_date": datetime.utcnow() - timedelta(days=365*2),
            "salary": 95000,
        },
        {
            "employee_number": "EMP003",
            "first_name": "Mike",
            "last_name": "Davis",
            "email": "mike.davis@darwinboxai.local",
            "department": "Finance",
            "business_unit": "Finance",
            "country": "US",
            "role": "Payroll Specialist",
            "hire_date": datetime.utcnow() - timedelta(days=365),
            "salary": 85000,
        },
        {
            "employee_number": "EMP004",
            "first_name": "Emma",
            "last_name": "Wilson",
            "email": "emma.wilson@darwinboxai.local",
            "department": "Compliance",
            "business_unit": "Operations",
            "country": "US",
            "role": "Compliance Officer",
            "hire_date": datetime.utcnow() - timedelta(days=180),
            "salary": 90000,
        },
        {
            "employee_number": "EMP005",
            "first_name": "Alex",
            "last_name": "Brown",
            "email": "alex.brown@darwinboxai.local",
            "department": "HR",
            "business_unit": "Operations",
            "country": "US",
            "role": "HR Administrator",
            "hire_date": datetime.utcnow() - timedelta(days=200),
            "salary": 75000,
        },
    ]

    for emp_data in employees_data:
        if not db.query(Employee).filter(Employee.employee_number == emp_data["employee_number"]).first():
            emp = Employee(
                employee_number=emp_data["employee_number"],
                first_name=emp_data["first_name"],
                last_name=emp_data["last_name"],
                email=emp_data["email"],
                department=emp_data["department"],
                business_unit=emp_data["business_unit"],
                country=emp_data["country"],
                legal_entity="Global",
                role=emp_data["role"],
                employment_status=EmploymentStatus.ACTIVE,
                employee_type=EmployeeType.FULL_TIME,
                hire_date=emp_data["hire_date"],
                salary=emp_data["salary"],
                currency="USD",
                data_sync_timestamp=datetime.utcnow(),
            )
            db.add(emp)

    db.commit()


def seed_sample_payroll(db: Session):
    """Seed sample payroll data."""
    employees = db.query(Employee).all()
    
    for emp in employees[:2]:  # Add payroll for first 2 employees
        # Create payroll records for last 3 months
        for i in range(3):
            period = (datetime.utcnow() - timedelta(days=30*i)).strftime("%Y-%m")
            
            if not db.query(PayrollRecord).filter(
                PayrollRecord.employee_id == emp.id,
                PayrollRecord.payroll_period == period
            ).first():
                record = PayrollRecord(
                    employee_id=emp.id,
                    payroll_period=period,
                    gross_salary=emp.salary / 12,
                    overtime_amount=500 * (i + 1),  # Varying overtime amounts
                    deductions=emp.salary / 12 * Decimal("0.15"),
                    net_salary=(
                        (emp.salary / 12)
                        + Decimal(500 * (i + 1))
                        - (emp.salary / 12 * Decimal("0.15"))
                    ),
                    status="PROCESSED",
                )
                db.add(record)

    db.commit()


def main():
    """Run all seeding."""
    # Create tables
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        print("Seeding permissions...")
        seed_permissions(db)
        
        print("Seeding roles...")
        seed_roles(db)
        
        print("Seeding users...")
        seed_users(db)
        
        print("Seeding employees...")
        seed_employees(db)
        
        print("Seeding sample payroll data...")
        seed_sample_payroll(db)
        
        print("✓ Database seeding complete!")
    except Exception as e:
        print(f"✗ Error during seeding: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
