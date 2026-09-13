import os
import sys
import sqlite3
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeout

# Cargar variables de entorno desde el archivo .env
load_dotenv()

USER = os.getenv("UNCP_USER")
PASS = os.getenv("UNCP_PASS")

BASE_URL = "https://erpaprendizaje.uncp.edu.pe"

# Ruta de la base de datos
DB_FILE = Path(__file__).parent.parent.parent / "data" / "uncp_tasks.db"


# ─────────────────────────────────────────────
# HELPERS DE BASE DE DATOS
# ─────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    """Retorna una conexión a la BD local."""
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_FILE)


def _save_curso(conn: sqlite3.Connection, nombre: str, url: str):
    """Inserta o actualiza un curso en la BD."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cursos (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            url    TEXT NOT NULL
        )
    """)
    conn.execute(
        "INSERT OR REPLACE INTO cursos (nombre, url) VALUES (?, ?)",
        (nombre.strip(), url.strip())
    )


def _save_tarea(conn: sqlite3.Connection, curso: str, nombre_tarea: str,
                enunciado: str, fecha_limite: str):
    """
    Inserta o actualiza una tarea en la BD.
    - Si la tarea ya existía con estado 'Entregada', NO sobreescribe ese estado.
    - Si la fecha_limite ya venció, marca automáticamente como 'Vencida'.
    - Si no, deja el estado en 'Pendiente'.
    """
    import re
    from datetime import datetime

    conn.execute("""
        CREATE TABLE IF NOT EXISTS tareas (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            curso        TEXT NOT NULL,
            nombre_tarea TEXT NOT NULL,
            enunciado    TEXT,
            fecha_limite TEXT,
            estado       TEXT DEFAULT 'Pendiente',
            UNIQUE(curso, nombre_tarea)
        )
    """)

    # Determinar si la tarea está vencida según la fecha_limite
    nuevo_estado = "Pendiente"
    if fecha_limite:
        # Intentar parsear la fecha en múltiples formatos comunes
        formatos = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S"]
        fecha_dt = None
        # Extraer solo la parte de fecha si hay texto adicional (ej: "Cierre: 10/09/2026")
        match = re.search(r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})", fecha_limite)
        if match:
            fecha_str = match.group(1)
            for fmt in formatos:
                try:
                    fecha_dt = datetime.strptime(fecha_str, fmt)
                    break
                except ValueError:
                    continue
        if fecha_dt and fecha_dt.date() < datetime.now().date():
            nuevo_estado = "Vencida"

    # Insertar o actualizar — pero NO sobreescribir estado si ya fue marcado como 'Entregada'
    conn.execute("""
        INSERT INTO tareas (curso, nombre_tarea, enunciado, fecha_limite, estado)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(curso, nombre_tarea) DO UPDATE SET
            enunciado    = excluded.enunciado,
            fecha_limite = excluded.fecha_limite,
            estado       = CASE
                WHEN tareas.estado = 'Entregada' THEN 'Entregada'
                ELSE excluded.estado
            END
    """, (curso.strip(), nombre_tarea.strip(), enunciado.strip(), fecha_limite.strip(), nuevo_estado))


# ─────────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────────

def _login(page: Page) -> bool:
    """
    Realiza el proceso de inicio de sesión en la plataforma.
    Retorna True si el login fue exitoso, False en caso contrario.
    """
    print("[INFO] Navegando a la plataforma UNCP...")
    try:
        page.goto(f"{BASE_URL}/", wait_until="domcontentloaded", timeout=60000)
    except Exception:
        page.wait_for_timeout(3000)

    page.wait_for_selector("#UserName", timeout=15000)
    page.wait_for_selector("#Password", timeout=15000)

    print(f"[INFO] Ingresando credenciales para el usuario: {USER}")
    page.fill("#UserName", USER)
    page.fill("#Password", PASS)

    # Pausa breve para que reCAPTCHA v3 genere el token en segundo plano
    page.wait_for_timeout(1500)
    page.click("#m_login_signin_submit")

    print("[INFO] Esperando respuesta del servidor...")
    page.wait_for_timeout(6000)

    current_url = page.url
    if "/login" not in current_url:
        print(f"[ÉXITO] Sesión iniciada. URL actual: {current_url}")
        return True
    else:
        error_el = page.query_selector(
            ".validation-summary-errors, .field-validation-error, .text-danger ul li"
        )
        error_text = error_el.inner_text().strip() if error_el else "Credenciales inválidas o timeout."
        print(f"[ERROR] No se pudo iniciar sesión: {error_text}")
        return False


