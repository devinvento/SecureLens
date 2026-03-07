from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.core.security import (
    generate_totp_secret, 
    get_totp_uri, 
    generate_qr_code_base64, 
    verify_totp,
    get_password_hash
)
from pydantic import BaseModel, EmailStr

router = APIRouter()

class TOTPVerify(BaseModel):
    token: str

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    is_active: bool = True
    is_superuser: bool = False

class UserUpdate(BaseModel):
    username: str = None
    email: EmailStr = None
    password: str = None
    is_active: bool = None
    is_superuser: bool = None

@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "is_active": current_user.is_active,
        "is_superuser": current_user.is_superuser,
        "totp_enabled": current_user.totp_enabled,
        "roles": [role.name for role in current_user.roles]
    }

@router.get("/", response_model=list)
def get_users(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
    users = db.query(User).all()
    return [{
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "is_active": u.is_active,
        "is_superuser": u.is_superuser,
        "totp_enabled": u.totp_enabled,
        "roles": [role.name for role in u.roles]
    } for u in users]

@router.post("/", response_model=dict)
def create_user(user_in: UserCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Check if user already exists
    user = db.query(User).filter((User.email == user_in.email) | (User.username == user_in.username)).first()
    if user:
        raise HTTPException(status_code=400, detail="User with this email or username already exists")
    
    user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        is_active=user_in.is_active,
        is_superuser=user_in.is_superuser
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "User created successfully", "id": user.id}

@router.put("/{user_id}", response_model=dict)
def update_user(user_id: int, user_in: UserUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user_in.username is not None:
        user.username = user_in.username
    if user_in.email is not None:
        user.email = user_in.email
    if user_in.password is not None:
        user.hashed_password = get_password_hash(user_in.password)
    if user_in.is_active is not None:
        user.is_active = user_in.is_active
    if user_in.is_superuser is not None:
        user.is_superuser = user_in.is_superuser
        
    db.commit()
    return {"message": "User updated successfully"}

@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
        
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully"}

@router.post("/2fa/setup")
def setup_2fa(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.totp_enabled:
        raise HTTPException(status_code=400, detail="2FA is already enabled")
    
    secret = generate_totp_secret()
    current_user.totp_secret = secret
    db.add(current_user)
    db.commit()
    
    uri = get_totp_uri(secret, current_user.email)
    qr_code = generate_qr_code_base64(uri)
    
    return {"secret": secret, "qr_code": qr_code}

@router.post("/2fa/enable")
def enable_2fa(data: TOTPVerify, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.totp_enabled:
        raise HTTPException(status_code=400, detail="2FA is already enabled")
    
    if not current_user.totp_secret:
        raise HTTPException(status_code=400, detail="2FA setup not initiated")
        
    if not verify_totp(current_user.totp_secret, data.token):
        raise HTTPException(status_code=401, detail="Invalid token")
        
    current_user.totp_enabled = True
    db.add(current_user)
    db.commit()
    
    return {"message": "2FA enabled successfully"}

@router.post("/2fa/disable")
def disable_2fa(data: TOTPVerify, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.totp_enabled:
        raise HTTPException(status_code=400, detail="2FA is not enabled")
        
    if not verify_totp(current_user.totp_secret, data.token):
        raise HTTPException(status_code=401, detail="Invalid token")
        
    current_user.totp_enabled = False
    current_user.totp_secret = None
    db.add(current_user)
    db.commit()
    
    return {"message": "2FA disabled successfully"}
