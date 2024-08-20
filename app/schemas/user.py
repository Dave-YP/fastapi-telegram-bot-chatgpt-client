from pydantic import BaseModel, EmailStr


class RegisterUser(BaseModel):
    email: EmailStr
    password: str
    message: str


class Question(BaseModel):
    user_id: str
    question: str


class UserResponse(BaseModel):
    id: int
    email: str
    tokens: int

    class Config:
        from_attributes = True