# ─────────────────────────────────────────────
# EXTRACCIÓN DE CURSOS
# ─────────────────────────────────────────────

def _extraer_cursos(page: Page) -> list[dict]:
    """
    Navega al dashboard y extrae todos los cursos disponibles.

    La plataforma usa AngularJS: los cursos se renderizan dinámicamente.
    Es necesario esperar a que Angular termine de inyectar los datos reales
    antes de leer el DOM (de lo contrario se leen plantillas {{...}}).

    Selectores confirmados por diagnóstico:
      - Contenedor: .row-body.box-courses
      - Cada fila:  .row-course  (con ng-repeat="course in listCourses")
      - Nombre:     span.title-course
      - Link:       a[href*="/web/course?s="]  (con UUID real tras renderizado)
    """
    print("[INFO] Extrayendo cursos disponibles desde el dashboard...")

    # Navegar al inicio para asegurar estar en el dashboard
    try:
        page.goto(f"{BASE_URL}/", wait_until="domcontentloaded", timeout=60000)
    except Exception:
        page.wait_for_timeout(3000)

    # ── Esperar a que Angular renderice los cursos ──────────────────────
    # Angular reemplaza {{course.sectionId}} por un UUID real.
    # Esperamos hasta que al menos un link .row-course > a tenga un UUID real
    # (es decir, su href NO contenga '{{').
    print("[INFO] Esperando renderizado de AngularJS...")
    try:
        page.wait_for_function(
            """() => {
                const links = document.querySelectorAll('a[href*="/web/course?s="]');
                // Al menos un link debe tener un href sin llaves de plantilla
                return links.length > 0 && !links[0].getAttribute('href').includes('{{');
            }""",
            timeout=20000
        )
        print("[INFO] Angular terminó de renderizar los cursos.")
    except PlaywrightTimeout:
        print("[WARN] Angular tardó demasiado. Intentando extracción parcial...")
    # Pausa adicional para que termine el scroll virtual si existe
    page.wait_for_timeout(1500)

    # ── Scroll para cargar todos los cursos (lista scrolleable) ─────────
    contenedor_cursos = page.query_selector(".row-body.box-courses")
    cursos_extraidos = set()

    for _ in range(30):  # máximo 30 iteraciones de scroll
        # Extraer todos los cursos visibles con datos reales
        datos = page.evaluate(
            """() => {
                const rows = document.querySelectorAll('.row-course');
                const resultado = [];
                for (const row of rows) {
                    const link = row.querySelector('a[href*="/web/course?s="]');
                    const titulo = row.querySelector('span.title-course');
                    if (!link || !titulo) continue;

                    const href  = link.getAttribute('href') || '';
                    const nombre = titulo.innerText.trim();

                    // Ignorar si aún son plantillas de Angular sin resolver
                    if (href.includes('{{') || nombre.includes('{{')) continue;
                    if (!href || !nombre) continue;

                    resultado.push({ nombre: nombre, href: href });
                }
                return resultado;
            }"""
        )

        nuevos = 0
        for d in datos:
            if d["href"] not in cursos_extraidos:
                cursos_extraidos.add(d["href"])
                nuevos += 1

        # Scroll hacia abajo dentro del contenedor de cursos
        if contenedor_cursos:
            contenedor_cursos.evaluate("el => el.scrollTop += 400")
        else:
            page.evaluate("window.scrollBy(0, 400)")

        page.wait_for_timeout(700)

        # Si no hay nuevos cursos tras el scroll, terminamos
        if nuevos == 0 and len(cursos_extraidos) > 0:
            break

    # Reconstruir la lista final con nombre + URL completa
    # Hacemos una extracción final con todos los datos
    datos_finales = page.evaluate(
        """() => {
            const rows = document.querySelectorAll('.row-course');
            const resultado = [];
            for (const row of rows) {
                const link  = row.querySelector('a[href*="/web/course?s="]');
                const titulo = row.querySelector('span.title-course');
                if (!link || !titulo) continue;
                const href   = link.getAttribute('href') || '';
                const nombre = titulo.innerText.trim();
                if (href.includes('{{') || nombre.includes('{{')) continue;
                resultado.push({ nombre: nombre, href: href });
            }
            return resultado;
        }"""
    )

    # Reconstruir lista final deduplicada por URL
    visto = set()
    cursos = []
    for d in datos_finales:
        url_completa = d["href"] if d["href"].startswith("http") else f"{BASE_URL}{d['href']}"
        if url_completa not in visto and d["nombre"] and not d["href"].startswith("#"):
            visto.add(url_completa)
            cursos.append({"nombre": d["nombre"], "url": url_completa})

    print(f"[INFO] Se encontraron {len(cursos)} cursos.")
    for c in cursos:
        print(f"       -> {c['nombre']}")
    return cursos




