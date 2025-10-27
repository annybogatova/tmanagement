from fastapi import APIRouter, Query
import random
import asyncio
from typing import Optional, List, Dict
from compute_service import run_simulations

router = APIRouter(prefix="/calculate", tags=["calculate"])


def generate_random_tasks(n_tasks: int,
                          max_preds: int = 3,
                          max_duration: int = 10,
                          max_resource_per_task: int = 5,
                          seed: Optional[int] = None) -> List[Dict]:
    """
        Генерирует список задач (каждая задача — dict с keys: id, duration, resource, preds).
        - n_tasks: количество задач в одном проекте (вершины DAG).
        - preds: список id предшественников (чтобы гарантировать топологические зависимости).
    """
    rng = random.Random(seed)
    tasks = []
    for tid in range(1, n_tasks + 1):
        if tid == 1:
            preds = []
        else:
            k = rng.randint(0, min(max_preds, tid - 1))
            preds = rng.sample(range(1, tid), k) if k > 0 else []
        tasks.append({
            "id": tid,
            "duration": rng.randint(1, max_duration),  # целое
            "resource": rng.randint(1, max_resource_per_task),
            "preds": preds
        })
    return tasks


@router.post("/orders/random")
async def calculate_random_order(n_tasks: int = Query(50, ge=1, le=10000),
                                 iterations: int = Query(1_000_000, ge=1, le=5_000_000),
                                 workers: Optional[int] = Query(None),
                                 max_resource: int = Query(10, gt=0),
                                 seed: Optional[int] = Query(None),  # начальное значение для генерации
                                 log_time_unit: Optional[int] = Query(None)
                                 ):
    """
        Эндпоинт:
        - n_tasks: сколько задач в проекте (не количество последовательностей).
        - iterations: сколько случайных топ\-порядков (последовательностей) сгенерировать и оценить.
          Текст задания говорит: "создав случайным образом 1000000 последовательностей" — это iterations.
        - workers: число процессов для параллельной оценки (если None — выбирается автоматически).
        - max_resource: ограничение суммарного ресурса одновременно (в задаче = 10).
        Внутри мы:
          1) генерируем `tasks`,
          2) вызываем run_simulations в отдельном потоке (чтобы не блокировать event loop),
          3) получаем агрегированную статистику и лучший порядок.
    """

    tasks = generate_random_tasks(n_tasks, seed=seed)
    # heavy CPU-bound job — запускаем в отдельном потоке, внутри него создаются процессы
    result_stats = await asyncio.to_thread(
        run_simulations,
        tasks,
        iterations,
        max_resource,
        workers,
        00,       # seed_base — базовый сид для генерации случайных порядков в процессах
        10000,   # sample_size — сколько значений сохраняем для приближённой медианы (экономия памяти)
        256,     # chunksize — размер порции работ, передаваемых каждому процессу
        True,     # return_best_order — возвращать ли лучший найденный порядок
        log_dir="logs",
        log_time_unit=log_time_unit
    )
    return result_stats
