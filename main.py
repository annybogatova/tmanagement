from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from crud import orders_crud, tasks_crud
from database import get_db, init_db
import calculate_router
from schemas import OrderModel, OrderCreate, TaskModel, TaskCreate, PredModel


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Инициализация БД ---
    await init_db()
    yield

# --- Создание приложения ---
app = FastAPI(
    lifespan=lifespan
)


@app.get("/")
async def ping_db(db: AsyncSession = Depends(get_db)):
    # пингуем подключение к бд: "db": "ok" если успешно
    await db.execute(text('SELECT 1'))
    return {"db": "ok"}


# Endpoints для заказов
@app.post("/orders/create", response_model=OrderModel, summary="Create a new order", tags=["orders"])
async def create(order_in: OrderCreate, db: AsyncSession = Depends(get_db)):
    return await orders_crud.create_order(db, order_in)


@app.get("/orders/{order_id}", response_model=OrderModel, summary="Get an order by ID", tags=["orders"])
async def get_one(order_id: int, db: AsyncSession = Depends(get_db)):
    order = await orders_crud.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="order not found")
    return order


@app.put("/orders/{order_id}", response_model=OrderModel, summary="Update an existing order", tags=["orders"])
async def update(order_id: int, order_in: OrderCreate, db: AsyncSession = Depends(get_db)):
    order = await orders_crud.update_order(db, order_id, order_in)
    if not order:
        raise HTTPException(status_code=404, detail="order not found")
    return order


@app.delete("/orders/{order_id}", status_code=204, summary="Delete an order", tags=["orders"])
async def remove(order_id: int, db: AsyncSession = Depends(get_db)):
    ok = await orders_crud.delete_order(db, order_id)
    if not ok:
        raise HTTPException(status_code=404, detail="order not found")


# Endpoints для задач
@app.post("/orders/{order_id}/task", response_model=TaskModel, summary="Create a new task for an order", tags=["tasks"])
async def add_task(order_id: int, task_in: TaskCreate, db: AsyncSession = Depends(get_db)):
    task = await tasks_crud.create_task(db, order_id, task_in)
    if task is None:
        raise HTTPException(status_code=404, detail="order not found")
    return task


@app.get("/tasks/{task_id}", response_model=TaskModel, summary="Get a task by ID", tags=["tasks"])
async def get_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await tasks_crud.get_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return task


@app.patch("/tasks/{task_id}", response_model=TaskModel, summary="Set task predecessors", tags=["tasks"])
async def set_preds(task_id: int, preds_in: PredModel, db: AsyncSession = Depends(get_db)):
    task = await tasks_crud.set_task_preds(db, task_id, preds_in.pred)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return task


@app.delete("/tasks/{task_id}", status_code=204, summary="Delete a task", tags=["tasks"])
async def remove_task(task_id: int, db: AsyncSession = Depends(get_db)):
    ok = await tasks_crud.delete_task(db, task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="task not found")

app.include_router(calculate_router.router)
