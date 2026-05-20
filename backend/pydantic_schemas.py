from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime
from .db.models import Status 

class BirdResponse(BaseModel):
    model_config = ConfigDict(from_attributes = True)

    bird_name: str
    confidence_score: float
    start_time: float
    end_time: float

class JobCreate(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes = True)

    id: int
    status: Status
    created_at: datetime

    latitude: Optional[float] = None
    longitude: Optional[float] = None

    result_profile: Optional[str] = None        # optional until langchain is done
    classifications: List[BirdResponse] = []    # empty until lambda done with bird classification

class JobCreateResponse(BaseModel):
    job: JobResponse
    upload_url: str