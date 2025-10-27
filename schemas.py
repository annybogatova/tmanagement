from pydantic import BaseModel, Field, conint
from typing import List
from datetime import date


# --- Входные (create/update) ---
class PredModel(BaseModel):
    pred: List[int]


class TaskCreate(BaseModel):
    task: str
    duration: conint(gt=0)  # > 0
    resource: conint(ge=0)  # >= 0


class OrderCreate(BaseModel):
    order_name: str
    start_date: date


# --- Выходные (response) ---
class TaskModel(BaseModel):
    id: int
    task: str
    duration: int
    resource: int
    preds: List[int] = Field(default_factory=list)  # создаст пустой список по умолчанию

    class Config:
        orm_mode = True


class OrderModel(BaseModel):
    id: int
    order_name: str
    start_date: date
    tasks: List[TaskModel] = Field(default_factory=list)

    class Config:
        orm_mode = True
