# UNCP Agent - Asistente Académico Autónomo

**UNCP_agent** es un asistente de Inteligencia Artificial diseñado para optimizar el flujo de trabajo académico de estudiantes de la Universidad Nacional del Centro del Perú (UNCP). Integra automatización web, gestión local de archivos y un agente basado en LLM (gemini).

---

## 🎯 Características Principales

- **Sincronización Automática:** Extrae cursos y plazos de tareas pendientes desde la plataforma virtual (ERP UNCP).
- **Gestión Local Organizada:** Administra automáticamente un sistema de archivos local (`UNCP/[Curso]/Tareas/`) para guardar materiales y entregables.
- **Asistente Conversacional:** Interfaz de chat moderna para interactuar en lenguaje natural con el sistema.
- **Envíos Asistidos Seguros:** Prepara el envío de tareas automáticamente, requiriendo **siempre la confirmación final** del usuario antes de la entrega definitiva.

---

## 🏗️ Arquitectura del Proyecto

El proyecto está dividido en dos componentes principales:

1. **`backend/` (FastAPI + Playwright + Agente ReAct)**:
   - Proveedor de la API REST (`/chat`, `/estado`, `/historial`).
   - Scraper con Playwright para interactuar con la plataforma virtual universitaria.
   - Agente inteligente que razona y utiliza herramientas (Listar archivos, Sincronizar, Preparar envío).
   - Base de datos SQLite local para registro de tareas y evitar raspados innecesarios.

2. **`frontend/` (SPA Vanilla HTML5/CSS3/JS)**:
   - Interfaz web institucional con chat en tiempo real, barra lateral de cursos/tareas y estado de conexión.

---

## 📋 Requisitos Previos

1. **Python 3.10+** instalado.
2. Dependencias principales (`fastapi`, `uvicorn`, `playwright`, `openai`, `python-dotenv`).

```bash
# Instalación de dependencias
cd backend
pip install -r requirements.txt

# Instalación de navegadores de Playwright
python -m playwright install chromium
```

---

## ⚙️ Configuración

1. En la carpeta `backend/`, copia el archivo `.env.example` a `.env`.
2. Completa tus credenciales de acceso y clave API:

```env
# Credenciales del Portal UNCP
UNCP_USER=tu_usuario
UNCP_PASS=tu_contraseña

# Claves de LLM (Para el modelo Gemini a través del SDK compatible con OpenAI)
OPENAI_API_KEY=tu_gemini_api_key
GEMINI_MODEL=gemini-2.0-flash
LLM_PROVIDER=gemini
```

---

## 🚀 Cómo Ejecutar el Proyecto

Para utilizar la aplicación web completa, necesitas iniciar tanto el Backend como el Frontend en terminales separadas.

### 1. Iniciar el Backend (API)
Abre una terminal y ejecuta:

```bash
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```
> La API estará disponible en `http://127.0.0.1:8000`

### 2. Iniciar el Frontend (Web UI)
Abre una **segunda terminal** y ejecuta:

```bash
cd frontend
python -m http.server 3000
```
> Accede a la interfaz web desde tu navegador en **`http://127.0.0.1:3000`**

---

## ⚠️ Detalles de Seguridad y Límites (Importante)

El agente opera bajo reglas estrictas para proteger tu información y desempeño académico:

1. **Sin Envíos Automáticos**: El agente **NUNCA** hace clic en "Enviar tarea" por sí mismo. Prepara todo (inicio de sesión, navegación, carga del archivo) y pausa el navegador de forma visible para que tú confirmes la entrega manualmente.
2. **Archivos Locales Controlados**: Para realizar un envío, el archivo debe encontrarse exclusivamente en la carpeta `UNCP/[Nombre_del_Curso]/Tareas/` correspondiente.
3. **Restricción de Acciones Web**: El bot no interactúa en foros, no modifica datos de perfil y no publica comentarios.
4. **Almacenamiento Local**: Todo el historial de chats y el registro de tareas se guarda de manera 100% local en tu sistema (SQLite/JSON). Las credenciales nunca se comparten fuera del script de automatización y el modelo LLM.

---

## 🛠️ Opciones de Despliegue en la Nube

Si deseas ejecutar este proyecto de forma remota, la arquitectura recomendada es:
- **Frontend**: AWS Amplify (Despliegue automático y estático).
- **Backend (FastAPI + Playwright)**: Instancia de Amazon EC2 (t3.micro/small).
*Nota: AWS Lambda no es compatible con el módulo Playwright debido a sus requerimientos de interfaz gráfica para el modo asistido visible.*
