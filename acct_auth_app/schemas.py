from pydantic import BaseModel, Field
from typing import Optional

# --- PYDANTIC SCHEMAS ---
class SignupRequest(BaseModel):
    user_id: Optional[str] = None
    password: Optional[str] = None

class UpdateRequest(BaseModel):
    nickname: Optional[str] = None
    comment: Optional[str] = None
