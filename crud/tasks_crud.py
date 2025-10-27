from typing import List, Optional, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models_db import Task, Order


async def create_task(db: AsyncSession, order_id: int, task_in) -> Optional[Task]:
    order = await db.get(Order, order_id)
    if not order:
        return None
    task = Task(task=task_in.task, duration=task_in.duration, resource=task_in.resource, order_id=order_id)
    db.add(task)
    await db.commit()
    result = await db.execute(
        select(Task).options(selectinload(Task.preds_rel)).where(Task.id == task.id)
    )
    return result.scalars().first()


async def get_task(db: AsyncSession, task_id: int) -> Optional[Task]:
    result = await db.execute(
        select(Task).options(selectinload(Task.preds_rel)).where(Task.id == task_id)
    )
    return result.scalars().first()


async def list_tasks(db: AsyncSession) -> Sequence[Task]:
    result = await db.execute(
        select(Task).options(selectinload(Task.preds_rel))
    )
    return result.scalars().all()


async def delete_task(db: AsyncSession, task_id: int) -> bool:
    task = await db.get(Task, task_id)
    if not task:
        return False
    await db.delete(task)
    await db.commit()
    return True


async def set_task_preds(db: AsyncSession, task_id: int, pred_ids: List[int]) -> Optional[Task]:
    # загрузим саму задачу вместе с уже существующими preds_rel, чтобы избежать ленивого загрузки при присвоении
    result = await db.execute(
        select(Task).options(selectinload(Task.preds_rel)).where(Task.id == task_id)
    )
    task = result.scalars().first()
    if not task:
        return None

    # подготовим список id (уберём самоссылку и дубликаты)
    filtered_ids = [pid for pid in dict.fromkeys(pred_ids) if pid != task_id]
    if not filtered_ids:
        task.preds_rel = []
    else:
        # загружаем только существующие предшественники одним запросом
        preds_result = await db.execute(select(Task).where(Task.id.in_(filtered_ids)))
        preds_objs = preds_result.scalars().all()
        # на всякий случай отфильтруем любые совпадения с task_id
        preds_objs = [p for p in preds_objs if p.id != task_id]
        # присваиваем найденные объекты
        task.preds_rel = preds_objs

    await db.commit()

    # вернуть свежую версию задачи с подгруженными preds_rel
    result = await db.execute(
        select(Task).options(selectinload(Task.preds_rel)).where(Task.id == task.id)
    )
    return result.scalars().first()
