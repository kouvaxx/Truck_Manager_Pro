from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select
from typing import Annotated

from app.database import create_db_and_tables, get_session
from app.models import InventoryItem, Client, ServiceOrder, ServiceOrderItem, ServiceOrderStatus
from datetime import datetime
import google.generativeai as genai
import os
import urllib.parse
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

# Configuração da API do Gemini
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("ALERTA: GOOGLE_API_KEY não encontrada no arquivo .env")

genai.configure(api_key=api_key)
# Mantendo gemini-flash-latest que foi o confirmado como disponível
model = genai.GenerativeModel('gemini-flash-latest')

app = FastAPI()
templates = Jinja2Templates(directory="app/templates")

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, session: Session = Depends(get_session)):
    # 1. Calcular Valor Total do Estoque (Custo)
    items = session.exec(select(InventoryItem)).all()
    total_inventory_value = sum(item.cost_price * item.quantity for item in items)
    
    # 2. Contar Itens com Estoque Baixo
    low_stock_count = sum(1 for item in items if item.quantity <= item.min_quantity)
    
    # 3. Contar OS Abertas
    open_os_count = len(session.exec(select(ServiceOrder).where(ServiceOrder.status == ServiceOrderStatus.OPEN)).all())
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "total_inventory_value": total_inventory_value,
        "low_stock_count": low_stock_count,
        "open_os_count": open_os_count
    })

# --- Rotas de Estoque ---
@app.get("/inventory", response_class=HTMLResponse)
async def read_inventory(
    request: Request, 
    search: str = "", 
    session: Session = Depends(get_session)
):
    query = select(InventoryItem)
    
    if search:
        query = query.where(
            (InventoryItem.name.ilike(f"%{search}%")) | 
            (InventoryItem.category.ilike(f"%{search}%"))
        )
    
    items = session.exec(query).all()
    
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/inventory_rows.html", {"request": request, "items": items})
        
    return templates.TemplateResponse("inventory.html", {"request": request, "items": items, "search": search})

@app.post("/inventory/add")
async def add_item(
    request: Request,
    name: Annotated[str, Form()],
    category: Annotated[str, Form()],
    cost_price: Annotated[float, Form()],
    sell_price: Annotated[float, Form()],
    quantity: Annotated[int, Form()],
    min_quantity: Annotated[int, Form()] = 5,
    location: Annotated[str, Form()] = "",
    session: Session = Depends(get_session)
):
    new_item = InventoryItem(
        name=name, category=category, cost_price=cost_price, 
        sell_price=sell_price, quantity=quantity, 
        min_quantity=min_quantity, location=location
    )
    session.add(new_item)
    session.commit()
    session.commit()
    return RedirectResponse(url="/inventory", status_code=303)

@app.get("/inventory/{item_id}/edit", response_class=HTMLResponse)
async def edit_item_row(request: Request, item_id: int, session: Session = Depends(get_session)):
    item = session.get(InventoryItem, item_id)
    if not item: raise HTTPException(status_code=404)
    return templates.TemplateResponse("partials/inventory_edit_row.html", {"request": request, "item": item})

@app.get("/inventory/{item_id}", response_class=HTMLResponse)
async def get_item_row(request: Request, item_id: int, session: Session = Depends(get_session)):
    item = session.get(InventoryItem, item_id)
    if not item: raise HTTPException(status_code=404)
    # Reusa o partial de linhas, passando uma lista com 1 item
    return templates.TemplateResponse("partials/inventory_rows.html", {"request": request, "items": [item]})

@app.put("/inventory/{item_id}", response_class=HTMLResponse)
async def update_item(
    request: Request,
    item_id: int,
    name: Annotated[str, Form()],
    category: Annotated[str, Form()],
    sell_price: Annotated[float, Form()],
    quantity: Annotated[int, Form()],
    session: Session = Depends(get_session)
):
    item = session.get(InventoryItem, item_id)
    if not item: raise HTTPException(status_code=404)
    
    item.name = name
    item.category = category
    item.sell_price = sell_price
    item.quantity = quantity
    
    session.add(item)
    session.commit()
    session.refresh(item)
    
    return templates.TemplateResponse("partials/inventory_rows.html", {"request": request, "items": [item]})

