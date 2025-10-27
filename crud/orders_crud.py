from typing import Sequence, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models_db import Order, Task
from schemas import OrderCreate


_common_options = [selectinload(Order.tasks).selectinload(Task.preds_rel)]


async def create_order(db: AsyncSession, order_in: OrderCreate) -> Order:
    order = Order(order_name=order_in.order_name, start_date=order_in.start_date)
    db.add(order)
    await db.commit()
    # гарантированно загрузим order вместе с tasks в одной операции до закрытия сессии
    result = await db.execute(
        select(Order).options(*_common_options).where(Order.id == order.id)
    )
    order_with_tasks = result.scalars().first()
    return order_with_tasks  # возвращаем объект с загруженными связями


async def update_order(db: AsyncSession, order_id: int, order_in: OrderCreate) -> Optional[Order]:
    order = await db.get(Order, order_id)
    if not order:
        return None
    order.order_name = order_in.order_name
    order.start_date = order_in.start_date
    await db.commit()
    result = await db.execute(
        select(Order).options(*_common_options).where(Order.id == order.id)
    )
    return result.scalars().first()


async def delete_order(db: AsyncSession, order_id: int) -> bool:
    order = await db.get(Order, order_id)
    if not order:
        return False
    await db.delete(order)
    await db.commit()
    return True


async def get_order(db: AsyncSession, order_id: int) -> Optional[Order]:
    result = await db.execute(
        select(Order).options(*_common_options).where(Order.id == order_id)
    )
    return result.scalars().first()


async def list_orders(db: AsyncSession) -> Sequence[Order]:
    result = await db.execute(select(Order).options(*_common_options))
    return result.scalars().all()
