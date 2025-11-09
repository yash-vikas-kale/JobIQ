from pydantic import BaseModel, EmailStr

# Pydantic schema for validation
class User(BaseModel):
    name: str
    email: EmailStr
    password: str
    created_at: str | None = None
