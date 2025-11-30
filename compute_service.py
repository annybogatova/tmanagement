import random
import heapq
import math
import time
import json

from typing import List, Dict, Tuple, Optional, Any
from concurrent.futures import ProcessPoolExecutor

MAX_RESOURCE_DEFAULT = 10


def prepare_compact_data(tasks: List[dict]):
    """
        Преобразуем входной список задач в компактные структуры:

        - task_nodes: список id задач
        - task_info: {id: (duration, resource)}
        - preds_map: {id: [pred_ids]}
        Это ускоряет доступ внутри горячих функций.
    """
    task_nodes = []
    task_info = {}
    preds_map = {}
    for t in tasks:
        tid = int(t["id"])
        task_nodes.append(tid)
        task_info[tid] = (int(t["duration"]), int(t["resource"]))
        preds_map[tid] = [int(x) for x in t.get("preds", [])]
    return task_nodes, task_info, preds_map


def _random_topo_order(nodes: List[int], preds_map: Dict[int, List[int]], rng: random.Random) -> List[int]:
    """
       Генерирует случайный топологический порядок (randomized Kahn's algorithm):
       - считаем входные степени (indeg)
       - выбираем случайный доступный узел (без предшественников), удаляем его и обновляем
       - итог: допустимый порядок задач, сохраняющий зависимости preds_map
       Если граф содержит цикл (неправильные данные), то оставшиеся вершины перемешиваются и добиваются длины.
    """
    indeg = {n: 0 for n in nodes}
    out = {n: [] for n in nodes}
    for t, preds in preds_map.items():
        for p in preds:
            out.setdefault(p, []).append(t)
            indeg[t] = indeg.get(t, 0) + 1
    available = [n for n, d in indeg.items() if d == 0]
    order = []
    while available:
        idx = rng.randrange(len(available))
        node = available.pop(idx)
        order.append(node)
        for nbr in out.get(node, ()):
            indeg[nbr] -= 1
            if indeg[nbr] == 0:
                available.append(nbr)
    if len(order) != len(nodes):
        # если что-то осталось (цикл) — просто дополняем случайным порядком оставшиеся
        remaining = [n for n in nodes if n not in order]
        rng.shuffle(remaining)
        order.extend(remaining)
    return order


def _makespan_for_order(order: List[int], task_info: Dict[int, Tuple[float, int]], preds_map: Dict[int, List[int]],
                        max_resource: int) -> float:
    """
        Симуляция выполнения задач в заданном порядке при ограничении суммарного ресурса:
        - running: min-heap событий (end_time, task_id, resource) — отслеживаем активные задачи
        - resource_in_use: сколько ресурса занято в текущий момент
        - finish_times: время завершения каждой задачи (чтобы учитывать предшественников)
        Алгоритм для каждой задачи tid в order:
          1) earliest = max(finish_times[pred] for pred in preds) — задача не может стартовать до завершения предов
          2) освобождаем завершившиеся к моменту earliest задачи (pop из heap)
          3) если после этого нет свободного ресурса (resource_in_use + res > max_resource),
             извлекаем следующее ближайшее событие (передвигаем текущий момент на end_time), освобождаем ресурс,
             повторяем до тех пор, пока хватит ресурса
          4) стартуем задачу: start = t, end = start + dur, пушим событие в heap и увеличиваем resource_in_use
        Возвращаем makespan = максимальное время завершения.
    """
    running = []  # heap of (end_time, task_id, resource)
    resource_in_use = 0
    scheduled_end: Dict[int, float] = {}
    makespan = 0.0

    for tid in order:
        dur, res = task_info[tid]
        preds = preds_map.get(tid, [])
        # проверка: все предки должны быть запланированы ранее в этом order
        missing = [p for p in preds if p not in scheduled_end]
        if missing:
            raise RuntimeError(f"Invalid order: predecessors {missing} for task {tid} are not scheduled before it")
        # earliest — по запланированным окончаниям предков
        earliest = max((scheduled_end.get(p, 0.0) for p in preds), default=0.0)
        t = earliest
        # освобождаем завершившиеся до или в t
        while running and running[0][0] <= t:
            end_time, _, ended_res = heapq.heappop(running)
            resource_in_use -= ended_res
        # если не хватает ресурса — ждем ближайшего завершения(ий)
        while resource_in_use + res > max_resource and running:
            end_time, _, ended_res = heapq.heappop(running)
            if end_time > t:
                t = end_time
            resource_in_use -= ended_res
            while running and running[0][0] <= t:
                et2, _, er2 = heapq.heappop(running)
                resource_in_use -= er2
        # стартуем задачу и сохраняем запланированное окончание
        start = t
        end = start + dur
        scheduled_end[tid] = end
        makespan = max(makespan, end)
        heapq.heappush(running, (end, tid, res))
        resource_in_use += res

    return makespan


