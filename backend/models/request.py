from pydantic import BaseModel, Field


class UserInput(BaseModel):
    city: str = Field(default="", description="City the user is in")
    budget: float = Field(default=0, description="Total budget for the day in local currency")
    available_time: str = Field(default="", description="Free-text time available, e.g. '4 hours'")
    mood: str = Field(default="", description="Free-text mood description")
    interests: list[str] = Field(default_factory=list, description="List of interests")
    constraints: list[str] = Field(default_factory=list, description="List of constraints")
