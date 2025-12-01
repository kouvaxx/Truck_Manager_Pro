from sqlmodel import SQLModel, create_engine, Session
from app.models import *

# Nome do arquivo do banco de dados SQLite
sqlite_file_name = "oficina.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

# Configurações para SQLite (necessário para evitar erros de thread em alguns casos)
connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)

def create_db_and_tables():
    """
    Cria o banco de dados e todas as tabelas definidas nos modelos.
    Deve ser chamado na inicialização da aplicação.
    """
    SQLModel.metadata.create_all(engine)

def get_session():
    """
    Dependência para obter uma sessão do banco de dados.
    Gerencia o ciclo de vida da sessão (abre e fecha automaticamente).
    """
    with Session(engine) as session:
        yield session
