"""
main.py — Punto de entrada de la API del UNCP_agent

Exposición de endpoints REST con FastAPI para ser consumidos por el frontend.
En modo desarrollo se puede usar también como CLI ejecutando: python main.py --cli
"""

import sys
import os
import argparse
from pathlib import Path
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

sys.path.append(str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.agent import UNCPAgent
from src.core.db import init_db, get_connection

# ─── Modelos de Request/Response ──────────────────────────────────────────────

class MensajeRequest(BaseModel):
    mensaje: str | None = None
    prompt: str | None = None
    sesion_id: str = "default"

    def get_texto(self) -> str:
        return self.mensaje or self.prompt or ""

class MensajeResponse(BaseModel):
    respuesta: str
    herramientas_usadas: list[str]
    iteraciones: int
    error: str | None = None

class EstadoResponse(BaseModel):
    proveedor: str
    modelo: str
    mensajes_en_historial: int

# ─── Ciclo de vida de la aplicación ───────────────────────────────────────────

# Almacén de sesiones en memoria (por sesión_id → instancia de agente)
# Para producción se puede reemplazar por Redis u otro backend
_sesiones: dict[str, UNCPAgent] = {}

def _get_agente(sesion_id: str) -> UNCPAgent:
    """Retorna o crea una instancia del agente para la sesión indicada."""
    if sesion_id not in _sesiones:
        proveedor = os.getenv("LLM_PROVIDER", "gemini").lower()
        _sesiones[sesion_id] = UNCPAgent(provider=proveedor)
    return _sesiones[sesion_id]

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa recursos al arrancar el servidor."""
    init_db()
    print("\n" + "=" * 50)
    print("  UNCP_agent API — Servidor iniciado")
    print(f"  Proveedor LLM: {os.getenv('LLM_PROVIDER', 'gemini').upper()}")
    print("=" * 50 + "\n")
    yield
    # Limpieza al apagar (si fuera necesario)
    _sesiones.clear()

# ─── Aplicación FastAPI ────────────────────────────────────────────────────────

app = FastAPI(
    title="UNCP Agent API",
    description="API del asistente académico autónomo para la Universidad Nacional del Centro del Perú.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS: permite peticiones desde el frontend local y cualquier origen de desarrollo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/", tags=["Info"])
def raiz():
    """Health check del servidor."""
    return {"status": "ok", "agente": "UNCP_agent", "version": "1.0.0"}


@app.post("/chat", response_model=MensajeResponse, tags=["Agente"])
def chat(request: MensajeRequest):
    """
    Envía un mensaje al agente y recibe su respuesta.
    El agente puede ejecutar herramientas (sincronizar, listar tareas, subir archivo) 
    de forma autónoma antes de responder.
    """
    texto = request.get_texto()
    if not texto.strip():
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")

    agente = _get_agente(request.sesion_id)
    resultado = agente.chat(texto)
    return MensajeResponse(**resultado)


@app.get("/historial/{sesion_id}", tags=["Agente"])
def obtener_historial(sesion_id: str):
    """Retorna el historial de conversación de una sesión (sin el system prompt)."""
    agente = _get_agente(sesion_id)
    return {"sesion_id": sesion_id, "historial": agente.obtener_historial_chat()}


@app.delete("/historial/{sesion_id}", tags=["Agente"])
def limpiar_historial(sesion_id: str):
    """Reinicia la conversación de una sesión."""
    agente = _get_agente(sesion_id)
    agente.limpiar_historial()
    return {"status": "ok", "mensaje": "Historial reiniciado correctamente."}


@app.get("/estado/{sesion_id}", response_model=EstadoResponse, tags=["Agente"])
def estado_agente(sesion_id: str):
    """Retorna metadatos del agente para la sesión indicada."""
    agente = _get_agente(sesion_id)
    return EstadoResponse(**agente.get_estado())



@app.get("/tareas", tags=["Frontend"])
def obtener_tareas():
    """Retorna la lista plana de todas las tareas sincronizadas en la BD."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, curso, nombre_tarea, enunciado, fecha_limite, estado FROM tareas ORDER BY curso, id")
        filas = cursor.fetchall()
        tareas = []
        for fila in filas:
            tareas.append({
                "id": fila[0],
                "curso": fila[1],
                "nombre_tarea": fila[2],
                "enunciado": fila[3],
                "fecha_limite": fila[4],
                "estado": fila[5]
            })
        return {"status": "ok", "tareas": tareas}
    except Exception as e:
        return {"status": "error", "detalle": str(e)}
    finally:
        conn.close()


