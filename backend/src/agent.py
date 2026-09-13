"""
agent.py — Cerebro del UNCP_agent

Implementa un bucle ReAct (Reason + Act) con soporte para:
  - Encadenamiento de múltiples herramientas en una sola vuelta (multi-step)
  - Historial de conversación persistente por sesión
  - Límite de seguridad de iteraciones para evitar bucles infinitos
  - Señal de estado para el frontend (pensando / ejecutando herramienta / respondiendo)
  - Modo CLI y modo API (FastAPI)
"""

import json
import logging
from typing import cast, Generator
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))

from src.core.connector import get_client
from src.tools import TOOLS_SCHEMA, TOOLS_MAP
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolUnionParam

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger("UNCP_agent")

# ─── System Prompt ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """Eres el UNCP_agent, asistente personal institucional para estudiantes de la Universidad Nacional del Centro del Perú (UNCP).

Tu tono es formal, profesional, claro y académico. Nunca uses emojis ni lenguaje coloquial.

=== TUS CAPACIDADES ===
- Sincronizar y listar cursos y tareas desde la plataforma virtual.
- Organizar las carpetas locales del estudiante (estructura UNCP/[Curso]/Tareas/).
- Detectar y alertar sobre tareas próximas a vencer.
- Gestionar la subida de trabajos a la plataforma.

=== PROTOCOLO OBLIGATORIO PARA ENVÍO DE TAREAS ===
Sigue estos pasos en orden estricto. No te saltes ninguno.

PASO 1 — LISTAR: Usa listar_archivos_tarea(curso) para mostrar los archivos disponibles.
PASO 2 — PREPARAR: Usa preparar_envio_tarea(curso, archivo, tarea) para validar y mostrar los detalles al usuario. Luego pregunta explícitamente: "¿Confirma el envío de este archivo para la tarea indicada? Responda 'sí' para proceder o 'no' para cancelar."
PASO 3 — EJECUTAR: ÚNICAMENTE si el usuario responde de forma afirmativa y explícita (ej: 'sí', 'confirmo', 'procede', 'dale'), usa ejecutar_envio_tarea(). En cualquier otro caso, cancela e informa al usuario.

