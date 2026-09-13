import json
from pathlib import Path
import sys

# Asegurar que el path relativo funcione
sys.path.append(str(Path(__file__).parent.parent))

from src.core.db import get_connection
from src.services.file_manager import FileManager
from src.services.scraper import sincronizar_cursos_y_tareas

fm = FileManager()

def obtener_tareas_pendientes() -> str:
    """Devuelve las tareas pendientes extraídas de la base de datos."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT curso, nombre_tarea, fecha_limite FROM tareas WHERE estado='Pendiente'")
    tareas = cursor.fetchall()
    conn.close()
    
    if not tareas:
        return "No hay tareas pendientes en este momento."
        
    resultado = "Tareas pendientes:\n"
    for curso, nombre, fecha in tareas:
        resultado += f"- [{curso}] {nombre} (Vence: {fecha})\n"
    return resultado

def sincronizar_plataforma() -> str:
    """
    Abre el navegador, inicia sesión en la plataforma UNCP, extrae todos los
    cursos y sus tareas, y los guarda en la base de datos local.
    Retorna un resumen del proceso.
    """
    resultado = sincronizar_cursos_y_tareas()
    return resultado["resumen"]


def listar_cursos() -> str:
    """Devuelve todos los cursos registrados en la base de datos local."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT nombre FROM cursos ORDER BY nombre")
        cursos = cursor.fetchall()
    except Exception:
        cursos = []
    finally:
        conn.close()

    if not cursos:
        return (
            "No hay cursos en la base de datos local. "
            "Solicite al usuario que ejecute una sincronización primero."
        )
    return "Cursos registrados:\n" + "\n".join(f"- {c[0]}" for c in cursos)


def organizar_carpetas(cursos_str: str) -> str:
    """Recibe una lista de cursos separados por coma y crea las carpetas."""
    cursos = [c.strip() for c in cursos_str.split(",") if c.strip()]
    res = fm.setup_course_folders(cursos)
    return f"Carpetas creadas/verificadas para {len(cursos)} cursos en la raíz {res['root']}."

def listar_archivos_tarea(curso: str) -> str:
    """Lista los archivos disponibles en la carpeta Tareas del curso indicado."""
    res = fm.listar_archivos_tareas(curso)
    if not res['found']:
        return f"Error: {res['error']}"
    if not res['archivos']:
        return (
            f"La carpeta de tareas del curso existe ({res['course_path']}) "
            f"pero está vacía. Copia el archivo a entregar en esa carpeta primero."
        )
    lista = "\n".join(f"  - {f}" for f in res['archivos'])
    return (
        f"Archivos disponibles en la carpeta de tareas de '{curso}':\n"
        f"{lista}\n\n"
        f"Ruta de la carpeta: {res['course_path']}"
    )

def preparar_envio_tarea(curso: str, archivo: str, tarea: str) -> str:
    """Verifica el archivo local y prepara los detalles para la confirmación del usuario."""
    res = fm.verify_file_for_upload(curso, archivo)
    if not res['valid']:
        return f"Error al preparar envío: {res['error_message']}"
    
    archivos_str = "\n".join(f"- {p}" for p in res['file_paths'])
    return (
        f"Archivos validados correctamente.\n"
        f"Detalles para confirmar:\n"
        f"- Tarea: {tarea}\n"
        f"- Curso: {curso}\n"
        f"Archivos:\n{archivos_str}\n\n"
        f"POR FAVOR, PREGUNTA AL USUARIO SI CONFIRMA ESTE ENVÍO ANTES DE EJECUTARLO. "
        f"Aclara que la ejecución abrirá el navegador de forma visible, adjuntará los archivos y se pausará esperando un clic manual final del usuario (o confirmación) para mayor seguridad."
    )

