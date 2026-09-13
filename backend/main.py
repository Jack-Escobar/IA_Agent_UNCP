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
from src.core.db import init_db

# ─── Modelos de Request/Response ──────────────────────────────────────────────

class MensajeRequest(BaseModel):
    mensaje: str
    sesion_id: str = "default"  # Identificador de sesión para multi-usuario (futuro)

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

# CORS: permite peticiones desde el frontend local (Vite/React suele usar 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:5173"],
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
    if not request.mensaje.strip():
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")

    agente = _get_agente(request.sesion_id)
    resultado = agente.chat(request.mensaje)
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
