# tmanagement

Простой REST API для управления заказами и задачами и вычислительный сервис для оценки длительности проекта методом случайных топ\-порядков.

## Кратко о задаче
1. Создать/изменить/удалить заказ: `{order_name: "...", start_date: "YYYY-MM-DD"}`.  
2. Для заказа добавлять/удалять задачи: `{task: "имя", duration: 2, resource: 10}`.  
3. Для задачи задавать массив предшественников: `{pred: [1,2,3]}`.  
4. Написать вычислительный сервис, который рассчитает длительность проекта (исходя из того что существует ограничение использования ресурса max = 10), создав случайным образом 1000000 последовательностей работ и рассчитывает параллельно  длительности каждой последовательности (прообраз генетического алгоритма)

## Запуск локально
1. Установить PostgreSQL и создать БД `tmanagement`. По умолчанию ожидается:
   - хост: `localhost`
   - порт: `5433`
   - пользователь: `postgres`
   - пароль: `admin`  
   

   Эти параметры можно изменить в `database.py`:
   ```
   DATABASE_URL = "postgresql+asyncpg://<пользователь>:<пароль>@<хост>:<порт>/<имя_бд>"
   ```

2. Создать виртуальное окружение и установить зависимости:
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

3. Запустить сервер:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

4. Swagger UI: `http://<ваш_ip>:8000/docs`

## Тесты
- Запуск тестов (сервер должен быть запущен):
```bash
SERVICE_HOST=127.0.0.1:8000 pytest -v -s tests
```
Важно: в запросах поле `start_date` должно быть строкой в ISO формате (`"YYYY-MM-DD"`). 

Ошибка `TypeError: Object of type date is not JSON serializable` появляется, если послать `date` объект в `json` вместо строки — используйте `date.isoformat()`.

## Основные эндпоинты
### Заказы
- `POST /orders` — создать заказ  
  Request JSON (OrderCreate):
  ```json
  {
      "order_name": "Изготовить изделие", 
      "start_date": "2025-10-31" 
  }
  ```
  Response (OrderModel): 
  ```
  { 
    id* string 
    order_name* string
    start_date* string date(YYYY-MM-DD)
    tasks array<TaskModel>
  }
    ```

- `GET /orders/all` — список всех заказов  
  Response: список `OrderModel`.

- `GET /orders/{order_id}` — получить заказ
  Response: `OrderModel`

- `PUT /orders/{order_id}` — обновить заказ. Request JSON: OrderCreate

- `DELETE /orders/{order_id}` — удалить заказ (204 - при успехе)

### Задачи
- `POST /orders/{order_id}/task` — добавить задачу к заказу  
  Request JSON (TaskCreate):
  ```json
  { 
    "task": "Задача 1", 
    "duration": 2, 
    "resource": 3 
  }
  ```
  Response (TaskModel):
  ```
  { 
    id* integer
    task* string
    duration* integer
    resource* integer
    preds array<integer>  // список id предшественников
  }
    ```

- `GET /tasks/all` - список всех задач. Response: список `TaskModel`.
- `GET /tasks/{task_id}`- получить задачу. Response: `TaskModel`.
- `DELETE /tasks/{task_id}` - удалить задачу (204 - при успехе)

- `PATCH /tasks/{task_id}` — задать предшественников  
  Request JSON:
  ```json
  { 
    "pred": [1, 2] 
  }
  ```
  Response: обновлённый `TaskModel` с `preds: [..]`

### Вычисление
- `POST /calculate/orders/random` — запуск вычислений случайных топ\-порядков (CPU\-bound)
  Query параметры:
  - `n_tasks` (int) — количество задач в проекте
  - `iterations` (int) — сколько случайных порядков генерировать
  - `workers` (int|None) — число процессов
  - `max_resource` (int) — ограничение ресурса
  - `seed` (int|None)
  - `log_time_unit` (float|None)
  

  Возвращаемая структура (основные поля):
  ```json
  {
    "iterations": 1000000,
    "max_resource": 10,
    "workers": 8,
    "stats": {
      "avg": 123.4,
      "std": 5.6,
      "min": 100.0,
      "max": 150.0,
      "median_approx": 122.0,
      "sample_size_used": 10000,
      "elapsed_seconds": 12.34
    },
    "best": {
      "makespan": 100.0,
      "order": [ ... ],              // фактическая хронология стартов
      "order_topological": [ ... ]   // исходный топологический порядок
    },
    "log_file": "logs/best_order_....json"  // если logging включён и успешен
  }
  ```


## Немного о топологическом порядке (коротко)
- Топологический порядок — это линейная последовательность вершин ориентированного ациклического графа (DAG), где для каждой дуги `u -> v` вершина `u` идёт раньше `v`.  
- В проекте используется случайный алгоритм на основе алгоритма Kahn: всегда выбирается случайный из доступных (indegree=0) узлов, это даёт случайный корректный топ\-порядок. Если в данных есть цикл, оставшиеся вершины дополняются в случайном порядке (данные некорректны).

## Что делает `select(Order).options(*_common_options)`
- В коде запрос к БД (в `crud/orders_crud.py`) использует:
  ```py
  select(Order).options(selectinload(Order.tasks).selectinload(Task.preds_rel))
  ```
  Это означает: подгрузить `tasks` у каждого заказа и для каждой задачи подгрузить `preds_rel` в одном/нескольких эффективных запросах (eager loading). Это предотвращает ленивые дополнительные запросы при сериализации модели после закрытия сессии.

## Полезные файлы
- `main.py` — точка входа FastAPI  
- `database.py` — конфигурация SQLAlchemy Async engine и сессий  
- `models_db.py` — ORM модели `Order`, `Task` и таблица `task_pred`  
- `crud/` — операции CRUD  
- `routers/` — маршруты API  
- `compute_service.py` — вычислительный модуль для симуляций  
- `tests/` — pytest тесты

