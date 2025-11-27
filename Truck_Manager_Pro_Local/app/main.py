from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select
from typing import Annotated

from app.database import create_db_and_tables, get_session
from app.models import InventoryItem

app = FastAPI()

templates = Jinja2Templates(directory="app/templates")

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/inventory", response_class=HTMLResponse)
async def read_inventory(request: Request, session: Session = Depends(get_session)):
    items = session.exec(select(InventoryItem)).all()
    return templates.TemplateResponse("inventory.html", {"request": request, "items": items})

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
        name=name,
        category=category,
        cost_price=cost_price,
        sell_price=sell_price,
        quantity=quantity,
        min_quantity=min_quantity,
        location=location
    )
    session.add(new_item)
    session.commit()
    
    # Redirect back to inventory page to refresh the list
    # With HTMX hx-target="body", this will replace the whole body with the updated page
    return RedirectResponse(url="/inventory", status_code=303)

@app.delete("/inventory/{item_id}")
async def delete_item(item_id: int, session: Session = Depends(get_session)):
    item = session.get(InventoryItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    session.delete(item)
    session.commit()
    # Return empty response so HTMX removes the element
    return Response(status_code=200)
