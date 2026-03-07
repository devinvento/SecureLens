from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.role_permission import Role, Permission
from pydantic import BaseModel

router = APIRouter()

class RoleResponse(BaseModel):
    id: int
    name: str
    display_name: str
    description: str = None
    is_system: bool = False
    
    class Config:
        from_attributes = True

class PermissionResponse(BaseModel):
    id: int
    name: str
    display_name: str
    description: str = None
    category: str = None
    
    class Config:
        from_attributes = True

class RoleCreate(BaseModel):
    name: str
    display_name: str
    description: str = None

class RoleUpdate(BaseModel):
    name: str = None
    display_name: str = None
    description: str = None

class PermissionCreate(BaseModel):
    name: str
    display_name: str
    description: str = None
    category: str = None

class PermissionUpdate(BaseModel):
    name: str = None
    display_name: str = None
    description: str = None
    category: str = None

@router.get("/", response_model=List[RoleResponse])
def get_roles(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
    return db.query(Role).all()

@router.post("/", response_model=RoleResponse)
def create_role(role_in: RoleCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
    role = Role(
        name=role_in.name, 
        display_name=role_in.display_name,
        description=role_in.description
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    return role

@router.put("/{role_id}", response_model=RoleResponse)
def update_role(role_id: int, role_in: RoleUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
        
    if role_in.name:
        role.name = role_in.name
    if role_in.display_name:
        role.display_name = role_in.display_name
    if role_in.description:
        role.description = role_in.description
        
    db.commit()
    db.refresh(role)
    return role

@router.delete("/{role_id}")
def delete_role(role_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    if role.is_system:
        raise HTTPException(status_code=400, detail="Cannot delete a system role")
        
    db.delete(role)
    db.commit()
    return {"message": "Role deleted successfully"}

@router.get("/permissions", response_model=List[PermissionResponse])
def get_permissions(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
    return db.query(Permission).all()

@router.post("/permissions", response_model=PermissionResponse)
def create_permission(perm_in: PermissionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
    perm = Permission(
        name=perm_in.name, 
        display_name=perm_in.display_name,
        description=perm_in.description,
        category=perm_in.category
    )
    db.add(perm)
    db.commit()
    db.refresh(perm)
    return perm

@router.put("/permissions/{permission_id}", response_model=PermissionResponse)
def update_permission(permission_id: int, perm_in: PermissionUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
    perm = db.query(Permission).filter(Permission.id == permission_id).first()
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")
        
    if perm_in.name:
        perm.name = perm_in.name
    if perm_in.display_name:
        perm.display_name = perm_in.display_name
    if perm_in.description:
        perm.description = perm_in.description
    if perm_in.category:
        perm.category = perm_in.category
        
    db.commit()
    db.refresh(perm)
    return perm

@router.delete("/permissions/{permission_id}")
def delete_permission(permission_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
    perm = db.query(Permission).filter(Permission.id == permission_id).first()
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")
    db.delete(perm)
    db.commit()
    return {"message": "Permission deleted successfully"}

@router.post("/{role_id}/permissions/{permission_id}")
def assign_permission_to_role(role_id: int, permission_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
    role = db.query(Role).filter(Role.id == role_id).first()
    perm = db.query(Permission).filter(Permission.id == permission_id).first()
    if not role or not perm:
        raise HTTPException(status_code=404, detail="Role or Permission not found")
    if perm not in role.permissions:
        role.permissions.append(perm)
        db.commit()
    return {"message": "Permission assigned to role successfully"}

@router.delete("/{role_id}/permissions/{permission_id}")
def remove_permission_from_role(role_id: int, permission_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
    role = db.query(Role).filter(Role.id == role_id).first()
    perm = db.query(Permission).filter(Permission.id == permission_id).first()
    if not role or not perm:
        raise HTTPException(status_code=404, detail="Role or Permission not found")
    if perm in role.permissions:
        role.permissions.remove(perm)
        db.commit()
    return {"message": "Permission removed from role successfully"}

@router.post("/{user_id}/assign/{role_id}")
def assign_role(user_id: int, role_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    user = db.query(User).filter(User.id == user_id).first()
    role = db.query(Role).filter(Role.id == role_id).first()
    
    if not user or not role:
        raise HTTPException(status_code=404, detail="User or Role not found")
        
    if role not in user.roles:
        user.roles.append(role)
        db.commit()
        
    return {"message": "Role assigned successfully"}
