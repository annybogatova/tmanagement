from sqlalchemy import Column, Integer, String, Date, ForeignKey, Table
from sqlalchemy.orm import relationship
from database import Base

# --- Промежуточная таблица для связей предшествующих задач ---
task_pred_table = Table(
    "task_pred",
    Base.metadata,
    Column("task_id", Integer, ForeignKey("tasks.id"), primary_key=True),
    Column("pred_id", Integer, ForeignKey("tasks.id"), primary_key=True),
)


# --- Таблица заказов ---
class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    order_name = Column(String, nullable=False)
    start_date = Column(Date, nullable=False)

    # связь один-ко-многим
    # back_populates указывает на атрибут в классе Task
    # cascade="all, delete-orphan" — при удалении заказа удаляются все связанные задачи
    tasks = relationship("Task", back_populates="order", cascade="all, delete-orphan")

    @property
    def task_ids(self) -> list[int]:
        return [t.id for t in self.tasks]  # возвращаем список id задач — можно использовать в Pydantic с orm_mode


# --- Таблица задач ---
class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    task = Column(String, nullable=False)
    duration = Column(Integer, nullable=False)
    resource = Column(Integer, nullable=False)

    # внешний ключ на заказ, при удалении заказа удаляются все связанные задачи
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"))
    order = relationship("Order", back_populates="tasks")  # связь многие-к-одному с заказом

    # связь многие-ко-многим с предшественниками через промежуточную таблицу
    preds_rel = relationship(
        "Task",
        secondary=task_pred_table,
        primaryjoin=id == task_pred_table.c.task_id,  # связь текущей строки с колонкой task_id
        secondaryjoin=id == task_pred_table.c.pred_id,  # связь предшественников с колонкой pred_id
        # у предшественников появляется атрибут dependents для доступа к задачам, которые от них зависят
        backref="dependents"
    )

    @property
    def preds(self) -> list:
        # возвращаем список id предшественников — можно использовать в Pydantic с orm_mode
        return [p.id for p in self.preds_rel]


# пример создания заказа
# BEGIN;
#
# -- 1) Создать заказ и получить его id
# INSERT INTO orders (order_name, start_date)
# VALUES ('Order A', '2025-10-01')
# RETURNING id;
#
# -- Клиент получает, например, order_id = 1
#
# -- 2) Вставить несколько задач и сразу получить их id
# INSERT INTO tasks (task, duration, resource, order_id)
# VALUES
#   ('Task 1', 5, 2, 1),
#   ('Task 2', 3, 1, 1),
#   ('Task 3', 2, 1, 1)
# RETURNING id, task;
#
# -- Клиент получит набор строк с id, например (10,'Task 1'), (11,'Task 2'), (12,'Task 3')
#
# -- 3) Используя полученные id, вставить предшественников
# INSERT INTO task_pred (task_id, pred_id)
# VALUES
#   (11, 10),
#   (12, 10);
#
# COMMIT;
