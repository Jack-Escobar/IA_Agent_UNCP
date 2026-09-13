/**
 * ADESAPILOT - Frontend Application Logic v2
 * Handles UI interactions, API communication, and dynamic rendering.
 */

class AdesaPilotApp {
  constructor() {
    this.apiBaseUrl = 'http://127.0.0.1:8000';
    this.sessionId = this.getOrCreateSessionId();
    this.isProcessing = false;
    this.cursosData = [];
    this.activeFilter = 'todas';

    // Elementos DOM
    this.chatForm      = document.getElementById('chat-form');
    this.chatInput     = document.getElementById('chat-input');
    this.chatMessages  = document.getElementById('chat-messages');
    this.chatViewport  = document.getElementById('chat-viewport');
    this.sendBtn       = document.getElementById('send-btn');
    this.statusDot     = document.getElementById('status-dot');
    this.statusText    = document.getElementById('status-text');
    this.agentStateText= document.getElementById('agent-state-text');
    this.tasksList     = document.getElementById('tasks-list');
    this.clearChatBtn  = document.getElementById('clear-chat-btn');
    this.syncPlatformBtn = document.getElementById('sync-platform-btn');
    this.syncSidebarBtn  = document.getElementById('sync-sidebar-btn');

    // Explorador de archivos (Right Sidebar)
    this.openFilesBtn    = document.getElementById('open-files-btn');
    this.closeFilesBtn   = document.getElementById('close-file-explorer-btn');
    this.syncFilesBtn    = document.getElementById('sync-files-btn');
    this.filesSidebar    = document.getElementById('file-explorer-sidebar');
    this.filesTree       = document.getElementById('files-tree');

    // Sidebar Mobile
    this.sidebar        = document.getElementById('sidebar');
    this.sidebarOverlay = document.getElementById('sidebar-overlay');
    this.openSidebarBtn = document.getElementById('open-sidebar-btn');
    this.closeSidebarBtn= document.getElementById('close-sidebar-btn');

    this.init();
  }

  init() {
    this.setupEventListeners();
    this.setupAutoResizeInput();
    this.checkBackendConnection();
    this.fetchCursosAndRender();
    this.fetchFilesAndRender();

    // Reconexión periódica
    setInterval(() => this.checkBackendConnection(), 15000);
  }

  getOrCreateSessionId() {
    let sid = localStorage.getItem('uncp_session_id');
    if (!sid) {
      sid = 'session_' + Math.random().toString(36).substring(2, 9);
      localStorage.setItem('uncp_session_id', sid);
    }
    return sid;
  }

  // ─── EVENT LISTENERS ────────────────────────────────────────────────────────

  setupEventListeners() {
    if (this.clearChatBtn) this.clearChatBtn.addEventListener('click', () => this.clearChat());

    if (this.syncPlatformBtn) {
      this.syncPlatformBtn.addEventListener('click', () =>
        this.sendQuickPrompt('Sincronizar la plataforma virtual con mis cursos y tareas actuales')
      );
    }
    if (this.syncSidebarBtn) {
      this.syncSidebarBtn.addEventListener('click', () =>
        this.sendQuickPrompt('Sincronizar la plataforma virtual')
      );
    }

    // Filtros del sidebar
    document.querySelectorAll('.filter-chip').forEach(chip => {
      chip.addEventListener('click', (e) => {
        document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
        e.target.classList.add('active');
        this.activeFilter = e.target.dataset.filter;
        this.renderCursos();
      });
    });

    // Sidebar Móvil (Izquierda)
    if (this.openSidebarBtn) {
      this.openSidebarBtn.addEventListener('click', () => {
        this.sidebar.classList.add('open');
        this.sidebarOverlay.classList.add('active');
      });
    }
    const closeSidebar = () => {
      this.sidebar.classList.remove('open');
      this.sidebarOverlay.classList.remove('active');
    };
    if (this.closeSidebarBtn) this.closeSidebarBtn.addEventListener('click', closeSidebar);
    if (this.sidebarOverlay) {
      this.sidebarOverlay.addEventListener('click', () => {
        closeSidebar();
        if (this.filesSidebar) this.filesSidebar.classList.remove('open');
      });
    }

    // Sidebar Móvil (Derecha - Archivos)
    if (this.openFilesBtn) {
      this.openFilesBtn.addEventListener('click', () => {
        this.filesSidebar.classList.add('open');
        this.sidebarOverlay.classList.add('active');
      });
    }
    if (this.closeFilesBtn) {
      this.closeFilesBtn.addEventListener('click', () => {
        this.filesSidebar.classList.remove('open');
        this.sidebarOverlay.classList.remove('active');
      });
    }
    
    if (this.syncFilesBtn) {
      this.syncFilesBtn.addEventListener('click', () => this.fetchFilesAndRender());
    }
  }

