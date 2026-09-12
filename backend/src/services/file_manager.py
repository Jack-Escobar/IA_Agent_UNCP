import os
import shutil
from pathlib import Path

class FileManager:
    """
    Gestiona la organización del sistema de archivos local para los cursos y tareas.
    Implementa los criterios de aceptación AC-2.x y AC-4.x.
    """
    
    def __init__(self, base_dir: str = None):
        """
        Inicializa el FileManager.
        :param base_dir: Ruta base donde se creará la carpeta UNCP. Si no se provee, 
                         se crea en el directorio actual del proyecto.
        """
        if base_dir is None:
            # Por defecto, en la carpeta raíz del proyecto (2 niveles arriba de 'services' -> src -> backend -> UNCP_agent)
            # Para mayor flexibilidad, permitimos que el entorno o main.py defina la ruta exacta, 
            # pero asumimos una carpeta 'UNCP' al mismo nivel de 'backend' o en el current working directory.
            # Aquí usamos el Current Working Directory (CWD) + 'UNCP'
            self.base_dir = Path.cwd() / 'UNCP'
        else:
            self.base_dir = Path(base_dir) / 'UNCP'

    def setup_course_folders(self, courses: list) -> dict:
        """
        Crea la estructura raíz y las carpetas para cada curso.
        [AC-2.1, AC-2.2, AC-2.3]
        
        :param courses: Lista de nombres de cursos.
        :return: Diccionario con el estado de creación de las carpetas.
        """
        results = {}
        
        # [AC-2.1] Crear carpeta raíz UNCP si no existe
        self.base_dir.mkdir(parents=True, exist_ok=True)
        results['root'] = str(self.base_dir)
        results['courses'] = {}

        for course in courses:
            # Limpiamos el nombre del curso para que sea válido en el sistema de archivos
            safe_course_name = "".join([c for c in course if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).rstrip()
            course_path = self.base_dir / safe_course_name
            
            materiales_path = course_path / 'Materiales'
            tareas_path = course_path / 'Tareas'
            
            # [AC-2.2] Crear subcarpetas
            materiales_path.mkdir(parents=True, exist_ok=True)
            tareas_path.mkdir(parents=True, exist_ok=True)
            
            results['courses'][safe_course_name] = {
                'created': True,
                'path': str(course_path),
                'materiales': str(materiales_path),
                'tareas': str(tareas_path)
            }
            
        return results

    def verify_file_for_upload(self, course_name: str, filename: str) -> dict:
        """
        Verifica que el archivo exista en la carpeta 'Tareas' del curso y no esté vacío.
        [AC-4.1, AC-4.2, AC-3.3]
        
        :param course_name: Nombre del curso.
        :param filename: Nombre del archivo a enviar.
        :return: Diccionario con el resultado de la validación.
        """
        safe_course_name = "".join([c for c in course_name if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).rstrip()
        file_path = self.base_dir / safe_course_name / 'Tareas' / filename
        
        response = {
            'valid': False,
            'file_path': str(file_path),
            'error_message': None
        }

        # [AC-4.1] Archivo Inexistente
        if not file_path.exists() or not file_path.is_file():
            response['error_message'] = f"El archivo '{filename}' no fue encontrado en la carpeta del curso '{safe_course_name}/Tareas'."
            return response
            
        # [AC-4.2] Archivo en Blanco / Vacío
        if file_path.stat().st_size == 0:
            response['error_message'] = f"El archivo '{filename}' está en blanco (0 bytes). No se permite el envío de archivos vacíos."
            return response
            
        # Archivo válido
        response['valid'] = True
        return response
