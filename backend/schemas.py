from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CustomerJourneyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    segment: str = Field(min_length=2, max_length=60)
    region: str = Field(min_length=2, max_length=60)
    risk_score: int = Field(ge=0, le=100)
    recommended_action: str = Field(min_length=2, max_length=160)


class CustomerJourneyRead(CustomerJourneyCreate):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RegisterRequest(BaseModel):
    email: str = Field(
        min_length=3,
        max_length=120,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )
    password: str = Field(min_length=4, max_length=128)


class UserRead(BaseModel):
    id: int
    email: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
