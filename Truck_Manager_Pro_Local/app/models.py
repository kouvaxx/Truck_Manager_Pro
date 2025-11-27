from typing import Optional
from sqlmodel import Field, SQLModel
from datetime import datetime
from enum import Enum

class ServiceOrderStatus(str, Enum):
    OPEN = "Open"
    CLOSED = "Closed"
    PENDING = "Pending"

class Client(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    phone: str
    email: Optional[str] = None
    car_model: str
    car_plate: str

class InventoryItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    category: str
    cost_price: float
    sell_price: float
    quantity: int
    min_quantity: int
    location: Optional[str] = None

class ServiceOrder(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(foreign_key="client.id")
    status: ServiceOrderStatus = Field(default=ServiceOrderStatus.OPEN)
    total_value: float = Field(default=0.0)
    created_at: datetime = Field(default_factory=datetime.now)

class ServiceOrderItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="serviceorder.id")
    item_id: int = Field(foreign_key="inventoryitem.id")
    quantity_sold: int
    price_at_moment: float