# ─────────────────────────────────────────────
# EXTRACCIÓN DE TAREAS POR CURSO
# ─────────────────────────────────────────────

def _extraer_tareas_de_curso(page: Page, curso: dict) -> list[dict]:
    """
    Extrae todas las tareas de un curso navegando directamente a la URL de tareas.

    Insight del diagnostico: la URL de tareas comparte el mismo sectionId que el curso:
      /web/course?s=<UUID>   →   /web/homework?s=<UUID>

    Esto evita tener que hacer clic en el boton "Tareas" dentro de la pagina del curso,
    lo que es mas rapido y robusto.
    """
    nombre_curso = curso["nombre"]
    url_curso    = curso["url"]

    # Extraer el sectionId del parametro ?s= de la URL del curso
    seccion_id = ""
    if "?s=" in url_curso:
        seccion_id = url_curso.split("?s=")[-1].strip()

    if not seccion_id:
        print(f"[WARN] No se pudo extraer sectionId de: {url_curso}. Saltando.")
        return []

    url_tareas = f"{BASE_URL}/web/homework?s={seccion_id}"
    print(f"\n[INFO] Curso: {nombre_curso}")
    print(f"       Navegando a tareas: {url_tareas}")

    # Navegar directamente a la pagina de tareas
    try:
        page.goto(url_tareas, wait_until="domcontentloaded", timeout=60000)
    except Exception:
        page.wait_for_timeout(3000)

    # Esperar a que Angular termine de renderizar la lista de tareas
    # Angular puede mostrar un spinner de carga mientras obtiene los datos
    try:
        page.wait_for_function(
            """() => {
                // Esperar hasta que el spinner de carga desaparezca O haya contenido real
                const spinner = document.querySelector('img[src*="loading"]');
                const contenido = document.querySelector('.m-portlet__body');
                if (spinner && spinner.offsetParent !== null) return false; // aun cargando
                return contenido !== null;
            }""",
            timeout=15000
        )
    except Exception:
        page.wait_for_timeout(3000)

    page.wait_for_timeout(1000)

    # Verificar si no hay tareas disponibles (mensaje Angular renderizado)
    contenido_texto = ""
    try:
        contenido_texto = page.inner_text(".m-portlet__body") or ""
    except Exception:
        contenido_texto = page.inner_text("body") or ""

    if "no hay tareas" in contenido_texto.lower():
        print(f"       Sin tareas disponibles en este curso.")
        return []

    # Extraer tareas — intentar con multiples selectores posibles
    # (cuando haya tareas reales podremos ajustar estos selectores)
    tareas = []

    datos_tareas = page.evaluate(
        """() => {
            const resultado = [];

            // Intentar diferentes estructuras de lista de tareas
            const selectores = [
                '.row-annoucement',      // clase observada en el diagnóstico
                '.row-homework',
                '.homework-item',
                'tr.ng-scope',
                '.m-widget4__item',
                '.list-group-item',
                'table tbody tr',
            ];

            let filas = [];
            for (const sel of selectores) {
                filas = document.querySelectorAll(sel);
                if (filas.length > 0) break;
            }

            for (const fila of filas) {
                const texto = fila.innerText.trim();
                if (!texto || texto.length < 3) continue;

                // Buscar nombre de la tarea (primer texto significativo)
                const nombreEl = fila.querySelector(
                    'h3, span.title-homework, .homework-title, td:first-child, ' +
                    'span.ng-binding, h5, h4, strong'
                );
                const nombre = nombreEl ? nombreEl.innerText.trim() : texto.split('\\n')[0].trim();

                // Buscar fecha limite (priorizando la de cierre)
                const lineas = texto.split('\\n').map(l => l.trim()).filter(Boolean);
                let fecha = '';
                
                // 1. Buscar explicitamente fecha de cierre
                for (const linea of lineas) {
                    if (linea.toLowerCase().includes('cierre') || 
                        linea.toLowerCase().includes('vence') || 
                        linea.toLowerCase().includes('límite') ||
                        linea.toLowerCase().includes('limite')) {
                        fecha = linea;
                        break;
                    }
                }
                
                // 2. Si no hay cierre explícito, tomar la última fecha válida disponible
                if (!fecha) {
                    for (const linea of lineas) {
                        if (/\\d{2}[/\\-]\\d{2}[/\\-]\\d{4}/.test(linea) ||
                            linea.toLowerCase().includes('fecha') ||
                            linea.toLowerCase().includes('entrega')) {
                            fecha = linea;
                        }
                    }
                }

                if (nombre && !nombre.includes('{{')) {
                    resultado.push({
                        nombre_tarea: nombre,
                        enunciado: lineas[1] || '',
                        fecha_limite: fecha
                    });
                }
            }
            return resultado;
        }"""
    )

    tareas = datos_tareas
    print(f"       {len(tareas)} tarea(s) encontrada(s).")
    return tareas



