from typing import Optional
from sqlmodel import Field, SQLModel
from datetime import datetime
from enum import Enum

# --- Enums ---
class ServiceOrderStatus(str, Enum):
    """Status possíveis para uma Ordem de Serviço."""
    OPEN = "Open"       # Aberta
    CLOSED = "Closed"   # Fechada
    PENDING = "Pending" # Pendente

# --- Modelos de Dados (Tabelas) ---

class Client(SQLModel, table=True):
    """
    Representa um Cliente da oficina.
    Armazena dados pessoais e do veículo principal.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(description="Nome completo do cliente")
    phone: str = Field(description="Telefone para contato/WhatsApp")
    email: Optional[str] = None
    car_model: str = Field(description="Modelo do veículo (ex: Fiat Uno)")
    car_plate: str = Field(description="Placa do veículo")

class InventoryItem(SQLModel, table=True):
    """
    Representa um item no Estoque (Peça ou Produto).
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    category: str = Field(description="Categoria da peça (ex: Motor, Freio)")
    cost_price: float = Field(description="Preço de Custo")
    sell_price: float = Field(description="Preço de Venda")
    quantity: int = Field(description="Quantidade atual em estoque")
    min_quantity: int = Field(description="Quantidade mínima para alerta")
    location: Optional[str] = Field(default=None, description="Localização física na oficina")

class ServiceOrder(SQLModel, table=True):
    """
    Representa uma Ordem de Serviço (OS).
    Vincula um cliente a um conjunto de serviços/peças.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(foreign_key="client.id", description="ID do Cliente vinculado")
    status: ServiceOrderStatus = Field(default=ServiceOrderStatus.OPEN)
    total_value: float = Field(default=0.0, description="Valor total acumulado da OS")
    created_at: datetime = Field(default_factory=datetime.now, description="Data de abertura")

class ServiceOrderItem(SQLModel, table=True):
    """
    Item individual dentro de uma OS.
    Registra qual peça foi usada e o preço cobrado no momento.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="serviceorder.id")
    item_id: int = Field(foreign_key="inventoryitem.id")
    quantity_sold: int
    price_at_moment: float = Field(description="Preço da peça no momento da venda (congela o preço)")
