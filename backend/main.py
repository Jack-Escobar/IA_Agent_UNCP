import sys
from pathlib import Path

# Ajustar el path para que encuentre src (útil si se ejecuta desde la raíz o dentro de backend)
sys.path.append(str(Path(__file__).parent))

from src.services.file_manager import FileManager

def test_file_manager():
    print("=== Iniciando prueba del FileManager ===\n")
    
    # Asumimos que la carpeta base del proyecto es el directorio superior a 'backend'
    base_project_dir = Path(__file__).parent.parent
    
    # Instanciar el gestor (creará la carpeta UNCP en la base del proyecto)
    fm = FileManager(base_dir=str(base_project_dir))
    
    # Lista de cursos simulada (en el futuro vendrá del scraper)
    cursos_prueba = [
        "Ingeniería de Software II",
        "Sistemas Inteligentes",
        "Desarrollo de Aplicaciones Web"
    ]
    
    print(f"1. Creando estructura para los cursos: {cursos_prueba}")
    resultados = fm.setup_course_folders(cursos_prueba)
    print(f"   [OK] Raíz creada en: {resultados['root']}")
    for curso, data in resultados['courses'].items():
        print(f"   [OK] Estructura de '{curso}' lista.")
        
    print("\n2. Simulando verificación de archivos...")
    curso_test = "Sistemas Inteligentes"
    
    # Prueba 2A: Archivo Inexistente
    file_inexistente = "tarea_final.pdf"
    res_in = fm.verify_file_for_upload(curso_test, file_inexistente)
    if not res_in['valid']:
        print(f"   [TEST AC-4.1 EXITOSO] -> {res_in['error_message']}")
        
    # Prueba 2B: Archivo de 0 bytes (Vacío)
    file_vacio = "informe_vacio.docx"
    path_vacio = Path(resultados['courses'][curso_test]['tareas']) / file_vacio
    path_vacio.touch() # Crear archivo de 0 bytes
    
    res_va = fm.verify_file_for_upload(curso_test, file_vacio)
    if not res_va['valid']:
        print(f"   [TEST AC-4.2 EXITOSO] -> {res_va['error_message']}")
        
    # Prueba 2C: Archivo válido
    file_valido = "proyecto_final.zip"
    path_valido = Path(resultados['courses'][curso_test]['tareas']) / file_valido
    path_valido.write_text("Contenido simulado del proyecto.") # Mayor a 0 bytes
    
    res_val = fm.verify_file_for_upload(curso_test, file_valido)
    if res_val['valid']:
        print(f"   [TEST AC-3.3 EXITOSO] -> El archivo '{file_valido}' es válido y listo para subir.")

    print("\n=== Prueba finalizada con éxito ===")

if __name__ == "__main__":
    test_file_manager()