def ejecutar_envio_tarea(curso: str, archivo: str, tarea: str) -> str:
    """Ejecuta el envío final. Solo debe llamarse tras la confirmación del usuario."""
    from src.services.scraper import subir_tarea_plataforma
    res = fm.verify_file_for_upload(curso, archivo)
    if not res['valid']:
         return f"Error: Archivo(s) no válido(s). {res['error_message']}"
    
    # Llamamos al script de scraper que abre la plataforma en modo visible y pausa.
    resultado = subir_tarea_plataforma(curso, tarea, res['file_paths'])
    return resultado['resumen']

# ---------------------------------------------------------------------
# Registro de herramientas (Schema de OpenAI)
# ---------------------------------------------------------------------
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "sincronizar_plataforma",
            "description": (
                "Abre un navegador, inicia sesión en la plataforma UNCP, extrae la lista "
                "de cursos y todas las tareas disponibles, y las guarda en la base de datos "
                "local. Usar cuando el usuario pida 'sincronizar', 'actualizar tareas' o "
                "'mostrar mis cursos' por primera vez."
            ),
            "parameters": {"type": "object", "properties": {}},
        }
    },
    {
        "type": "function",
        "function": {
            "name": "listar_cursos",
            "description": "Muestra todos los cursos registrados en la base de datos local.",
            "parameters": {"type": "object", "properties": {}},
        }
    },
    {
        "type": "function",
        "function": {
            "name": "obtener_tareas_pendientes",
            "description": "Consulta las tareas académicas pendientes del usuario y sus fechas límite.",
            "parameters": {"type": "object", "properties": {}},
        }
    },
    {
        "type": "function",
        "function": {
            "name": "organizar_carpetas",
            "description": "Crea o verifica la estructura local de carpetas (Materiales y Tareas) para los cursos dados.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cursos_str": {
                        "type": "string",
                        "description": "Lista de nombres de cursos separados por comas. Ej: 'Matemática, Física II'",
                    }
                },
                "required": ["cursos_str"],
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "listar_archivos_tarea",
            "description": "Lista los archivos disponibles en la carpeta local 'Tareas' del curso indicado. Usar SIEMPRE antes de preparar_envio_tarea para confirmar qué archivos existen, evitando que el usuario tenga que escribir rutas completas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "curso": {"type": "string", "description": "Nombre del curso cuya carpeta Tareas se quiere listar."},
                },
                "required": ["curso"],
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "preparar_envio_tarea",
            "description": "Paso 1 del envío: Verifica que el archivo exista localmente y esté listo. Devuelve los detalles que DEBES mostrar al usuario para pedirle confirmación obligatoria.",
            "parameters": {
                "type": "object",
                "properties": {
                    "curso": {"type": "string", "description": "Nombre del curso."},
                    "archivo": {"type": "string", "description": "Nombre de los archivos a enviar, separados por comas (ej. 'tarea1.pdf, tarea2.pdf')."},
                    "tarea": {"type": "string", "description": "Nombre de la tarea en la plataforma."},
                },
                "required": ["curso", "archivo", "tarea"],
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ejecutar_envio_tarea",
            "description": "Paso 2 del envío: ¡ATENCIÓN! NO USAR sin la confirmación previa explícita del usuario obtenida tras preparar_envio_tarea. Esta función sube el archivo a la plataforma.",
            "parameters": {
                "type": "object",
                "properties": {
                    "curso": {"type": "string", "description": "Nombre del curso."},
                    "archivo": {"type": "string", "description": "Nombre de los archivos a enviar, separados por comas."},
                    "tarea": {"type": "string", "description": "Nombre de la tarea en la plataforma."},
                },
                "required": ["curso", "archivo", "tarea"],
            }
        }
    }
]

TOOLS_MAP = {
    "sincronizar_plataforma": sincronizar_plataforma,
    "listar_cursos": listar_cursos,
    "obtener_tareas_pendientes": obtener_tareas_pendientes,
    "organizar_carpetas": organizar_carpetas,
    "listar_archivos_tarea": listar_archivos_tarea,
    "preparar_envio_tarea": preparar_envio_tarea,
    "ejecutar_envio_tarea": ejecutar_envio_tarea,
}
