from typing import List
from pydantic import BaseModel

class TagModel(BaseModel):
    Key: str
    Value: str

class InstanceModel(BaseModel):
    ImageId: str
    InstanceType: str
    LaunchTime: str
    Tags: List[TagModel]

class ReservationModel(BaseModel):
    Instances: List[InstanceModel]

class RootModel(BaseModel):
    Reservations: List[ReservationModel]
