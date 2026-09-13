import os
import shutil
from pathlib import Path

# Ruta raíz del proyecto (UNCP_agent/)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

class FileManager:
    """
    Gestiona la organización del sistema de archivos local para los cursos y tareas.
    La carpeta UNCP/ siempre se ubica dentro de la raíz del proyecto.
    """
    
    def __init__(self, base_dir: str = None):
        if base_dir is None:
            # Siempre dentro del proyecto: UNCP_agent/UNCP/
            self.base_dir = PROJECT_ROOT / 'UNCP'
        else:
            self.base_dir = Path(base_dir) / 'UNCP'

    def setup_course_folders(self, courses: list) -> dict:
        """
        Crea la estructura raíz y las carpetas para cada curso.
        """
        results = {}
        self.base_dir.mkdir(parents=True, exist_ok=True)
        results['root'] = str(self.base_dir)
        results['courses'] = {}

        for course in courses:
            safe_course_name = self._safe_name(course)
            course_path = self.base_dir / safe_course_name
            
            materiales_path = course_path / 'Materiales'
            tareas_path = course_path / 'Tareas'
            
            materiales_path.mkdir(parents=True, exist_ok=True)
            tareas_path.mkdir(parents=True, exist_ok=True)
            
            results['courses'][safe_course_name] = {
                'created': True,
                'path': str(course_path),
                'materiales': str(materiales_path),
                'tareas': str(tareas_path)
            }
            
        return results

    def listar_archivos_tareas(self, course_name: str) -> dict:
        """
        Lista todos los archivos disponibles en la carpeta Tareas del curso dado.
        Usa búsqueda flexible (fuzzy) para encontrar el curso incluso con nombres parciales.
        """
        curso_path = self._find_course_folder(course_name)
        if curso_path is None:
            return {
                'found': False,
                'error': f"No se encontró carpeta para el curso '{course_name}'. Asegúrese de haber organizado las carpetas primero.",
                'archivos': []
            }
        
        tareas_path = curso_path / 'Tareas'
        if not tareas_path.exists():
            return {
                'found': True,
                'course_path': str(tareas_path),
                'error': "La carpeta 'Tareas' no existe aún.",
                'archivos': []
            }

        archivos = [
            f.name for f in tareas_path.iterdir()
            if f.is_file() and not f.name.startswith('.')
        ]
        return {
            'found': True,
            'course_path': str(tareas_path),
            'error': None,
            'archivos': sorted(archivos)
        }

    def verify_file_for_upload(self, course_name: str, filenames_str: str) -> dict:
        """
        Verifica que uno o varios archivos existan en la carpeta 'Tareas' de un curso específico
        y que no estén en blanco (0 bytes). Retorna las rutas absolutas listas para Playwright.
        """
        # 1. Encontrar la carpeta del curso y su subcarpeta Tareas
        course_folder = self._find_course_folder(course_name)
        if not course_folder:
            return {
                'valid': False,
                'file_paths': [],
                'error_message': f"No se encontró la carpeta local para el curso '{course_name}'. Cursos disponibles: {self._list_available_courses()}"
            }

        tareas_path = course_folder / 'Tareas'
        if not tareas_path.exists():
            return {
                'valid': False,
                'file_paths': [],
                'error_message': f"El curso '{course_folder.name}' no tiene una carpeta 'Tareas'."
            }
        
        # 2. Separar los nombres de archivos por comas y validar cada uno
        filenames = [f.strip() for f in filenames_str.split(",") if f.strip()]
        if not filenames:
            return {
                'valid': False,
                'file_paths': [],
                'error_message': "No se proporcionó ningún nombre de archivo."
            }
            
        valid_paths = []
        errors = []
        
        for filename in filenames:
            file_path = self._find_file_in_folder(tareas_path, filename)
            if file_path is None:
                errors.append(f"No encontrado: '{filename}'")
            elif file_path.stat().st_size == 0:
                errors.append(f"Vacío (0 bytes): '{filename}'")
            else:
                valid_paths.append(str(file_path))
                
        if errors:
            archivos_disp = [f.name for f in tareas_path.iterdir() if f.is_file()] if tareas_path.exists() else []
            return {
                'valid': False,
                'file_paths': [],
                'error_message': f"Errores en los archivos: {'; '.join(errors)}. Archivos disponibles: {archivos_disp}"
            }

        return {
            'valid': True,
            'file_paths': valid_paths,
            'error_message': None
        }

    # ─── Helpers privados ──────────────────────────────────────────────────

    def _safe_name(self, name: str) -> str:
        """Elimina caracteres no permitidos en nombres de carpeta."""
        return "".join(
            c for c in name if c.isalpha() or c.isdigit() or c in (' ', '-', '_')
        ).strip()

    def _find_course_folder(self, course_name: str) -> Path | None:
        """
        Busca la carpeta del curso de forma flexible:
        1. Coincidencia exacta (insensible a mayúsculas)
        2. La carpeta contiene el nombre del curso (o viceversa)
        """
        if not self.base_dir.exists():
            return None
        
        course_lower = course_name.lower().strip()
        best_match = None

        for folder in self.base_dir.iterdir():
            if not folder.is_dir():
                continue
            folder_lower = folder.name.lower()
            
            # Coincidencia exacta
            if folder_lower == course_lower:
                return folder
            
            # La carpeta contiene el término buscado o viceversa
            if course_lower in folder_lower or folder_lower in course_lower:
                best_match = folder

        return best_match

    def _find_file_in_folder(self, folder: Path, filename: str) -> Path | None:
        """
        Busca un archivo en una carpeta de forma flexible:
        1. Nombre exacto
        2. Insensible a mayúsculas/minúsculas
        3. Nombre sin extensión coincide
        """
        if not folder.exists():
            return None
        
        filename_lower = filename.lower().strip()
        filename_stem = Path(filename).stem.lower()
        best_match = None

        for f in folder.iterdir():
            if not f.is_file():
                continue
            
            # Coincidencia exacta
            if f.name == filename:
                return f
            
            # Insensible a mayúsculas
            if f.name.lower() == filename_lower:
                return f
            
            # Coincidencia por nombre sin extensión
            if f.stem.lower() == filename_stem:
                best_match = f

        return best_match

    def _list_available_courses(self) -> str:
        """Lista los cursos disponibles en la carpeta UNCP/."""
        if not self.base_dir.exists():
            return "ninguno (carpeta UNCP no existe)"
        folders = [f.name for f in self.base_dir.iterdir() if f.is_dir()]
        return str(folders) if folders else "ninguno"