def _single_simulation_return_order(task_nodes, task_info, preds_map, max_resource, seed):
    """
       Одна симуляция в одном процессе:
       - генерируем случайный топ\-порядок с заданным seed
       - вычисляем makespan для этого порядка
       Возвращаем tuple (makespan, order)
    """
    rng = random.Random(seed)
    order = _random_topo_order(task_nodes, preds_map, rng)
    makespan = _makespan_for_order(order, task_info, preds_map, max_resource)
    return makespan, order


def _worker_tuple(args):
    # адаптер для ProcessPoolExecutor.map — unpack аргументов
    seed, task_nodes, task_info, preds_map, max_resource = args
    return _single_simulation_return_order(task_nodes, task_info, preds_map, max_resource, seed)


def run_simulations(tasks: List[dict],
                    iterations: int = 1_000_000,
                    max_resource: int = MAX_RESOURCE_DEFAULT,
                    workers: Optional[int] = None,
                    seed_base: int = 0,
                    sample_size: int = 10000,
                    chunksize: int = 256,
                    return_best_order: bool = True,
                    log_dir: Optional[str] = None,
                    log_time_unit: Optional[float] = None):
    """
        Главная функция:
        - iterations: сколько случайных порядков сгенерировать и оценить (в задании: 1\,000\,000).
        - Определяет workers: если None — берёт число ядер * 2 ограниченное 32.
        - Параллельно распределяет iterations симуляций между процессами с помощью ProcessPoolExecutor.
        - Для каждой симуляции обновляет статистику онлайн:
            * среднее и дисперсию (алгоритм Вельфорда — без хранения всех значений)
            * минимальное/максимальное значение
            * reservoir sampling (размер sample_size) — для приближенной медианы без хранения всех iterations
            * сохраняет лучший найденный порядок (если return_best_order=True)
        - chunksize: сколько задач слать за раз в map для уменьшения IPC overhead
        """
    if iterations <= 0:
        raise ValueError("iterations must be > 0")
    task_nodes, task_info, preds_map = prepare_compact_data(tasks)
    # выбор числа процессов для ProcessPoolExecutor
    if workers is None:
        cpu = 1
        try:
            import os
            cpu = os.cpu_count() or 1
        except Exception:
            cpu = 1
        workers = max(1, min(32, cpu * 2))

    # статистика (Welford)
    n = 0
    mean = 0.0
    m2 = 0.0
    min_v = float("inf")
    max_v = float("-inf")
    sample = []
    rng_sample = random.Random(seed_base + 9999)
    best_makespan = float("inf")
    best_order = None
    start_time = time.time()

    # генератор аргументов для каждого запуска: разные сиды + неизменяемые данные
    seeds_iter = ((seed_base + i, task_nodes, task_info, preds_map, max_resource) for i in range(iterations))
    with ProcessPoolExecutor(max_workers=workers) as ex:
        # ex.map распараллеливает вызовы _worker_tuple над seeds_iter
        for i, res in enumerate(ex.map(_worker_tuple, seeds_iter, chunksize=chunksize)):
            makespan, order = res
            # обновляем Welford для среднего и дисперсии
            n += 1
            delta = makespan - mean
            mean += delta / n
            m2 += delta * (makespan - mean)
            if makespan < min_v:
                min_v = makespan
            if makespan > max_v:
                max_v = makespan
            # reservoir sampling: храним только sample_size случайных значений из всего потока
            if sample_size > 0:
                if len(sample) < sample_size:
                    sample.append(makespan)
                else:
                    # с вероятностью sample_size/(i+1) заменяем случайный элемент
                    j = rng_sample.randint(0, i)
                    if j < sample_size:
                        sample[j] = makespan
            # сохраняем лучший порядок
            if makespan < best_makespan:
                best_makespan = makespan
                best_order = order

    elapsed = time.time() - start_time
    stats: Dict[str, Any] = {"avg": None, "std": None}
    if n > 0:
        var = m2 / n
        stats["avg"] = mean
        stats["std"] = math.sqrt(var)
    stats.update({"min": (min_v if n else None), "max": (max_v if n else None)})
    # приближённая медиана по sample (если sample не пуст)
    median = None
    if sample:
        sample.sort()
        m = len(sample)
        median = sample[m // 2] if m % 2 == 1 else 0.5 * (sample[m//2 - 1] + sample[m//2])
    stats["median_approx"] = median
    stats["sample_size_used"] = len(sample)
    stats["elapsed_seconds"] = elapsed

    result = {"iterations": iterations, "max_resource": max_resource, "workers": workers, "stats": stats}
    if return_best_order:
        if best_order is None:
            result["best"] = {"makespan": None, "order": None}
        else:
            try:
                _, log_data = _makespan_for_order_log(best_order, task_info, preds_map, max_resource)
                start_times = log_data.get("start_times", {})
                start_sequence = [int(tid) for tid, _ in
                                  sorted(start_times.items(), key=lambda kv: (kv[1], int(kv[0])))]
            except Exception:
                start_sequence = best_order
            result["best"] = {
                "makespan": best_makespan,
                "order": start_sequence,  # фактическая хронология стартов
                "order_topological": best_order  # исходный топологический порядок (для отладки)
            }

    # Если запрошен лог — создаём каталог и логируем детально лучший порядок (локально, не из воркеров)
    if log_dir and best_order is not None:
        try:
            os.makedirs(log_dir, exist_ok=True)
            ts = int(time.time())
            fname = os.path.join(log_dir, f"best_order_{ts}.json")
            # собираем компактное описание задач для файла
            tasks_list = []
            for tid in task_nodes:
                dur, res = task_info[tid]
                preds = preds_map.get(tid, [])
                tasks_list.append({"id": tid, "duration": dur, "resource": res, "preds": preds})
            # прогоняем локально симуляцию с логом
            _, log_data = _makespan_for_order_log(best_order, task_info, preds_map, max_resource,
                                                  time_unit=log_time_unit)
            out = {
                "tasks": tasks_list,
                "order": best_order,
                "log": log_data,
                "meta": {"logged_at": ts, "iterations": iterations, "max_resource": max_resource}
            }
            with open(fname, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            result["log_file"] = fname
        except Exception as e:
            # не ломаем основной результат — возвращаем предупреждение в result
            result.setdefault("warnings", []).append(f"failed to write log: {e}")

    return result


def _makespan_for_order_log(order: List[int],
                            task_info: Dict[int, Tuple[float, int]],
                            preds_map: Dict[int, List[int]],
                            max_resource: int,
                            time_unit: Optional[float] = None) -> Tuple[float, Dict]:
    """
    Как _makespan_for_order, но с детальным логом.
    Исправлено: используем scheduled_end для учёта того, что задача
    не может стартовать до запланированного окончания всех предков.
    """
    running = []  # heap of (end_time, task_id, resource)
    resource_in_use = 0
    finish_times: Dict[int, float] = {}
    start_times: Dict[int, float] = {}
    scheduled_end: Dict[int, float] = {}  # плановые окончания для учёта preds
    makespan = 0.0
    events = []

    for tid in order:
        dur, res = task_info[tid]
        preds = preds_map.get(tid, [])

        # проверка: все предки должны быть уже запланированы (scheduled_end)
        missing = [p for p in preds if p not in scheduled_end]
        if missing:
            raise RuntimeError(f"Invalid order: predecessors {missing} for task {tid} are not scheduled before it")

        # earliest — по плановым окончаниям предков
        earliest = max((scheduled_end.get(p, 0.0) for p in preds), default=0.0)
        t = earliest

        # освобождаем завершившиеся до или в t
        while running and running[0][0] <= t:
            end_time, ended_tid, ended_res = heapq.heappop(running)
            resource_in_use -= ended_res
            finish_times[ended_tid] = end_time
            events.append({
                "time": end_time,
                "task": ended_tid,
                "event": "end",
                "resource": ended_res,
                "resource_in_use": resource_in_use
            })

        # если не хватает ресурса — ждем ближайшего завершения(ий)
        while resource_in_use + res > max_resource and running:
            end_time, ended_tid, ended_res = heapq.heappop(running)
            if end_time > t:
                t = end_time
            resource_in_use -= ended_res
            finish_times[ended_tid] = end_time
            events.append({
                "time": end_time,
                "task": ended_tid,
                "event": "end",
                "resource": ended_res,
                "resource_in_use": resource_in_use
            })
            while running and running[0][0] <= t:
                et2, tid2, er2 = heapq.heappop(running)
                resource_in_use -= er2
                finish_times[tid2] = et2
                events.append({
                    "time": et2,
                    "task": tid2,
                    "event": "end",
                    "resource": er2,
                    "resource_in_use": resource_in_use
                })

        # стартуем задачу
        start = t
        end = start + dur
        start_times[tid] = start
        scheduled_end[tid] = end  # сохраняем плановое окончание для предков
        makespan = max(makespan, end)
        heapq.heappush(running, (end, tid, res))
        resource_in_use += res
        events.append({
            "time": start,
            "task": tid,
            "event": "start",
            "resource": res,
            "resource_in_use": resource_in_use
        })

    # очистка оставшихся в running
    while running:
        end_time, ended_tid, ended_res = heapq.heappop(running)
        resource_in_use -= ended_res
        finish_times[ended_tid] = end_time
        events.append({
            "time": end_time,
            "task": ended_tid,
            "event": "end",
            "resource": ended_res,
            "resource_in_use": resource_in_use
        })

    events_sorted = sorted(events, key=lambda e: (e["time"], 0 if e["event"] == "end" else 1))

    # отсортированные списки start/finish по времени
    start_times_sorted = sorted(start_times.items(), key=lambda kv: (kv[1], kv[0]))
    finish_times_sorted = sorted(finish_times.items(), key=lambda kv: (kv[1], kv[0]))

    start_times_dict = {tid: t for tid, t in start_times_sorted}
    finish_times_dict = {tid: t for tid, t in finish_times_sorted}

    log = {
        "makespan": makespan,
        "start_times": start_times_dict,
        "finish_times": finish_times_dict,
        "events": events_sorted
    }

    # optional time sampling
    if time_unit is not None and time_unit > 0:
        samples = []
        intervals = [(start_times[t], finish_times[t], task_info[t][1], t) for t in order]
        t = 0.0
        while t <= math.ceil(makespan / time_unit) * time_unit:
            rsum = 0
            active = []
            for s, e, r, tid in intervals:
                if s <= t < e:
                    rsum += r
                    active.append(tid)
            samples.append({"time": t, "resource_in_use": rsum, "active": active})
            t += time_unit
        log["time_samples"] = samples

    return makespan, log
