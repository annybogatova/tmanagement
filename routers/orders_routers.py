from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from crud import orders_crud
from database import get_db
from schemas import OrderModel, OrderCreate


router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderModel, summary="Create a new order")
async def create(order_in: OrderCreate, db: AsyncSession = Depends(get_db)):
    return await orders_crud.create_order(db, order_in)


@router.get("/all", response_model=List[OrderModel], summary="List all orders")
async def list_all(db: AsyncSession = Depends(get_db)):
    return await orders_crud.list_orders(db)


@router.get("/{order_id}", response_model=OrderModel, summary="Get an order by ID")
async def get_one(order_id: int, db: AsyncSession = Depends(get_db)):
    order = await orders_crud.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="order not found")
    return order


@router.put("/{order_id}", response_model=OrderModel, summary="Update an existing order")
async def update(order_id: int, order_in: OrderCreate, db: AsyncSession = Depends(get_db)):
    order = await orders_crud.update_order(db, order_id, order_in)
    if not order:
        raise HTTPException(status_code=404, detail="order not found")
    return order


@router.delete("/{order_id}", status_code=204, summary="Delete an order")
async def remove(order_id: int, db: AsyncSession = Depends(get_db)):
    ok = await orders_crud.delete_order(db, order_id)
    if not ok:
        raise HTTPException(status_code=404, detail="order not found")
