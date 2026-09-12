import os
import sys
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

# Cargar variables de entorno desde el archivo .env
load_dotenv()

USER = os.getenv("UNCP_USER")
PASS = os.getenv("UNCP_PASS")

def test_uncp_login():
    """
    Script de prueba para automatizar la autenticación en ERP UNCP / ADESA Aula Virtual.
    Verifica si es posible iniciar sesión mediante script con Playwright y notifica
    en la consola el resultado (Éxito o Error).
    """
    # Validar que existan credenciales configuradas
    if not USER or USER == "tu_codigo_o_usuario" or not PASS or PASS == "tu_contrasena":
        print("[ERROR] Por favor, configura tus credenciales reales en el archivo .env")
        print("        Ejemplo en .env:")
        print("        UNCP_USER=tu_codigo_de_estudiante")
        print("        UNCP_PASS=tu_contrasena_real")
        sys.exit(1)

    print("==================================================")
    print(" INICIANDO PRUEBA DE AUTENTICACIÓN UNCP ERP")
    print("==================================================")
    print(f"[INFO] Usuario configurado: {USER}")
    print("[INFO] Iniciando navegador Chromium vía Playwright...")
    
    with sync_playwright() as p:
        # Modo con interfaz gráfica (headless=False) para evitar detección de automatización por reCAPTCHA v3
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized"
            ]
        )
        context = browser.new_context(
            no_viewport=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            target_url = "https://erpaprendizaje.uncp.edu.pe/"
            print(f"[INFO] Navegando a la URL: {target_url}")
            page.goto(target_url, wait_until="networkidle", timeout=35000)

            # Esperar a que los elementos del formulario de login estén presentes
            print("[INFO] Localizando formulario de acceso (ADESA Aula Virtual)...")
            page.wait_for_selector("#UserName", timeout=15000)
            page.wait_for_selector("#Password", timeout=15000)

            print("[INFO] Ingresando credenciales en los campos correspondientes...")
            page.fill("#UserName", USER)
            page.fill("#Password", PASS)

            # Esperar un momento breve para permitir que reCAPTCHA v3 genere el token en segundo plano
            page.wait_for_timeout(1500)

            print("[INFO] Haciendo clic en el botón 'INGRESAR'...")
            page.click("#m_login_signin_submit")

            # Esperar la navegación o respuesta del servidor
            print("[INFO] Esperando respuesta del servidor...")
            page.wait_for_timeout(6000)

            current_url = page.url
            print(f"[INFO] URL actual alcanzada: {current_url}")

            # Buscar elementos de mensaje de error en la página de login
            error_msg_el = page.query_selector(".validation-summary-errors, .field-validation-error, .text-danger ul li:not([style*='display:none'])")
            error_text = error_msg_el.inner_text().strip() if error_msg_el else ""

            # Evaluación del resultado:
            # 1. Si la URL actual cambió y ya no contiene "/login", el login fue exitoso.
            # 2. Si hay mensaje de error explicito en pantalla.
            # 3. Si se mantiene en /login.
            if "/login" not in current_url:
                print("\n" + "=" * 60)
                print(" [ ÉXITO ] ¡INICIO DE SESIÓN EXITOSO!")
                print(" Se logró ingresar a la plataforma institucional mediante el script.")
                print(f" URL de destino: {current_url}")
                print("=" * 60 + "\n")
            elif error_text:
                print("\n" + "=" * 60)
                print(" [ ERROR ] NO SE PUDO INGRESAR.")
                print(f" Detalle del error reportado por la plataforma: '{error_text}'")
                print("=" * 60 + "\n")
            else:
                print("\n" + "=" * 60)
                print(" [ ERROR ] NO SE PUDO INGRESAR.")
                print(" El servidor no concedió el acceso y permaneció en la página de inicio de sesión.")
                print(" Posibles causas: Credenciales incorrectas o requerimiento de validación manual.")
                print("=" * 60 + "\n")

            # Mantiene la ventana abierta 3 segundos para observación visual si se desea
            page.wait_for_timeout(3000)

        except Exception as err:
            print("\n" + "=" * 60)
            print(" [ ERROR ] OCURRIÓ UNA EXCEPCIÓN DURANTE LA EJECUCIÓN DEL SCRIPT:")
            print(f" {str(err)}")
            print("=" * 60 + "\n")

        finally:
            print("[INFO] Cerrando sesión del navegador...")
            browser.close()

if __name__ == "__main__":
    test_uncp_login()
