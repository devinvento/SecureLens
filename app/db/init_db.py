import logging
from sqlalchemy.orm import Session
from app.db.session import SessionLocal, engine
from app.db.base import Base
from app.models.user import User
from app.models.target import Target
from app.models.role_permission import Role, Permission
from app.core.security import get_password_hash, pwd_context

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db(db: Session) -> None:
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created.")

    # Create permissions from old project
    permissions_data = [
        # Container permissions
        ('view_containers', 'View Containers', 'View Docker containers and their status', 'containers'),
        ('start_containers', 'Start Containers', 'Start Docker containers', 'containers'),
        ('stop_containers', 'Stop Containers', 'Stop Docker containers', 'containers'),
        ('restart_containers', 'Restart Containers', 'Restart Docker containers', 'containers'),
        ('remove_containers', 'Remove Containers', 'Remove Docker containers', 'containers'),
        ('view_logs', 'View Container Logs', 'View Docker container logs', 'containers'),
        ('exec_commands', 'Execute Commands', 'Execute commands in containers', 'containers'),
        
        # User management permissions
        ('view_users', 'View Users', 'View user accounts', 'users'),
        ('create_users', 'Create Users', 'Create new user accounts', 'users'),
        ('edit_users', 'Edit Users', 'Edit user accounts', 'users'),
        ('delete_users', 'Delete Users', 'Delete user accounts', 'users'),
        ('manage_roles', 'Manage Roles', 'Manage user roles and permissions', 'users'),
        
        # System permissions
        ('view_dashboard', 'View Dashboard', 'Access main dashboard', 'system'),
        ('system_settings', 'System Settings', 'Modify system settings', 'system'),
        ('run_scans', 'Run Scans', 'Allow running vulnerability scans', 'security'),
        ('view_results', 'View Results', 'Allow viewing scan results', 'security'),
    ]
    
    db_perms = {}
    for name, display_name, description, category in permissions_data:
        perm = db.query(Permission).filter(Permission.name == name).first()
        if not perm:
            perm = Permission(
                name=name,
                display_name=display_name,
                description=description,
                category=category
            )
            db.add(perm)
            db.commit()
            db.refresh(perm)
        db_perms[name] = perm

    # Create roles from old project
    roles_data = [
        {
            'name': 'admin',
            'display_name': 'Administrator',
            'description': 'Full system access with all permissions',
            'is_system': True,
            'permissions': [p[0] for p in permissions_data]
        },
        {
            'name': 'manager',
            'display_name': 'Manager',
            'description': 'Can manage containers and view users',
            'is_system': True,
            'permissions': [
                'view_dashboard', 'view_containers', 'start_containers', 'stop_containers',
                'restart_containers', 'view_logs', 'view_users', 'run_scans', 'view_results'
            ]
        },
        {
            'name': 'developer',
            'display_name': 'Developer',
            'description': 'Can manage containers and execute commands',
            'is_system': True,
            'permissions': [
                'view_dashboard', 'view_containers', 'start_containers', 'stop_containers',
                'restart_containers', 'view_logs', 'exec_commands', 'run_scans'
            ]
        },
        {
            'name': 'viewer',
            'display_name': 'Viewer',
            'description': 'Read-only access',
            'is_system': True,
            'permissions': ['view_dashboard', 'view_containers', 'view_logs', 'view_results']
        }
    ]

    for r_data in roles_data:
        role = db.query(Role).filter(Role.name == r_data["name"]).first()
        if not role:
            role = Role(
                name=r_data["name"], 
                display_name=r_data["display_name"],
                description=r_data["description"],
                is_system=r_data["is_system"]
            )
            for p_name in r_data["permissions"]:
                role.permissions.append(db_perms[p_name])
            db.add(role)
            db.commit()
            logger.info(f"Role '{role.name}' created.")

    # Create an admin user if not exists
    user = db.query(User).filter(User.email == "admin@securelens.local").first()
    if not user:
        user = User(
            username="admin",
            email="admin@securelens.local",
            hashed_password=get_password_hash("admin123"),
            is_superuser=True
        )
        # Assign admin role
        admin_role = db.query(Role).filter(Role.name == "admin").first()
        if admin_role:
            user.roles.append(admin_role)
            
        db.add(user)
        logger.info("Admin user created.")
    else:
        # Check if hash is identifiable, if not, re-hash "admin123"
        if pwd_context.identify(user.hashed_password) is None:
            logger.warning("Unidentifiable hash for admin user. Re-hashing default password.")
            user.hashed_password = get_password_hash("admin123")
            db.add(user)
        # Ensure username is set
        if not user.username:
            user.username = "admin"
            db.add(user)

    # Seed Lab Mode targets
    targets_data = [
        {"name": "DVWA", "url": "http://dvwa.local", "description": "Damn Vulnerable Web App"},
        {"name": "Juice Shop", "url": "http://juice-shop.local", "description": "OWASP Juice Shop"},
        {"name": "bWAPP", "url": "http://bwapp.local", "description": "buggy web application"},
    ]

    for target_data in targets_data:
        target = db.query(Target).filter(Target.name == target_data["name"]).first()
        if not target:
            target = Target(**target_data)
            db.add(target)
            logger.info(f"Target '{target.name}' created.")

    db.commit()

def main() -> None:
    logger.info("Creating initial data")
    db = SessionLocal()
    init_db(db)
    logger.info("Initial data created")

if __name__ == "__main__":
    main()
