import base64
import re

from typing import Optional
from fastapi import FastAPI, Header, HTTPException, Request, Depends, status
from fastapi.responses import JSONResponse

from sqlalchemy.orm import Session

from . import models, schemas
from .database import SessionLocal, engine

# Create tables
models.Base.metadata.create_all(bind=engine)


# --- Helper Functions ---

# Create Basic Auth header string for testing. In real application, it is supposed to be generated and sent from client.
# Format: "Basic " + base64("user_id:password")
def generate_basic_auth_token(user_id: str, password: str) -> str:
    raw_str = f"{user_id}:{password}"
    b64_str = base64.b64encode(raw_str.encode('utf-8')).decode('utf-8')
    return f"Basic {b64_str}"


def validate_signup_input(user_id: str, password: str):
    # User ID: 6-20 chars, alphanumeric
    if not re.fullmatch(r"^[a-zA-Z0-9]{6,20}$", user_id):
        return "Input length is incorrect" if not (6 <= len(user_id) <= 20) else "Incorrect character pattern"
    
    # Password: 8-20 chars, alphanumeric + symbols (ASCII 33-126)
    if not re.fullmatch(r"^[!-~]{8,20}$", password):
        return "Input length is incorrect" if not (8 <= len(password) <= 20) else "Incorrect character pattern"
    
    return None

def validate_update_input(nickname: Optional[str], comment: Optional[str]):
    if nickname is not None:
        if len(nickname) > 30 or not nickname.isprintable():
             return "String length limit exceeded or containing invalid characters"

    if comment is not None:
        if len(comment) > 100 or not comment.isprintable():
             return "String length limit exceeded or containing invalid characters"
    
    return None

# --- FASTAPI APP SETUP ---
app = FastAPI()

# Dependency to get DB session per request
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(db: Session, authorization: str):
    """
    Decodes Basic Auth header and retrieves user from DB.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail={"message": "Authentication failed"})
    
    # Decode Basic Auth header and extract user_id and password
    try:
        prefix, encoded = authorization.split(" ", 1)
        if prefix != "Basic":
            raise HTTPException(status_code=401, detail={"message": "Authentication failed"})
        decoded = base64.b64decode(encoded).decode('utf-8')
        user_id, password = decoded.split(":", 1)
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=401, detail={"message": "Authentication failed"})

    # Find user in DB
    user = db.query(models.User).filter(models.User.user_id == user_id).first()
    
    if not user or user.password != password:
         raise HTTPException(status_code=401, detail={"message": "Authentication failed"})
    
    return user

# --- EXCEPTION HANDLER (Match Screenshot Format) ---
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    content = exc.detail
    if isinstance(content, str):
        content = {"message": content}
    return JSONResponse(status_code=exc.status_code, content=content)


# --- ENDPOINTS ---
@app.post("/signup")
def signup(req: schemas.SignupRequest, db: Session = Depends(get_db)):
    # 1. Check Missing Fields
    if not req.user_id or not req.password:
        raise HTTPException(status_code=400, detail={
            "message": "Account creation failed", 
            "cause": "Required user_id and password"
        })

    # 2. Check Input Format
    error_cause = validate_signup_input(req.user_id, req.password)
    if error_cause:
        raise HTTPException(status_code=400, detail={
            "message": "Account creation failed", 
            "cause": error_cause
        })

    # 3. Check Duplicate in DB
    existing_user = db.query(models.User).filter(models.User.user_id == req.user_id).first()
    if existing_user:
        raise HTTPException(status_code=400, detail={
            "message": "Account creation failed", 
            "cause": "Already same user_id is used"
        })

    # 4. Create User with token
    new_user = models.User(
        user_id=req.user_id,
        password=req.password,
        nickname=req.nickname if req.nickname else req.user_id, # Default nickname is user_id
        comment=req.comment if req.comment else "", # Default comment is empty string
        # auth_token=generate_basic_auth_token(req.user_id, req.password) # If need testing, generate token here. 
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "message": "Account successfully created",
        "user": {
            "user_id": new_user.user_id,
            "nickname": new_user.nickname,
            #"authorization token": new_user.auth_token # For testing purpose. 
        }
    }

@app.get("/users/{user_id}")
def get_user(
    user_id: str, 
    auth_header: str | None = Header(None),
    db: Session = Depends(get_db)
):

    # Find requested user
    target_user = db.query(models.User).filter(models.User.user_id == user_id).first()  
    if not target_user:
        raise HTTPException(status_code=404, detail={"message": "No user found"})
    
    # Validate Auth
    get_current_user(db, auth_header)

    # build response payload; omit comment key when it's an empty string
    user_payload = {
        "user_id": target_user.user_id,
        "nickname": target_user.nickname,
    }
    if target_user.comment:  # non‑empty string
        user_payload["comment"] = target_user.comment

    return {
        "message": "User details by user_id",
        "user": user_payload
    }

@app.patch("/users/{user_id}")
def update_user(
    user_id: str, 
    req: schemas.UpdateRequest, 
    auth_header: str | None = Header(None),
    db: Session = Depends(get_db)
):
    # 1. Auth & Permission Check
    current_user = get_current_user(db, auth_header)
    
    # Permission Check: Users can only update their own account information
    if current_user.user_id != user_id:
        raise HTTPException(status_code=403, detail={"message": "No permission for update"})

    # 2. Check existence (Though get_current_user guarantees it, good for safety)
    if not current_user:
        raise HTTPException(status_code=404, detail={"message": "No user found"})

    # 3. Check for empty body
    if req.nickname is None and req.comment is None:
         raise HTTPException(status_code=400, detail={
            "message": "User updation failed", 
            "cause": "Required nickname or comment"
        })

    # 4. Validate Inputs
    error_cause = validate_update_input(req.nickname, req.comment)
    if error_cause:
        raise HTTPException(status_code=400, detail={
            "message": "User updation failed", 
            "cause": error_cause
        })
    
    # 5. Update Fields
    if req.nickname is not None:
        # If empty string provided, reset to user_id.
        current_user.nickname = req.nickname if req.nickname else user_id
    
    if req.comment is not None:
        current_user.comment = req.comment

    db.commit()
    db.refresh(current_user)
    
    # build response payload; omit comment key when it's an empty string
    user_payload = {
        "user_id": current_user.user_id,
        "nickname": current_user.nickname,
    }
    if current_user.comment:  # non‑empty string
        user_payload["comment"] = current_user.comment

    return {
        "message": "User successfully updated",
        "user": user_payload
    }

@app.post("/close")
def close_account(
    auth_header: str | None = Header(None),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(db, auth_header)
    
    db.delete(current_user)
    db.commit()

    return {
        "message": "Account and user successfully removed"
    }