# ─────────────────────────────────────────────
# FUNCIÓN PRINCIPAL PÚBLICA
# ─────────────────────────────────────────────

def sincronizar_cursos_y_tareas() -> dict:
    """
    Función principal llamada por el agente ReAct cuando el usuario solicita
    sincronizar sus cursos y tareas con la plataforma UNCP.

    Proceso:
    1. Login en la plataforma.
    2. Extracción de todos los cursos disponibles.
    3. Por cada curso, extracción de tareas pendientes.
    4. Guardado en SQLite local.

    Retorna:
        dict con 'cursos' (list) y 'resumen' (str) para el agente.
    """
    if not USER or not PASS:
        return {
            "exito": False,
            "resumen": "Error: No se encontraron credenciales en el archivo .env (UNCP_USER / UNCP_PASS)."
        }

    print("\n" + "=" * 60)
    print("  SINCRONIZACIÓN DE CURSOS Y TAREAS — UNCP")
    print("=" * 60)

    resultado_cursos = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized"
            ]
        )
        context = browser.new_context(
            no_viewport=True,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        try:
            # 1. Login
            if not _login(page):
                browser.close()
                return {
                    "exito": False,
                    "resumen": "Error: No se pudo iniciar sesión en la plataforma UNCP."
                }

            # 2. Extraer cursos
            cursos = _extraer_cursos(page)
            if not cursos:
                browser.close()
                return {
                    "exito": False,
                    "resumen": "No se encontraron cursos disponibles en el dashboard."
                }

            # 3. Guardar cursos y extraer tareas
            conn = _get_conn()

            for curso in cursos:
                _save_curso(conn, curso["nombre"], curso["url"])

                tareas = _extraer_tareas_de_curso(page, curso)
                for tarea in tareas:
                    _save_tarea(
                        conn,
                        curso["nombre"],
                        tarea["nombre_tarea"],
                        tarea["enunciado"],
                        tarea["fecha_limite"]
                    )

                resultado_cursos.append({
                    "curso": curso["nombre"],
                    "tareas_encontradas": len(tareas)
                })

            conn.commit()
            conn.close()

            # Construir resumen para el agente (solo ASCII para compatibilidad Windows)
            total_tareas = sum(r["tareas_encontradas"] for r in resultado_cursos)
            resumen_lineas = [
                "[OK] Sincronizacion completada exitosamente.",
                f"Cursos registrados: {len(cursos)}",
                f"Tareas totales encontradas: {total_tareas}",
                "",
                "Detalle por curso:"
            ]
            for r in resultado_cursos:
                icono = "[!]" if r["tareas_encontradas"] > 0 else "[ok]"
                resumen_lineas.append(
                    f"  {icono} {r['curso']}: {r['tareas_encontradas']} tarea(s)"
                )

            resumen = "\n".join(resumen_lineas)
            print("\n" + resumen)

            return {
                "exito": True,
                "cursos": resultado_cursos,
                "resumen": resumen
            }

        except Exception as e:
            print(f"[ERROR] Excepción durante la sincronización: {e}")
            return {
                "exito": False,
                "resumen": f"Error inesperado durante la sincronización: {str(e)}"
            }
        finally:
            print("\n[INFO] Cerrando navegador...")
            browser.close()


# ─────────────────────────────────────────────
# SUBIDA DE TAREA (VISUAL CON PAUSA)
# ─────────────────────────────────────────────

def subir_tarea_plataforma(curso: str, tarea_nombre: str, rutas_archivos: list[str]) -> dict:
    """
    Simula la navegacion para subir uno o varios archivos a una tarea especifica.
    ATENCION: Este script NO presiona el boton final de envio. Deja el navegador
    abierto en pausa para que el usuario valide y confirme la entrega.

    Flujo:
      1. Login
      2. Navegar a la lista de tareas del curso
      3. Hacer clic en 'Ver detalle' de la tarea específica
      4. Adjuntar el archivo via input[type=file]
      5. *** PAUSA OBLIGATORIA *** — el script se detiene aquí.
         El usuario DEBE confirmar visualmente y hacer clic en 'Enviar tarea' él mismo.

    Ejecutado siempre en modo VISIBLE (headless=False) por directiva de seguridad (AGENTS.md).
    """
    if not USER or not PASS:
        return {"exito": False, "resumen": "Error: Credenciales no configuradas en .env."}

    print("\n" + "=" * 60)
    print(f"  PREPARANDO ENVIO DE TAREA: {tarea_nombre}")
    print(f"  Curso : {curso}")
    
    nombres_archivos = [os.path.basename(p) for p in rutas_archivos]
    print(f"  Archivo(s): {', '.join(nombres_archivos)}")
    print("=" * 60)

    # Validar que los archivos existan antes de abrir el navegador
    for ruta in rutas_archivos:
        if not os.path.isfile(ruta):
            return {"exito": False, "resumen": f"El archivo '{ruta}' no existe en el sistema local."}

    with sync_playwright() as p:
        # MODO VISIBLE — nunca headless para envíos
        browser = p.chromium.launch(
            headless=False,
            args=["--start-maximized", "--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            no_viewport=True,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        try:
            # ── 1. Login ────────────────────────────────────────────────
            if not _login(page):
                browser.close()
                return {"exito": False, "resumen": "Fallo al iniciar sesion en la plataforma."}

            # ── 2. Buscar el curso ──────────────────────────────────────
            print(f"\n[INFO] Buscando el curso '{curso}' en la plataforma...")
            cursos = _extraer_cursos(page)

            # Busqueda flexible: exacta primero, luego parcial (insensible a mayusculas)
            curso_target = None
            curso_lower = curso.lower().strip()
            for c in cursos:
                if c["nombre"].lower() == curso_lower:
                    curso_target = c
                    break
            if not curso_target:
                for c in cursos:
                    if curso_lower in c["nombre"].lower() or c["nombre"].lower() in curso_lower:
                        curso_target = c
                        break

            if not curso_target:
                browser.close()
                nombres = [c["nombre"] for c in cursos]
                return {
                    "exito": False,
                    "resumen": f"No se encontro el curso '{curso}'. Cursos disponibles: {nombres}"
                }

            print(f"[OK] Curso encontrado: {curso_target['nombre']}")

            # ── 3. Navegar a la lista de tareas del curso ───────────────
            seccion_id = ""
            if "?s=" in curso_target["url"]:
                seccion_id = curso_target["url"].split("?s=")[-1].strip()

            url_tareas = f"{BASE_URL}/web/homework?s={seccion_id}"
            print(f"[INFO] Navegando a tareas: {url_tareas}")
            page.goto(url_tareas, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)

            # ── 4. Hacer clic en 'Ver detalle' de la tarea ─────────────
            print(f"[INFO] Buscando el boton 'Ver detalle' para la tarea '{tarea_nombre}'...")

            # Buscamos el elemento de la tarea por su texto y luego el enlace/boton de detalle
            # La estructura HTML observada en la imagen:
            #   .row-annoucement  (fila de tarea)
            #     → encabezado con nombre de tarea
            #     → boton/enlace "Ver detalle" (si está disponible)
            tarea_encontrada = False
            tarea_lower = tarea_nombre.lower().strip()

            filas = page.query_selector_all(".row-annoucement")
            for fila in filas:
                texto_fila = (fila.inner_text() or "").lower()
                if tarea_lower in texto_fila:
                    # Buscar el boton o enlace de "Ver detalle" dentro de esta fila
                    btn_detalle = fila.query_selector("a[href*='/web/homework/upload'], button")
                    if not btn_detalle:
                        # Intentar buscar por texto
                        btn_detalle = fila.query_selector("a")

                    if btn_detalle:
                        print(f"[OK] Tarea encontrada. Haciendo clic en 'Ver detalle'...")
                        btn_detalle.click()
                        tarea_encontrada = True
                        break
                    else:
                        # Si no hay boton, la tarea puede no estar disponible aun
                        print(f"[WARN] Se encontro la tarea pero no tiene boton de entrega activo.")
                        browser.close()
                        return {
                            "exito": False,
                            "resumen": f"La tarea '{tarea_nombre}' no tiene disponible la opcion de entrega en este momento. Revisa la fecha de apertura."
                        }

            if not tarea_encontrada:
                browser.close()
                return {
                    "exito": False,
                    "resumen": f"No se encontro la tarea '{tarea_nombre}' en la lista del curso. Verifica que el nombre sea correcto."
                }

            # ── 5. Esperar la pagina de carga de archivo ────────────────
            print("[INFO] Esperando la pagina de subida de tarea...")
            page.wait_for_url("**/homework/upload**", timeout=15000)
            page.wait_for_timeout(2000)

            # ── 6. Adjuntar el archivo ──────────────────────────────────
            # La pagina de la UNCP no permite multiples archivos en un solo set_input_files,
            # requiere clickear "Adjuntar" y usar el nuevo input por cada archivo extra.
            nombres_archivos = [os.path.basename(p) for p in rutas_archivos]
            print(f"[INFO] Adjuntando {len(rutas_archivos)} archivo(s): {', '.join(nombres_archivos)}")

            for ruta in rutas_archivos:
                # Buscamos el boton para agregar un nuevo slot de archivo
                btn_adjuntar = page.query_selector("button:has-text('Adjuntar'), a:has-text('Adjuntar')")
                if btn_adjuntar:
                    btn_adjuntar.click()
                    page.wait_for_timeout(1000)
                
                inputs_file = page.query_selector_all("input[type='file']")
                if not inputs_file:
                    browser.close()
                    return {"exito": False, "resumen": "No se pudo encontrar el campo de subida de archivo en la pagina."}
                
                # Asignar el archivo al último input disponible (el que se acaba de crear)
                ultimo_input = inputs_file[-1]
                ultimo_input.set_input_files(ruta)
                print(f"[OK] Archivo '{os.path.basename(ruta)}' adjuntado.")
                page.wait_for_timeout(1000)

            page.wait_for_timeout(1500)

            # ── 7. PAUSA OBLIGATORIA antes de 'Enviar tarea' ────────────
            # El agente NUNCA hara clic en 'Enviar tarea' automáticamente.
            # El usuario debe revisar y confirmar visualmente antes de enviar.
            print("\n" + "!" * 60)
            print("  [ATENCION — ACCION REQUERIDA DEL USUARIO]")
            print("!")
            print(f"  Archivo(s) '{', '.join(nombres_archivos)}' adjuntado(s).")
            print("  El script esta en PAUSA.")
            print("  Revisa la ventana del navegador:")
            print("    1. Verifica que el archivo adjunto sea el correcto.")
            print("    2. Si estas de acuerdo, haz clic en 'Enviar tarea'.")
            print("    3. Si deseas cancelar, simplemente cierra la ventana.")
            print("!" * 60)

            # page.pause() abre el Playwright Inspector — el script queda suspendido
            # hasta que el usuario cierre el inspector o haga clic en Resume.
            page.pause()

            return {
                "exito": True,
                "resumen": (
                    f"El/los archivo(s) '{', '.join(nombres_archivos)}' fue/fueron adjuntado(s) exitosamente "
                    f"en la tarea '{tarea_nombre}'. El navegador quedó en pausa para que el "
                    f"usuario realice la confirmación y envío final."
                )
            }

        except PlaywrightTimeout:
            return {"exito": False, "resumen": "Tiempo de espera agotado durante la navegacion. Intente de nuevo."}
        except Exception as e:
            return {"exito": False, "resumen": f"Error inesperado durante la subida: {str(e)}"}
        finally:
            try:
                browser.close()
            except Exception:
                pass


# ─────────────────────────────────────────────
# TEST DIRECTO (legacy, se mantiene para pruebas)
# ─────────────────────────────────────────────

def test_uncp_login():
    """Script de prueba de autenticación (uso directo por terminal)."""
    resultado = sincronizar_cursos_y_tareas()
    if resultado["exito"]:
        print("\n[ ÉXITO ] Proceso completado correctamente.")
    else:
        print(f"\n[ ERROR ] {resultado['resumen']}")


if __name__ == "__main__":
    test_uncp_login()