  setupAutoResizeInput() {
    if (!this.chatInput) return;
    this.chatInput.addEventListener('input', () => {
      this.chatInput.style.height = 'auto';
      this.chatInput.style.height = this.chatInput.scrollHeight + 'px';
    });
    this.chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.handleFormSubmit(e);
      }
    });
  }

  // ─── CONEXIÓN ────────────────────────────────────────────────────────────────

  async checkBackendConnection() {
    try {
      const res = await fetch(`${this.apiBaseUrl}/`);
      if (res.ok) {
        this.statusDot.className = 'status-dot online';
        this.statusText.textContent = 'Backend conectado';
      } else throw new Error();
    } catch {
      this.statusDot.className = 'status-dot offline';
      this.statusText.textContent = 'Desconectado (8000)';
    }
  }

  // ─── CURSOS & TAREAS SIDEBAR ─────────────────────────────────────────────────

  async fetchCursosAndRender() {
    try {
      const res = await fetch(`${this.apiBaseUrl}/tareas/cursos`);
      if (res.ok) {
        const data = await res.json();
        if (data.status === 'ok') {
          this.cursosData = data.cursos;
          this.renderCursos();
          
          // Solo ejecutar la alerta proactiva la primera vez que se carga
          if (!this.proactiveAlertSent) {
            this.checkProactiveAlerts();
            this.proactiveAlertSent = true;
          }
        }
      }
    } catch (e) {
      console.warn('Error cargando cursos:', e);
    }
  }

  renderCursos() {
    if (!this.tasksList) return;

    if (!this.cursosData || this.cursosData.length === 0) {
      this.tasksList.innerHTML = `
        <div class="empty-state">
          <i class="fa-solid fa-circle-info"></i>
          <p>Sin cursos. Usa <strong>Sincronizar Portal</strong> para extraer tus cursos.</p>
        </div>`;
      return;
    }

    let html = '';
    this.cursosData.forEach((curso, idx) => {
      // Filtrar tareas según el filtro activo
      let tareas = curso.tareas || [];
      if (this.activeFilter === 'urgente') {
        tareas = tareas.filter(t => this.getEstadoMeta(t.estado).clase === 'urgente');
      } else if (this.activeFilter === 'pendiente') {
        tareas = tareas.filter(t => this.getEstadoMeta(t.estado).clase === 'pendiente');
      }

      // Contar pendientes: solo tareas que NO están Entregadas ni Vencidas
      const totalPendientes = (curso.tareas || []).filter(
        t => !['Entregada', 'Vencida'].includes(t.estado)
      ).length;

      const courseId = `curso-${idx}`;
      const esVacio = tareas.length === 0;

      html += `
        <div class="course-accordion">
          <button class="course-header" onclick="app.toggleCurso('${courseId}')">
            <div class="course-header-left">
              <i class="fa-solid fa-chevron-right accordion-arrow" id="arrow-${courseId}"></i>
              <span class="course-name">${this.escapeHtml(curso.nombre)}</span>
            </div>
            ${totalPendientes > 0 ? `<span class="course-badge">${totalPendientes}</span>` : ''}
          </button>
          <div class="course-tasks" id="${courseId}" style="display:none;">
            ${esVacio ? `<p class="no-tasks-msg">Sin tareas para este filtro.</p>` :
              tareas.map(t => this.buildTaskCard(t)).join('')
            }
          </div>
        </div>
      `;
    });

    this.tasksList.innerHTML = html;
  }

  toggleCurso(courseId) {
    const panel = document.getElementById(courseId);
    const arrow = document.getElementById(`arrow-${courseId}`);
    if (!panel) return;
    const isOpen = panel.style.display !== 'none';
    panel.style.display = isOpen ? 'none' : 'block';
    arrow.classList.toggle('open', !isOpen);
  }

  buildTaskCard(tarea) {
    const meta = this.getEstadoMeta(tarea.estado);
    // No se puede enviar a tareas vencidas o ya entregadas
    const esEnviable = !tarea.estado.toLowerCase().includes('entregada') &&
                       !tarea.estado.toLowerCase().includes('vencida');
    
    return `
      <div class="task-card task-card--sm" 
           ${esEnviable ? `
           draggable="false"
           ondragover="app.handleDragOver(event)" 
           ondragleave="app.handleDragLeave(event)" 
           ondrop="app.handleDrop(event, '${this.escapeHtml(tarea.nombre_tarea)}')"
           ` : 'title="Entrega bloqueada: esta tarea está vencida o ya fue entregada."'}>
        <div class="task-card-header">
          <span class="status-badge ${meta.clase}">${meta.icono} ${this.escapeHtml(tarea.estado)}</span>
          <button class="btn-change-estado" 
                  title="Cambiar estado"
                  onclick="app.openEstadoModal(${tarea.id}, '${this.escapeHtml(tarea.nombre_tarea)}', '${this.escapeHtml(tarea.estado)}')">
            <i class="fa-solid fa-pen-to-square"></i>
          </button>
        </div>
        <h4 class="task-name" 
            onclick="app.sendQuickPrompt('Preparar envío de la tarea: ${this.escapeHtml(tarea.nombre_tarea)}')"
            title="Preparar envío">
          ${this.escapeHtml(tarea.nombre_tarea)}
        </h4>
        <div class="task-card-footer">
          <i class="fa-regular fa-clock"></i>
          <span>${this.escapeHtml(tarea.fecha_limite || 'Sin fecha')}</span>
        </div>
      </div>
    `;
  }

  getEstadoMeta(estado) {
    const e = (estado || '').toLowerCase();
    if (e.includes('vencida') || e.includes('vencido')) return { clase: 'vencida', icono: '⏰' };
    if (e.includes('entregada') || e.includes('completada')) return { clase: 'entregada', icono: '✅' };
    if (e.includes('urgente') || e.includes('vence pronto')) return { clase: 'urgente', icono: '🚨' };
    if (e.includes('progreso')) return { clase: 'progreso', icono: '🔄' };
    return { clase: 'pendiente', icono: '📋' };
  }

  checkProactiveAlerts() {
    if (!this.cursosData) return;
    
    let tareasUrgentes = [];
    const hoy = new Date();
    
    // Buscar en todos los cursos
    this.cursosData.forEach(curso => {
      if (!curso.tareas) return;
      curso.tareas.forEach(tarea => {
        // Ignorar tareas ya entregadas o vencidas
        if (tarea.estado === 'Entregada' || tarea.estado === 'Vencida') return;
        
        if (tarea.fecha_limite) {
          // Extraer la fecha con formato DD/MM/YYYY o similar usando regex
          const match = tarea.fecha_limite.match(/(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})/);
          if (match) {
            let [, d, m, y] = match;
            if (y.length === 2) y = '20' + y;
            const fechaLimite = new Date(y, m - 1, d);
            
            // Calcular diferencia en días
            const diffTime = fechaLimite - hoy;
            const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
            
            // Si vence en 3 días o menos
            if (diffDays >= 0 && diffDays <= 3) {
              tareasUrgentes.push({
                curso: curso.nombre,
                tarea: tarea.nombre_tarea,
                dias: diffDays
              });
            }
          }
        }
      });
    });

    if (tareasUrgentes.length > 0) {
      let listaHtml = tareasUrgentes.map(t => 
        `<li><strong>${this.escapeHtml(t.tarea)}</strong> <br><small>${this.escapeHtml(t.curso)} (Vence en ${t.dias} días)</small></li>`
      ).join('');
      
      const alertMsg = `
        <h3><i class="fa-solid fa-bell" style="color: var(--status-urgente)"></i> Alerta Proactiva</h3>
        <p>He detectado <strong>${tareasUrgentes.length} tarea(s)</strong> que vencen pronto. Te recomiendo priorizarlas:</p>
        <ul style="margin-left: 20px; margin-top: 10px;">
          ${listaHtml}
        </ul>
      `;
      this.addMessageToUI('AdesaPilot', alertMsg, 'agent', true);
    }
  }

  // ─── EXPLORADOR DE ARCHIVOS & DRAG AND DROP ─────────────────────────────────

  async fetchFilesAndRender() {
    if (!this.filesTree) return;
    this.filesTree.innerHTML = `<div class="empty-state"><i class="fa-solid fa-circle-notch fa-spin"></i><p>Cargando archivos...</p></div>`;
    
    try {
      const res = await fetch(`${this.apiBaseUrl}/archivos/estructura`);
      if (res.ok) {
        const data = await res.json();
        if (data.status === 'ok') {
          this.renderFiles(data.cursos);
        } else {
          this.filesTree.innerHTML = `<div class="empty-state"><i class="fa-solid fa-triangle-exclamation"></i><p>Error leyendo archivos locales.</p></div>`;
        }
      }
    } catch (e) {
      this.filesTree.innerHTML = `<div class="empty-state"><i class="fa-solid fa-triangle-exclamation"></i><p>Desconectado del servidor.</p></div>`;
    }
  }

  renderFiles(cursos) {
    if (!cursos || cursos.length === 0) {
      this.filesTree.innerHTML = `<div class="empty-state"><i class="fa-regular fa-folder-open"></i><p>No se encontró la carpeta UNCP/ o está vacía.</p></div>`;
      return;
    }

    let html = '';
    let hasFiles = false;

    cursos.forEach(curso => {
      // Solo nos importan los archivos de Tareas/
      const tareas = curso.archivos_tareas || [];
      if (tareas.length === 0) return;
      
      hasFiles = true;
      html += `
        <div class="file-course-group">
          <div class="file-course-header">${this.escapeHtml(curso.nombre)}</div>
          ${tareas.map(f => `
            <div class="file-item" draggable="true" 
                 onclick="app.toggleFileSelection(this, '${this.escapeHtml(f.ruta)}')"
                 ondragstart="app.handleDragStart(event, '${this.escapeHtml(f.ruta)}')">
              <div class="file-icon"><i class="${this.getFileIcon(f.extension)}"></i></div>
              <div class="file-details">
                <span class="file-name" title="${this.escapeHtml(f.nombre)}">${this.escapeHtml(f.nombre)}</span>
                <span class="file-size">${this.formatBytes(f.tamano)}</span>
              </div>
            </div>
          `).join('')}
        </div>
      `;
    });

    if (!hasFiles) {
      this.filesTree.innerHTML = `<div class="empty-state"><i class="fa-regular fa-file"></i><p>No hay archivos en las carpetas de Tareas.</p></div>`;
    } else {
      this.filesTree.innerHTML = html;
    }
  }

  toggleFileSelection(element, filePath) {
    element.classList.toggle('selected');
    if (element.classList.contains('selected')) {
      element.dataset.filepath = filePath;
    } else {
      delete element.dataset.filepath;
    }
  }

  getFileIcon(ext) {
    const icons = {
      '.pdf': 'fa-solid fa-file-pdf',
      '.doc': 'fa-solid fa-file-word',
      '.docx': 'fa-solid fa-file-word',
      '.xls': 'fa-solid fa-file-excel',
      '.xlsx': 'fa-solid fa-file-excel',
      '.ppt': 'fa-solid fa-file-powerpoint',
      '.pptx': 'fa-solid fa-file-powerpoint',
      '.zip': 'fa-solid fa-file-zipper',
      '.rar': 'fa-solid fa-file-zipper',
      '.jpg': 'fa-solid fa-file-image',
      '.png': 'fa-solid fa-file-image',
    };
    return icons[ext] || 'fa-solid fa-file';
  }

  formatBytes(bytes, decimals = 1) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024, dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
  }

  handleDragStart(e, filePath) {
    const draggedItem = e.currentTarget;
    let filesToDrag = [];
    
    // Si el elemento arrastrado está seleccionado, arrastramos todos los seleccionados
    if (draggedItem.classList.contains('selected')) {
      document.querySelectorAll('.file-item.selected').forEach(el => {
        if (el.dataset.filepath) filesToDrag.push(el.dataset.filepath);
      });
    } else {
      // Si no, solo arrastramos este
      filesToDrag.push(filePath);
    }
    
    // Guardamos la lista de rutas separadas por pipe (|)
    e.dataTransfer.setData('text/plain', filesToDrag.join('|'));
    e.dataTransfer.effectAllowed = 'copy';
  }

  handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
    const card = e.currentTarget;
    card.classList.add('drag-over');
  }

  handleDragLeave(e) {
    e.preventDefault();
    const card = e.currentTarget;
    card.classList.remove('drag-over');
  }

  handleDrop(e, taskName) {
    e.preventDefault();
    const card = e.currentTarget;
    card.classList.remove('drag-over');

    // Segunda capa de seguridad: verificar el estado de la tarea en los datos locales
    if (this.cursosData) {
      for (const curso of this.cursosData) {
        const tarea = (curso.tareas || []).find(t => t.nombre_tarea === taskName);
        if (tarea) {
          const estado = (tarea.estado || '').toLowerCase();
          if (estado.includes('vencida') || estado.includes('entregada')) {
            this.showToast(`⛔ Entrega bloqueada: la tarea "${taskName}" está ${tarea.estado}.`, 'error');
            return;
          }
          break;
        }
      }
    }
    
    const dragData = e.dataTransfer.getData('text/plain');
    if (dragData) {
      const filePaths = dragData.split('|');
      const numFiles = filePaths.length;
      
      let prompt = `Prepara el envío de la tarea "${taskName}" adjuntando `;
      if (numFiles === 1) {
        const fileName = filePaths[0].split('/').pop().split('\\').pop();
        prompt += `el archivo "${fileName}" ubicado en "${filePaths[0]}"`;
        this.showToast(`Preparando envío de ${fileName}`, 'success');
      } else {
        const listText = filePaths.map(p => {
          const fn = p.split('/').pop().split('\\').pop();
          return `"${fn}" (ruta: "${p}")`;
        }).join(', ');
        prompt += `los siguientes archivos: ${listText}`;
        this.showToast(`Preparando envío de ${numFiles} archivos`, 'success');
      }
      
      this.sendQuickPrompt(prompt);
      
      // Limpiar selección de archivos después del drop
      document.querySelectorAll('.file-item.selected').forEach(el => {
        el.classList.remove('selected');
        delete el.dataset.filepath;
      });
      
      // Cerrar sidebar en móvil si está abierto
      if (this.filesSidebar) this.filesSidebar.classList.remove('open');
      if (this.sidebarOverlay) this.sidebarOverlay.classList.remove('active');
    }
  }

  // ─── MODAL CAMBIO DE ESTADO ──────────────────────────────────────────────────

  openEstadoModal(tareaId, nombreTarea, estadoActual) {
    // Eliminar modal previo si existe
    const prev = document.getElementById('estado-modal');
    if (prev) prev.remove();

    const modal = document.createElement('div');
    modal.id = 'estado-modal';
    modal.className = 'modal-overlay';
    modal.innerHTML = `
      <div class="modal-box">
        <div class="modal-header">
          <h3><i class="fa-solid fa-pen-to-square"></i> Cambiar Estado de Tarea</h3>
          <button class="btn-icon" onclick="document.getElementById('estado-modal').remove()">
            <i class="fa-solid fa-xmark"></i>
          </button>
        </div>
        <div class="modal-body">
          <p class="modal-task-name">${this.escapeHtml(nombreTarea)}</p>
          <p class="modal-label">Selecciona el nuevo estado:</p>
          <div class="estado-options">
            ${['Pendiente', 'En progreso', 'Entregada', 'Vencida'].map(est => `
              <button class="estado-option ${est === estadoActual ? 'selected' : ''}" 
                      data-estado="${est}"
                      onclick="app.selectEstadoOption(this, '${est}')">
                ${this.getEstadoMeta(est).icono} ${est}
              </button>
            `).join('')}
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" onclick="document.getElementById('estado-modal').remove()">Cancelar</button>
          <button class="btn-primary" id="confirm-estado-btn" onclick="app.confirmCambioEstado(${tareaId})">
            <i class="fa-solid fa-check"></i> Confirmar
          </button>
        </div>
      </div>
    `;

    // Cerrar al hacer clic fuera del box
    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.remove();
    });

    document.body.appendChild(modal);
    // Animación de entrada
    requestAnimationFrame(() => modal.classList.add('visible'));

    // Guardar estado seleccionado actual
    modal._estadoSeleccionado = estadoActual;
  }

  selectEstadoOption(btn, estado) {
    document.querySelectorAll('.estado-option').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
    const modal = document.getElementById('estado-modal');
    if (modal) modal._estadoSeleccionado = estado;
  }

  async confirmCambioEstado(tareaId) {
    const modal = document.getElementById('estado-modal');
    const nuevoEstado = modal ? modal._estadoSeleccionado : null;
    if (!nuevoEstado) return;

    const confirmBtn = document.getElementById('confirm-estado-btn');
    confirmBtn.disabled = true;
    confirmBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Guardando...';

    try {
      const res = await fetch(`${this.apiBaseUrl}/tareas/${tareaId}/estado`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ estado: nuevoEstado })
      });
      const data = await res.json();
      if (data.status === 'ok') {
        modal.remove();
        await this.fetchCursosAndRender(); // refrescar sidebar
        this.showToast(`Estado actualizado a "${nuevoEstado}"`, 'success');
      } else {
        this.showToast('Error al actualizar estado', 'error');
        confirmBtn.disabled = false;
        confirmBtn.innerHTML = '<i class="fa-solid fa-check"></i> Confirmar';
      }
    } catch (e) {
      this.showToast('Error de conexión', 'error');
      confirmBtn.disabled = false;
      confirmBtn.innerHTML = '<i class="fa-solid fa-check"></i> Confirmar';
    }
  }

  // ─── TOAST NOTIFICATIONS ─────────────────────────────────────────────────────

  showToast(mensaje, tipo = 'success') {
    const prev = document.getElementById('toast-notification');
    if (prev) prev.remove();

    const toast = document.createElement('div');
    toast.id = 'toast-notification';
    toast.className = `toast toast--${tipo}`;
    toast.innerHTML = `
      <i class="fa-solid ${tipo === 'success' ? 'fa-check-circle' : 'fa-triangle-exclamation'}"></i>
      <span>${this.escapeHtml(mensaje)}</span>
    `;
    document.body.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('visible'));
    setTimeout(() => { toast.classList.remove('visible'); setTimeout(() => toast.remove(), 300); }, 3000);
  }

  // ─── CHAT ────────────────────────────────────────────────────────────────────

  sendQuickPrompt(text) {
    this.chatInput.value = text;
    this.chatInput.dispatchEvent(new Event('input'));
    this.handleFormSubmit(new Event('submit'));
  }

  async handleFormSubmit(e) {
    if (e) e.preventDefault();
    const promptText = this.chatInput.value.trim();
    if (!promptText || this.isProcessing) return;

    const welcomeCard = document.querySelector('.welcome-card');
    if (welcomeCard) welcomeCard.remove();

    this.appendUserMessage(promptText);
    this.chatInput.value = '';
    this.chatInput.style.height = 'auto';
    this.setProcessingState(true, 'Pensando...');

    const agentMsg = this.createAgentMessagePlaceholder();

    try {
      const res = await fetch(`${this.apiBaseUrl}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: promptText, sesion_id: this.sessionId })
      });
      if (!res.ok) throw new Error(`Error ${res.status}`);
      const data = await res.json();
      this.updateAgentMessageContent(agentMsg, data);

      // Si usó herramientas, refrescar sidebar automáticamente
      if (data.herramientas_usadas && data.herramientas_usadas.length > 0) {
        this.agentStateText.textContent = 'Actualizando tareas...';
        await this.fetchCursosAndRender();
      }
    } catch (err) {
      this.updateAgentMessageError(agentMsg,
        'Error al comunicarse con el backend. Asegúrate de que FastAPI esté ejecutándose en el puerto 8000.'
      );
    } finally {
      this.setProcessingState(false, 'Listo para ayudarte');
    }
  }

  setProcessingState(isProcessing, statusText) {
    this.isProcessing = isProcessing;
    if (this.sendBtn) this.sendBtn.disabled = isProcessing;
    if (this.agentStateText) this.agentStateText.textContent = statusText;
  }

  appendUserMessage(text) {
    const div = document.createElement('div');
    div.className = 'message-group user-group';
    div.innerHTML = `
      <div class="avatar"><i class="fa-solid fa-user"></i></div>
      <div class="message-content">
        <div class="message-header">
          <span class="sender-name">Tú</span>
          <span class="message-time">${this.getCurrentTime()}</span>
        </div>
        <div class="message-body">${this.escapeHtml(text)}</div>
      </div>`;
    this.chatMessages.appendChild(div);
    this.scrollToBottom();
  }

  createAgentMessagePlaceholder() {
    const div = document.createElement('div');
    div.className = 'message-group agent-group';
    div.innerHTML = `
      <div class="avatar"><i class="fa-solid fa-robot"></i></div>
      <div class="message-content">
        <div class="message-header">
          <span class="sender-name">AdesaPilot</span>
          <span class="message-time">${this.getCurrentTime()}</span>
        </div>
        <div class="message-body loading-body">
          <div class="tool-badge">
            <i class="fa-solid fa-gear fa-spin"></i>
            <span>Procesando consulta...</span>
          </div>
        </div>
      </div>`;
    this.chatMessages.appendChild(div);
    this.scrollToBottom();
    return div;
  }

  updateAgentMessageContent(msgGroup, data) {
    const body = msgGroup.querySelector('.message-body');
    body.classList.remove('loading-body');
    let html = '';
    if (data.herramientas_usadas && data.herramientas_usadas.length > 0) {
      data.herramientas_usadas.forEach(tool => {
        html += `<div class="tool-badge"><i class="fa-solid fa-bolt"></i><span>Herramienta: <strong>${this.escapeHtml(tool)}</strong></span></div>`;
      });
    }
    html += `<div class="formatted-text">${this.formatMarkdown(data.respuesta || '')}</div>`;
    body.innerHTML = html;
    this.scrollToBottom();
  }

  updateAgentMessageError(msgGroup, errorMsg) {
    const body = msgGroup.querySelector('.message-body');
    body.classList.remove('loading-body');
    body.innerHTML = `<div class="formatted-text" style="color:var(--status-danger)"><i class="fa-solid fa-triangle-exclamation"></i> ${this.escapeHtml(errorMsg)}</div>`;
    this.scrollToBottom();
  }

  formatMarkdown(text) {
    if (!text) return '';
    let html = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    html = html.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    html = html.replace(/^### (.+)$/gm, '<h4>$1</h4>');
    html = html.replace(/^## (.+)$/gm, '<h3>$1</h3>');
    html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>[\s\S]+?<\/li>)/g, '<ul>$1</ul>');
    html = html.replace(/\n/g, '<br>');
    return html;
  }

  async clearChat() {
    if (!confirm('¿Deseas limpiar el historial de la conversación actual?')) return;
    try {
      await fetch(`${this.apiBaseUrl}/historial/${this.sessionId}`, { method: 'DELETE' });
    } catch (e) {
      console.warn('Error al borrar historial:', e);
    }
    this.chatMessages.innerHTML = `
      <div class="message-group agent-group welcome-card">
        <div class="avatar"><i class="fa-solid fa-robot"></i></div>
        <div class="message-content">
          <div class="message-body">
            <p>Conversación reiniciada. ¿En qué puedo ayudarte ahora?</p>
          </div>
        </div>
      </div>`;
  }

  scrollToBottom() {
    setTimeout(() => {
      if (this.chatViewport) this.chatViewport.scrollTop = this.chatViewport.scrollHeight;
    }, 50);
  }

  getCurrentTime() {
    return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }
}

// Inicializar al cargar DOM
let app;
document.addEventListener('DOMContentLoaded', () => { app = new AdesaPilotApp(); });