@app.delete("/inventory/{item_id}")
async def delete_item(item_id: int, session: Session = Depends(get_session)):
    item = session.get(InventoryItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    session.delete(item)
    session.commit()
    return Response(status_code=200)

# --- Rotas de Clientes ---
@app.get("/clients", response_class=HTMLResponse)
async def read_clients(request: Request, session: Session = Depends(get_session)):
    clients = session.exec(select(Client)).all()
    return templates.TemplateResponse("clients.html", {"request": request, "clients": clients})

@app.post("/clients/add")
async def add_client(
    request: Request,
    name: Annotated[str, Form()],
    phone: Annotated[str, Form()],
    car_model: Annotated[str, Form()],
    car_plate: Annotated[str, Form()],
    email: Annotated[str, Form()] = None,
    session: Session = Depends(get_session)
):
    new_client = Client(name=name, phone=phone, email=email, car_model=car_model, car_plate=car_plate)
    session.add(new_client)
    session.commit()
    return RedirectResponse(url="/clients", status_code=303)

# --- Rotas de OS ---
@app.get("/os", response_class=HTMLResponse)
async def read_os_list(request: Request, session: Session = Depends(get_session)):
    results = session.exec(select(ServiceOrder, Client).where(ServiceOrder.client_id == Client.id)).all()
    os_list = [{"os": r[0], "client": r[1]} for r in results]
    clients = session.exec(select(Client)).all()
    return templates.TemplateResponse("os_list.html", {"request": request, "os_list": os_list, "clients": clients})

@app.post("/os/create")
async def create_os(client_id: Annotated[int, Form()], session: Session = Depends(get_session)):
    new_os = ServiceOrder(client_id=client_id, status=ServiceOrderStatus.OPEN)
    session.add(new_os)
    session.commit()
    session.refresh(new_os)
    return RedirectResponse(url=f"/os/{new_os.id}", status_code=303)

@app.get("/os/{os_id}", response_class=HTMLResponse)
async def read_os_details(os_id: int, request: Request, session: Session = Depends(get_session)):
    os_obj = session.get(ServiceOrder, os_id) # Renomeado para evitar conflito com modulo os
    if not os_obj: raise HTTPException(status_code=404, detail="OS não encontrada")
    client = session.get(Client, os_obj.client_id)
    
    items_query = select(ServiceOrderItem, InventoryItem).where(
        ServiceOrderItem.order_id == os_id, ServiceOrderItem.item_id == InventoryItem.id
    )
    items_results = session.exec(items_query).all()
    
    # Criar objeto simples para view
    class ItemView:
        def __init__(self, order_item, inv_item):
            self.id = order_item.id
            self.name = inv_item.name
            self.quantity_sold = order_item.quantity_sold
            self.price_at_moment = order_item.price_at_moment
            
    view_items = [ItemView(oi, ii) for oi, ii in items_results]
    inventory = session.exec(select(InventoryItem)).all()

    return templates.TemplateResponse("os_details.html", {
        "request": request, "os": os_obj, "client": client, "os_items": view_items, "inventory": inventory
    })

@app.post("/os/{os_id}/add_item")
async def add_os_item(
    os_id: int, 
    request: Request, 
    item_id: Annotated[int, Form()], 
    quantity: Annotated[int, Form()], 
    session: Session = Depends(get_session)
):
    # Validações básicas
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantidade deve ser positiva")

    os_obj = session.get(ServiceOrder, os_id)
    inventory_item = session.get(InventoryItem, item_id)
    
    if not os_obj or not inventory_item: 
        raise HTTPException(status_code=404, detail="Item ou OS não encontrados")
    
    # 1. VALIDAÇÃO DE ESTOQUE (CORREÇÃO CRÍTICA)
    if inventory_item.quantity < quantity:
        # Retorna um script JS simples para alertar o usuário sem quebrar a página
        return HTMLResponse(
            f"""<script>
                alert('Erro: Estoque insuficiente!\\nDisponível: {inventory_item.quantity}\\nSolicitado: {quantity}');
                window.history.back();
            </script>"""
        )
        
    # 2. Cria o item na OS
    order_item = ServiceOrderItem(
        order_id=os_id, 
        item_id=item_id, 
        quantity_sold=quantity, 
        price_at_moment=inventory_item.sell_price
    )
    session.add(order_item)
    
    # 3. Atualiza Totais e Estoque
    os_obj.total_value += (quantity * inventory_item.sell_price)
    inventory_item.quantity -= quantity # Baixa no estoque
    
    session.add(os_obj)
    session.add(inventory_item)
    session.commit()
    
    return RedirectResponse(url=f"/os/{os_id}", status_code=303)


# --- ADICIONE ESTA NOVA FUNÇÃO (REMOVER ITEM) ---
@app.delete("/os/{os_id}/item/{item_row_id}")
async def delete_os_item(
    os_id: int, 
    item_row_id: int, 
    session: Session = Depends(get_session)
):
    """Remove um item da OS e DEVOLVE ao estoque (Estorno)"""
    os_obj = session.get(ServiceOrder, os_id)
    
    # Busca o registro da venda (ServiceOrderItem)
    order_item = session.get(ServiceOrderItem, item_row_id)
    
    if not os_obj or not order_item:
        raise HTTPException(status_code=404)
        
    # Busca a peça original para devolver ao estoque
    inventory_item = session.get(InventoryItem, order_item.item_id)
    
    # 1. Estorno Financeiro
    subtotal = order_item.quantity_sold * order_item.price_at_moment
    os_obj.total_value -= subtotal
    
    # Evitar erros de arredondamento flutuante deixando negativo
    if os_obj.total_value < 0: os_obj.total_value = 0
    
    # 2. Estorno de Estoque (Se o item ainda existir no cadastro)
    if inventory_item:
        inventory_item.quantity += order_item.quantity_sold
        session.add(inventory_item)
    
    # 3. Remove o item da OS
    session.delete(order_item)
    session.add(os_obj)
    session.commit()
    
    return Response(status_code=200) # HTMX remove a linha da tabela

@app.post("/os/{os_id}/close")
async def close_os(os_id: int, session: Session = Depends(get_session)):
    os_obj = session.get(ServiceOrder, os_id)
    if not os_obj: 
        raise HTTPException(status_code=404, detail="OS não encontrada")
    
    # Atualiza status para Fechado
    os_obj.status = ServiceOrderStatus.CLOSED
    session.add(os_obj)
    session.commit()
    
    # Recarrega a página para mostrar o novo estado
    return RedirectResponse(url=f"/os/{os_id}", status_code=303)

@app.get("/os/{os_id}/print", response_class=HTMLResponse)
async def print_os(os_id: int, request: Request, session: Session = Depends(get_session)):
    """Rota simplificada apenas para impressão"""
    os_obj = session.get(ServiceOrder, os_id)
    if not os_obj: raise HTTPException(status_code=404)
    client = session.get(Client, os_obj.client_id)
    
    # Busca itens
    items_results = session.exec(select(ServiceOrderItem, InventoryItem).where(
        ServiceOrderItem.order_id == os_id, ServiceOrderItem.item_id == InventoryItem.id
    )).all()
    
    # Prepara dados para o template
    class PrintItem:
        def __init__(self, oi, ii):
            self.name = ii.name
            self.qty = oi.quantity_sold
            self.price = oi.price_at_moment
            self.subtotal = oi.quantity_sold * oi.price_at_moment

    print_items = [PrintItem(oi, ii) for oi, ii in items_results]

    return templates.TemplateResponse("print_os.html", {
        "request": request, 
        "os": os_obj, 
        "client": client, 
        "items": print_items,
        "now": datetime.now()
    })

# --- IA ---
@app.post("/os/{os_id}/generate_report")
async def generate_report(os_id: int, session: Session = Depends(get_session)):
    os_obj = session.get(ServiceOrder, os_id)
    if not os_obj: return HTMLResponse("OS not found", status_code=404)
    client = session.get(Client, os_obj.client_id)
    
    items_results = session.exec(select(ServiceOrderItem, InventoryItem).where(
        ServiceOrderItem.order_id == os_id, ServiceOrderItem.item_id == InventoryItem.id
    )).all()
    
    items_list_str = "".join([f"- {ii.name} (x{oi.quantity_sold})\n" for oi, ii in items_results])
    
    if not items_list_str:
        return HTMLResponse("""
        <div class="alert alert-warning">
            <i class="bi bi-exclamation-triangle"></i> 
            Adicione peças ou serviços à OS antes de gerar o relatório.
        </div>
        """)
        
    prompt = f"""
    Atue como um mecânico chefe honesto e profissional.
    Escreva uma mensagem curta para WhatsApp para o cliente {client.name} (Carro: {client.car_model}).
    
    LISTA REAL DE PEÇAS/SERVIÇOS REALIZADOS (USE APENAS ESTES):
    {items_list_str}
    
    Valor Total: R$ {os_obj.total_value:.2f}
    
    Instruções RÍGIDAS:
    1. Cite APENAS as peças listada acima. NÃO INVENTE NENHUM OUTRO SERVIÇO.
    2. Se a lista for pequena, seja breve.
    3. Explique a importância técnica do que foi feito.
    4. Justifique o valor com base na qualidade/mão de obra.
    5. Seja cordial. Sem markdown.
    """
    
    try:
        response = model.generate_content(prompt)
        message = response.text
        whatsapp_link = f"https://wa.me/55{client.phone.replace(' ','')}?text={urllib.parse.quote(message)}"
        
        return HTMLResponse(f"""
        <div class="bg-success-subtle border border-success p-3 rounded text-success-emphasis">
            <h5 class="fw-bold"><i class="bi bi-robot"></i> Relatório Pronto:</h5>
            <p style="white-space: pre-line;">{message}</p>
            <a href="{whatsapp_link}" target="_blank" class="btn btn-success fw-bold"><i class="bi bi-whatsapp"></i> Enviar</a>
        </div>""")
    except Exception as e:
        return HTMLResponse(f"<div class='alert alert-danger'>Erro IA: {str(e)}</div>")

@app.post("/inventory/{item_id}/analyze")
async def analyze_price(item_id: int, session: Session = Depends(get_session)):
    item = session.get(InventoryItem, item_id)
    if not item: return HTMLResponse("Item não encontrado")

    prompt = f"""Analise preço autopeça Brasil. Produto: {item.name}. Venda: R$ {item.sell_price:.2f}.
    Responda HTML puro (<span> ou <small>):
    1. 'Preço Baixo/Justo/Alto'.
    2. Faixa estimada mercado.
    3. Use classes Bootstrap (text-success/warning/danger)."""
    
    try:
        response = model.generate_content(prompt)
        return HTMLResponse(response.text)
    except Exception as e:
        return HTMLResponse(f"<span class='text-danger'>Erro IA: {str(e)}</span>")
