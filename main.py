import asyncio
import socket
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, init_db
from routers import orders_routers, tasks_routers, calculate_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Автоопределение IP ---
    def get_local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            print("Exception")
            return "127.0.0.1"

    loop = asyncio.get_event_loop()
    local_ip = await loop.run_in_executor(None, get_local_ip)

    print("\n" + "="*60)
    print("FASTAPI СЕРВЕР ЗАПУЩЕН")
    print("Локально:          http://127.0.0.1:8000")
    print(f"С телефона:        http://{local_ip}:8000")
    print(f"Swagger:           http://{local_ip}:8000/docs")
    print(f"Redoc:             http://{local_ip}:8000/redoc")
    print("="*60 + "\n")

    # --- Инициализация БД ---
    await init_db()
    yield

# --- Создание приложения ---
app = FastAPI(
    lifespan=lifespan,
    title="Мой API",
    version="1.0.0"
)


@app.get("/ping-db")
async def ping_db(db: AsyncSession = Depends(get_db)):
    # пингуем подключение к бд: "db": "ok" если успешно
    await db.execute(text('SELECT 1'))
    return {"db": "ok"}

app.include_router(orders_routers.router)
app.include_router(tasks_routers.router)
app.include_router(calculate_router.router)
