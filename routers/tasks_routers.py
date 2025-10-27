from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from schemas import TaskCreate, TaskModel, PredModel
import crud.tasks_crud as tasks_crud


router = APIRouter(tags=["tasks"])


@router.post("/orders/{order_id}/task", response_model=TaskModel, summary="Create a new task for an order")
async def add_task(order_id: int, task_in: TaskCreate, db: AsyncSession = Depends(get_db)):
    task = await tasks_crud.create_task(db, order_id, task_in)
    if task is None:
        raise HTTPException(status_code=404, detail="order not found")
    return task


@router.get("/tasks/all", response_model=List[TaskModel], summary="List all tasks")
async def list_all_tasks(db: AsyncSession = Depends(get_db)):
    return await tasks_crud.list_tasks(db)


@router.get("/tasks/{task_id}", response_model=TaskModel, summary="Get a task by ID")
async def get_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await tasks_crud.get_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return task


@router.patch("/tasks/{task_id}", response_model=TaskModel, summary="Set task predecessors")
async def set_preds(task_id: int, preds_in: PredModel, db: AsyncSession = Depends(get_db)):
    task = await tasks_crud.set_task_preds(db, task_id, preds_in.pred)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return task


@router.delete("/tasks/{task_id}", status_code=204, summary="Delete a task")
async def remove_task(task_id: int, db: AsyncSession = Depends(get_db)):
    ok = await tasks_crud.delete_task(db, task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="task not found")
