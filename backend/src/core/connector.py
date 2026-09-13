import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

def get_client(provider: str = "gemini"):
    """
    Configura y retorna el cliente OpenAI configurado para el proveedor seleccionado,
    además del nombre del modelo por defecto a usar.
    
    Proveedores soportados:
    - gemini: Usa la API de Google Gemini (requiere GEMINI_API_KEY).
    - ollama: Usa un servidor local de Ollama.
    """
    
    if provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY no encontrada en .env")
        
        # Gemini con compatibilidad OpenAI SDK (tool calling disponible)
        client = OpenAI(
            api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        # gemini-2.0-flash: modelo rápido, soporte completo de tool calling
        model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        return client, model_name
        
    elif provider == "ollama":
        # Configuración estándar para Ollama local
        client = OpenAI(
            api_key="ollama", # Ollama no requiere una API key real
            base_url="http://localhost:11434/v1"
        )
        # Asegúrate de tener este modelo descargado (`ollama run llama3.2`)
        model_name = "llama3.2" 
        return client, model_name
        
    else:
        raise ValueError(f"Proveedor '{provider}' no soportado.")
