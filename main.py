from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, init_db
from routers import orders_routers, tasks_routers, calculate_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # вызываем инициализацию БД при старте
    await init_db()

    yield


app = FastAPI(lifespan=lifespan)


@app.get("/ping-db")
async def ping_db(db: AsyncSession = Depends(get_db)):
    # пингуем подключение к бд: "db": "ok" если успешно
    await db.execute(text('SELECT 1'))
    return {"db": "ok"}

app.include_router(orders_routers.router)
app.include_router(tasks_routers.router)
app.include_router(calculate_router.router)
