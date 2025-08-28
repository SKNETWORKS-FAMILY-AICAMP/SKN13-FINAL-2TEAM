from pydantic import BaseModel
from typing import Optional

class SurveyAnswers(BaseModel):
    q1_priority: Optional[str] = None
    q2_daily_look: Optional[str] = None
    q3_fit: Optional[str] = None
    q4_color: Optional[str] = None
    q5_direction: Optional[str] = None