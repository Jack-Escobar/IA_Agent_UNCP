import sqlite3
import os
from pathlib import Path

# Configurar la ruta de la base de datos local
DB_PATH = Path(__file__).parent.parent.parent / 'data'
DB_FILE = DB_PATH / 'uncp_tasks.db'

def init_db():
    """Inicializa la base de datos y crea la tabla de tareas si no existe."""
    if not DB_PATH.exists():
        DB_PATH.mkdir(parents=True, exist_ok=True)
        
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cursos (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            url    TEXT NOT NULL
        )
    ''')

    # [AC-1.2] Atributos obligatorios: nombre, enunciado, curso, fecha límite, estado
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tareas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            curso TEXT NOT NULL,
            nombre_tarea TEXT NOT NULL,
            enunciado TEXT,
            fecha_limite TEXT,
            estado TEXT DEFAULT 'Pendiente',
            UNIQUE(curso, nombre_tarea)
        )
    ''')
    
    conn.commit()
    conn.close()

def get_connection():
    """Retorna una conexión a la base de datos."""
    return sqlite3.connect(DB_FILE)

# Inicializar DB al cargar el módulo
init_db()
