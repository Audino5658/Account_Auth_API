import base64
import re
from typing import Optional
from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI()

# --- In-Memory Database ---
# Format: { "user_id": { "password": "...", "nickname": "...", "comment": "..." } }
users_db = {}

# --- Pydantic Models ---
class SignupRequest(BaseModel):
    user_id: Optional[str] = None
    password: Optional[str] = None

class UpdateRequest(BaseModel):
    nickname: Optional[str] = None
    comment: Optional[str] = None

# --- Helper Functions ---

def validate_auth(authorization: str = Header(None)):
    """
    Parses Basic Auth header and returns the user_id if valid.
    Raises 401 if invalid.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail={"message": "Authentication failed"})
    
    try:
        scheme, param = authorization.split()
        if scheme.lower() != 'basic':
            raise ValueError
        decoded = base64.b64decode(param).decode('utf-8')
        user_id, password = decoded.split(':', 1)
    except (ValueError, IndexError, ImportError):
        raise HTTPException(status_code=401, detail={"message": "Authentication failed"})

    if user_id not in users_db or users_db[user_id]['password'] != password:
        raise HTTPException(status_code=401, detail={"message": "Authentication failed"})
    
    return user_id

def validate_signup_input(user_id: str, password: str):
    # User ID: 6-20 chars, alphanumeric
    if not re.fullmatch(r"^[a-zA-Z0-9]{6,20}$", user_id):
        return "Input length is incorrect" if not (6 <= len(user_id) <= 20) else "Incorrect character pattern"
    
    # Password: 8-20 chars, alphanumeric + symbols (ASCII 33-126), no spaces/control
    # regex: ^[!-~]{8,20}$ matches ASCII 33 (!) to 126 (~)
    if not re.fullmatch(r"^[!-~]{8,20}$", password):
        return "Input length is incorrect" if not (8 <= len(password) <= 20) else "Incorrect character pattern"
    
    return None

def validate_update_input(nickname: Optional[str], comment: Optional[str]):
    # Nickname: Max 30, no control chars
    if nickname is not None:
        if len(nickname) > 30:
            return "String length limit exceeded or containing invalid characters"
        if not nickname.isprintable():
             return "String length limit exceeded or containing invalid characters"

    # Comment: Max 100, no control chars
    if comment is not None:
        if len(comment) > 100:
            return "String length limit exceeded or containing invalid characters"
        if not comment.isprintable():
             return "String length limit exceeded or containing invalid characters"
    
    return None

# --- Custom Exception Handler to match Screenshot JSON format ---
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    content = exc.detail
    # If detail is just a string, wrap it. If it's a dict (our custom errors), use as is.
    if isinstance(content, str):
        content = {"message": content}
    return JSONResponse(status_code=exc.status_code, content=content)


# --- Endpoints ---

@app.post("/signup")
def signup(req: SignupRequest):
    # 1. Check existence
    if not req.user_id or not req.password:
        raise HTTPException(status_code=400, detail={
            "message": "Account creation failed", 
            "cause": "Required user_id and password"
        })

    # 2. Check Input format
    error_cause = validate_signup_input(req.user_id, req.password)
    if error_cause:
        raise HTTPException(status_code=400, detail={
            "message": "Account creation failed", 
            "cause": error_cause
        })

    # 3. Check Duplicate
    if req.user_id in users_db:
        raise HTTPException(status_code=400, detail={
            "message": "Account creation failed", 
            "cause": "Already same user_id is used"
        })

    # 4. Create User
    users_db[req.user_id] = {
        "password": req.password,
        "nickname": req.user_id, # Default is user_id
        "comment": ""
    }

    return {
        "message": "Account successfully created",
        "user": {
            "user_id": req.user_id,
            "nickname": req.user_id
        }
    }

@app.get("/users/{user_id}")
def get_user(user_id: str, auth_user: str = Header(None, alias="Authorization")):
    # Validate Auth (We just need to ensure a valid user is logged in)
    try:
        current_user = validate_auth(auth_user)
    except HTTPException as e:
        # Step 3 screenshot implies generic 401 JSON
        raise e

    if user_id not in users_db:
        raise HTTPException(status_code=404, detail={"message": "No user found"})

    target_user = users_db[user_id]
    
    # Construct response
    return {
        "message": "User details by user_id",
        "user": {
            "user_id": user_id,
            "nickname": target_user["nickname"],
            "comment": target_user["comment"]
        }
    }

@app.patch("/users/{user_id}")
def update_user(user_id: str, req: UpdateRequest, auth_user: str = Header(None, alias="Authorization")):
    # 1. Auth Check
    current_user = validate_auth(auth_user)

    # 2. Permission Check (403 if trying to update someone else)
    if current_user != user_id:
        raise HTTPException(status_code=403, detail={"message": "No permission for update"})
    
    if user_id not in users_db:
        raise HTTPException(status_code=404, detail={"message": "No user found"})

    # 3. Required fields check
    if req.nickname is None and req.comment is None:
         raise HTTPException(status_code=400, detail={
            "message": "User updation failed", 
            "cause": "Required nickname or comment"
        })

    # 4. Validation
    error_cause = validate_update_input(req.nickname, req.comment)
    if error_cause:
        raise HTTPException(status_code=400, detail={
            "message": "User updation failed", 
            "cause": error_cause
        })
    
    # 5. Update Logic
    if req.nickname is not None:
        # If empty, reset to user_id (Pattern 1 in GET requirements implies this behavior)
        users_db[user_id]["nickname"] = req.nickname if req.nickname else user_id
    
    if req.comment is not None:
        users_db[user_id]["comment"] = req.comment # Empty string clears it
    
    return {
        "message": "User successfully updated",
        "user": {
            "user_id": user_id,
            "nickname": users_db[user_id]["nickname"],
            "comment": users_db[user_id]["comment"]
        }
    }

@app.post("/close")
def close_account(auth_user: str = Header(None, alias="Authorization")):
    current_user = validate_auth(auth_user)
    
    # Delete user
    if current_user in users_db:
        del users_db[current_user]

    return {
        "message": "Account and user successfully removed"
    }