=== REGLAS ABSOLUTAS ===
- JAMÁS ejecutes ejecutar_envio_tarea sin haber completado los PASOS 1 y 2 y recibido confirmación explícita.
- JAMÁS asumas el nombre del archivo. Siempre usa listar_archivos_tarea primero.
- El navegador se abrirá en modo visible. El clic final en "Enviar tarea" lo da el usuario. Informa esto.
- Nunca navegues fuera de los cursos del estudiante ni interactúes con foros o perfiles.
- Si una acción falla, informa el error con claridad y sugiere alternativas."""


# ─── Clase Principal del Agente ───────────────────────────────────────────────

class UNCPAgent:
    """
    Agente ReAct con soporte para multi-turn tool calling.
    El historial de conversación se mantiene en memoria por instancia.
    Para el frontend, crea una instancia por sesión de usuario.
    """

    MAX_ITERACIONES = 8  # Límite de seguridad para evitar bucles infinitos

    def __init__(self, provider: str = "gemini"):
        self.provider = provider
        self.client, self.model = get_client(provider)
        self.historial: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        log.info(f"UNCP_agent iniciado | Proveedor: {provider} | Modelo: {self.model}")

    # ── Procesamiento de herramientas ──────────────────────────────────────────

    def _ejecutar_tool(self, tool_call) -> str:
        """Ejecuta una herramienta del mapa y retorna su resultado como string."""
        nombre = tool_call.function.name
        try:
            argumentos = json.loads(tool_call.function.arguments or "{}")
        except json.JSONDecodeError:
            return f"Error: argumentos JSON inválidos para '{nombre}'."

        log.info(f"Herramienta: {nombre}({argumentos})")

        if nombre not in TOOLS_MAP:
            return f"Error: la herramienta '{nombre}' no existe en este agente."

        try:
            resultado = TOOLS_MAP[nombre](**argumentos)
            return str(resultado)
        except TypeError as e:
            return f"Error de parámetros en '{nombre}': {e}"
        except Exception as e:
            log.error(f"Error ejecutando '{nombre}': {e}")
            return f"Error inesperado ejecutando '{nombre}': {e}"

    # ── Ciclo ReAct principal ──────────────────────────────────────────────────

    def chat(self, mensaje_usuario: str) -> dict:
        """
        Procesa un mensaje del usuario.

        Retorna un dict con:
          - 'respuesta': str — texto final para el usuario
          - 'herramientas_usadas': list[str] — nombres de tools ejecutadas
          - 'iteraciones': int — rondas del bucle ReAct
          - 'error': str | None
        """
        self.historial.append({"role": "user", "content": mensaje_usuario})

        herramientas_usadas = []
        iteracion = 0

        while iteracion < self.MAX_ITERACIONES:
            iteracion += 1
            log.info(f"ReAct iteración {iteracion}/{self.MAX_ITERACIONES}")

            # ── Llamada al modelo ──────────────────────────────────────────────
            try:
                respuesta = self.client.chat.completions.create(
                    model=self.model,
                    messages=self.historial,
                    tools=cast(list[ChatCompletionToolUnionParam], TOOLS_SCHEMA),
                    tool_choice="auto",
                )
            except Exception as e:
                log.error(f"Error llamando al modelo: {e}")
                return {
                    "respuesta": f"Error de comunicación con el modelo de lenguaje: {e}",
                    "herramientas_usadas": herramientas_usadas,
                    "iteraciones": iteracion,
                    "error": str(e),
                }

            mensaje = respuesta.choices[0].message
            finish_reason = respuesta.choices[0].finish_reason

            # ── Sin tool calls → respuesta final ──────────────────────────────
            if not mensaje.tool_calls or finish_reason == "stop":
                contenido = mensaje.content or ""
                self.historial.append({"role": "assistant", "content": contenido})
                log.info(f"Respuesta final entregada tras {iteracion} iteración(es).")
                return {
                    "respuesta": contenido,
                    "herramientas_usadas": herramientas_usadas,
                    "iteraciones": iteracion,
                    "error": None,
                }

            # ── Hay tool calls → ejecutar y continuar bucle ────────────────────
            # Guardamos el mensaje del modelo (con sus tool_calls) en el historial
            self.historial.append(mensaje)

            for tool_call in mensaje.tool_calls:
                herramientas_usadas.append(tool_call.function.name)
                resultado = self._ejecutar_tool(tool_call)

                # Añadir resultado de la herramienta al historial
                self.historial.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": resultado,
                })

        # ── Límite de iteraciones alcanzado ────────────────────────────────────
        aviso = (
            "Se alcanzó el límite de iteraciones del agente. "
            "Es posible que la solicitud sea demasiado compleja. Por favor, reformúlela."
        )
        self.historial.append({"role": "assistant", "content": aviso})
        log.warning("Limite de iteraciones alcanzado.")
        return {
            "respuesta": aviso,
            "herramientas_usadas": herramientas_usadas,
            "iteraciones": iteracion,
            "error": "max_iterations_reached",
        }

    # ── Gestión del historial ──────────────────────────────────────────────────

    def limpiar_historial(self):
        """Reinicia la conversación manteniendo solo el system prompt."""
        self.historial = [{"role": "system", "content": SYSTEM_PROMPT}]
        log.info("Historial de conversación reiniciado.")

    def obtener_historial_chat(self) -> list[dict]:
        """Retorna el historial filtrado (sin el system prompt) para el frontend."""
        return [
            {"role": m["role"], "content": m.get("content", "")}
            for m in self.historial
            if m.get("role") in ("user", "assistant") and m.get("content")
        ]

    def get_estado(self) -> dict:
        """Retorna metadatos del estado actual del agente."""
        return {
            "proveedor": self.provider,
            "modelo": self.model,
            "mensajes_en_historial": len(self.historial),
        }
