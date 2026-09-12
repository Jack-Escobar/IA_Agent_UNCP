# Especificaciones.md - Requerimientos del Producto y Criterios de Aceptación

Este documento define los requerimientos funcionales, el problema a resolver, la persona objetivo y los criterios de aceptación para el desarrollo e implementación del **UNCP_agent**. La especificación se enfoca estrictamente en **qué** debe cumplir el sistema y sus resultados esperados, sin prescribir detalles de implementación técnica.

---

## 1. El Problema (The Problem)

### 1.1. Contexto y Puntos de Dolor
Los estudiantes universitarios gestionan simultáneamente múltiples asignaturas, cada una con diversas tareas, entregables y materiales de estudio distribuidos en plataformas virtuales. Esta dinámica genera los siguientes problemas críticos:
* **Riesgo de Omisión de Entregas:** Vencimiento imprevisto de plazos límite debido a la falta de visibilidad consolidada de las fechas de cierre de cada tarea.
* **Pérdida de Tiempo Operativo:** Ineficiencia por la navegación repetitiva manual entre múltiples secciones de la plataforma virtual para consultar pendientes y subir archivos.
* **Desorden en Almacenamiento Local:** Falta de una estructura homogénea para organizar materiales académicos (sílabos, lecturas, diapositivas) y archivos de entrega por asignatura.

### 1.2. Impacto Esperado
El objetivo fundamental del sistema es:
1. **Prevenir e Imposibilitar Olvidos:** Garantizar que el estudiante sea alertado sobre plazos próximos para evitar la no entrega de tareas.
2. **Optimizar el Tiempo del Estudiante:** Reducir a cero los pasos manuales innecesarios de consulta y subida de archivos.
3. **Asegurar la Estructuración de Información:** Mantener un orden estandarizado e impecable en el almacenamiento de archivos académicos locales.

---

## 2. Perfil de Usuario (Target Persona)

* **Rol:** Estudiante Universitario de la Universidad Nacional del Centro del Perú (UNCP).
* **Características:**
  * Cursa múltiples asignaturas en paralelo con alta densidad de actividades evaluativas.
  * Requiere un asistente proactivo que reduzca la carga cognitiva de gestión administrativa.
  * Busca mantener el control final sobre las entregas académicas mediante un flujo de confirmación explícito.

---

## 3. Criterios de Aceptación (Acceptance Criteria)

Para considerar el sistema completado y aceptado, se deben satisfacer cuantitativa y cualitativamente los siguientes criterios por cada área de funcionalidad:

### 3.1. Visibilidad y Monitoreo de Tareas
* **[AC-1.1] Extracción Consolidada:** El sistema debe presentar una vista clara y consolidada de todas las tareas asignadas en los cursos activos.
* **[AC-1.2] Atributos Obligatorios por Tarea:** Para cada tarea detectada, el sistema debe mostrar obligatoriamente:
  1. Nombre exacto de la tarea.
  2. Enunciado o instrucciones completas de la tarea (extraídas directamente de la página de la tarea).
  3. Curso al que pertenece.
  4. Fecha y hora exacta de vencimiento.
  5. Estado actual de entrega (ej. *Pendiente*, *Enviado para calificar*, *No entregado*).
* **[AC-1.3] Notificación Proactiva de Vencimiento:** El sistema debe alertar al estudiante con prioridad sobre aquellas tareas pendientes cuyos plazos de entrega estén próximos a vencer.

### 3.2. Organización del Sistema de Archivos Local
* **[AC-2.1] Creación de Estructura de Directorios:** El sistema debe verificar y/o crear la carpeta raíz `UNCP` en la ubicación definida por el usuario.
* **[AC-2.2] Jerarquía Estandarizada por Asignatura:** Dentro de la carpeta `UNCP`, se debe generar automáticamente una carpeta por cada curso registrado. Cada carpeta de curso debe contener exactamente dos subcarpetas:
  * `Materiales/` (destinada a sílabos, diapositivas y lecturas).
  * `Tareas/` (destinada a los entregables preparados para el curso).
* **[AC-2.3] Estado Inicial:** Tras la inicialización del directorio, las subcarpetas `Materiales` y `Tareas` deben quedar creadas correctamente para recibir archivos.

### 3.3. Proceso de Confirmación de Envíos
* **[AC-3.1] Verificación Previa al Envío:** El sistema debe informar detallada y explícitamente al estudiante qué archivo local se va a subir y a qué curso y tarea corresponde.
* **[AC-3.2] Confirmación Explicita:** El sistema no ejecutará ningún envío definitivo en la plataforma virtual hasta recibir la aprobación directa y afirmativa del estudiante.
* **[AC-3.3] Origen de Archivos:** Todo archivo que se pretenda enviar debe tomarse exclusivamente de la carpeta `Tareas` correspondiente al curso en cuestión dentro de la estructura local `UNCP`.

### 3.4. Manejo de Excepciones y Casos Borde
* **[AC-4.1] Archivo Inexistente:** Si el usuario solicita enviar un archivo que no existe en la ruta local correspondiente, el sistema debe informar claramente que el documento no fue encontrado y solicitar la especificación o ubicación de un archivo válido.
* **[AC-4.2] Archivo en Blanco / Vacío:** Si el archivo seleccionado tiene un tamaño de 0 bytes o carece de contenido, el sistema debe notificar su condición de "archivo en blanco" y solicitar la corrección respectiva antes de permitir cualquier intento de subida.
* **[AC-4.3] Tarea Vencida:** Si la fecha límite de la tarea ya ha sido sobrepasada en la plataforma, el sistema debe emitir un mensaje informativo advirtiendo que la fecha límite fue superada antes de realizar cualquier acción.

---

## 4. Matriz de Verificación y Criterios de Éxito

| Id Criterio | Módulo | Resultado Esperado | Condición de Aceptación |
| :--- | :--- | :--- | :--- |
| **AC-1.1** | Monitoreo | Presentación de lista de tareas | Muestra tareas de todos los cursos inscritos |
| **AC-1.2** | Monitoreo | Detalle de campos obligatorios | Incluye nombre, enunciado, curso, fecha límite y estado |
| **AC-2.1** | Archivos | Estructura `UNCP/` creada | Subdirectorios `Materiales` y `Tareas` por cada curso |
| **AC-3.1** | Envíos | Notificación pre-envío | Muestra archivo, curso y tarea antes de confirmar |
| **AC-4.1** | Excepciones | Archivo no encontrado | Emite alerta y pide archivo nuevo sin fallar |
| **AC-4.2** | Excepciones | Archivo de 0 bytes | Detecta archivo vacío y bloquea el envío |
| **AC-4.3** | Excepciones | Fecha límite expirada | Notifica vencimiento explícitamente al usuario |