@app.get("/tareas/cursos", tags=["Frontend"])
def obtener_tareas_por_curso():
    """Retorna las tareas agrupadas por curso para el sidebar del frontend."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Obtener lista de cursos con sus tareas
        cursor.execute("""
            SELECT c.nombre, c.url,
                   t.id, t.nombre_tarea, t.enunciado, t.fecha_limite, t.estado
            FROM cursos c
            LEFT JOIN tareas t ON t.curso = c.nombre
            ORDER BY c.nombre, t.id
        """)
        filas = cursor.fetchall()
        cursos_dict = {}
        for fila in filas:
            nombre_curso = fila[0]
            if nombre_curso not in cursos_dict:
                cursos_dict[nombre_curso] = {
                    "nombre": nombre_curso,
                    "url": fila[1],
                    "tareas": []
                }
            if fila[2] is not None:  # id de tarea puede ser NULL si LEFT JOIN sin tareas
                cursos_dict[nombre_curso]["tareas"].append({
                    "id": fila[2],
                    "nombre_tarea": fila[3],
                    "enunciado": fila[4],
                    "fecha_limite": fila[5],
                    "estado": fila[6]
                })
        return {"status": "ok", "cursos": list(cursos_dict.values())}
    except Exception as e:
        return {"status": "error", "detalle": str(e)}
    finally:
        conn.close()


class CambioEstadoRequest(BaseModel):
    estado: str  # "Pendiente", "Entregada", "Vencida"


@app.put("/tareas/{tarea_id}/estado", tags=["Frontend"])
def cambiar_estado_tarea(tarea_id: int, body: CambioEstadoRequest):
    """Permite cambiar el estado de una tarea manualmente desde el frontend."""
    estados_validos = ["Pendiente", "Entregada", "Vencida", "En progreso"]
    if body.estado not in estados_validos:
        raise HTTPException(
            status_code=400,
            detail=f"Estado inválido. Debe ser uno de: {', '.join(estados_validos)}"
        )
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE tareas SET estado = ? WHERE id = ?", (body.estado, tarea_id))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Tarea no encontrada.")
        conn.commit()
        return {"status": "ok", "mensaje": f"Estado actualizado a '{body.estado}'."}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        return {"status": "error", "detalle": str(e)}
    finally:
        conn.close()


@app.get("/archivos/estructura", tags=["Frontend"])
def obtener_estructura_archivos():
    """
    Escanea la carpeta UNCP/ local y devuelve el árbol de archivos por curso.
    Solo incluye la carpeta Tareas/ de cada curso (los entregables relevantes).
    """
    # La carpeta UNCP/ está en la raíz del proyecto (un nivel arriba del backend/)
    uncp_root = Path(__file__).parent.parent / "UNCP"
    if not uncp_root.exists():
        return {"status": "ok", "cursos": [], "ruta_base": str(uncp_root)}

    cursos = []
    try:
        for curso_dir in sorted(uncp_root.iterdir()):
            if not curso_dir.is_dir():
                continue

            tareas_dir    = curso_dir / "Tareas"
            materiales_dir = curso_dir / "Materiales"

            archivos_tareas = []
            archivos_materiales = []

            # Archivos en Tareas/
            if tareas_dir.exists():
                for f in sorted(tareas_dir.iterdir()):
                    if f.is_file() and not f.name.startswith('.'):
                        archivos_tareas.append({
                            "nombre": f.name,
                            "ruta": str(f).replace("\\", "/"),
                            "tamano": f.stat().st_size,
                            "extension": f.suffix.lower()
                        })

            # Archivos en Materiales/
            if materiales_dir.exists():
                for f in sorted(materiales_dir.iterdir()):
                    if f.is_file() and not f.name.startswith('.'):
                        archivos_materiales.append({
                            "nombre": f.name,
                            "ruta": str(f).replace("\\", "/"),
                            "tamano": f.stat().st_size,
                            "extension": f.suffix.lower()
                        })

            cursos.append({
                "nombre": curso_dir.name,
                "tareas_dir_existe": tareas_dir.exists(),
                "materiales_dir_existe": materiales_dir.exists(),
                "archivos_tareas": archivos_tareas,
                "archivos_materiales": archivos_materiales
            })

        return {
            "status": "ok",
            "ruta_base": str(uncp_root).replace("\\", "/"),
            "cursos": cursos
        }
    except Exception as e:
        return {"status": "error", "detalle": str(e)}


# ─── Modo CLI (para pruebas rápidas sin levantar el servidor) ──────────────────



def cli():
    """Interfaz de línea de comandos para pruebas locales."""
    init_db()
    print("=" * 52)
    print("  UNCP Agent - Modo CLI (solo para desarrollo)")
    print("=" * 52)
    print("Comandos: 'salir' para terminar | 'limpiar' para reset\n")

    proveedor = os.getenv("LLM_PROVIDER", "gemini").lower()
    agente = UNCPAgent(provider=proveedor)

    while True:
        try:
            pedido = input("Tú: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nSaliendo...")
            break

        if pedido.lower() in ("salir", "exit", "quit"):
            print("Hasta pronto.")
            break

        if pedido.lower() == "limpiar":
            agente.limpiar_historial()
            print("[Sistema] Historial reiniciado.\n")
            continue

        if not pedido:
            continue

        print("\nUNCP_agent: pensando...\n")
        resultado = agente.chat(pedido)

        print(f"UNCP_agent: {resultado['respuesta']}")
        if resultado["herramientas_usadas"]:
            print(f"  [Herramientas: {', '.join(resultado['herramientas_usadas'])}]")
        print()


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="UNCP Agent")
    parser.add_argument("--cli", action="store_true", help="Ejecutar en modo CLI")
    parser.add_argument("--host", default="127.0.0.1", help="Host del servidor API")
    parser.add_argument("--port", type=int, default=8000, help="Puerto del servidor API")
    args = parser.parse_args()

    if args.cli:
        cli()
    else:
        import uvicorn
        uvicorn.run("main:app", host=args.host, port=args.port, reload=True)
