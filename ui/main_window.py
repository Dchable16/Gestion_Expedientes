# ui/main_window.py

import subprocess
import platform
import textwrap
import logging
import os

from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton,
                             QTableWidget, QTableWidgetItem, QComboBox, QLineEdit, QLabel, QDateEdit, QMessageBox,
                             QFileDialog, QDialog, QHeaderView, QFormLayout, QGroupBox,QInputDialog,
                             QStatusBar, QStyle, QMenu, QAction, QFrame, QAbstractItemView, QApplication,
                             QTreeWidget, QTreeWidgetItem)

from PyQt5.QtCore import Qt, QDate, QObject, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QColor, QCursor 
from PyQt5.QtPrintSupport import QPrinter
from PyQt5.QtGui import QTextDocument

from constants import (ExpedientesTab, BusquedaAvanzadaTab, VencidosTab,
                       REGISTROS_POR_PAGINA, CATEGORIAS_DOCUMENTALES, 
                       ConcentracionTab, SeriesTab,  ReportesTab,
                       ESTADOS_EXPEDIENTE, SERIES_DOCUMENTALES,
                       ControlGestionTab, LotesTab, HistorialLotesTab, 
                       DestinoFinalTab, PrestamosTab, ANIO_INICIO_SISTEMA,
                       ANIOS_ATRAS_FILTRO,ORIGENES_CG, ESTATUS_CG, OPCIONES_VALORACION)

from .dialog_helpers import mostrar_mensaje
from datetime import datetime

from .custom_widgets import NumericTableWidgetItem, DateTableWidgetItem
from ui.seleccionar_fechas_dialog import SeleccionarFechasDialog
from ui.document_selection_dialog import DocumentSelectionDialog
from utils.config_manager import get_template_path, get_template_cg_path
from ui.visualizador_expediente import VisualizadorExpediente
from ui.nuevo_expediente_dialog import NuevoExpedienteDialog
from ui.control_gestion_dialog import ControlGestionDialog
from negocio.expediente_service import ExpedienteService
from ui.respuestas_dialog import RespuestasDialog
from ui.importador_dialog import ImportadorDialog
from ui.pdf_viewer_dialog import PdfViewerDialog
from negocio.backup_service import BackupService
from negocio.import_service import ImportService
from ui.ubicacion_dialog import UbicacionDialog
from ui.historial_dialog import HistorialDialog
from ui.dashboard_widget import DashboardWidget
from negocio.excel_service import ExcelService
from negocio.email_service import EmailService
from ui.contacto_dialog import ContactoDialog
from ui.prestamo_dialog import PrestamoDialog
from ui.usuarios_dialog import UsuariosDialog
from utils.concurrencia import GestorTareas
from ui.paginator import Paginator


class MainWindow(QMainWindow):
    def __init__(self, expediente_service: ExpedienteService, backup_service: BackupService, excel_service: ExcelService, email_service: EmailService, import_service: ImportService, usuario_actual: str = "invitado"):
        super().__init__()
        self.usuario_actual = usuario_actual
        self.expediente_service = expediente_service
        self.backup_service = backup_service
        self.excel_service = excel_service
        self.email_service = email_service
        self.import_service = import_service
        self.setWindowTitle("Sistema de Gestión de Expedientes")
        self.setWindowTitle(f"Sistema de Gestión de Expedientes - Usuario: {self.usuario_actual}")
        self.resize(1280, 720)
        self.setMinimumSize(1024, 600)
        self.paginator_expedientes = Paginator(registros_por_pagina_default=50)
        self.paginator_busqueda = Paginator(registros_por_pagina_default=50)
        self.paginator_cg = Paginator(registros_por_pagina_default=50)
        self.busqueda_actual = ""
        self.filtros_actuales_busq = {}
        self.busqueda_avanzada_activa = False
        self.initUI()
        self.crear_menu_principal()
        self.connect_signals()
        self.expediente_service.signals.datos_actualizados.connect(self.actualizar_interfaz)
        self.cargar_control_gestion()
        self.cargar_expedientes()
        self.cargar_expedientes_vencidos()
        self.buscar_expedientes_en_concentracion()
        self.buscar_series()
        self.action_map = {
            'editar':       {'texto': "📝 Editar", 'handler': self.abrir_dialogo_edicion},
            'eliminar':     {'texto': "🗑️ Eliminar", 'handler': self.eliminar_expediente},
            'respuestas':   {'texto': "💬 Respuestas", 'handler': self.mostrar_respuestas},
            'enviar_correo':{'texto': "📧 Enviar Correo", 'handler': self.enviar_correo},
            'ver_pdf':      {'texto': "📄 Ver PDF", 'handler': self.ver_pdf},
            'ver_completo': {'texto': "👁️ Ver Expediente", 'handler': self.ver_completo},
            'restaurar':    {'texto': "🔄 Restaurar a Trámite", 'handler': self.restaurar_de_concentracion},
            'mover_concentracion': {'texto': "🗄️ Mover a Concentración", 'handler': self.mover_un_expediente},
            'historial':    {'texto': "🕒 Ver Historial", 'handler': self.ver_historial_expediente},
            'editar_cg':    {'texto': "📝 Editar", 'handler': self.editar_control_gestion},
            'eliminar_cg':  {'texto': "🗑️ Eliminar", 'handler': self.eliminar_control_gestion},
            'historial_cg': {'texto': "🕒 Ver Historial", 'handler': self.ver_historial_cg},
            'imprimir_cg':  {'texto': "🖨️ Imprimir Formato", 'handler': self.imprimir_formato_cg},
            'imprimir_etiquetas': {'texto': "🏷️ Generar Etiquetas", 'handler': self.imprimir_caratula_desde_menu},
            'revertir_destino': {'texto': "↩️ Revertir a Bodega", 'handler': self.revertir_destino_menu},
            'prestar': {'texto': "🤝 Prestar Físicamente", 'handler': self.abrir_dialogo_prestamo},
            'devolver': {'texto': "📥 Registrar Devolución", 'handler': self.registrar_devolucion},
            'reimprimir_vale': {'texto': "🖨️ Reimprimir Vale", 'handler': self.reimprimir_vale},
        }

    def initUI(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        self.tabs = QTabWidget()
        self.tabs.setUsesScrollButtons(True)
        repo_para_dashboard = self.import_service.expediente_repository
        self.dashboard = DashboardWidget(repo_para_dashboard)
        self.tabs.addTab(self.dashboard, "Inicio")
        self.tabs.addTab(self.create_cuadro_clasificacion_tab(), "Cuadro de Clasificación (CGCA)")
        self.tabs.addTab(self.create_control_gestion_tab(), "Control de Gestión")
        self.tabs.addTab(self.create_expedientes_tab(), "Expedientes")
        self.tabs.addTab(self.create_busqueda_avanzada_tab(), "Búsqueda Avanzada")
        self.tabs.addTab(self.create_consulta_series_tab(), "Consulta Series")
        self.tabs.addTab(self.create_reportes_tab(), "Reportes")
        self.tabs.addTab(self.create_archivo_concentracion_tab(), "Archivo de Concentración")
        self.tabs.addTab(self.create_prestamos_tab(), "Préstamos Físicos")
        layout.addWidget(self.tabs)
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Listo")
    
    def solicitar_crear_backup(self):
        """
        Pide al usuario un nombre opcional y le pide al servicio que cree el backup.
        """
        nombre, ok = QInputDialog.getText(self, 
            "Crear Copia de Seguridad", 
            "Ingrese un nombre descriptivo para la copia (opcional):")
        
        if ok:
            success, message = self.backup_service.crear_backup(nombre)
            
            if success:
                self.expediente_service.registrar_evento_externo("CREAR_BACKUP", f"Se generó una copia de seguridad: {message}")
                mostrar_mensaje(self,"Éxito", message, QMessageBox.Information)
            else:
               mostrar_mensaje(self,"Error", message, QMessageBox.Critical)
    
    def solicitar_restaurar_backup(self):
        """
        Orquesta el proceso completo para restaurar una copia de seguridad.
        """
        backups = self.backup_service.listar_backups()
        if not backups:
            mostrar_mensaje(self,"Restaurar", "No se encontraron copias de seguridad.")
            return
        nombres_backup = [b['nombre'] for b in backups]
        nombre_seleccionado, ok = QInputDialog.getItem(self, "Restaurar Copia de Seguridad", 
                                                       "Seleccione una copia para restaurar:", nombres_backup, 0, False)
        if not ok or not nombre_seleccionado:
            return

        reply = QMessageBox.question(self, "Confirmación Crítica",
                                     "<b>ADVERTENCIA:</b> Esta acción reemplazará permanentemente la base de datos actual con los datos de la copia de seguridad.<br><br>"
                                     "Todos los cambios no guardados en un backup se perderán.<br><br>"
                                     "¿Está absolutamente seguro de que desea continuar?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply != QMessageBox.Yes:
            return
        try:
            ruta_backup_seleccionado = next(b['ruta'] for b in backups if b['nombre'] == nombre_seleccionado)
            success, message = self.backup_service.restaurar_backup(ruta_backup_seleccionado)
            if not success:
                raise Exception(message)
                self.expediente_service.registrar_evento_externo("RESTAURAR_BACKUP", f"CRÍTICO: Se sobrescribió la BD restaurando el backup {nombre_seleccionado}")
            self.cargar_expedientes()
            mostrar_mensaje(self,"Éxito", "La base de datos ha sido restaurada y los datos han sido recargados.")
        except Exception as e:
            logging.error("Error en la Restauración", exc_info=True)
            mostrar_mensaje(self,"Error en la Restauración", str(e), QMessageBox.Critical)

            self.cargar_expedientes()

    def create_expedientes_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        title_label = QLabel("GESTIÓN DE EXPEDIENTES")
        title_label.setObjectName("title_label")
        layout.addWidget(title_label)

        search_group = QGroupBox("Búsqueda de Expedientes")
        search_layout = QHBoxLayout(search_group)

        self.line_edit_buscar_expediente = QLineEdit(placeholderText="Buscar por folio, asunto o categoría...")
        
        self.btn_buscar_expediente = QPushButton("Buscar")
        
        self.btn_limpiar_busqueda = QPushButton("Limpiar")
        self.btn_limpiar_busqueda.setObjectName("btn_limpiar")

        self.btn_nuevo = QPushButton("Nuevo Expediente")
        self.btn_nuevo.setObjectName("btn_nuevo")

        search_layout.addWidget(self.line_edit_buscar_expediente)
        search_layout.addWidget(self.btn_buscar_expediente)
        search_layout.addWidget(self.btn_limpiar_busqueda)
        search_layout.addStretch()
        search_layout.addWidget(self.btn_nuevo)
        layout.addWidget(search_group)
        
        controles_superiores_layout = QHBoxLayout()
        self.combo_por_pagina = QComboBox()
        self.combo_por_pagina.setObjectName("combo_paginacion")
        self.combo_por_pagina.addItems(REGISTROS_POR_PAGINA)
        self.combo_por_pagina.setCurrentText(str(self.paginator_expedientes.por_pagina))
        
        controles_superiores_layout.addWidget(QLabel("Registros por página:"))
        controles_superiores_layout.addWidget(self.combo_por_pagina)
        controles_superiores_layout.addStretch()
        
        layout.addLayout(controles_superiores_layout)

        table_container = QFrame()
        table_container.setFrameShape(QFrame.StyledPanel)
        table_container.setObjectName("table_container")
        
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)

        self.tabla_expedientes = QTableWidget()
        self.tabla_expedientes.setColumnCount(ExpedientesTab.COLUMN_COUNT)
        self.tabla_expedientes.setHorizontalHeaderLabels(["ID", "Tipo", "Categoría", "Folio", "Fecha", "Asunto", "Serie", "Carpeta", "Páginas", "Respaldo", "Clasificación", "Apertura", "Cierre", "Vencimiento", "Acciones"])
        
        self.tabla_expedientes.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla_expedientes.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla_expedientes.setSelectionMode(QTableWidget.SingleSelection)
        self.tabla_expedientes.setAlternatingRowColors(True)
        self.tabla_expedientes.verticalHeader().setVisible(False)
        self.tabla_expedientes.setWordWrap(True)
        
        self.tabla_expedientes.verticalHeader().setDefaultSectionSize(60)
        self.tabla_expedientes.setColumnHidden(ExpedientesTab.RESPALDO, True)
        
        header = self.tabla_expedientes.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(ExpedientesTab.ASUNTO, QHeaderView.Stretch)
        header.setSectionResizeMode(ExpedientesTab.RESPALDO, QHeaderView.Stretch)

        table_layout.addWidget(self.tabla_expedientes)
        layout.addWidget(table_container)
        
        controles_inferiores_layout = QHBoxLayout()
        self.btn_primera_pagina = QPushButton("<< Primera")
        self.btn_primera_pagina.setObjectName("pagination_btn")
        self.btn_anterior = QPushButton("< Anterior")
        self.btn_anterior.setObjectName("pagination_btn")
        self.lbl_info_pagina = QLabel("Página 1 / 1")
        self.btn_siguiente = QPushButton("Siguiente >")
        self.btn_siguiente.setObjectName("pagination_btn")
        self.btn_ultima_pagina = QPushButton("Última >>")
        self.btn_ultima_pagina.setObjectName("pagination_btn") 
        
        controles_inferiores_layout.addStretch()
        controles_inferiores_layout.addWidget(self.btn_primera_pagina)
        controles_inferiores_layout.addWidget(self.btn_anterior)
        controles_inferiores_layout.addWidget(self.lbl_info_pagina)
        controles_inferiores_layout.addWidget(self.btn_siguiente)
        controles_inferiores_layout.addWidget(self.btn_ultima_pagina)
        controles_inferiores_layout.addStretch()

        layout.addLayout(controles_inferiores_layout)

        return widget

    def crear_menu_principal(self):
        menubar = self.menuBar()
        menu_archivo = menubar.addMenu("Archivo")
        accion_importar = QAction("Importar base de datos...", self)
        accion_importar.triggered.connect(self.abrir_dialogo_importacion)
        menu_archivo.addAction(accion_importar)
        
        menu_backup = menu_archivo.addMenu("Copias de Seguridad")
        accion_crear_backup = QAction("Crear copia de seguridad...", self)
        accion_restaurar_backup = QAction("Restaurar desde copia...", self)
        
        menu_backup.addAction(accion_crear_backup)
        menu_backup.addAction(accion_restaurar_backup)
        
        self.accion_crear_backup = accion_crear_backup
        self.accion_restaurar_backup = accion_restaurar_backup
        
        menu_archivo.addSeparator()
        accion_salir = QAction("Salir", self)
        accion_salir.triggered.connect(self.close)
        menu_archivo.addAction(accion_salir)
        
        menu_reportes = menubar.addMenu("Reportes")
        accion_productividad = QAction("📊 Reporte de Productividad (Quincenal)", self)
        accion_productividad.triggered.connect(self.mostrar_reporte_quincenal)
        menu_reportes.addAction(accion_productividad)
        
        if self.usuario_actual == "admin":
            menu_admin = menubar.addMenu("Administración")
            
            accion_usuarios = QAction("Gestionar Usuarios", self)
            accion_usuarios.setStatusTip("Crear o eliminar usuarios del sistema")
            accion_usuarios.triggered.connect(self.abrir_gestion_usuarios)
            accion_historial = QAction("Ver Historial de Actividad", self)
            accion_historial.triggered.connect(self.abrir_historial)
            
            menu_admin.addAction(accion_historial)
            menu_admin.addAction(accion_usuarios)
    
    def abrir_gestion_usuarios(self):
        """Abre el diálogo para gestionar credenciales."""
        repo = self.expediente_service._repository
        
        dialog = UsuariosDialog(repository=repo, parent=self)
        dialog.exec_()
    
    def abrir_historial(self):
        repo = self.expediente_service._repository
        dialog = HistorialDialog(repo, self)
        dialog.exec_()
    
    def ver_historial_expediente(self, expediente_id):
        """Muestra el historial filtrado para este expediente específico."""
        repo = self.expediente_service._repository
        texto_busqueda = f"ID {expediente_id}"       
        dialog = HistorialDialog(repository=repo, parent=self, filtro_texto=texto_busqueda)
        dialog.exec_()
    
    def ver_historial_cg(self, cg_id):
        """
        Muestra el historial filtrado EXCLUSIVAMENTE para Control de Gestión.
        Busca la etiqueta única 'Gestión ID' para no mezclarse con expedientes.
        """
        repo = self.expediente_service._repository
        texto_busqueda = f"(ID {cg_id})"
        dialog = HistorialDialog(repository=repo, parent=self, filtro_texto=texto_busqueda)
        dialog.exec_()
    
    def abrir_dialogo_importacion(self):
        """
        Abre el diálogo de importación y al cerrar actualiza TODO el sistema.
        """
        dialog = ImportadorDialog(import_service=self.import_service, parent=self)
        dialog.exec_()
        self.actualizar_interfaz()
    
    def cambiar_registros_por_pagina(self, valor_str):
        """
        Se activa cuando el usuario cambia el número de registros por página en la pestaña de expedientes.
        """
        if not valor_str: return
        valor = int(valor_str)
        
        self.paginator_expedientes.por_pagina = valor
        self.paginator_expedientes.ir_a_pagina(1)
        
    def cambiar_registros_por_pagina_busq(self, valor_str):
        """
        Se activa cuando el usuario cambia el número de registros por página en la búsqueda avanzada.
        """
        if not valor_str: return
        valor = int(valor_str)

        self.paginator_busqueda.por_pagina = valor
        self.paginator_busqueda.ir_a_pagina(1)

    def cargar_expedientes(self, pagina: int = 1):
        """Carga los expedientes de la página especificada."""
        try:
            expedientes, total_registros = self.expediente_service.obtener_expedientes_para_ui(
                pagina, 
                self.paginator_expedientes.por_pagina, 
                self.busqueda_actual
            )
            
            self.paginator_expedientes.actualizar_estado(
                total_registros,
                self.paginator_expedientes.por_pagina
            )
            
            self.poblar_tabla_expedientes(expedientes)
            self.actualizar_controles_paginacion()
            self.statusBar().showMessage(f"Mostrando {len(expedientes)} de {total_registros} expedientes. Página {self.paginator_expedientes.pagina_actual} de {self.paginator_expedientes.total_paginas}")

        except Exception as e:
            logging.error("Error al cargar expedientes: %s", e, exc_info=True)
            mostrar_mensaje(self,"Error", f"Error al cargar expedientes: {e}", QMessageBox.Critical)

    def buscar_expedientes(self):
        """Inicia una nueva búsqueda y resetea la paginación a la primera página."""
        self.busqueda_actual = self.line_edit_buscar_expediente.text().strip()
        self.paginator_expedientes.ir_a_pagina(1)
        
    def limpiar_busqueda(self):
        """Limpia la búsqueda y recarga desde la página 1."""
        self.line_edit_buscar_expediente.clear()
        self.busqueda_actual = ""
        self.paginator_expedientes.ir_a_pagina(1)
    
    def actualizar_controles_paginacion(self):
        """Actualiza el label y el estado de los botones usando el paginator."""
        self.lbl_info_pagina.setText(f"Página {self.paginator_expedientes.pagina_actual} / {self.paginator_expedientes.total_paginas}")
        es_primera = (self.paginator_expedientes.pagina_actual == 1)
        es_ultima = (self.paginator_expedientes.pagina_actual == self.paginator_expedientes.total_paginas)
        
        self.btn_anterior.setEnabled(not es_primera)
        self.btn_primera_pagina.setEnabled(not es_primera)
        self.btn_siguiente.setEnabled(not es_ultima)
        self.btn_ultima_pagina.setEnabled(not es_ultima)
        
    def actualizar_controles_paginacion_busq(self):
        """Actualiza los controles de paginación para la búsqueda avanzada usando su paginator."""
        self.lbl_info_pagina_busq.setText(f"Página {self.paginator_busqueda.pagina_actual} / {self.paginator_busqueda.total_paginas}")
        es_primera = (self.paginator_busqueda.pagina_actual == 1)
        es_ultima = (self.paginator_busqueda.pagina_actual == self.paginator_busqueda.total_paginas)
        
        self.btn_anterior_busq.setEnabled(not es_primera)
        self.btn_primera_pagina_busq.setEnabled(not es_primera)
        self.btn_siguiente_busq.setEnabled(not es_ultima)
        self.btn_ultima_pagina_busq.setEnabled(not es_ultima)

    def abrir_dialogo_edicion(self, expediente_id=None, tabla_origen=None):
        if not isinstance(expediente_id, int):
            expediente_id = None
            
        dialog = NuevoExpedienteDialog(
            expediente_service=self.expediente_service,
            parent=self,
            expediente_id=expediente_id
        )
        if dialog.exec_() == QDialog.Accepted:
            
            if expediente_id is not None and tabla_origen is not None:
                self._refrescar_y_mantener_foco(tabla_origen, id_foco=expediente_id)
            else:
                self.paginator_expedientes.forzar_recarga()
    
    def _crear_boton_acciones(self, tabla: QTableWidget, fila: int) -> QWidget:
        """
        Crea el widget contenedor con un botón de menú para una fila de una tabla.
    
        Args:
            tabla (QTableWidget): La tabla a la que pertenece el botón.
            fila (int): El número de fila donde se insertará el botón.
    
        Returns:
            QWidget: El widget contenedor listo para ser insertado en una celda.
        """
        menu_btn = QPushButton()
        menu_btn.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        menu_btn.setObjectName("action_menu_btn")
        
        menu_btn.clicked.connect(
            lambda checked, t=tabla: self._mostrar_menu_on_demand(t)
        )
        
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(menu_btn)
        layout.setAlignment(Qt.AlignCenter)
        
        return container
    
    def _poblar_tabla(self, tabla: QTableWidget, datos: list, config_columnas: list, columna_acciones: int = -1, callback_estilo=None, descongelar_al_final: bool = True):
        """
        Función genérica UNIVERSAL.
        Compatible con tablas simples (Expedientes) y avanzadas (Control Gestión).
        """
        tabla.setUpdatesEnabled(False) 
        tabla.setSortingEnabled(False)
        
        try:
            tabla.clearContents()
            tabla.setRowCount(len(datos))
            for col, cfg in enumerate(config_columnas):
                if 'width' in cfg:
                    tabla.setColumnWidth(col, cfg['width'])

            # 3. BUCLE PRINCIPAL
            for i, fila_datos in enumerate(datos):
                for j, config in enumerate(config_columnas):
                    clave = config['key']
                    tipo = config.get('type', 'text')
                    valor = fila_datos.get(clave)
                    
                    item = None
                    
                    # --- Lógica de Tipos ---
                    if tipo == 'numeric':
                        sort_value = valor if valor is not None and str(valor).strip() != '' else -1
                        item = NumericTableWidgetItem(str(valor) if valor is not None else "", sort_value)
                        
                        # Pequeña excepción para mantener tus colores de 'dias_vencido' en Expedientes
                        if clave == 'dias_vencido' and isinstance(valor, int):
                            if valor > 0: item.setForeground(QColor("red"))
                            else: item.setForeground(QColor("#d35400"))

                    elif tipo == 'date':
                        display_value = ""
                        date_obj = QDate()
                        if valor:
                            try:
                                val_str = str(valor).split(" ")[0] # Quitamos hora si existe
                                date_obj = QDate.fromString(val_str, "yyyy-MM-dd")
                                if date_obj.isValid():
                                    display_value = date_obj.toString("dd-MM-yyyy")
                                else:
                                    display_value = str(valor)
                            except:
                                display_value = str(valor)
                        item = DateTableWidgetItem(display_value, date_obj)
                        
                    else: # text
                        valor_str = str(valor) if valor is not None else ""
                        item = QTableWidgetItem(valor_str)
                        if len(valor_str) > 40:
                            texto_globo = "\n".join(textwrap.wrap(valor_str, width=60))
                            item.setToolTip(texto_globo)
                    if callback_estilo:
                        callback_estilo(item, clave, valor, fila_datos)
                    
                    tabla.setItem(i, j, item)

                # Botones de acción
                if columna_acciones != -1:
                    widget = self._crear_boton_acciones(tabla, i)
                    tabla.setCellWidget(i, columna_acciones, widget)
        
        except Exception as e:
            print(f"Error poblando tabla: {e}") # Log simple por seguridad

        finally:
            tabla.setSortingEnabled(True)
            if descongelar_al_final:
                tabla.setUpdatesEnabled(True)
    
    def _ejecutar_en_hilo(self, funcion_worker, callback_final, *args, **kwargs):
        """
        Ejecuta una función en un hilo secundario para no bloquear la UI.
        Delega el trabajo al Gestor de Tareas de concurrencia.
        """
        GestorTareas.ejecutar_en_segundo_plano(funcion_worker, callback_final, *args, **kwargs)

    def poblar_tabla_expedientes(self, data: list):
        config = [
            {'key': 'id', 'type': 'numeric'},
            {'key': 'tipo_documento', 'type': 'text'},
            {'key': 'categoria_documental', 'type': 'text'},
            {'key': 'folio', 'type': 'text'},
            {'key': 'fecha', 'type': 'date'},
            {'key': 'asunto', 'type': 'text'},
            {'key': 'serie_documental', 'type': 'text'},
            {'key': 'carpeta', 'type': 'text'},
            {'key': 'paginas', 'type': 'numeric'},
            {'key': 'documento_respaldo', 'type': 'text'},
            {'key': 'clasificacion', 'type': 'text'},
            {'key': 'apertura', 'type': 'numeric'},
            {'key': 'cierre', 'type': 'numeric'},
            {'key': 'vencimiento', 'type': 'date'},
        ]
        self._poblar_tabla(self.tabla_expedientes, data, config, columna_acciones=ExpedientesTab.ACCIONES, callback_estilo=self._aplicar_estilos_expedientes)
        
    def _aplicar_estilos_expedientes(self, item, clave, valor, fila_datos):
        """Callback para pintar alertas específicas en la tabla de Expedientes."""
        # Verificamos si el campo invisible 'esta_prestado' viene activado desde la BD
        expediente_prestado = fila_datos.get('esta_prestado', 0) == 1
        
        # Si estamos en la columna Asunto y está prestado, pintamos la alerta
        if clave == 'asunto' and expediente_prestado:
            item.setText(f"🛑 [PRESTADO] {valor}")
            item.setForeground(QColor("#c0392b")) # Rojo peligro
            font = item.font()
            font.setBold(True)
            item.setFont(font)

    def eliminar_expediente(self, tabla_activa, row, expediente_id):
        folio = tabla_activa.item(row, ExpedientesTab.FOLIO).text()
        
        reply = QMessageBox.question(self, 'Confirmar', f"¿Eliminar expediente con folio '{folio}'?", 
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            success, message = self.expediente_service.eliminar_expediente(expediente_id)
            if success:
                self.statusBar().showMessage(message)
                self._refrescar_y_mantener_foco(tabla_activa, fila_foco=row)
                self.cargar_expedientes()
                self.buscar_respuestas_avanzada()
                self.cargar_expedientes_vencidos()
                self.buscar_expedientes_en_concentracion()
            else:
                mostrar_mensaje(self,"Error", message, QMessageBox.Warning)
    
    def mostrar_respuestas(self, expediente_id: int, tabla_origen: QTableWidget):
        """
        Abre el diálogo de respuestas para un expediente, inyectando el servicio.
        """
        try:
            dialog = RespuestasDialog(
                expediente_service=self.expediente_service,
                expediente_id=expediente_id,
                parent=self
            )
            dialog.exec_()
            self._refrescar_y_mantener_foco(tabla_origen, id_foco=expediente_id)
        except Exception as e:
            logging.error("No se pudo abrir el gestor de respuestas: %s", e, exc_info=True)
            mostrar_mensaje(self,"Error", f"No se pudo abrir el gestor de respuestas: {str(e)}", QMessageBox.Critical)

    def ver_pdf(self, expediente_id):
        """
        Obtiene la ruta del PDF del expediente y lo abre en un diálogo integrado.
        Registra el evento en el historial.
        """
        self.statusBar().showMessage(f"Buscando el PDF para el expediente ID {expediente_id}...")
        success, result_path = self.expediente_service.obtener_ruta_pdf_expediente(expediente_id)
    
        if success:

            try:
                datos = self.expediente_service.obtener_datos_expediente(expediente_id)
                folio = datos.get('folio', 'S/F') if datos else 'Desconocido'
                
                self.expediente_service.registrar_evento_externo(
                    "VER_PDF", 
                    f"Se visualizó el documento digital del expediente ID {expediente_id} (Folio: {folio})"
                )
            except Exception:
                pass # Si falla el log, no impedimos que vea el PDF

            self.statusBar().showMessage(f"Abriendo visor para: {result_path}")
            dialogo_visor = PdfViewerDialog(result_path, self)
            dialogo_visor.exec_()
            self.statusBar().showMessage("Listo")
        else:
            mostrar_mensaje(self, "Archivo no Encontrado", result_path, QMessageBox.Warning)
            self.statusBar().showMessage("Archivo no encontrado")
    
    def ver_pdf_respuesta(self, respuesta_id: int):
        """
        Abre el PDF de una respuesta específica en el diálogo integrado.
        Registra el evento en el historial con el folio correcto.
        """
        self.statusBar().showMessage(f"Buscando el PDF para la respuesta ID {respuesta_id}...")
        success, result_path = self.expediente_service.obtener_ruta_pdf_respuesta(respuesta_id)
    
        if success:
            try:
                datos = self.expediente_service.obtener_datos_respuesta(respuesta_id)
                folio = datos.get('folio', 'S/F') if datos else 'Desconocido'
                self.expediente_service.registrar_evento_externo(
                    "VER_PDF_RESPUESTA", 
                    f"Se visualizó el documento adjunto de la respuesta ID {respuesta_id} (Folio Respuesta: {folio})"
                )
            except Exception as e:
                logging.error(f"Error al registrar historial respuesta: {e}")
                pass 

            self.statusBar().showMessage(f"Abriendo visor para: {result_path}")
            dialogo_visor = PdfViewerDialog(result_path, self)
            dialogo_visor.exec_()
            self.statusBar().showMessage("Listo")
        else:
            mostrar_mensaje(self, "Archivo no Encontrado", result_path, QMessageBox.Warning)
            self.statusBar().showMessage("Archivo no encontrado")

    def ver_completo(self, expediente_id: int):
        """
        Abre el visualizador de expediente completo, inyectando el servicio.
        Registra el evento en el historial.
        """
        try:
            # [HISTORIAL] Registramos que se consultó la ficha completa
            self.expediente_service.registrar_evento_externo(
                "VER_EXPEDIENTE", 
                f"Se consultó la ficha completa del expediente ID {expediente_id}"
            )

            dialog = VisualizadorExpediente(
                expediente_service=self.expediente_service,
                expediente_id=expediente_id,
                parent=self
            )
            dialog.exec_()
        except Exception as e:
            logging.error("No se pudo abrir el visualizador: %s", e, exc_info=True)
            mostrar_mensaje(self,"Error", f"No se pudo abrir el visualizador: {str(e)}", QMessageBox.Critical)

    def cerrar_expediente(self, expediente_id, tabla_origen):
        success, message = self.expediente_service.cerrar_expediente(expediente_id)
        mostrar_mensaje(self, "Resultado", message, QMessageBox.Information)
        if success:
            self._refrescar_y_mantener_foco(tabla_origen, id_foco=expediente_id)

    def cancelar_cierre(self, expediente_id, tabla_origen):
        success, message = self.expediente_service.cancelar_cierre_expediente(expediente_id)
        mostrar_mensaje(self, "Resultado", message)
        if success:
            self._refrescar_y_mantener_foco(tabla_origen, id_foco=expediente_id)
   
    def create_busqueda_avanzada_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)
        
        title_label = QLabel("BÚSQUEDA AVANZADA")
        title_label.setObjectName("title_label")
        layout.addWidget(title_label)

        # Grupo de búsqueda
        search_group = QGroupBox("Filtros de Búsqueda Avanzada")
        
        form_layout = QFormLayout(search_group)
        form_layout.setContentsMargins(10, 15, 10, 15)
        form_layout.setSpacing(12)

        # Fila 1: Búsqueda de texto y botones
        busqueda_group_inner = QGroupBox("Búsqueda")
        row1_layout = QHBoxLayout(busqueda_group_inner)
        self.texto_busqueda_avanzada = QLineEdit(placeholderText="Buscar en asunto y folio de respuestas...")
        self.btn_buscar_avanzada = QPushButton("Buscar")
        self.btn_limpiar_avanzada = QPushButton("Limpiar")
        self.btn_limpiar_avanzada.setObjectName("btn_limpiar")
        row1_layout.addWidget(self.texto_busqueda_avanzada, 1)
        row1_layout.addWidget(self.btn_buscar_avanzada)
        row1_layout.addWidget(self.btn_limpiar_avanzada)
        form_layout.addRow(busqueda_group_inner)


        row_container = QWidget()
        row_layout = QHBoxLayout(row_container)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(15)
        
        categoria_group = QGroupBox("Categoría")
        categoria_group.setProperty("filterGroup", True)
        categoria_layout = QHBoxLayout(categoria_group)
        self.categoria_doc_busq = QComboBox()
        self.categoria_doc_busq.addItem("")
        self.categoria_doc_busq.addItems(CATEGORIAS_DOCUMENTALES[1:])
        categoria_layout.addWidget(self.categoria_doc_busq)
        
        fecha_group = QGroupBox("Fecha Respuesta")
        categoria_group.setProperty("filterGroup", True)
        fecha_layout = QHBoxLayout(fecha_group)
        fecha_layout.setContentsMargins(5, 10, 5, 5)
        
        self.fecha_resp_inicio = QDateEdit(calendarPopup=True)
        self.fecha_resp_inicio.setDate(QDate.currentDate().addYears(-6))
        self.fecha_resp_inicio.setDisplayFormat("dd-MM-yyyy")
        
        self.fecha_resp_fin = QDateEdit(calendarPopup=True)
        self.fecha_resp_fin.setDate(QDate.currentDate())
        self.fecha_resp_fin.setDisplayFormat("dd-MM-yyyy")
        
        fecha_layout.addWidget(QLabel("Desde:"))
        fecha_layout.addWidget(self.fecha_resp_inicio)
        fecha_layout.addWidget(QLabel("Hasta:"))
        fecha_layout.addWidget(self.fecha_resp_fin)
        
        serie_group = QGroupBox("Serie")
        categoria_group.setProperty("filterGroup", True)
        serie_layout = QHBoxLayout(serie_group)
        self.serie_doc_busq = QComboBox()
        self.serie_doc_busq.addItem("")
        try:
            for serie in self.expediente_service.obtener_series_documentales():
                self.serie_doc_busq.addItem(serie['codigo_serie'])
        except Exception as e:
            logging.error("Error al cargar series en búsqueda avanzada: %s", e, exc_info=True)
            print(f"Error al cargar series en búsqueda avanzada: {e}")
        serie_layout.addWidget(self.serie_doc_busq)
        
        anio_group = QGroupBox("Año")
        categoria_group.setProperty("filterGroup", True)
        anio_layout = QHBoxLayout(anio_group)
        self.anio_apertura_busq = QComboBox()
        self.anio_apertura_busq.addItem("")
        self.anio_apertura_busq.addItems([str(year) for year in range(2017, QDate.currentDate().year() + 2)])
        anio_layout.addWidget(self.anio_apertura_busq)
        
        row_layout.addWidget(categoria_group, 2)
        row_layout.addWidget(fecha_group, 3)
        row_layout.addWidget(serie_group, 2)
        row_layout.addWidget(anio_group, 1)
        
        form_layout.addRow(row_container)
        
        table_container = QFrame()
        table_container.setFrameShape(QFrame.StyledPanel)
        table_container.setObjectName("table_container")
        table_layout = QVBoxLayout(table_container)
        
        self.tabla_busqueda_avanzada = QTableWidget()
        self.configurar_tabla_busqueda_avanzada()
        table_layout.addWidget(self.tabla_busqueda_avanzada)
        
        layout.addWidget(search_group)
        
        controles_superiores_layout = QHBoxLayout()
        self.combo_por_pagina_busq = QComboBox()
        self.combo_por_pagina_busq.setObjectName("combo_paginacion")
        self.combo_por_pagina_busq.addItems(REGISTROS_POR_PAGINA)
        self.combo_por_pagina_busq.setCurrentText(str(self.paginator_busqueda.por_pagina))
        
        controles_superiores_layout.addWidget(QLabel("Registros por página:"))
        controles_superiores_layout.addWidget(self.combo_por_pagina_busq)
        controles_superiores_layout.addStretch()
        
        layout.addLayout(controles_superiores_layout)
        
        layout.addWidget(table_container, 1)
        paginacion_layout_busq = QHBoxLayout()
        
        self.btn_primera_pagina_busq = QPushButton("<< Primera")
        self.btn_primera_pagina_busq.setObjectName("pagination_btn")
        
        self.btn_anterior_busq = QPushButton("< Anterior")
        self.btn_anterior_busq.setObjectName("pagination_btn")
        
        self.lbl_info_pagina_busq = QLabel("Página 1 / 1")
        
        self.btn_siguiente_busq = QPushButton("Siguiente >")
        self.btn_siguiente_busq.setObjectName("pagination_btn")
        
        self.btn_ultima_pagina_busq = QPushButton("Última >>")
        self.btn_ultima_pagina_busq.setObjectName("pagination_btn")
        
        paginacion_layout_busq.addStretch()
        paginacion_layout_busq.addWidget(self.btn_primera_pagina_busq)
        paginacion_layout_busq.addWidget(self.btn_anterior_busq)
        paginacion_layout_busq.addWidget(self.lbl_info_pagina_busq)
        paginacion_layout_busq.addWidget(self.btn_siguiente_busq)
        paginacion_layout_busq.addWidget(self.btn_ultima_pagina_busq)
        paginacion_layout_busq.addStretch()
        
        layout.addLayout(paginacion_layout_busq)
        return widget
    
    def configurar_tabla_busqueda_avanzada(self):
        """Configura las propiedades de la tabla de búsqueda avanzada."""
        self.tabla_busqueda_avanzada.setColumnCount(BusquedaAvanzadaTab.COLUMN_COUNT)
        self.tabla_busqueda_avanzada.setHorizontalHeaderLabels([ "ID Exp." , "ID Resp." , "Tipo" , "Categoría" , "Folio" , "Fecha" , "Asunto ", "Serie" , "Carpeta" , "Páginas" , "Documento " , "Clasificación" , "Apertura" , "Cierre" , "Vencimiento" , "Acciones" ])
        self.tabla_busqueda_avanzada.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla_busqueda_avanzada.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla_busqueda_avanzada.setSelectionMode(QTableWidget.SingleSelection)
        self.tabla_busqueda_avanzada.setAlternatingRowColors(True)
        self.tabla_busqueda_avanzada.verticalHeader().setVisible(False)
        self.tabla_busqueda_avanzada.setWordWrap(True)
        
        self.tabla_busqueda_avanzada.verticalHeader().setDefaultSectionSize(60)
        self.tabla_busqueda_avanzada.setColumnHidden(BusquedaAvanzadaTab.DOCUMENTO, True)
        
        header = self.tabla_busqueda_avanzada.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(BusquedaAvanzadaTab.ASUNTO, QHeaderView.Stretch)
        header.setSectionResizeMode(BusquedaAvanzadaTab.DOCUMENTO, QHeaderView.Stretch)

    def poblar_tabla_busqueda_avanzada(self, data):
        config = [
            {'key': 'expediente_id', 'type': 'numeric'},
            {'key': 'id', 'type': 'numeric'},
            {'key': 'tipo_documento', 'type': 'text'},
            {'key': 'categoria_documental', 'type': 'text'},
            {'key': 'folio', 'type': 'text'},
            {'key': 'fecha_respuesta', 'type': 'date'},
            {'key': 'asunto_respuesta', 'type': 'text'},
            {'key': 'serie_documental', 'type': 'text'},
            {'key': 'carpeta', 'type': 'text'},
            {'key': 'paginas', 'type': 'numeric'},
            {'key': 'documento_respuesta', 'type': 'text'},
            {'key': 'clasificacion', 'type': 'text'},
            {'key': 'apertura', 'type': 'numeric'},
            {'key': 'cierre', 'type': 'numeric'},
            {'key': 'vencimiento', 'type': 'date'},
        ]
        self._poblar_tabla(self.tabla_busqueda_avanzada, data, config, columna_acciones=BusquedaAvanzadaTab.ACCIONES)

    def _mostrar_menu_on_demand(self, tabla_activa: QTableWidget):
        """
        Crea y muestra el menú de acciones.
        CORREGIDO: Diferencia entre Expedientes y Control de Gestión para evitar validaciones cruzadas.
        """
        pos_global = QCursor.pos()
        pos_local = tabla_activa.viewport().mapFromGlobal(pos_global)
        
        index = tabla_activa.indexAt(pos_local)
        if not index.isValid():
            return 
    
        fila = index.row()
    
        acciones_disponibles, id_column = [], 0
        es_control_gestion = False  # Bandera para saber si estamos en CG
        
        # 1. Configurar acciones según la tabla
        if tabla_activa is self.tabla_expedientes:
            acciones_disponibles, id_column = ['editar', 'eliminar', 'separator', 'respuestas', 'separator', 'ver_pdf', 'ver_completo',
                                               'historial', 'enviar_correo', 'separator', 'imprimir_etiquetas', 'separator', 'prestar'], ExpedientesTab.ID
        elif tabla_activa is self.tabla_cg:
            acciones_disponibles, id_column = ['editar_cg', 'historial_cg', 'imprimir_cg', 'eliminar_cg'], 0
            es_control_gestion = True  # ¡Importante!
        elif tabla_activa is self.tabla_busqueda_avanzada:
            acciones_disponibles, id_column = ['ver_pdf','ver_completo', 'respuestas', 'historial', 'enviar_correo', 'separator','imprimir_etiquetas'], BusquedaAvanzadaTab.ID_EXPEDIENTE
        elif tabla_activa is self.tabla_vencidos:
            acciones_disponibles, id_column = ['ver_completo',  'historial', 'separator', 'enviar_correo', 'mover_concentracion'], 0
        elif tabla_activa is self.tabla_concentracion:
            acciones_disponibles, id_column = ['ver_completo', 'historial', 'enviar_correo', 'restaurar', 'separator', 'prestar'], 0
        elif tabla_activa is getattr(self, 'tabla_destinos_finales', None): # <--- NUEVA REGLA
            acciones_disponibles, id_column = ['ver_completo', 'historial', 'separator', 'revertir_destino'], DestinoFinalTab.ID_REGISTRO
        elif tabla_activa is getattr(self, 'tabla_prestamos', None):
            acciones_disponibles, id_column = ['ver_completo', 'historial', 'separator','separator', 'reimprimir_vale', 'devolver'], PrestamosTab.ID_PRESTAMO
        # 2. Obtener el ID del registro seleccionado
        try:
            id_registro = int(tabla_activa.item(fila, id_column).text())
        except (AttributeError, ValueError):
            return
    
        # 3. Validaciones específicas (SOLO si NO es Control de Gestión)
        expediente_esta_cerrado = False
        
        if not es_control_gestion:
            # Buscamos en la tabla de expedientes solo si es un expediente
            datos_exp = self.expediente_service.obtener_datos_expediente(id_registro)
            if not datos_exp: return
            
            cierre_val = datos_exp.get("cierre")
            expediente_esta_cerrado = cierre_val is not None and str(cierre_val).strip() != ""
        
        # 4. Construir el menú
        menu = QMenu(self)
    
        for nombre_accion in acciones_disponibles:
            if nombre_accion == 'separator':
                menu.addSeparator()
                continue
            
            info = self.action_map.get(nombre_accion)
            if not info: continue
    
            accion = QAction(info['texto'], self)
            
            # --- Configuración de Handlers ---
            
            if nombre_accion == 'ver_pdf' and tabla_activa is self.tabla_busqueda_avanzada:
                try:
                    respuesta_id = int(tabla_activa.item(fila, BusquedaAvanzadaTab.ID_RESPUESTA).text())
                    accion.triggered.connect(lambda checked, rid=respuesta_id: self.ver_pdf_respuesta(rid))
                except (AttributeError, ValueError):
                    accion.setEnabled(False) 
            
            elif nombre_accion == 'editar':
                accion.triggered.connect(lambda checked, eid=id_registro, t=tabla_activa: self.abrir_dialogo_edicion(eid, t))
            
            elif nombre_accion == 'eliminar':
                accion.triggered.connect(lambda checked, eid=id_registro, t=tabla_activa, r=fila: self.eliminar_expediente(t, r, eid))
            
            elif nombre_accion == 'respuestas':
                accion.triggered.connect(lambda checked, eid=id_registro, t=tabla_activa: self.mostrar_respuestas(eid, t))
            
            else:
                # Handler genérico (funciona para CG también, pasando el ID correcto)
                handler_correcto = info['handler']
                accion.triggered.connect(lambda checked, eid=id_registro, h=handler_correcto: h(eid))
            
            # Deshabilitar opciones si el expediente está cerrado (No aplica a CG)
            if not es_control_gestion and expediente_esta_cerrado and nombre_accion in ['editar', 'respuestas']:
                accion.setEnabled(False)
                accion.setText(f"{info['texto']} (Cerrado)")
            
            menu.addAction(accion)
    
        # 5. Opciones Extra (Cerrar/Abrir) - Solo para Expedientes
        if tabla_activa is self.tabla_expedientes or tabla_activa is self.tabla_busqueda_avanzada:
            menu.addSeparator()
            if expediente_esta_cerrado:
                accion = QAction("🔓 Cancelar Cierre", self)
                accion.triggered.connect(lambda checked, eid=id_registro, t=tabla_activa: self.cancelar_cierre(eid, t))
            else:
                accion = QAction("🔒 Cerrar Expediente", self)
                accion.triggered.connect(lambda checked, eid=id_registro, t=tabla_activa: self.cerrar_expediente(eid, t))
            menu.addAction(accion)
    
        menu.exec_(QCursor.pos())
    
    def mover_un_expediente(self, expediente_id):
        """Abre el diálogo de ubicación y mueve un único expediente a concentración."""
        dialog = UbicacionDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            ubicacion = dialog.get_ubicacion()
            ids_a_mover = [expediente_id]
            
            success, message = self.expediente_service.mover_expedientes_a_concentracion(ids_a_mover, ubicacion)
            
            if success:
                mostrar_mensaje(self,"Éxito", message, QMessageBox.Information)
                self.cargar_expedientes_vencidos()
                self.buscar_expedientes_en_concentracion()
                self.cargar_expedientes() 
            else:
                mostrar_mensaje(self,"Error", message, QMessageBox.Warning)

    def limpiar_busqueda_avanzada(self):
        """Limpia todos los filtros de la búsqueda avanzada y la tabla de resultados."""
        self.texto_busqueda_avanzada.clear()
        self.categoria_doc_busq.setCurrentIndex(0)
        self.fecha_resp_inicio.setDate(QDate.currentDate().addYears(-6))
        self.fecha_resp_fin.setDate(QDate.currentDate())
        self.serie_doc_busq.setCurrentIndex(0)
        self.anio_apertura_busq.setCurrentIndex(0)
        self.tabla_busqueda_avanzada.setRowCount(0)
        self.statusBar().showMessage("Filtros de búsqueda avanzada limpiados.")
    
    def buscar_respuestas_avanzada(self, pagina: int = 1, es_nueva_busqueda: bool = False):
        if es_nueva_busqueda:
            self.busqueda_avanzada_activa = True
        
        if es_nueva_busqueda:
            self.filtros_actuales_busq = {
                'texto': self.texto_busqueda_avanzada.text().strip(),
                'categoria_documental': self.categoria_doc_busq.currentText(),
                'fecha_inicio': self.fecha_resp_inicio.date().toString("yyyy-MM-dd"),
                'fecha_fin': self.fecha_resp_fin.date().toString("yyyy-MM-dd"),
                'serie_documental': self.serie_doc_busq.currentText(),
                'apertura': self.anio_apertura_busq.currentText()
            }
            self.filtros_actuales_busq = {k: v for k, v in self.filtros_actuales_busq.items() if v}
    
        try:
            self.statusBar().showMessage("Realizando búsqueda...")
            
            respuestas, total_registros = self.expediente_service.buscar_respuestas_paginado(
                self.filtros_actuales_busq, pagina, self.paginator_busqueda.por_pagina
            )

            self.paginator_busqueda.actualizar_estado(
                total_registros,
                self.paginator_busqueda.por_pagina
            )
            
            self.poblar_tabla_busqueda_avanzada(respuestas)
            self.actualizar_controles_paginacion_busq() 
            self.statusBar().showMessage(f"Se encontraron {total_registros} respuestas. Mostrando página {self.paginator_busqueda.pagina_actual} de {self.paginator_busqueda.total_paginas}.")
    
        except Exception as e:
            logging.error("Ocurrió un error en la búsqueda: %s", e, exc_info=True)
            mostrar_mensaje(self,"Error", f"Ocurrió un error en la búsqueda: {e}", QMessageBox.Critical)

    
    def create_reportes_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)
        
        title_label = QLabel("REPORTES DE EXPEDIENTES")
        title_label.setObjectName("title_label")
        layout.addWidget(title_label)

        search_group = QGroupBox("Filtros del Reporte")
        
        form_layout = QFormLayout(search_group)
        form_layout.setContentsMargins(10, 15, 10, 15)
        form_layout.setSpacing(12)
        
        
        def create_filter_group(parent_layout, title, widget, stretch=1):
            group = QGroupBox(title)
            group.setProperty("filterGroup", True)
            lyt = QHBoxLayout(group)
            lyt.setContentsMargins(5, 15, 5, 5)
            lyt.addWidget(widget)
            parent_layout.addWidget(group, stretch)

        filters_row = QWidget()
        filters_layout = QHBoxLayout(filters_row)
        filters_layout.setContentsMargins(0, 0, 0, 0)
        filters_layout.setSpacing(10)
        
        self.tipo_reporte_combo = QComboBox()
        self.tipo_reporte_combo.addItems(["Expedientes", "Respuestas"])
        create_filter_group(filters_layout, "Tipo de Reporte", self.tipo_reporte_combo, 2)

        self.reporte_fecha_inicio = QDateEdit(calendarPopup=True)
        self.reporte_fecha_inicio.setDate(QDate.currentDate().addYears(ANIOS_ATRAS_FILTRO))
        self.reporte_fecha_inicio.setDisplayFormat("dd-MM-yyyy")
        create_filter_group(filters_layout, "Fecha Inicio", self.reporte_fecha_inicio, 1)
        
        self.reporte_fecha_fin = QDateEdit(calendarPopup=True)
        self.reporte_fecha_fin.setDate(QDate.currentDate())
        self.reporte_fecha_fin.setDisplayFormat("dd-MM-yyyy")
        create_filter_group(filters_layout, "Fecha Fin", self.reporte_fecha_fin, 1)
        
        self.reporte_serie_combo = QComboBox()
        self.reporte_serie_combo.addItem("Todas")
        try:
            for serie in self.expediente_service.obtener_series_documentales():
                self.reporte_serie_combo.addItem(serie['codigo_serie'])
        except Exception as e:
            logging.error("Error al cargar series en reportes: %s", e, exc_info=True)
            print(f"Error al cargar series en reportes: {e}")
        create_filter_group(filters_layout, "Serie", self.reporte_serie_combo, 2)
        
        self.reporte_categoria_combo = QComboBox()
        self.reporte_categoria_combo.addItem("Todas")
        self.reporte_categoria_combo.addItems(CATEGORIAS_DOCUMENTALES[1:])
        create_filter_group(filters_layout, "Categoría", self.reporte_categoria_combo, 2)

        self.reporte_estado_combo = QComboBox()
        self.reporte_estado_combo.addItems(ESTADOS_EXPEDIENTE)
        create_filter_group(filters_layout, "Estado", self.reporte_estado_combo, 1)

        buttons_container = QWidget()
        buttons_layout = QHBoxLayout(buttons_container)
        buttons_layout.addStretch()
        self.btn_generar_reporte_filtrado = QPushButton("Generar Reporte")
        self.btn_limpiar_filtros_reporte = QPushButton("Limpiar Filtros")
        self.btn_limpiar_filtros_reporte.setObjectName("btn_limpiar")
                     
        buttons_layout.addWidget(self.btn_generar_reporte_filtrado)
        buttons_layout.addWidget(self.btn_limpiar_filtros_reporte)
        
        form_layout.addRow(filters_row)
        form_layout.addRow(buttons_container)
        
        table_container = QFrame()
        table_container.setFrameShape(QFrame.StyledPanel)
        table_container.setObjectName("table_container")
        
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        
        toolbar_container = QWidget()
        toolbar_layout = QHBoxLayout(toolbar_container)
        toolbar_layout.setContentsMargins(10, 5, 10, 5)
        
        export_label = QLabel("Exportar:")
        
        self.btn_exportar_excel = QPushButton("Excel")
        self.btn_exportar_excel.setObjectName("btn_exportar")
        
        self.btn_generar_inventario = QPushButton("Inventario")
        self.btn_generar_inventario.setObjectName("btn_base")
        
        toolbar_layout.addWidget(export_label)
        toolbar_layout.addWidget(self.btn_exportar_excel)
        toolbar_layout.addWidget(self.btn_generar_inventario)
        toolbar_layout.addStretch()
        
        self.tabla_reportes = QTableWidget()
        self.tabla_reportes.setColumnCount(ReportesTab.COLUMN_COUNT)
        self.tabla_reportes.setHorizontalHeaderLabels(["ID", "Tipo", "Categoría", "Folio", "Fecha", "Asunto", "Serie", "Carpeta", "Páginas", "Respaldo", "Clasificación", "Apertura", "Cierre", "Vencimiento", "Estado", "Días Vencido"])
        self.tabla_reportes.verticalHeader().setVisible(False)
        self.tabla_reportes.setAlternatingRowColors(True)
        self.tabla_reportes.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla_reportes.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla_reportes.setWordWrap(True)
        
        self.tabla_reportes.verticalHeader().setDefaultSectionSize(60)
        self.tabla_reportes.setColumnHidden(ReportesTab.RESPALDO_EXP, True)
        
        header = self.tabla_reportes.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(ReportesTab.ASUNTO_EXP, QHeaderView.Stretch)
        header.setSectionResizeMode(ReportesTab.RESPALDO_EXP, QHeaderView.Stretch)
        
        table_layout.addWidget(toolbar_container)
        table_layout.addWidget(self.tabla_reportes)

        layout.addWidget(search_group)
        layout.addWidget(table_container, 1)
        
        return widget
    
    def generar_reporte_filtrado(self):
        try:
            tipo_reporte = self.tipo_reporte_combo.currentText()
            
            filtros = {
                'fecha_inicio': self.reporte_fecha_inicio.date().toString("yyyy-MM-dd"),
                'fecha_fin': self.reporte_fecha_fin.date().toString("yyyy-MM-dd"),
                'categoria_documental': self.reporte_categoria_combo.currentText(),
                'serie_documental': self.reporte_serie_combo.currentText(),
                'estado': self.reporte_estado_combo.currentText()
            }
            
            self.statusBar().showMessage(f"Generando reporte de {tipo_reporte}...")
            
            datos_reporte = []
            if tipo_reporte == "Expedientes":
                datos_reporte = self.expediente_service.obtener_datos_para_reporte(filtros)
            else: # Respuestas
                datos_reporte = self.expediente_service.obtener_datos_para_reporte_respuestas(filtros)
            
            self.poblar_tabla_reportes(datos_reporte, tipo_reporte)
            self.statusBar().showMessage(f"Reporte generado. Se encontraron {len(datos_reporte)} registros.")

        except Exception as e:
            logging.error("Ocurrió un error al generar el reporte: %s", e, exc_info=True)
            mostrar_mensaje(self,"Error", f"Ocurrió un error al generar el reporte: {str(e)}", QMessageBox.Critical)
            self.statusBar().showMessage("Error")
    
    def limpiar_filtros_reporte(self):
        self.reporte_fecha_inicio.setDate(QDate.currentDate().addYears(ANIOS_ATRAS_FILTRO))
        self.reporte_fecha_fin.setDate(QDate.currentDate())
        self.reporte_serie_combo.setCurrentIndex(0)
        self.reporte_categoria_combo.setCurrentIndex(0)
        self.reporte_estado_combo.setCurrentIndex(0)
        self.tabla_reportes.setRowCount(0)
        
        self.statusBar().showMessage("Filtros limpiados. Genere un nuevo reporte.")

    def poblar_tabla_reportes(self, data: list, tipo_reporte: str):
        """
        Puebla la tabla de reportes. Usa la función genérica y añade lógica
        específica para las columnas calculadas con el formato correcto.
        """
        headers = []
        config = []
    
        if tipo_reporte == "Expedientes":
            headers = ["ID", "Tipo", "Categoría", "Folio", "Fecha", "Asunto", "Serie", "Carpeta", "Páginas", "Respaldo", "Clasificación", "Apertura", "Cierre", "Vencimiento", "Estado", "Días Vencido"]
            config = [
                {'key': 'id', 'type': 'numeric'}, {'key': 'tipo_documento', 'type': 'text'},
                {'key': 'categoria_documental', 'type': 'text'}, {'key': 'folio', 'type': 'text'},
                {'key': 'fecha', 'type': 'date'}, {'key': 'asunto', 'type': 'text'},
                {'key': 'serie_documental', 'type': 'text'}, {'key': 'carpeta', 'type': 'text'},
                {'key': 'paginas', 'type': 'numeric'}, {'key': 'documento_respaldo', 'type': 'text'},
                {'key': 'clasificacion', 'type': 'text'}, {'key': 'apertura', 'type': 'numeric'},
                {'key': 'cierre', 'type': 'numeric'}, {'key': 'vencimiento', 'type': 'date'}
            ]
        
        elif tipo_reporte == "Respuestas":
            headers = ["ID Resp.", "ID Exp.", "Tipo", "Categoría", "Folio", "Fecha", "Asunto", "Páginas", "Respaldo", "Serie", "Carpeta", "Clasificación", "Apertura", "Cierre", "Vencimiento", "Estado", "Días Vencido"]
            config = [
                {'key': 'id', 'type': 'numeric'}, {'key': 'expediente_id', 'type': 'numeric'},
                {'key': 'tipo_documento', 'type': 'text'}, {'key': 'categoria_documental', 'type': 'text'},
                {'key': 'folio', 'type': 'text'}, {'key': 'fecha_respuesta', 'type': 'date'},
                {'key': 'asunto_respuesta', 'type': 'text'}, {'key': 'paginas', 'type': 'numeric'},{'key': 'documento_respuesta', 'type': 'text'},
                {'key': 'serie_documental', 'type': 'text'}, {'key': 'carpeta', 'type': 'text'},
                {'key': 'clasificacion', 'type': 'text'}, {'key': 'apertura', 'type': 'numeric'},
                {'key': 'cierre', 'type': 'numeric'}, {'key': 'vencimiento', 'type': 'date'}
            ]
    
        self.tabla_reportes.setColumnCount(len(headers))
        self.tabla_reportes.setHorizontalHeaderLabels(headers)
        
        self._poblar_tabla(self.tabla_reportes, data, config)
    
        if data:
            today = datetime.now().date()
            col_estado = self.tabla_reportes.columnCount() - 2
            col_dias = self.tabla_reportes.columnCount() - 1
            
            for i, fila_datos in enumerate(data):
                estado = "Abierto"
                if fila_datos.get('vencimiento') and str(fila_datos.get('vencimiento')).strip():
                    try:
                        if datetime.strptime(fila_datos.get('vencimiento'), '%Y-%m-%d').date() < today:
                            estado = "Vencido"
                    except ValueError: pass
                
                if estado != "Vencido" and fila_datos.get("cierre") is not None and str(fila_datos.get("cierre")).strip() != "":
                    estado = "Cerrado"
                    
                # Aplicamos la columna dinámica de Estado
                self.tabla_reportes.setItem(i, col_estado, QTableWidgetItem(estado))
    
                # 2. Calcular, formatear y establecer los Días Vencido
                dias = fila_datos.get('dias_vencido')
                item_dias = NumericTableWidgetItem("", 999999) # Item por defecto
                if isinstance(dias, int):
                    display_text = ""
                    if dias >= 0:
                        display_text = f"Faltan {dias} día{'s' if dias != 1 else ''}"
                        item_dias.setForeground(QColor("red"))

                    else:
                        num_dias = abs(dias)
                        display_text = f"Vencido hace {num_dias} día{'s' if num_dias != 1 else ''}"
                        item_dias.setForeground(QColor("#d35400"))
                    
                    item_dias.setText(display_text)
                    item_dias.sort_key = dias
                
                # Aplicamos la columna dinámica de Días Vencido
                self.tabla_reportes.setItem(i, col_dias, item_dias)
    
        header = self.tabla_reportes.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        if tipo_reporte == "Expedientes":
            header.setSectionResizeMode(ReportesTab.ASUNTO_EXP, QHeaderView.Stretch)
            header.setSectionResizeMode(ReportesTab.RESPALDO_EXP, QHeaderView.Stretch)
        elif tipo_reporte == "Respuestas":
            header.setSectionResizeMode(ReportesTab.ASUNTO_RESP, QHeaderView.Stretch)
    
        self.tabla_reportes.setSortingEnabled(True)

    def exportar_reporte_a_excel(self):
        """
        Abre un diálogo "Guardar como", recoge los datos de la tabla 
        y los manda al servicio de Excel en un hilo.
        """
        if self.tabla_reportes.rowCount() == 0:
            mostrar_mensaje(self,"Exportar", "No hay datos en la tabla para exportar.", QMessageBox.Warning)
            return

        default_filename = f"reporte_{datetime.now().strftime('%Y%m%d')}.xlsx"
        
        filepath, _ = QFileDialog.getSaveFileName(self, 
            "Guardar Reporte como...", 
            default_filename,
            "Archivos de Excel (*.xlsx)"
        )

        if not filepath:
            return

        try:
            headers = [self.tabla_reportes.horizontalHeaderItem(i).text() for i in range(self.tabla_reportes.columnCount())]
            data_to_export = []
            for row in range(self.tabla_reportes.rowCount()):
                row_data = {}
                for col, header in enumerate(headers):
                    item = self.tabla_reportes.item(row, col)
                    # El cambio clave: revisa si el item existe antes de leer el texto
                    row_data[header] = item.text() if item else ""
                data_to_export.append(row_data)
        except Exception as e:
            logging.error("No se pudieron leer los datos de la tabla para exportar: %s", e, exc_info=True)
            mostrar_mensaje(self,"Error de Lectura", f"No se pudieron leer los datos de la tabla para exportar: {e}", QMessageBox.Critical)
            return

        self.statusBar().showMessage("Exportando a Excel, por favor espere...")
        self.btn_exportar_excel.setEnabled(False)
        tipo_reporte = self.tipo_reporte_combo.currentText()
        self.expediente_service.registrar_evento_externo(
            "EXPORTACIÓN_EXCEL", 
            f"Se descargó un archivo de Excel con {len(data_to_export)} registros filtrados de '{tipo_reporte}'."
        )
        self._ejecutar_en_hilo(
            self.excel_service.create_report,
            self.on_exportacion_finalizada,
            data_to_export,
            filepath
        )
    
    def exportar_inventario_completo(self):
        # Primero, obtenemos todos los expedientes sin filtros ni paginación
        try:
            todos_los_expedientes = self.expediente_service.obtener_datos_para_reporte({})
        except Exception as e:
            logging.error("No se pudieron obtener los datos para el inventario: %s", e, exc_info=True)
            mostrar_mensaje(self,"Error", f"No se pudieron obtener los datos para el inventario: {e}", QMessageBox.Critical)
            return

        if not todos_los_expedientes:
            mostrar_mensaje(self,"Inventario", "No hay expedientes para generar el inventario.", QMessageBox.Warning)
            return
            
        template_path = get_template_path() # Usamos nuestro config manager
        output_path, _ = QFileDialog.getSaveFileName(self, "Guardar Inventario como...", "inventario_completo.xlsx", "Archivos de Excel (*.xlsx)")

        if not output_path:
            return
            
        self.statusBar().showMessage("Generando inventario completo, esto puede tardar...")
        self.btn_generar_inventario.setEnabled(False)
        self.expediente_service.registrar_evento_externo("EXPORTACION_MASIVA", "Se generó y descargó el Inventario Completo del sistema en Excel.")
        self._ejecutar_en_hilo(
            self.excel_service.create_inventory_from_template,
            self.on_inventario_finalizado,
            todos_los_expedientes,
            template_path,
            output_path
        )

    def on_inventario_finalizado(self, resultado):
        success, message = resultado
        if success:
            mostrar_mensaje(self,"Éxito", message)
        else:
            mostrar_mensaje(self,"Error de Inventario", message, QMessageBox.Critical)
        
        self.btn_generar_inventario.setEnabled(True)
        self.statusBar().showMessage("Listo")
       
    def create_archivo_concentracion_tab(self):
        """Crea la pestaña de Archivo de Concentración con sus subpestañas."""
        tab_widget = QTabWidget()
        tab_widget.setUsesScrollButtons(True)
        
        tab_vencidos = self.create_vencidos_sub_tab()
        tab_transferencias = self.create_transferencias_sub_tab()
        tab_concentracion = self.create_concentracion_sub_tab()
        tab_dictamenes = self.create_dictamenes_sub_tab()
        tab_destino_final = self.create_destino_final_sub_tab()
        tab_historial_lotes = self.create_historial_lotes_sub_tab()
        
        tab_widget.addTab(tab_vencidos, "1. Preparación de Documentos")
        tab_widget.addTab(tab_transferencias, "2. Transferencias en Tránsito")
        tab_widget.addTab(tab_concentracion, "3. Acervo en Concentración")
        tab_widget.addTab(tab_dictamenes, "4. Valoración Secundaria") 
        tab_widget.addTab(tab_destino_final, "5. Destino Final")
        tab_widget.addTab(tab_historial_lotes, "6. Historial de Acuses")

        
        return tab_widget
    
    def create_vencidos_sub_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        
        title_label = QLabel("ARCHIVO DE CONCENTRACIÓN - EXPEDIENTES VENCIDOS")
        title_label.setObjectName("title_label")
        layout.addWidget(title_label)
        
        search_group = self.create_filtros_vencidos()
        
        btn_group = QGroupBox("Acciones")
        btn_layout = QHBoxLayout(btn_group)
        self.btn_actualizar_vencidos = QPushButton("Actualizar Base")
        self.btn_actualizar_vencidos.setObjectName("btn_base")
        self.btn_generar_inventario_vencidos = QPushButton("📋 Reporte Transferencia Primaria")
        self.btn_generar_inventario_vencidos.clicked.connect(self.exportar_inventario_seleccionados)
        self.btn_mover_a_concentracion = QPushButton("📦 Empaquetar en Lote")
        self.btn_exportar_vencidos = QPushButton("Exportar a Excel")
        self.btn_exportar_vencidos.setObjectName("btn_exportar")
        btn_layout.addWidget(self.btn_actualizar_vencidos)
        btn_layout.addWidget(self.btn_generar_inventario_vencidos)
        btn_layout.addWidget(self.btn_mover_a_concentracion)
        btn_layout.addWidget(self.btn_exportar_vencidos)
        btn_layout.addStretch()

        table_container = QFrame()
        table_container.setFrameShape(QFrame.StyledPanel)
        table_container.setObjectName("table_container")
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0,0,0,0)
        
        self.tabla_vencidos = QTableWidget()
        self.configurar_tabla_vencidos()
        table_layout.addWidget(self.tabla_vencidos)
        
        layout.addWidget(search_group)
        layout.addWidget(btn_group)
        layout.addWidget(table_container, 1)
        
        return widget
    
    def create_transferencias_sub_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        
        title_label = QLabel("MIS TRANSFERENCIAS (LOTES EN TRÁNSITO)")
        title_label.setObjectName("title_label")
        layout.addWidget(title_label)
        
        btn_group = QGroupBox("Gestión de Paquetes")
        btn_layout = QHBoxLayout(btn_group)
        
        self.btn_actualizar_lotes = QPushButton("🔄 Actualizar Tabla")
        self.btn_reimprimir_lote = QPushButton("🖨️ Reimprimir Excel de Inventario")
        self.btn_cancelar_lote = QPushButton("🚫 Cancelar Paquete")
        self.btn_cancelar_lote.setObjectName("btn_peligro")
        self.btn_confirmar_entrega = QPushButton("✅ Confirmar Entrega en Concentración")
        self.btn_confirmar_entrega.setObjectName("btn_exito")
        
        btn_layout.addWidget(self.btn_actualizar_lotes)
        btn_layout.addWidget(self.btn_reimprimir_lote)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancelar_lote)
        btn_layout.addWidget(self.btn_confirmar_entrega)
        
        # Tabla de Lotes
        self.tabla_lotes = QTableWidget()
        self.tabla_lotes.setColumnCount(LotesTab.COLUMN_COUNT)
        self.tabla_lotes.setHorizontalHeaderLabels(["ID", "Folio del Lote", "Fecha de Creación", "Usuario Creador"])
        self.tabla_lotes.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla_lotes.setSelectionMode(QTableWidget.SingleSelection)
        self.tabla_lotes.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla_lotes.setAlternatingRowColors(True)
        self.tabla_lotes.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        layout.addWidget(btn_group)
        layout.addWidget(self.tabla_lotes, 1)
        
        # Cargar datos iniciales
        self.cargar_lotes_transferencia()
        
        return widget
    
    def create_historial_lotes_sub_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        
        title_label = QLabel("HISTORIAL DE LOTES ENTREGADOS")
        title_label.setObjectName("title_label")
        layout.addWidget(title_label)
        
        btn_group = QGroupBox("Consultas y Acuses")
        btn_layout = QHBoxLayout(btn_group)
        
        self.btn_actualizar_historial_lotes = QPushButton("🔄 Actualizar Tabla")
        self.btn_ver_acuse_pdf = QPushButton("👁️ Ver Acuse (PDF)")
        self.btn_ver_acuse_pdf.setObjectName("btn_info")
        
        btn_layout.addWidget(self.btn_actualizar_historial_lotes)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_ver_acuse_pdf)
        
        self.tabla_historial_lotes = QTableWidget()
        self.tabla_historial_lotes.setColumnCount(HistorialLotesTab.COLUMN_COUNT)
        self.tabla_historial_lotes.setHorizontalHeaderLabels(["ID Lote", "Folio", "Fecha Creación", "Fecha Entrega", "Creador", "Acuse Adjunto"])
        self.tabla_historial_lotes.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla_historial_lotes.setSelectionMode(QTableWidget.SingleSelection)
        self.tabla_historial_lotes.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla_historial_lotes.setAlternatingRowColors(True)
        self.tabla_historial_lotes.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        layout.addWidget(btn_group)
        layout.addWidget(self.tabla_historial_lotes, 1)
        
        self.cargar_historial_lotes()
        
        return widget
    
    def create_concentracion_sub_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        
        title_label = QLabel("ARCHIVO DE CONCENTRACIÓN - EXPEDIENTES EN CONCENTRACIÓN")
        title_label.setObjectName("title_label")
        layout.addWidget(title_label)
        
        search_group = self.crear_filtros_concentracion()
        
        btn_group = QGroupBox("Acciones")
        btn_layout = QHBoxLayout(btn_group)
        self.btn_exportar_concentracion = QPushButton("Exportar a Excel")
        self.btn_exportar_concentracion.setObjectName("btn_exportar")
        self.btn_proponer_valoracion = QPushButton("📦 Proponer para Valoración")
        self.btn_proponer_valoracion.setObjectName("btn_accion_naranja")
        self.btn_proponer_valoracion.clicked.connect(self.crear_lote_valoracion_seleccionados)
        btn_layout.addWidget(self.btn_exportar_concentracion)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_proponer_valoracion)

        table_container = QFrame()
        table_container.setFrameShape(QFrame.StyledPanel)
        table_container.setObjectName("table_container")
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0,0,0,0)

        self.tabla_concentracion = QTableWidget()
        self.configurar_tabla_concentracion()
        table_layout.addWidget(self.tabla_concentracion)
        
        layout.addWidget(search_group)
        layout.addWidget(btn_group)
        layout.addWidget(table_container, 1)
        return widget
    
    def create_filtros_vencidos(self):
        """Crea y devuelve el QGroupBox con todos los filtros para la sub-pestaña de Vencidos."""
        search_group_vencidos = QGroupBox("Filtros de Búsqueda")
                
        form_layout_vencidos = QFormLayout(search_group_vencidos)
        form_layout_vencidos.setContentsMargins(5, 5, 5, 5)
        form_layout_vencidos.setSpacing(10)
                
        busqueda_group_vencidos = QGroupBox("Búsqueda")
        busqueda_group_vencidos.setProperty("filterGroup", True)
        
        row1_layout = QHBoxLayout(busqueda_group_vencidos)
        row1_layout.setContentsMargins(5, 15, 5, 5)
        row1_layout.setSpacing(10)
        
        self.texto_busqueda_vencidos = QLineEdit()
        self.texto_busqueda_vencidos.setPlaceholderText("Buscar en asunto y folio...")
        row1_layout.addWidget(self.texto_busqueda_vencidos, 1)
        
        self.btn_buscar_vencidos = QPushButton("Buscar")
       
        self.btn_limpiar_vencidos = QPushButton("Limpiar")
        self.btn_limpiar_vencidos.setObjectName("btn_limpiar")
        
        row1_layout.addWidget(self.btn_buscar_vencidos)
        row1_layout.addWidget(self.btn_limpiar_vencidos)
        
        form_layout_vencidos.addRow(busqueda_group_vencidos)
        
        row_container = QWidget()
        row_layout = QHBoxLayout(row_container)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(15)
        
        categoria_group = QGroupBox("Categoría")
        categoria_layout = QHBoxLayout(categoria_group)
        self.categoria_doc_vencidos = QComboBox()
        self.categoria_doc_vencidos.addItem("")
        self.categoria_doc_vencidos.addItems(CATEGORIAS_DOCUMENTALES[1:])
        categoria_layout.addWidget(self.categoria_doc_vencidos)
        
        fecha_group = QGroupBox("Fecha Vencimiento")
        fecha_layout = QHBoxLayout(fecha_group)
        self.fecha_vencimiento_inicio = QDateEdit(calendarPopup=True)
        self.fecha_vencimiento_inicio.setDate(QDate.currentDate().addYears(ANIOS_ATRAS_FILTRO))
        self.fecha_vencimiento_inicio.setDisplayFormat("dd-MM-yyyy")
        self.fecha_vencimiento_fin = QDateEdit(calendarPopup=True)
        self.fecha_vencimiento_fin.setDate(QDate.currentDate())
        self.fecha_vencimiento_fin.setDisplayFormat("dd-MM-yyyy")
        fecha_layout.addWidget(QLabel("Desde:"))
        fecha_layout.addWidget(self.fecha_vencimiento_inicio)
        fecha_layout.addWidget(QLabel("Hasta:"))
        fecha_layout.addWidget(self.fecha_vencimiento_fin)

        serie_group = QGroupBox("Serie")
        serie_layout = QHBoxLayout(serie_group)
        self.serie_doc_vencidos = QComboBox()
        self.serie_doc_vencidos.addItem("")
        self.serie_doc_vencidos.addItems(SERIES_DOCUMENTALES[1:])
        serie_layout.addWidget(self.serie_doc_vencidos)
        
        anio_group = QGroupBox("Año")
        anio_layout = QHBoxLayout(anio_group)
        self.anio_vencimiento_vencidos = QComboBox()
        self.anio_vencimiento_vencidos.addItem("")
        self.anio_vencimiento_vencidos.addItems([str(year) for year in range(2017, QDate.currentDate().year() + 2)])
        anio_layout.addWidget(self.anio_vencimiento_vencidos)

        row_layout.addWidget(categoria_group, 2)
        row_layout.addWidget(fecha_group, 3)
        row_layout.addWidget(serie_group, 2)
        row_layout.addWidget(anio_group, 1)
        
        form_layout_vencidos.addRow(row_container)
        
        return search_group_vencidos
    
    def crear_filtros_concentracion(self):
        """Crea y devuelve el QGroupBox con todos los filtros para la sub-pestaña de Concentración."""
        search_group = QGroupBox("Filtros de Búsqueda")
                
        form_layout = QFormLayout(search_group)
        form_layout.setContentsMargins(5, 5, 5, 5)
        form_layout.setSpacing(10)
        
        busqueda_group = QGroupBox("Búsqueda")
        busqueda_group.setProperty("filterGroup", True)
        
        row1_layout = QHBoxLayout(busqueda_group)
        row1_layout.setContentsMargins(5, 15, 5, 5)
        row1_layout.setSpacing(10)
        
        self.texto_busqueda_concentracion = QLineEdit()
        self.texto_busqueda_concentracion.setPlaceholderText("Buscar en asunto, folio o ubicación...")
        row1_layout.addWidget(self.texto_busqueda_concentracion, 1)
        
        self.btn_buscar_concentracion = QPushButton("Buscar")
        
        self.btn_limpiar_concentracion = QPushButton("Limpiar")
        self.btn_limpiar_concentracion.setObjectName("btn_limpiar")
        
        row1_layout.addWidget(self.btn_buscar_concentracion)
        row1_layout.addWidget(self.btn_limpiar_concentracion)
        
        form_layout.addRow(busqueda_group)
        
        row_container = QWidget()
        row_layout = QHBoxLayout(row_container)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(15)
        
        categoria_group = QGroupBox("Categoría")
        categoria_layout = QHBoxLayout(categoria_group)
        self.categoria_doc_concentracion = QComboBox()
        self.categoria_doc_concentracion.addItem("")
        self.categoria_doc_concentracion.addItems(CATEGORIAS_DOCUMENTALES[1:])
        categoria_layout.addWidget(self.categoria_doc_concentracion)
        
        fecha_group = QGroupBox("Fecha Ingreso")
        fecha_layout = QHBoxLayout(fecha_group)
        self.fecha_ingreso_inicio = QDateEdit(calendarPopup=True)
        self.fecha_ingreso_inicio.setDate(QDate.currentDate().addYears(ANIOS_ATRAS_FILTRO))
        self.fecha_ingreso_inicio.setDisplayFormat("dd-MM-yyyy")
        self.fecha_ingreso_fin = QDateEdit(calendarPopup=True)
        self.fecha_ingreso_fin.setDate(QDate.currentDate())
        self.fecha_ingreso_fin.setDisplayFormat("dd-MM-yyyy")
        fecha_layout.addWidget(QLabel("Desde:"))
        fecha_layout.addWidget(self.fecha_ingreso_inicio)
        fecha_layout.addWidget(QLabel("Hasta:"))
        fecha_layout.addWidget(self.fecha_ingreso_fin)

        serie_group = QGroupBox("Serie")
        serie_layout = QHBoxLayout(serie_group)
        self.serie_doc_concentracion = QComboBox()
        self.serie_doc_concentracion.addItem("")
        self.serie_doc_concentracion.addItems(SERIES_DOCUMENTALES[1:])
        serie_layout.addWidget(self.serie_doc_concentracion)
        
        anio_group = QGroupBox("Año Apertura")
        anio_layout = QHBoxLayout(anio_group)
        self.anio_apertura_concentracion = QComboBox()
        self.anio_apertura_concentracion.addItem("")
        self.anio_apertura_concentracion.addItems([str(year) for year in range(2017, QDate.currentDate().year() + 2)])
        anio_layout.addWidget(self.anio_apertura_concentracion)

        row_layout.addWidget(categoria_group, 2)
        row_layout.addWidget(fecha_group, 3)
        row_layout.addWidget(serie_group, 2)
        row_layout.addWidget(anio_group, 1)
        
        form_layout.addRow(row_container)
        
        return search_group
    
    def cargar_expedientes_vencidos(self):
        """Pide al servicio los expedientes vencidos, aplicando los filtros, y los carga en la tabla."""
        try:
            filtros = {
                'texto_busqueda': self.texto_busqueda_vencidos.text().strip(),
                'categoria': self.categoria_doc_vencidos.currentText(),
                'serie': self.serie_doc_vencidos.currentText(),
                'anio': self.anio_vencimiento_vencidos.currentText(),
                'fecha_inicio': self.fecha_vencimiento_inicio.date().toString("yyyy-MM-dd"),
                'fecha_fin': self.fecha_vencimiento_fin.date().toString("yyyy-MM-dd")
            }
            filtros = {k: v for k, v in filtros.items() if v and v != ""}

            self.statusBar().showMessage("Cargando expedientes vencidos...")
            datos = self.expediente_service.obtener_expedientes_para_archivar(filtros)
            self.tabla_vencidos.clearSelection()
            self.poblar_tabla_vencidos(datos)
            
            mensaje_status = f"Se encontraron {len(datos)} expedientes pendientes de archivar."
            self.statusBar().showMessage(mensaje_status)

            if self.sender() == self.btn_actualizar_vencidos:
                mostrar_mensaje(self,"Actualización Completa", mensaje_status)

        except Exception as e:
            logging.error("No se pudieron cargar los expedientes vencidos: %s", e, exc_info=True)
            mostrar_mensaje(self,"Error", f"No se pudieron cargar los expedientes vencidos:\n{e}", QMessageBox.Critical)

    def buscar_expedientes_en_concentracion(self):
        """Pide al servicio que busque en el archivo de concentración aplicando todos los filtros."""
        try:
            filtros = {
                'texto_busqueda': self.texto_busqueda_concentracion.text().strip(),
                'categoria': self.categoria_doc_concentracion.currentText(),
                'serie': self.serie_doc_concentracion.currentText(),
                'anio': self.anio_apertura_concentracion.currentText(),
                'fecha_inicio': self.fecha_ingreso_inicio.date().toString("yyyy-MM-dd"),
                'fecha_fin': self.fecha_ingreso_fin.date().toString("yyyy-MM-dd")
            }
            filtros = {k: v for k, v in filtros.items() if v and v != ""}
            
            self.statusBar().showMessage("Buscando en archivo de concentración...")
            
            datos = self.expediente_service.buscar_en_concentracion(filtros)
            
            self.poblar_tabla_concentracion(datos)
            
            self.statusBar().showMessage(f"Se encontraron {len(datos)} resultados.")
        except Exception as e:
            logging.error("No se pudo realizar la búsqueda: %s", e, exc_info=True)
            mostrar_mensaje(self,"Error", f"No se pudo realizar la búsqueda: {e}", QMessageBox.Critical)

    def poblar_tabla_vencidos(self, data: list):
        config = [
            {'key': 'id', 'type': 'numeric'},
            {'key': 'tipo_documento', 'type': 'text'},
            {'key': 'categoria_documental', 'type': 'text'},
            {'key': 'folio', 'type': 'text'},
            {'key': 'fecha', 'type': 'date'},
            {'key': 'asunto', 'type': 'text'},
            {'key': 'serie_documental', 'type': 'text'},
            {'key': 'carpeta', 'type': 'text'},
            {'key': 'paginas', 'type': 'numeric'},
            {'key': 'documento_respaldo', 'type': 'text'},
            {'key': 'clasificacion', 'type': 'text'},
            {'key': 'apertura', 'type': 'numeric'},
            {'key': 'cierre', 'type': 'numeric'},
            {'key': 'vencimiento', 'type': 'date'},
            {'key': 'dias_vencido', 'type': 'numeric'},
        ]
        self._poblar_tabla(self.tabla_vencidos, data, config, columna_acciones=VencidosTab.ACCIONES)
        self.tabla_vencidos.sortByColumn(0, Qt.AscendingOrder)

    def poblar_tabla_concentracion(self, data: list):
        """Puebla la tabla de expedientes en concentración usando la función genérica."""
        config = [
            {'key': 'id', 'type': 'numeric'},
            {'key': 'tipo_documento', 'type': 'text'},
            {'key': 'categoria_documental', 'type': 'text'},
            {'key': 'folio', 'type': 'text'},
            {'key': 'fecha', 'type': 'date'},
            {'key': 'asunto', 'type': 'text'},
            {'key': 'serie_documental', 'type': 'text'},
            {'key': 'carpeta', 'type': 'text'},
            {'key': 'paginas', 'type': 'numeric'},
            {'key': 'documento_respaldo', 'type': 'text'},
            {'key': 'clasificacion', 'type': 'text'},
            {'key': 'apertura', 'type': 'numeric'},
            {'key': 'cierre', 'type': 'numeric'},
            {'key': 'vencimiento', 'type': 'date'},
            {'key': 'fecha_ingreso', 'type': 'date'},
            {'key': 'lote_origen', 'type': 'text'},
            {'key': 'ubicacion_area', 'type': 'text'},
            {'key': 'ubicacion_pasillo', 'type': 'text'},
            {'key': 'ubicacion_anaquel', 'type': 'text'},
            {'key': 'ubicacion_charola', 'type': 'text'},
            {'key': 'dias_para_baja', 'type': 'numeric'},
        ]
        
        self._poblar_tabla(self.tabla_concentracion, data, config, 
                           columna_acciones=ConcentracionTab.ACCIONES, 
                           callback_estilo=self._aplicar_estilos_concentracion)
        
        self.tabla_concentracion.sortByColumn(0, Qt.AscendingOrder)
    
    def _aplicar_estilos_concentracion(self, item, clave, valor, fila_datos):
        """Centraliza las reglas de color para la tabla de Concentración."""
        expediente_prestado = fila_datos.get('esta_prestado', 0) == 1
        
        if clave == 'asunto' and expediente_prestado:
            item.setText(f"🛑 [PRESTADO] {valor}")
            item.setForeground(QColor("#c0392b")) # Rojo
            font = item.font()
            font.setBold(True)
            item.setFont(font)

        elif clave == 'dias_para_baja' and isinstance(valor, int):
            if valor > 0:
                item.setText(f"Faltan {valor} día{'s' if valor != 1 else ''}")
                item.setForeground(QColor("#d35400")) # Naranja
            else:
                item.setText("Listo para baja")
                item.setForeground(QColor("green"))
    
    def configurar_tabla_vencidos(self):
        """Configura las propiedades visuales y de comportamiento de la tabla de vencidos."""
        self.tabla_vencidos.setColumnCount(VencidosTab.COLUMN_COUNT)
        self.tabla_vencidos.setHorizontalHeaderLabels([
            "ID", "Tipo", "Categoría", "Folio", "Fecha", "Asunto", "Serie", 
            "Carpeta", "Páginas", "Documento Respaldo", "Clasificación", "Apertura", 
            "Cierre", "Vencimiento", "Días Vencido", "Acciones"
        ])
        self.tabla_vencidos.verticalHeader().setVisible(False)
        self.tabla_vencidos.setAlternatingRowColors(True)
        self.tabla_vencidos.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla_vencidos.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla_vencidos.setSelectionMode(QTableWidget.ExtendedSelection)
        self.tabla_vencidos.setWordWrap(True)
        
        self.tabla_vencidos.verticalHeader().setDefaultSectionSize(60)
        self.tabla_vencidos.setColumnHidden(VencidosTab.DOCUMENTO_RESPALDO, True)
        
        header = self.tabla_vencidos.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(VencidosTab.ASUNTO, QHeaderView.Stretch)
        header.setSectionResizeMode(VencidosTab.DOCUMENTO_RESPALDO, QHeaderView.Stretch)

    def configurar_tabla_concentracion(self):
        """Configura las propiedades de la tabla de expedientes en concentración."""
        self.tabla_concentracion.setColumnCount(ConcentracionTab.COLUMN_COUNT)
        self.tabla_concentracion.setHorizontalHeaderLabels([
            "ID", "Tipo", "Categoría", "Folio", "Fecha", "Asunto", "Serie", 
            "Carpeta", "Páginas", "Documento Respaldo", "Clasificación", "Apertura", 
            "Cierre", "Vencimiento", "Fecha Ingreso", "Caja",
            "Área", "Pasillo", "Anaquel", "Charola",
            "Días para Baja", "Acciones"
        ])
        self.tabla_concentracion.verticalHeader().setVisible(False)
        self.tabla_concentracion.setAlternatingRowColors(True)
        self.tabla_concentracion.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla_concentracion.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla_concentracion.setSelectionMode(QTableWidget.ExtendedSelection)
        self.tabla_concentracion.setWordWrap(True)
        
        self.tabla_concentracion.verticalHeader().setDefaultSectionSize(60)
        self.tabla_concentracion.setColumnHidden(ConcentracionTab.DOCUMENTO_RESPALDO, True)
        
        header = self.tabla_concentracion.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(ConcentracionTab.ASUNTO, QHeaderView.Interactive)
        self.tabla_concentracion.setColumnWidth(ConcentracionTab.ASUNTO, 92)
        
    def limpiar_busqueda_concentracion(self):
        self.texto_busqueda_concentracion.clear()
        self.categoria_doc_concentracion.setCurrentIndex(0)
        self.serie_doc_concentracion.setCurrentIndex(0)
        self.anio_apertura_concentracion.setCurrentIndex(0)
        self.fecha_ingreso_inicio.setDate(QDate.currentDate().addYears(ANIOS_ATRAS_FILTRO))
        self.fecha_ingreso_fin.setDate(QDate.currentDate())
        self.buscar_expedientes_en_concentracion()
        
    def limpiar_filtros_vencidos(self):
        """Limpia todos los filtros de la sub-pestaña de vencidos y recarga la tabla."""
        self.texto_busqueda_vencidos.clear()
        self.categoria_doc_vencidos.setCurrentIndex(0)
        self.serie_doc_vencidos.setCurrentIndex(0)
        self.anio_vencimiento_vencidos.setCurrentIndex(0)
        self.fecha_vencimiento_inicio.setDate(QDate.currentDate().addYears(ANIOS_ATRAS_FILTRO))
        self.fecha_vencimiento_fin.setDate(QDate.currentDate())
        self.cargar_expedientes_vencidos()
        
    def restaurar_de_concentracion(self, expediente_id: int):
        """
        Restaura un expediente del archivo de concentración.
        """
        reply = QMessageBox.question(self, 'Confirmar Restauración',
                                     f"¿Está seguro de que desea restaurar el expediente ID {expediente_id} a trámite?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            success, message = self.expediente_service.restaurar_expediente(expediente_id)
            if success:
                mostrar_mensaje(self,"Éxito", message, QMessageBox.Information)
                self.cargar_expedientes_vencidos()
                self.buscar_expedientes_en_concentracion()
                self.cargar_expedientes()
            else:
                mostrar_mensaje(self,"Error", message, QMessageBox.Warning)
        
    def exportar_vencidos_a_excel(self):
        """Exporta la lista actual de expedientes vencidos a Excel."""
        filtros = {
            'texto_busqueda': self.texto_busqueda_vencidos.text().strip(),
            'categoria': self.categoria_doc_vencidos.currentText(),
            'serie': self.serie_doc_vencidos.currentText(),
            'anio': self.anio_vencimiento_vencidos.currentText(),
            'fecha_inicio': self.fecha_vencimiento_inicio.date().toString("yyyy-MM-dd"),
            'fecha_fin': self.fecha_vencimiento_fin.date().toString("yyyy-MM-dd")
        }
        filtros = {k: v for k, v in filtros.items() if v and v != ""}
        
        datos_para_exportar = self.expediente_service.obtener_expedientes_para_archivar(filtros)
        
        if not datos_para_exportar:
            mostrar_mensaje(self,"Exportar", "No hay datos para exportar con los filtros actuales.", QMessageBox.Warning)
            return
        
        default_filename = f"reporte_vencidos_{datetime.now().strftime('%Y%m%d')}.xlsx"
        filepath, _ = QFileDialog.getSaveFileName(self, "Guardar Reporte como...", default_filename, "Archivos de Excel (*.xlsx)")
        if not filepath:
            return
    
        self.statusBar().showMessage("Exportando a Excel, por favor espere...")
        self.btn_exportar_vencidos.setEnabled(False)
        self.expediente_service.registrar_evento_externo("EXPORTAR_VENCIDOS", f"Se exportó a Excel la bandeja de {len(datos_para_exportar)} expedientes vencidos.")
        
        self._ejecutar_en_hilo(
            self.excel_service.create_report,
            self.on_exportacion_finalizada, # Reutilizamos el mismo callback
            datos_para_exportar,
            filepath
        )

    def exportar_concentracion_a_excel(self):
        """Exporta la lista actual de expedientes en concentración a Excel."""
        filtros = {
            'texto_busqueda': self.texto_busqueda_concentracion.text().strip(),
            'categoria': self.categoria_doc_concentracion.currentText(),
            'serie': self.serie_doc_concentracion.currentText(),
            'anio': self.anio_apertura_concentracion.currentText(),
            'fecha_inicio': self.fecha_ingreso_inicio.date().toString("yyyy-MM-dd"),
            'fecha_fin': self.fecha_ingreso_fin.date().toString("yyyy-MM-dd")
        }
        filtros = {k: v for k, v in filtros.items() if v and v != ""}
        
        datos_para_exportar = self.expediente_service.buscar_en_concentracion(filtros)

        if not datos_para_exportar:
            mostrar_mensaje(self,"Exportar", "No hay datos para exportar con los filtros actuales.", QMessageBox.Warning)
            return
        
        default_filename = f"reporte_concentracion_{datetime.now().strftime('%Y%m%d')}.xlsx"
        filepath, _ = QFileDialog.getSaveFileName(self, "Guardar Reporte como...", default_filename, "Archivos de Excel (*.xlsx)")
        if not filepath:
            return
    
        self.statusBar().showMessage("Exportando a Excel, por favor espere...")
        self.btn_exportar_concentracion.setEnabled(False)
        self.expediente_service.registrar_evento_externo("EXPORTAR_BODEGA", f"Se exportó a Excel un inventario filtrado con {len(datos_para_exportar)} registros físicos de la Bodega (Concentración).")
        
        self._ejecutar_en_hilo(
            self.excel_service.create_report,
            self.on_exportacion_finalizada, # Reutilizamos el mismo callback
            datos_para_exportar,
            filepath
        )

    def on_exportacion_finalizada(self, resultado):
        """Slot para manejar el final de CUALQUIER exportación a Excel."""
        success, message = resultado
        if success:
            mostrar_mensaje(self, "Exportación Completa", message, QMessageBox.Information)
        else:
            mostrar_mensaje(self, "Error de Exportación", message, QMessageBox.Critical)
            
        self.btn_exportar_excel.setEnabled(True)
        self.btn_exportar_vencidos.setEnabled(True)
        self.btn_exportar_concentracion.setEnabled(True)
        self.statusBar().showMessage("Listo")
    
    def create_cuadro_clasificacion_tab(self):
        """Crea la pestaña del Árbol Jerárquico Institucional (CGCA)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)
        
        title_label = QLabel("CUADRO GENERAL DE CLASIFICACIÓN ARCHIVÍSTICA (CGCA)")
        title_label.setObjectName("title_label")
        layout.addWidget(title_label)
        
        # Barra superior con botones de control
        top_layout = QHBoxLayout()
        
        btn_actualizar = QPushButton("🔄 Actualizar Árbol")
        # Le asignamos el color azul oscuro (btn_info)
        btn_actualizar.setObjectName("btn_info")
        btn_actualizar.clicked.connect(self.cargar_arbol_clasificacion)
        
        btn_expandir = QPushButton("📂 Expandir Todo")
        # Le asignamos el color gris (btn_secondary)
        btn_expandir.setObjectName("btn_secondary")
        btn_expandir.clicked.connect(lambda: self.arbol_clasificacion.expandAll())
        
        btn_contraer = QPushButton("📁 Contraer Todo")
        # Le asignamos el color gris (btn_secondary)
        btn_contraer.setObjectName("btn_secondary")
        btn_contraer.clicked.connect(lambda: self.arbol_clasificacion.collapseAll())
        
        lbl_info = QLabel("<i>Haga doble clic en un Expediente para abrir su ficha completa.</i>")
        lbl_info.setStyleSheet("color: gray;")
        top_layout.addWidget(btn_actualizar)
        top_layout.addWidget(btn_expandir)
        top_layout.addWidget(btn_contraer)
        top_layout.addStretch()
        top_layout.addWidget(lbl_info)
        layout.addLayout(top_layout)
        
        # Construcción del Widget del Árbol
        self.arbol_clasificacion = QTreeWidget()
        self.arbol_clasificacion.setHeaderLabels([
            "Estructura Documental", 
            "Código / Clasificación", 
            "Condición", 
            "Estatus Archivístico",
            "Fecha Vencimiento", 
        ])
        self.arbol_clasificacion.setAlternatingRowColors(True)
        self.arbol_clasificacion.setAnimated(True)
        
        # Ajuste de las columnas
        header = self.arbol_clasificacion.header()
        header.setStretchLastSection(False) # <--- Muy importante agregar esta línea aquí
        header.setSectionResizeMode(0, QHeaderView.Stretch)           # Columna 0 (Asunto) ocupa todo el espacio
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Columna 1 (Código) se ajusta al texto
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Columna 2 (Condición) se ajusta al texto
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Columna 3 (Estatus) se ajusta al texto
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Columna 4 (Fecha) se ajusta al texto
        
        # Evento: Al hacer doble clic en una hoja (Expediente), lo abrimos!
        self.arbol_clasificacion.itemDoubleClicked.connect(self.on_nodo_arbol_doble_clic)
        
        layout.addWidget(self.arbol_clasificacion, 1)
        
        # Disparo inicial al arrancar el programa
        self.cargar_arbol_clasificacion()
        
        return widget
    
    def cargar_arbol_clasificacion(self):
        """Manda a armar el diccionario en un hilo y lo pinta cuando regresa."""
        if not hasattr(self, 'arbol_clasificacion'): return
        
        self.statusBar().showMessage("Armando Cuadro General de Clasificación, por favor espere...")
        self.arbol_clasificacion.clear()
        
        self._ejecutar_en_hilo(
            self.expediente_service.obtener_arbol_clasificacion,
            self._on_arbol_listo
        )

    def _on_arbol_listo(self, resultado):
        """Recibe el diccionario procesado (resultado_tarea.resultado) y pinta los Nodos."""
        success = False
        diccionario_arbol = None
        
        # Envoltorio del callback del GestorTareas (por si retorna Tuple)
        if isinstance(resultado, tuple) and len(resultado) == 2:
            success, diccionario_arbol = resultado
        else:
            diccionario_arbol = resultado # Solo retornó el dict
        
        if not diccionario_arbol:
            self.statusBar().showMessage("Error al cargar el Árbol de Clasificación.")
            return
            
        # Nivel 0: El FONDO (Raíz Principal Mágica)
        nodo_fondo = QTreeWidgetItem(self.arbol_clasificacion, ["🏛️ FONDO: Comisión Nacional del Agua", "", "", "", ""])
        font_fondo = nodo_fondo.font(0); font_fondo.setBold(True); font_fondo.setPointSize(11); nodo_fondo.setFont(0, font_fondo)
        
        total_expedientes_fondo = 0

        # Nivel 1: Las SECCIONES
        for nombre_seccion, series in sorted(diccionario_arbol.items()):
            nodo_seccion = QTreeWidgetItem(nodo_fondo, [f"📁 SECCIÓN: {nombre_seccion}", "", "", "", ""])
            font_sec = nodo_seccion.font(0); font_sec.setBold(True); font_sec.setPointSize(10); nodo_seccion.setFont(0, font_sec)
            nodo_seccion.setForeground(0, QColor("#2980b9")) # Color Azul Gobierno
            
            exp_en_seccion = 0

            # Nivel 2: Las SERIES DOCUMENTALES
            for cod_serie, contenido in sorted(series.items()):
                datos_serie = contenido["datos_serie"]
                expedientes = contenido["expedientes"]
                
                num_exp = len(expedientes)
                exp_en_seccion += num_exp
                
                texto_serie = f"📂 SERIE: {datos_serie.get('nombre_serie', '')} ({num_exp} expedientes)"
                # Aquí ponemos el Código de la Serie en la Columna 1
                nodo_serie = QTreeWidgetItem(nodo_seccion, [texto_serie, cod_serie, "", "", ""])
                font_ser = nodo_serie.font(0); font_ser.setBold(True); nodo_serie.setFont(0, font_ser)
                
                # Nivel 3: Los EXPEDIENTES (Hojas finales)
                for exp in sorted(expedientes, key=lambda x: x.get('fecha', '')):
                    asunto_corto = (exp['asunto'][:210] + "...") if exp['asunto'] and len(exp['asunto']) > 210 else exp['asunto']
                    clasificacion = exp.get('clasificacion', 'S/C')
                    vencimiento_raw = exp.get('vencimiento', '-')
                    if vencimiento_raw and vencimiento_raw != "-":
                        # Separamos por el guion y le damos la vuelta
                        partes = str(vencimiento_raw).split('-')
                        if len(partes) == 3:
                            vencimiento = f"{partes[2]}-{partes[1]}-{partes[0]}"
                        else:
                            vencimiento = vencimiento_raw # Por si viene con otro formato raro
                    else:
                        vencimiento = "-"
                    
                    # Columna: Condición
                    condicion = "Cerrado 🔒" if exp.get('cierre') else "Abierto  📝"
                    
                    # Columna: Estatus Archivístico (Por defecto, como le pedimos "Todos" al repositorio, 
                    # si estuvieran en concentración, el flag interno lo diría. 
                    # Dado que estos son los activos de la tabla principal, están en Trámite).
                    estatus_archivistico = "En Trámite"
                    if exp.get('esta_prestado') == 1: 
                        estatus_archivistico = "Prestado 🛑"
                    
                    nodo_exp = QTreeWidgetItem(nodo_serie, [
                        f"📄 {asunto_corto}", 
                        clasificacion, 
                        condicion, 
                        estatus_archivistico,
                        vencimiento
                    ])
                    
                    # Escondemos el ID en la Columna 0 para usarlo al darle doble clic
                    nodo_exp.setData(0, Qt.UserRole, exp.get('id'))
                    
                    if exp['asunto']:
                        texto_globo = "\n".join(textwrap.wrap(exp['asunto'].strip(), width=60))
                        nodo_exp.setToolTip(0, texto_globo)
                    
                    # Pintar de rojo si está prestado físicamente
                    if exp.get('esta_prestado') == 1:
                        for col in range(5):
                            nodo_exp.setForeground(col, QColor("red"))

            # Agregamos un conteo a la Sección en la columna 1
            if exp_en_seccion > 0:
                nodo_seccion.setText(1, f"[{exp_en_seccion} registros]")
                total_expedientes_fondo += exp_en_seccion

        # Expandimos solo la raíz principal y su primer hijo (Secciones) por comodidad visual
        self.arbol_clasificacion.expandItem(nodo_fondo)
        for i in range(nodo_fondo.childCount()):
            self.arbol_clasificacion.expandItem(nodo_fondo.child(i))
            
        self.statusBar().showMessage(f"Cuadro General cargado exitosamente. ({total_expedientes_fondo} registros vivos)")

    def on_nodo_arbol_doble_clic(self, item, column):
        """Si es un Expediente (hoja final que tiene un ID escondido), lo abrimos!"""
        exp_id = item.data(0, Qt.UserRole)
        
        if exp_id: # Es un expediente
            # Reciclamos tu ventana espectacular que diseñaste para ver la ficha completa
            self.ver_completo(exp_id)
        
    def create_consulta_series_tab(self):
        """Crea la pestaña de Consulta de Series con su diseño y filtros originales."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)
        
        title_label = QLabel("SERIES DOCUMENTALES")
        title_label.setObjectName("title_label")
        layout.addWidget(title_label)

        search_group = QGroupBox("Filtros de Búsqueda de Series")
        
        filters_layout = QHBoxLayout(search_group)

        def create_filter_group(title, widget, stretch=1):
            group = QGroupBox(title)
            group.setProperty("filterGroup", True)
            
            lyt = QHBoxLayout(group)
            lyt.setContentsMargins(4, 4, 3, 4)
            lyt.addWidget(widget)
            filters_layout.addWidget(group, stretch)

        self.filtro_serie_codigo = QComboBox()
        self.filtro_serie_codigo.addItem("Todas")
        try:
            series = self.expediente_service.obtener_series_documentales()
            for serie in series:
                self.filtro_serie_codigo.addItem(serie['codigo_serie'])
        except Exception as e:
            logging.error("Error al cargar códigos de serie: %s", e, exc_info=True)
            print(f"Error al cargar códigos de serie: {e}")

        create_filter_group("Código", self.filtro_serie_codigo, 1)
        
        self.filtro_serie_nombre = QLineEdit(placeholderText="Buscar por Nombre...")
        create_filter_group("Nombre de la Serie", self.filtro_serie_nombre, 3)

        self.filtro_serie_area = QLineEdit(placeholderText="Buscar por Área Administrativa...")
        create_filter_group("Área Administrativa", self.filtro_serie_area, 3)

        self.btn_buscar_series = QPushButton("Buscar")
        self.btn_limpiar_series = QPushButton("Limpiar")
        self.btn_limpiar_series.setObjectName("btn_limpiar")
        filters_layout.addWidget(self.btn_buscar_series)
        filters_layout.addWidget(self.btn_limpiar_series)
        
        table_container = QFrame()
        table_container.setFrameShape(QFrame.StyledPanel)
        table_container.setObjectName("table_container")
        
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        
        toolbar_container = QWidget()
        toolbar_layout = QHBoxLayout(toolbar_container)
        toolbar_layout.setContentsMargins(10, 5, 10, 5)

        self.btn_ver_detalle_pdf = QPushButton("Ver Detalle PDF")
        self.btn_ver_detalle_pdf.setObjectName("btn_pdf")
        
        toolbar_layout.addWidget(self.btn_ver_detalle_pdf)
        toolbar_layout.addStretch() # Empuja el botón a la izquierda
        
        self.tabla_series = QTableWidget()
        self.configurar_tabla_series()
        table_layout.addWidget(toolbar_container)
        table_layout.addWidget(self.tabla_series)
        
        layout.addWidget(search_group)
        layout.addWidget(table_container, 1)
        return widget
    
    def configurar_tabla_series(self):
        """Configura las propiedades visuales y de comportamiento de la tabla de series."""
        self.tabla_series.setColumnCount(SeriesTab.COLUMN_COUNT)
        self.tabla_series.setHorizontalHeaderLabels([
            "Código", "Nombre de la Serie", "Área Administrativa", "Adm.", "Legal", "Fiscal", 
            "Trámite", "Concent.", "Total", "Pública", "Reserv.", "Confid.", 
            "Original", "Copia"
        ])
        
        self.tabla_series.verticalHeader().setVisible(False)
        self.tabla_series.setAlternatingRowColors(True)

        self.tabla_series.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla_series.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla_series.setSelectionMode(QTableWidget.SingleSelection)

        header = self.tabla_series.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)

        header.setSectionResizeMode(SeriesTab.AREA_ADMINISTRATIVA, QHeaderView.Stretch)
        
    def poblar_tabla_series(self, data: list):
        """Puebla la tabla de series documentales usando la función genérica."""
        config = [
            {'key': 'codigo_serie', 'type': 'text'},
            {'key': 'nombre_serie', 'type': 'text'},
            {'key': 'area_administrativa', 'type': 'text'},
            {'key': 'administrativo', 'type': 'text'},
            {'key': 'legal', 'type': 'text'},
            {'key': 'fiscal', 'type': 'text'},
            {'key': 'tramite', 'type': 'numeric'},
            {'key': 'concentracion', 'type': 'numeric'},
            {'key': 'total', 'type': 'numeric'},
            {'key': 'publica', 'type': 'text'},
            {'key': 'reservada', 'type': 'text'},
            {'key': 'confidencial', 'type': 'text'},
            {'key': 'original', 'type': 'text'},
            {'key': 'copia', 'type': 'text'},
        ]
        
        self._poblar_tabla(self.tabla_series, data, config)
    
    def buscar_series(self):
        """Recoge los filtros, pide los datos y puebla la tabla de series."""
        try:
            filtros = {
                'codigo': self.filtro_serie_codigo.currentText(),
                'nombre': self.filtro_serie_nombre.text().strip(),
                'area': self.filtro_serie_area.text().strip()
            }
            self.statusBar().showMessage("Buscando series documentales...")
            datos = self.expediente_service.buscar_series_documentales(filtros)
            self.poblar_tabla_series(datos)
            self.statusBar().showMessage(f"Se encontraron {len(datos)} series documentales.")
        except Exception as e:
            logging.error("Ocurrió un error al buscar series: %s", e, exc_info=True)
            mostrar_mensaje(self,"Error", f"Ocurrió un error al buscar series: {e}", QMessageBox.Critical)
    
    def limpiar_busqueda_series(self):
        """Limpia todos los filtros de la pestaña de series y recarga los datos."""
        self.filtro_serie_nombre.clear()
        self.filtro_serie_area.clear()
        self.filtro_serie_codigo.blockSignals(True) # Bloquear señales para evitar bucles
        self.filtro_serie_codigo.clear()
        self.filtro_serie_codigo.addItem("Todas")
        try:
            series = self.expediente_service.obtener_series_documentales()
            for serie in series:
                self.filtro_serie_codigo.addItem(serie['codigo_serie'])
        except Exception as e:
            logging.error("Error al recargar códigos de serie: %s", e, exc_info=True)
            print(f"Error al recargar códigos de serie: {e}")
        self.filtro_serie_codigo.blockSignals(False) # Restaurar señales
        self.buscar_series()
        
    def abrir_detalle_pdf_serie(self):
        """
        Abre el archivo PDF correspondiente a la serie documental seleccionada
        en un diálogo de visor integrado.
        """
        selected_rows = self.tabla_series.selectionModel().selectedRows()
        if not selected_rows:
            mostrar_mensaje(self,
                            "Sin Selección",
                            "Por favor, seleccione una serie de la tabla para ver su detalle.",
                            QMessageBox.Information)
            return
    
        selected_row_index = selected_rows[0].row()
        item_codigo = self.tabla_series.item(selected_row_index, 0)
        if not item_codigo:
            # Esto es un caso raro, pero es bueno manejarlo por seguridad
            return
            
        codigo_serie = item_codigo.text()
        
        self.statusBar().showMessage(f"Buscando el PDF para la serie {codigo_serie}...")
        success, result_path = self.expediente_service.obtener_ruta_pdf_serie(codigo_serie)
        
        if success:
            self.statusBar().showMessage(f"Abriendo visor para: {result_path}")
            dialog = PdfViewerDialog(result_path, self)
            dialog.exec_()
            self.statusBar().showMessage("Listo")
        else:
            mostrar_mensaje(self, "Archivo no Encontrado", result_path, QMessageBox.Warning)
            self.statusBar().showMessage("Archivo no encontrado")
            
    def _buscar_fila_por_id(self, tabla: QTableWidget, id_a_buscar: int, columna_id: int) -> int:
        """Busca un ID en una columna específica de una tabla y devuelve el índice de la fila."""
        for fila in range(tabla.rowCount()):
            item = tabla.item(fila, columna_id)
            if item and item.text().isdigit() and int(item.text()) == id_a_buscar:
                return fila
        return -1 # No encontrado
    
    def _refrescar_y_mantener_foco(self, tabla_a_enfocar: QTableWidget, id_foco: int = None, fila_foco: int = None):
        """
        Recarga los datos, selecciona la fila y MANTIENE la posición visual SIN PARPADEOS.
        """
        scroll_horizontal_previo = tabla_a_enfocar.horizontalScrollBar().value()
        scroll_vertical_previo = tabla_a_enfocar.verticalScrollBar().value() # Opcional: guardar scroll vertical también
        
        columna_id = 0
        
        if tabla_a_enfocar is self.tabla_expedientes:
            self.paginator_expedientes.forzar_recarga()
            columna_id = ExpedientesTab.ID
            
        elif tabla_a_enfocar is self.tabla_cg:
            self.cargar_control_gestion(mantener_vista_congelada=True)
            columna_id = 0
            
        elif self.busqueda_avanzada_activa and tabla_a_enfocar is self.tabla_busqueda_avanzada:
            self.paginator_busqueda.forzar_recarga()
            columna_id = BusquedaAvanzadaTab.ID_EXPEDIENTE
        fila_final = -1
        
        if id_foco is not None:
            fila_final = self._buscar_fila_por_id(tabla_a_enfocar, id_foco, columna_id)
        elif fila_foco is not None:
            if tabla_a_enfocar.rowCount() > 0:
                fila_final = min(fila_foco, tabla_a_enfocar.rowCount() - 1)

        if fila_final != -1:
            tabla_a_enfocar.selectRow(fila_final)
            tabla_a_enfocar.scrollToItem(
                tabla_a_enfocar.item(fila_final, 0),
                QAbstractItemView.ScrollHint.EnsureVisible
            )
            tabla_a_enfocar.horizontalScrollBar().setValue(scroll_horizontal_previo)
        tabla_a_enfocar.setUpdatesEnabled(True)
    
    def connect_signals(self):
        self.btn_nuevo.clicked.connect(lambda: self.abrir_dialogo_edicion())
        self.btn_buscar_expediente.clicked.connect(self.buscar_expedientes)
        self.line_edit_buscar_expediente.returnPressed.connect(self.buscar_expedientes)
        self.btn_limpiar_busqueda.clicked.connect(self.limpiar_busqueda)
        self.combo_por_pagina.currentTextChanged.connect(self.cambiar_registros_por_pagina)
        
        self.btn_siguiente.clicked.connect(self.paginator_expedientes.siguiente)
        self.btn_anterior.clicked.connect(self.paginator_expedientes.anterior)
        self.btn_primera_pagina.clicked.connect(self.paginator_expedientes.primera)
        self.btn_ultima_pagina.clicked.connect(self.paginator_expedientes.ultima)
        
        self.paginator_expedientes.pagina_cambiada.connect(self.cargar_expedientes)

        self.accion_crear_backup.triggered.connect(self.solicitar_crear_backup)
        self.accion_restaurar_backup.triggered.connect(self.solicitar_restaurar_backup)
        
        self.btn_buscar_avanzada.clicked.connect(lambda: self.buscar_respuestas_avanzada(pagina=1, es_nueva_busqueda=True))
        self.texto_busqueda_avanzada.returnPressed.connect(lambda: self.buscar_respuestas_avanzada(pagina=1, es_nueva_busqueda=True))
        self.btn_limpiar_avanzada.clicked.connect(self.limpiar_busqueda_avanzada)
        self.combo_por_pagina_busq.currentTextChanged.connect(self.cambiar_registros_por_pagina_busq)

        self.btn_siguiente_busq.clicked.connect(self.paginator_busqueda.siguiente)
        self.btn_anterior_busq.clicked.connect(self.paginator_busqueda.anterior)
        self.btn_primera_pagina_busq.clicked.connect(self.paginator_busqueda.primera)
        self.btn_ultima_pagina_busq.clicked.connect(self.paginator_busqueda.ultima)
        
        self.paginator_busqueda.pagina_cambiada.connect(lambda page: self.buscar_respuestas_avanzada(pagina=page, es_nueva_busqueda=False))

        self.btn_primera_cg.clicked.connect(self.paginator_cg.primera)
        self.btn_anterior_cg.clicked.connect(self.paginator_cg.anterior)
        self.btn_siguiente_cg.clicked.connect(self.paginator_cg.siguiente)
        self.btn_ultima_cg.clicked.connect(self.paginator_cg.ultima)
        
        self.paginator_cg.pagina_cambiada.connect(self.cargar_control_gestion)

        self.btn_generar_reporte_filtrado.clicked.connect(self.generar_reporte_filtrado)
        self.btn_generar_inventario.clicked.connect(self.exportar_inventario_completo)
        self.btn_limpiar_filtros_reporte.clicked.connect(self.limpiar_filtros_reporte)
        self.btn_exportar_excel.clicked.connect(self.exportar_reporte_a_excel)
        
        self.btn_actualizar_vencidos.clicked.connect(self.cargar_expedientes_vencidos)
        self.btn_mover_a_concentracion.clicked.connect(self.crear_lote_desde_vencidos)
        self.btn_exportar_vencidos.clicked.connect(self.exportar_vencidos_a_excel)
        self.btn_buscar_vencidos.clicked.connect(self.cargar_expedientes_vencidos)
        self.btn_limpiar_vencidos.clicked.connect(self.limpiar_filtros_vencidos)
        self.texto_busqueda_vencidos.returnPressed.connect(self.cargar_expedientes_vencidos)
        self.btn_actualizar_lotes.clicked.connect(self.cargar_lotes_transferencia)
        self.btn_reimprimir_lote.clicked.connect(self.reimprimir_lote_seleccionado)
        self.btn_cancelar_lote.clicked.connect(self.cancelar_lote_seleccionado)
        self.btn_confirmar_entrega.clicked.connect(self.confirmar_entrega_lote_seleccionado)
        self.btn_actualizar_historial_lotes.clicked.connect(self.cargar_historial_lotes)
        self.btn_ver_acuse_pdf.clicked.connect(self.ver_acuse_lote_seleccionado)

        self.btn_buscar_concentracion.clicked.connect(self.buscar_expedientes_en_concentracion)
        self.btn_limpiar_concentracion.clicked.connect(self.limpiar_busqueda_concentracion)
        self.btn_exportar_concentracion.clicked.connect(self.exportar_concentracion_a_excel)
        
        self.btn_buscar_series.clicked.connect(self.buscar_series)
        self.btn_limpiar_series.clicked.connect(self.limpiar_busqueda_series)
        self.filtro_serie_nombre.returnPressed.connect(self.buscar_series)
        self.filtro_serie_area.returnPressed.connect(self.buscar_series)
        self.btn_ver_detalle_pdf.clicked.connect(self.abrir_detalle_pdf_serie)
        
    def enviar_correo(self, expediente_id: int):
        # 1. Obtener destinatario (Código existente)
        success, result = self.email_service.leer_contactos_excel()
        if not success:
            mostrar_mensaje(self,"Error de Contactos", result, QMessageBox.Warning)
            return
    
        dialogo_contacto = ContactoDialog(result, self)
        if dialogo_contacto.exec_() != QDialog.Accepted:
            return
    
        email_destinatario = dialogo_contacto.get_selected_email()
        if not email_destinatario:
            return
    
        # 2. Obtener datos del expediente y respuestas (Código existente)
        datos_completos = self.expediente_service.obtener_vista_completa_expediente(expediente_id)
        if not datos_completos:
            mostrar_mensaje(self,"Error", "No se pudo obtener la información del expediente.", QMessageBox.Warning)
            return
                
        expediente = datos_completos['expediente']
        respuestas = datos_completos['respuestas']
        
        # 3. --- NUEVO: PREPARAR LISTA DE DOCUMENTOS DISPONIBLES ---
        documentos_candidatos = []
        
        # A. Documento Principal del Expediente
        if expediente.get('documento_respaldo'):
            documentos_candidatos.append({
                'descripcion': "📄 Documento Principal (Expediente)",
                'folio': expediente.get('folio', 'S/F'),
                'path': expediente.get('documento_respaldo')
            })
            
        # B. Documentos de Respuestas
        for r in respuestas:
            if r.get('documento_respuesta'):
                documentos_candidatos.append({
                    'descripcion': f"↩️ Respuesta: {r.get('asunto_respuesta', 'Sin Asunto')}",
                    'folio': r.get('folio', 'S/F'),
                    'path': r.get('documento_respuesta')
                })
        
        if not documentos_candidatos:
            mostrar_mensaje(self, "Sin adjuntos", "Este expediente no tiene documentos digitales vinculados.", QMessageBox.Warning)
            return

        # 4. --- NUEVO: MOSTRAR DIÁLOGO DE SELECCIÓN ---
        dialogo_seleccion = DocumentSelectionDialog(documentos_candidatos, self)
        if dialogo_seleccion.exec_() != QDialog.Accepted:
            return # El usuario canceló
            
        # 5. Obtener solo los archivos seleccionados por el usuario
        adjuntos_finales = dialogo_seleccion.get_selected_files()
        
        # 6. Preparar asunto y cuerpo (Código existente)
        clasificacion = expediente.get('clasificacion', 'N/A')
        asunto_correo = f"Documentos del Expediente con clasificación: {clasificacion}"
        
        cuerpo_correo = f"""
Estimado/a,
    
Le envío adjuntos los documentos seleccionados relacionados con el expediente con clasificación {clasificacion}.
    
Detalles del expediente:
-Fecha: {expediente.get('fecha', '')}
-Asunto: {expediente.get('asunto', '')}
-Serie documental: {expediente.get('serie_documental', '')}
-Carpeta: {expediente.get('carpeta', '')}

Se adjuntan {len(adjuntos_finales)} archivo(s).
    
Atentamente,
Sistema de Gestión de Expedientes
    """

        # 7. Guardar variables temporales para el historial
        self._temp_folio_correo = expediente.get('folio', 'S/F')
        self._temp_id_correo = expediente.get('id', 0)
        # Guardamos cuántos se enviaron para el log (opcional)
        self._temp_cantidad_adjuntos = len(adjuntos_finales)
        
        self.statusBar().showMessage("Enviando correo, por favor espere...")
        
        # 8. Enviar en hilo (Pasamos la lista filtrada 'adjuntos_finales')
        self._ejecutar_en_hilo(
            self.email_service.enviar_correo_con_adjuntos,
            self.on_correo_finalizado,
            email_destinatario,
            asunto_correo,
            cuerpo_correo,
            adjuntos_finales
        )

    def on_correo_finalizado(self, resultado):
        success, message = resultado
        self.statusBar().clearMessage()
        
        if success:
            mostrar_mensaje(self, "Éxito", message)
            
            folio = getattr(self, '_temp_folio_correo', 'Desconocido')
            exp_id = getattr(self, '_temp_id_correo', 0)
            cantidad = getattr(self, '_temp_cantidad_adjuntos', 0)
            
            # Mensaje mejorado para el historial
            self.expediente_service.registrar_evento_externo(
                "ENVIAR_CORREO", 
                f"Se enviaron {cantidad} documentos seleccionados del expediente ID {exp_id} (Folio: {folio}) por correo."
            )
        else:
            mostrar_mensaje(self, "Error", f"No se pudo enviar el correo:\n{message}", QMessageBox.Warning)

    def create_control_gestion_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15) 
        layout.setContentsMargins(10, 10, 10, 10)
        
        lbl_titulo = QLabel("CONTROL DE GESTIÓN Y CORRESPONDENCIA")
        lbl_titulo.setObjectName("title_label")
        layout.addWidget(lbl_titulo)
        
        # --- NUEVA BARRA DE FILTROS ---
        search_group = QGroupBox("Filtros de Búsqueda")
        search_layout = QHBoxLayout(search_group)
        search_layout.setSpacing(10)
        
        # 1. Filtro Año
        self.cmb_filtro_anio = QComboBox()
        anio_actual = str(datetime.now().year)
        self.cmb_filtro_anio.addItems(["Todos", anio_actual, str(int(anio_actual)-1), str(int(anio_actual)-2)])
        self.cmb_filtro_anio.currentIndexChanged.connect(self.cargar_control_gestion)
        
        # 2. Filtro Origen
        self.cmb_filtro_origen = QComboBox()
        self.cmb_filtro_origen.addItems(["Todos", "DG", "SGT", "GAS"])
        self.cmb_filtro_origen.currentIndexChanged.connect(self.cargar_control_gestion)
        
        # 3. Filtro Estatus
        self.cmb_filtro_estatus = QComboBox()
        self.cmb_filtro_estatus.addItems(ESTATUS_CG)
        self.cmb_filtro_estatus.currentIndexChanged.connect(self.cargar_control_gestion)
        
        # 4. Filtro Texto
        self.txt_buscar_cg = QLineEdit(placeholderText="Buscar por folio, asunto...")
        self.txt_buscar_cg.returnPressed.connect(self.cargar_control_gestion)
        
        # Botones
        btn_limpiar = QPushButton("Limpiar")
        btn_limpiar.setObjectName("btn_limpiar")
        btn_limpiar.clicked.connect(self.limpiar_busqueda_cg)
        
        self.btn_exportar_cg = QPushButton("Exportar")
        self.btn_exportar_cg.clicked.connect(self.exportar_control_gestion)
        
        self.btn_nuevo_cg = QPushButton("+ Nuevo")
        self.btn_nuevo_cg.setObjectName("btn_nuevo_cg") 
        self.btn_nuevo_cg.clicked.connect(self.nuevo_control_gestion)
        
        # Agregar widgets al layout (con etiquetas)
        search_layout.addWidget(QLabel("Año:"))
        search_layout.addWidget(self.cmb_filtro_anio)
        search_layout.addWidget(QLabel("Origen:"))
        search_layout.addWidget(self.cmb_filtro_origen)
        search_layout.addWidget(QLabel("Estatus:"))
        search_layout.addWidget(self.cmb_filtro_estatus)
        search_layout.addWidget(self.txt_buscar_cg)
        search_layout.addWidget(btn_limpiar)
        search_layout.addWidget(self.btn_exportar_cg)
        search_layout.addWidget(self.btn_nuevo_cg)
        
        layout.addWidget(search_group)
        
        # Controles de paginación superiores
        top_controls = QHBoxLayout()
        self.combo_por_pagina_cg = QComboBox()
        self.combo_por_pagina_cg.setObjectName("combo_paginacion")
        self.combo_por_pagina_cg.addItems(REGISTROS_POR_PAGINA)
        self.combo_por_pagina_cg.setCurrentText(str(self.paginator_cg.por_pagina))
        self.combo_por_pagina_cg.currentTextChanged.connect(self.cambiar_paginacion_cg)
        
        top_controls.addWidget(QLabel("Registros por página:"))
        top_controls.addWidget(self.combo_por_pagina_cg)
        top_controls.addStretch()
        layout.addLayout(top_controls)
        
        # Tabla
        self.tabla_cg = QTableWidget()
        # Asegúrate de tener 21 columnas (o las que definiste en tu header)
        headers = [
            "ID", "Origen","Folio", "Fecha Recepción", "Turnado a", "Remitente", "Área", 
            "Referencia", "Fecha del documento", "Asunto", "Prioridad", "Fecha Límite", 
            "Tipo Instrucción.", "Detalle Instrucción", "Observaciones", "Anexos", 
            "Requiere Respuesta", "Recibió", "C.C.P.", "Estatus", "Acciones"
        ]
        self.tabla_cg.setColumnCount(ControlGestionTab.COLUMN_COUNT)
        self.tabla_cg.setHorizontalHeaderLabels(headers)
        self.tabla_cg.setWordWrap(True)
        self.tabla_cg.verticalHeader().setVisible(False)
        self.tabla_cg.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla_cg.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla_cg.setAlternatingRowColors(True)
        
        self.tabla_cg.verticalHeader().setDefaultSectionSize(70)
        
        header = self.tabla_cg.horizontalHeader()
        
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        columnas_interactivas = [
            ControlGestionTab.ASUNTO, 
            ControlGestionTab.DETALLE_INSTRUCCION, 
            ControlGestionTab.OBSERVACIONES,
            ControlGestionTab.REMITENTE,     # <--- NUEVO
            ControlGestionTab.AREA,          # <--- NUEVO
            ControlGestionTab.CCP            # <--- NUEVO
        ]
        
        for col in columnas_interactivas:
            header.setSectionResizeMode(col, QHeaderView.Interactive)
        
        layout.addWidget(self.tabla_cg)
        
        # Paginación Inferior
        pag_layout = QHBoxLayout()
        self.btn_primera_cg = QPushButton("<< Primera")
        self.btn_primera_cg.setObjectName("pagination_btn")
        self.btn_anterior_cg = QPushButton("< Anterior")
        self.btn_anterior_cg.setObjectName("pagination_btn")
        self.lbl_pag_cg = QLabel("Página 1 / 1")
        self.btn_siguiente_cg = QPushButton("Siguiente >")
        self.btn_siguiente_cg.setObjectName("pagination_btn")
        self.btn_ultima_cg = QPushButton("Última >>")
        self.btn_ultima_cg.setObjectName("pagination_btn")
        
        pag_layout.addStretch()
        pag_layout.addWidget(self.btn_primera_cg)
        pag_layout.addWidget(self.btn_anterior_cg)
        pag_layout.addWidget(self.lbl_pag_cg)
        pag_layout.addWidget(self.btn_siguiente_cg)
        pag_layout.addWidget(self.btn_ultima_cg)
        pag_layout.addStretch()
        
        layout.addLayout(pag_layout)
        
        self.cargar_control_gestion()
        self.tabla_cg.setColumnWidth(ControlGestionTab.ASUNTO, 350)
        self.tabla_cg.setColumnWidth(ControlGestionTab.DETALLE_INSTRUCCION, 300)
        self.tabla_cg.setColumnWidth(ControlGestionTab.OBSERVACIONES, 250)
        self.tabla_cg.setColumnWidth(ControlGestionTab.REMITENTE, 200)
        self.tabla_cg.setColumnWidth(ControlGestionTab.AREA, 200)
        self.tabla_cg.setColumnWidth(ControlGestionTab.CCP, 180)
        
        return widget

    def cargar_control_gestion(self, *args, mantener_vista_congelada=False):
        """
        Carga datos sin alterar la geometría de las columnas.
        Esto previene el desajuste visual y mantiene los anchos de 600px.
        """
        # 1. Filtros
        filtros = {
            'texto': self.txt_buscar_cg.text().strip(),
            'origen': self.cmb_filtro_origen.currentText(),
            'estatus': self.cmb_filtro_estatus.currentText(),
            'anio': self.cmb_filtro_anio.currentText()
        }
        
        pagina = self.paginator_cg.pagina_actual
        limite = self.paginator_cg.por_pagina
        datos, total = self.expediente_service.obtener_lista_control_gestion(pagina, limite, filtros)
        
        # 2. Paginación
        self.paginator_cg.actualizar_estado(total, limite)
        self.lbl_pag_cg.setText(f"Página {self.paginator_cg.pagina_actual} / {self.paginator_cg.total_paginas}")
        
        self.btn_anterior_cg.setEnabled(self.paginator_cg.pagina_actual > 1)
        self.btn_primera_cg.setEnabled(self.paginator_cg.pagina_actual > 1)
        self.btn_siguiente_cg.setEnabled(self.paginator_cg.pagina_actual < self.paginator_cg.total_paginas)
        self.btn_ultima_cg.setEnabled(self.paginator_cg.pagina_actual < self.paginator_cg.total_paginas)

        # 3. Configuración SOLO de datos (Sin claves de ancho)
        config = [
            {'key': 'id', 'type': 'numeric'}, 
            {'key': 'origen', 'type': 'text'},
            {'key': 'folio', 'type': 'text'},
            {'key': 'fecha', 'type': 'date'},
            {'key': 'turnado_a', 'type': 'text'},
            {'key': 'remitente', 'type': 'text'},
            {'key': 'area', 'type': 'text'},
            {'key': 'referencia', 'type': 'text'},
            {'key': 'fecha_documento', 'type': 'date'},
            {'key': 'asunto', 'type': 'text'},
            {'key': 'prioridad', 'type': 'text'},
            {'key': 'fecha_limite', 'type': 'date'},
            {'key': 'tipo_instruccion', 'type': 'text'},
            {'key': 'detalle_instruccion', 'type': 'text'},
            {'key': 'observaciones', 'type': 'text'},
            {'key': 'documentos_anexos', 'type': 'text'},
            {'key': 'requiere_respuesta', 'type': 'text'},
            {'key': 'recibio', 'type': 'text'},
            {'key': 'ccp', 'type': 'text'},
            {'key': 'archivado', 'type': 'text'}
        ]

        # 4. Poblar Tabla (Congelando actualizaciones para evitar parpadeo)
        descongelar = not mantener_vista_congelada
        
        # Bloqueamos el repintado mientras llenamos
        self.tabla_cg.setUpdatesEnabled(False)
        
        self._poblar_tabla(
            tabla=self.tabla_cg,
            datos=datos,
            config_columnas=config,
            columna_acciones=ControlGestionTab.ACCIONES,
            callback_estilo=self._aplicar_estilos_cg,
            descongelar_al_final=False 
        )
        
        # Reactivamos el repintado
        if descongelar:
            self.tabla_cg.setUpdatesEnabled(True)
        
        self.statusBar().showMessage(f"Mostrando {len(datos)} registros de {total}.")
    
    def limpiar_busqueda_cg(self):
        """
        Resetea todos los filtros a su estado inicial y recarga la tabla.
        Usa blockSignals para evitar recargas múltiples innecesarias.
        """
        # 1. Bloqueamos las señales para que los cambios no disparen 'cargar_control_gestion' automáticamente
        self.cmb_filtro_anio.blockSignals(True)
        self.cmb_filtro_origen.blockSignals(True)
        self.cmb_filtro_estatus.blockSignals(True)
        
        # 2. Reseteamos los valores
        self.txt_buscar_cg.clear()                # Borrar texto
        self.cmb_filtro_anio.setCurrentIndex(0)   # Índice 0 suele ser "Todos" o el año actual, según tu orden
        self.cmb_filtro_origen.setCurrentIndex(0) # Índice 0 es "Todos"
        self.cmb_filtro_estatus.setCurrentIndex(0)# Índice 0 es "Todos"
        
        # 3. Desbloqueamos las señales
        self.cmb_filtro_anio.blockSignals(False)
        self.cmb_filtro_origen.blockSignals(False)
        self.cmb_filtro_estatus.blockSignals(False)
        
        # 4. Forzamos una única recarga limpia
        self.cargar_control_gestion()

    def nuevo_control_gestion(self):
        dialog = ControlGestionDialog(self.expediente_service, self)
        if dialog.exec_() == QDialog.Accepted:
            self.cargar_control_gestion()

    def editar_control_gestion(self, cg_id):
        # 1. BLOQUEAR SEÑALES AUTOMÁTICAS
        # Le decimos al servicio: "No avises a nadie todavía, yo me encargo".
        # Esto evita que la tabla se recargue sola y pierda el foco antes de tiempo.
        self.expediente_service.signals.blockSignals(True)
        
        try:
            dialog = ControlGestionDialog(self.expediente_service, self, cg_id)
            
            # 2. EJECUTAR DIÁLOGO
            if dialog.exec_() == QDialog.Accepted:
                
                # 3. ACTUALIZACIÓN MANUAL CONTROLADA
                # Ahora que el mensaje de éxito ya pasó y el diálogo se cerró,
                # nosotros recargamos la tabla poniendo el foco exactamente donde queremos.
                self._refrescar_y_mantener_foco(self.tabla_cg, id_foco=cg_id)
                
                # 4. ACTUALIZAR DASHBOARD MANUALMENTE
                # Como silenciamos la señal automática, debemos avisarle al dashboard nosotros mismos.
                if hasattr(self, 'dashboard') and hasattr(self.dashboard, 'cargar_datos'):
                    self.dashboard.cargar_datos()

        finally:
            # 5. RESTAURAR SEÑALES
            # Pase lo que pase (incluso si cancelas), volvemos a activar las señales
            # para que el resto de la aplicación siga funcionando normal.
            self.expediente_service.signals.blockSignals(False)

    def eliminar_control_gestion(self, cg_id):
        fila_actual = self.tabla_cg.currentRow()
        
        reply = QMessageBox.question(self, "Eliminar", "¿Seguro que desea eliminar este registro?",
                                     QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            # 1. BLOQUEAR SEÑALES (Para evitar recarga descontrolada)
            self.expediente_service.signals.blockSignals(True)
            
            try:
                success, msg = self.expediente_service.eliminar_control_gestion(cg_id)
                
                if success:
                    # 2. RECARGA MANUAL CONTROLADA (Sin parpadeo)
                    self._refrescar_y_mantener_foco(self.tabla_cg, fila_foco=fila_actual)
                    
                    # Actualizar dashboard manualmente
                    if hasattr(self, 'dashboard'): self.dashboard.cargar_datos()
                else:
                    QMessageBox.warning(self, "Error", msg)
                    
            finally:
                # 3. RESTAURAR SEÑALES
                self.expediente_service.signals.blockSignals(False)

    def cambiar_paginacion_cg(self, text):
        if not text: return
        self.paginator_cg.por_pagina = int(text)
        self.paginator_cg.ir_a_pagina(1)
        
    def exportar_control_gestion(self):
        """Exporta los registros de Control de Gestión a Excel."""
        texto_busqueda = self.txt_buscar_cg.text().strip()
        
        # 1. Obtener datos crudos de la base de datos
        datos = self.expediente_service.obtener_todo_control_gestion(texto_busqueda)
        
        if not datos:
            QMessageBox.warning(self, "Exportar", "No hay registros para exportar con los filtros actuales.")
            return

        # 2. (Opcional) Mapeo de nombres de columnas para que se vean bonitos en Excel
        # Si prefieres los nombres de la BD (ej. 'fecha_limite'), puedes saltar este paso.
        headers_map = {
            'id': 'ID', 'origen': 'Origen','folio': 'Folio', 'fecha': 'Fecha Recepción', 
            'turnado_a': 'Turnado A', 'remitente': 'Remitente', 'area': 'Área', 
            'referencia': 'Referencia', 'fecha_documento': 'Fecha Documento', 
            'asunto': 'Asunto', 'prioridad': 'Prioridad', 'fecha_limite': 'Fecha Límite', 
            'tipo_instruccion': 'Instrucción', 'detalle_instruccion': 'Detalle', 
            'observaciones': 'Observaciones', 'documentos_anexos': 'Anexos', 
            'requiere_respuesta': 'Req. Respuesta', 'recibio': 'Recibió', 
            'ccp': 'C.C.P.', 'archivado': 'Estatus'
        }
        
        datos_formateados = []
        for row in datos:
            new_row = {}
            for key, value in row.items():
                if key in headers_map:
                    new_row[headers_map[key]] = value
            datos_formateados.append(new_row)

        # 3. Guardar archivo
        filename = f"Control_Gestion_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        filepath, _ = QFileDialog.getSaveFileName(self, "Guardar Reporte", filename, "Archivos de Excel (*.xlsx)")
        
        if not filepath:
            return
            
        self.statusBar().showMessage("Exportando a Excel...")
        
        # 4. Ejecutar en hilo (reutilizando tu callback on_exportacion_finalizada)
        self._ejecutar_en_hilo(
            self.excel_service.create_report,
            self.on_exportacion_finalizada,
            datos_formateados,
            filepath
        )
    
    def imprimir_formato_cg(self, cg_id):
        """Genera el volante en Excel inyectando los cargos y leyendas solo para impresión."""
        # 1. Obtener datos crudos de la base de datos
        datos = self.expediente_service.obtener_control_gestion_por_id(cg_id)
        if not datos:
            mostrar_mensaje(self, "Error", "No se encontraron los datos del registro.", QMessageBox.Warning)
            return

        # --- MAGIA DE IMPRESIÓN (Solo en memoria, no toca la BD) ---
        dict_funcionarios = {
            "MTRO. HUGO ESTRADA ARROYO": "GERENTE DE AGUAS SUBTRRÁNEAS",
            "ING. MARÍA FERNANDA ANGULO ESCOTTO": "SUBGERENTE DE EXPLORACIÓN Y MONITOREO GEOHIDROLÓGICO",
            "ING. JULIETA MARES LÓPEZ": "SUBDIRECTORA DE ÁREA DE MANEJO DE ",
            "MTRA. ANGÉLICA MOLINA MALDONADO": "SUBGERENTE DE EVALUACIÓN Y ORDENAMIENTO DE ACUIFEROS",
            "ING. VÍCTOR MANUEL CASTAÑÓN ARCOS": "SUBGERENTE DE SISTEMAS DE INFORMACIÓN GEOHIDROLÓGICOS",
            "ING. JUAN MANUEL ANZALDO LARA": "SUBGERENTE DE INFORMACIÓN GEOGRÁFICA DEL AGUA",
            "SUBGERENTES": "",
            "ARCHIVO": "",
            "ENLACE": "",
            "NO APLICA": ""
        }
        
        turnado_raw = datos.get('turnado_a', '')
        if turnado_raw:
            nombres = [n.strip() for n in turnado_raw.split('\n') if n.strip()]
            nombres_formateados = []
            
            for nombre in nombres:
                puesto = dict_funcionarios.get(nombre, "")
                if puesto:
                    nombres_formateados.append(f"{nombre}\n{puesto}")
                else:
                    nombres_formateados.append(nombre)
            
            # Armamos el bloque bonito y agregamos la leyenda al final
            turnado_final = "\n\n".join(nombres_formateados)
            turnado_final += "\n\nGERENCIA DE AGUAS SUBTERRÁNEAS"
            
            # Sobrescribimos el dato en el diccionario (solo vive en memoria para este método)
            datos['turnado_a'] = turnado_final
        # ------------------------------------------------------------

        # 2. Definir rutas
        folio_safe = datos.get('folio', 'SF').replace('/', '-')
        nombre_archivo = f"Volante_{folio_safe}.xlsx"
        template_path = get_template_cg_path()
        
        output_path, _ = QFileDialog.getSaveFileName(self, "Guardar Volante", nombre_archivo, "Archivos de Excel (*.xlsx)")
        if not output_path:
            return

        self.statusBar().showMessage("Generando documentos...")
        
        # 3. Generar Excel
        success, msg = self.excel_service.generar_volante_cg(datos, template_path, output_path)
        
        if success:
            mensajes = [f"Excel generado: {os.path.basename(output_path)}"]
            pdf_success, pdf_result = self.excel_service.convertir_excel_a_pdf(output_path)
            
            try:
                os.startfile(output_path)
                if pdf_success:
                    mensajes.append(f"PDF generado: {os.path.basename(pdf_result)}")
                    os.startfile(pdf_result)
                else:
                    mensajes.append(f"(No se pudo crear PDF: {pdf_result})")
            except Exception as e:
                mensajes.append(f"Error al intentar abrir archivos: {e}")

            self.statusBar().showMessage("Proceso finalizado.")
            mostrar_mensaje(self, "Éxito", "\n".join(mensajes), QMessageBox.Information)
            
        else:
            mostrar_mensaje(self, "Error", msg, QMessageBox.Critical)
    
    def imprimir_caratula_desde_menu(self, expediente_id):
        """Genera el formato de etiquetas en Excel usando la plantilla."""
        if not expediente_id:
            QMessageBox.warning(self, "Atención", "Por favor seleccione un expediente primero.")
            return
            
        # 1. Cargar datos
        datos_completos = self.expediente_service.obtener_vista_completa_expediente(expediente_id)
        if not datos_completos:
            QMessageBox.warning(self, "Error", "No se pudieron cargar los datos del expediente.")
            return
            
        clasificacion = datos_completos['expediente'].get('clasificacion', 'S-C')
        clasificacion_limpia = clasificacion.replace('/', '_')
        nombre_sugerido = f"Etiquetas_{clasificacion_limpia}.xlsx"
        
        # 2. Pedir ruta de guardado
        ruta_guardado, _ = QFileDialog.getSaveFileName(
            self, "Guardar Etiquetas en Excel", nombre_sugerido, "Archivos de Excel (*.xlsx)"
        )
        
        if ruta_guardado:
            self.statusBar().showMessage("Clonando plantilla y llenando datos...")
            
            # --- AJUSTA ESTA RUTA DONDE GUARDES TU PLANTILLA ---
            ruta_plantilla = os.path.abspath(os.path.join("templates", "plantilla_etiquetas.xlsx"))
            
            if not os.path.exists(ruta_plantilla):
                QMessageBox.critical(self, "Error", f"No se encontró la plantilla de Excel en:\n{ruta_plantilla}\n\nPor favor coloque el archivo ahí.")
                self.statusBar().clearMessage()
                return

            # 3. Mandar al servicio de Excel a hacer el trabajo
            success, msg_o_ruta = self.excel_service.generar_etiquetas_excel(datos_completos, ruta_plantilla, ruta_guardado)
            
            if success:
                # 4. Abrir el archivo de Excel automáticamente
                try:
                    if platform.system() == "Windows":
                        os.startfile(ruta_guardado)
                    elif platform.system() == "Darwin":
                        subprocess.Popen(["open", ruta_guardado])
                    else:
                        subprocess.Popen(["xdg-open", ruta_guardado])
                        
                    self.statusBar().showMessage("Etiquetas de Excel generadas con éxito.")
                except Exception as e:
                    QMessageBox.warning(self, "Atención", f"El archivo se creó pero no se pudo abrir automáticamente.\n{e}")
            else:
                QMessageBox.critical(self, "Error", f"Fallo al generar el Excel:\n{msg_o_ruta}")
                self.statusBar().showMessage("Error al generar Excel.")
            
    def mostrar_reporte_quincenal(self):
        """Abre diálogo de fechas y muestra reporte de productividad."""
        # 1. Abrir diálogo de selección
        dialog = SeleccionarFechasDialog(self)
        
        if dialog.exec_() == QDialog.Accepted:
            # 2. Obtener fechas seleccionadas
            f_inicio, f_fin = dialog.get_fechas()
            
            # 3. Consultar base de datos
            stats = self.expediente_service.obtener_reporte_por_rango(f_inicio, f_fin)
            
            # 4. Mostrar Resultados
            mensaje = (
                f"<b>REPORTE DE PRODUCTIVIDAD</b><br><hr>"
                
                f"<b>PERIODO SELECCIONADO (Actual)</b><br>"
                f"<i>{stats['periodo_actual_texto']}</i><br>"
                f"<span style='font-size:14px'>Expedientes: <b>{stats['cant_actual']}</b></span><br><br>"
                
                f"<b>PERIODO ANTERIOR (Comparativo)</b><br>"
                f"<i>{stats['periodo_anterior_texto']}</i><br>"
                f"Expedientes: <b>{stats['cant_anterior']}</b><br><br>"
                
                f"<hr>"
                f"<b>TOTAL HISTÓRICO:</b> <span style='color:#27ae60; font-weight:bold; font-size:14px'>{stats['total_acumulado']}</span>"
            )
            
            QMessageBox.information(self, "Reporte de Productividad", mensaje)
            
    def actualizar_interfaz(self):
        """Refresca Dashboard y Tablas automáticamente."""
        # print("Sincronizando cambios...") # Debug opcional
        
        # A) Dashboard
        if hasattr(self, 'dashboard') and hasattr(self.dashboard, 'cargar_datos'):
             self.dashboard.cargar_datos() # Asegúrate que tu DashboardWidget tenga este método
             
        # B) Tablas
        self.cargar_control_gestion()
        if hasattr(self, 'cargar_expedientes'):
            self.cargar_expedientes()
            
        # C) Contadores de otras pestañas
        if hasattr(self, 'cargar_expedientes_vencidos'):
            self.cargar_expedientes_vencidos()
        if hasattr(self, 'buscar_expedientes_en_concentracion'):
            self.buscar_expedientes_en_concentracion()
        if hasattr(self, 'cargar_historial_lotes'):
            self.cargar_historial_lotes()
        if hasattr(self, 'cargar_historial_destino_final'):
            self.cargar_historial_destino_final()
        if hasattr(self, 'cargar_lotes_valoracion'):
            self.cargar_lotes_valoracion()
        if hasattr(self, 'cargar_arbol_clasificacion'):
            self.cargar_arbol_clasificacion()
            
    def _aplicar_estilos_cg(self, item, clave, valor, fila_datos):
        """Callback para pintar colores específicos y SEMÁFORO de Control de Gestión."""
        from datetime import datetime
        
        colores_origen = {"DG": "#8E44AD", "SGT": "#D35400", "GAS": "#27AE60"}
        if clave == 'origen':
            item.setTextAlignment(Qt.AlignCenter)
            font = item.font(); font.setBold(True); item.setFont(font)
            if valor in colores_origen:
                item.setBackground(QColor(colores_origen[valor]))
                item.setForeground(QColor("white"))
                
        elif clave == 'prioridad' and valor == "URGENTE":
            item.setForeground(QColor("red"))
            font = item.font(); font.setBold(True); item.setFont(font)
            
        # 2. SEMÁFORO INTELIGENTE ROBUSTO
        estatus = str(fila_datos.get('archivado', '')).strip().upper()
        esta_concluido = estatus == "CONCLUIDO" or estatus == "CANCELADO"
        
        if not esta_concluido and fila_datos.get('fecha_limite'):
            try:
                # Limpiamos la fecha por si la BD le agregó horas (ej. 2026-03-27 00:00:00)
                fecha_str = str(fila_datos['fecha_limite']).split(" ")[0]
                
                # Intentamos leer como Año-Mes-Día
                try:
                    fecha_lim = datetime.strptime(fecha_str, "%Y-%m-%d").date()
                except ValueError:
                    # Plan B: Si falla, intentamos leer como Día-Mes-Año
                    fecha_lim = datetime.strptime(fecha_str, "%d-%m-%Y").date()
                    
                fecha_formateada = fecha_lim.strftime("%d-%m-%Y")
                hoy = datetime.now().date()
                dias_restantes = (fecha_lim - hoy).days
                
                if clave == 'fecha_limite':
                    font = item.font(); font.setBold(True); item.setFont(font)
                    
                    if dias_restantes < 0:
                        item.setText(f"🛑 VENCIDO ({fecha_formateada})")
                        item.setForeground(QColor("#c0392b")) # Rojo
                    elif dias_restantes <= 2:
                        item.setText(f"⚠️ VENCE PRONTO ({fecha_formateada})")
                        item.setForeground(QColor("#d35400")) # Naranja
                    else:
                        item.setText(fecha_formateada)
                        item.setForeground(QColor("#27ae60")) # Verde
            except Exception as e:
                # Si llega a fallar algo rarísimo, lo imprimimos en consola pero no crasheamos
                print(f"Error en semáforo de fecha: {e}")
                pass 

        # 3. Estilos de Estatus
        if clave == 'archivado':
            font = item.font(); font.setBold(True); item.setFont(font)
            if estatus == "CONCLUIDO": item.setForeground(QColor("green"))
            elif estatus == "CANCELADO": item.setForeground(QColor("gray"))
            else: item.setForeground(QColor("#d35400"))
    
    def exportar_inventario_seleccionados(self):
        """Toma los expedientes seleccionados y genera el inventario oficial en Excel."""
        selected_rows = self.tabla_vencidos.selectionModel().selectedRows()
        if not selected_rows:
            mostrar_mensaje(self,"Sin Selección", "Por favor, seleccione (usando Control o Shift) los expedientes que desea incluir en el inventario.", QMessageBox.Warning)
            return
            
        # Extraemos los IDs de las filas seleccionadas
        ids_seleccionados = [int(self.tabla_vencidos.item(row.row(), 0).text()) for row in selected_rows]
        
        # Le preguntamos al usuario dónde quiere guardarlo
        ruta_guardado, _ = QFileDialog.getSaveFileName(
            self, "Guardar Inventario", f"Inventario_Transferencia_{datetime.now().strftime('%Y%m%d')}.xlsx", "Archivos de Excel (*.xlsx)"
        )
        
        if ruta_guardado:
            # Buscamos la plantilla en la carpeta templates
            ruta_plantilla = os.path.abspath(os.path.join("templates", "plantilla_transferencia_primaria.xlsx"))
            if not os.path.exists(ruta_plantilla):
                QMessageBox.critical(self, "Error", f"No se encontró la plantilla de Excel en:\n{ruta_plantilla}")
                return
                
            self.statusBar().showMessage("Generando Inventario Oficial...")
            self.btn_generar_inventario_vencidos.setEnabled(False)
            
            # Lo mandamos a procesar en un Hilo para que no se trabe la pantalla
            self._ejecutar_en_hilo(
                self.excel_service.generar_inventario_transferencia,
                self.on_exportacion_finalizada, # Reutilizamos tu alerta de éxito
                self.expediente_service,        # Le pasamos el servicio para que pueda hacer consultas
                ids_seleccionados,
                ruta_plantilla,
                ruta_guardado
            )
            self.btn_generar_inventario_vencidos.setEnabled(True)
            
    def crear_lote_desde_vencidos(self):
        """Toma los expedientes seleccionados de Vencidos y crea un lote."""
        selected_rows = self.tabla_vencidos.selectionModel().selectedRows()
        if not selected_rows:
            mostrar_mensaje(self,"Sin Selección", "Seleccione los expedientes que desea empaquetar.", QMessageBox.Warning)
            return
            
        ids_seleccionados = [int(self.tabla_vencidos.item(row.row(), 0).text()) for row in selected_rows]
        
        reply = QMessageBox.question(self, 'Confirmar Lote', 
                                     f"¿Crear un paquete de transferencia con {len(ids_seleccionados)} expedientes?", 
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                                     
        if reply == QMessageBox.Yes:
            success, msg = self.expediente_service.crear_lote_transferencia(ids_seleccionados)
            if success:
                mostrar_mensaje(self, "Lote Creado", msg, QMessageBox.Information)
                self.tabla_vencidos.clearSelection()
                self.cargar_expedientes_vencidos() # Recargamos para que desaparezcan de aquí
                self.cargar_lotes_transferencia()  # Aparecen en la pestaña nueva
            else:
                mostrar_mensaje(self, "Error", msg, QMessageBox.Warning)

    def cargar_lotes_transferencia(self):
        """Llena la tabla de la pestaña 'Mis Transferencias'."""
        if not hasattr(self, 'tabla_lotes'): return
        
        lotes = self.expediente_service.obtener_lotes_activos()
        self.tabla_lotes.setRowCount(0)
        for i, lote in enumerate(lotes):
            self.tabla_lotes.insertRow(i)
            self.tabla_lotes.setItem(i, LotesTab.ID, QTableWidgetItem(str(lote['id'])))
            self.tabla_lotes.setItem(i, LotesTab.FOLIO, QTableWidgetItem(lote['folio_lote']))
            self.tabla_lotes.setItem(i, LotesTab.FECHA_CREACION, QTableWidgetItem(str(lote['fecha_creacion'])))
            self.tabla_lotes.setItem(i, LotesTab.USUARIO, QTableWidgetItem(lote['usuario_creador']))

    def confirmar_entrega_lote_seleccionado(self):
        """Marca el lote como entregado y guarda su Acuse."""
        selected_rows = self.tabla_lotes.selectionModel().selectedRows()
        if not selected_rows:
            mostrar_mensaje(self, "Aviso", "Seleccione un lote de la tabla para confirmar su entrega física.", QMessageBox.Warning)
            return
            
        id_lote = int(self.tabla_lotes.item(selected_rows[0].row(), 0).text())
        folio_lote = self.tabla_lotes.item(selected_rows[0].row(), 1).text()
        
        dialog = UbicacionDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            ubicacion = dialog.get_ubicacion()
            ruta_pdf = dialog.get_pdf_path()
            
            success, msg = self.expediente_service.confirmar_entrega_lote(id_lote, folio_lote, ubicacion, ruta_pdf)
            
            if success:
                mostrar_mensaje(self, "Lote Entregado", msg, QMessageBox.Information)
                self.cargar_lotes_transferencia() 
                self.buscar_expedientes_en_concentracion() 
            else:
                mostrar_mensaje(self, "Error", msg, QMessageBox.Warning)
    
    def reimprimir_lote_seleccionado(self):
        """Reimprime el inventario en Excel del paquete seleccionado."""
        selected_rows = self.tabla_lotes.selectionModel().selectedRows()
        if not selected_rows:
            mostrar_mensaje(self, "Aviso", "Seleccione un lote de la tabla para reimprimir su inventario.", QMessageBox.Warning)
            return
            
        id_lote = int(self.tabla_lotes.item(selected_rows[0].row(), 0).text())
        folio_lote = self.tabla_lotes.item(selected_rows[0].row(), 1).text()
        
        # 1. Le preguntamos a la base de datos qué expedientes están en este lote
        ids_expedientes = self.expediente_service.obtener_ids_por_lote(id_lote)
        if not ids_expedientes:
            mostrar_mensaje(self, "Error", "Este lote está vacío.", QMessageBox.Warning)
            return
            
        # 2. Pedimos ruta de guardado
        ruta_guardado, _ = QFileDialog.getSaveFileName(
            self, "Reimprimir Inventario", f"Inventario_{folio_lote}.xlsx", "Archivos de Excel (*.xlsx)"
        )
        
        if ruta_guardado:
            ruta_plantilla = os.path.abspath(os.path.join("templates", "plantilla_transferencia_primaria.xlsx"))
            self.statusBar().showMessage(f"Reimprimiendo inventario {folio_lote}...")
            
            # 3. Mandamos llamar a tu mega motor de Excel
            self._ejecutar_en_hilo(
                self.excel_service.generar_inventario_transferencia,
                self.on_exportacion_finalizada,
                self.expediente_service,
                ids_expedientes,
                ruta_plantilla,
                ruta_guardado
            )
    
    def cancelar_lote_seleccionado(self):
        """Cancela el lote seleccionado y regresa los expedientes a Vencidos."""
        selected_rows = self.tabla_lotes.selectionModel().selectedRows()
        if not selected_rows:
            mostrar_mensaje(self, "Aviso", "Seleccione un lote de la tabla para cancelarlo.", QMessageBox.Warning)
            return
            
        id_lote = int(self.tabla_lotes.item(selected_rows[0].row(), 0).text())
        folio_lote = self.tabla_lotes.item(selected_rows[0].row(), 1).text()
        
        reply = QMessageBox.question(self, 'Confirmar Cancelación', 
                                     f"¿Está seguro de que desea DESARMAR el paquete {folio_lote}?\n\nLos expedientes volverán inmediatamente a su tabla de Vencidos.", 
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            success, msg = self.expediente_service.cancelar_lote_transferencia(id_lote, folio_lote)
            if success:
                mostrar_mensaje(self, "Paquete Cancelado", msg, QMessageBox.Information)
                self.cargar_lotes_transferencia() # Desaparece de esta tabla
                self.cargar_expedientes_vencidos() # Reaparecen en Vencidos
            else:
                mostrar_mensaje(self, "Error", msg, QMessageBox.Warning)
                
    def cargar_historial_lotes(self):
        """Llena la tabla del historial de lotes entregados."""
        if not hasattr(self, 'tabla_historial_lotes'): return
        
        lotes = self.expediente_service.obtener_lotes_entregados()
        self.tabla_historial_lotes.setRowCount(0)
        
        for i, lote in enumerate(lotes):
            self.tabla_historial_lotes.insertRow(i)
            self.tabla_historial_lotes.setItem(i, HistorialLotesTab.ID, QTableWidgetItem(str(lote['id'])))
            self.tabla_historial_lotes.setItem(i, HistorialLotesTab.FOLIO, QTableWidgetItem(lote['folio_lote']))
            self.tabla_historial_lotes.setItem(i, HistorialLotesTab.FECHA_CREACION, QTableWidgetItem(str(lote['fecha_creacion'])))
            self.tabla_historial_lotes.setItem(i, HistorialLotesTab.FECHA_ENTREGA, QTableWidgetItem(str(lote['fecha_entrega'])))
            self.tabla_historial_lotes.setItem(i, HistorialLotesTab.USUARIO, QTableWidgetItem(str(lote.get('usuario_creador', ''))))
            
            # Verificamos si tiene PDF y ponemos un texto bonito
            ruta_pdf = lote.get('archivo_inventario_pdf')
            tiene_acuse = "Sí 📎" if ruta_pdf else "No ❌"
            item_acuse = QTableWidgetItem(tiene_acuse)
            item_acuse.setTextAlignment(Qt.AlignCenter)
            self.tabla_historial_lotes.setItem(i, HistorialLotesTab.ACUSE, item_acuse)
            self.tabla_historial_lotes.item(i, HistorialLotesTab.ID).setData(Qt.UserRole, ruta_pdf)

    def ver_acuse_lote_seleccionado(self):
        """Abre el PDF del acuse en el visor integrado."""
        selected_rows = self.tabla_historial_lotes.selectionModel().selectedRows()
        if not selected_rows:
            mostrar_mensaje(self, "Aviso", "Seleccione un lote de la tabla para ver su acuse.", QMessageBox.Warning)
            return
            
        # Extraemos la ruta escondida
        ruta_pdf = self.tabla_historial_lotes.item(selected_rows[0].row(), 0).data(Qt.UserRole)
        folio_lote = self.tabla_historial_lotes.item(selected_rows[0].row(), 1).text()
        
        if not ruta_pdf or not os.path.exists(ruta_pdf):
            mostrar_mensaje(self, "Sin Acuse", f"El lote {folio_lote} no tiene un PDF adjunto o el archivo fue movido de la bóveda.", QMessageBox.Information)
            return
            
        self.statusBar().showMessage(f"Abriendo acuse para: {folio_lote}")
        
        # Usamos tu visor de PDF que ya tenías programado!
        dialogo_visor = PdfViewerDialog(ruta_pdf, self)
        dialogo_visor.exec_()
        self.statusBar().showMessage("Listo")
    
    def create_destino_final_sub_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        
        title_label = QLabel("REGISTRO DE DESTINOS FINALES (BAJAS Y ARCHIVO HISTÓRICO)")
        title_label.setObjectName("title_label")
        layout.addWidget(title_label)
        
        btn_group = QGroupBox("Consultas y Reportes")
        btn_layout = QHBoxLayout(btn_group)
        
        self.btn_actualizar_destinos = QPushButton("🔄 Actualizar Tabla")
        self.btn_actualizar_destinos.clicked.connect(self.cargar_historial_destino_final)
        
        btn_layout.addWidget(self.btn_actualizar_destinos)
        btn_layout.addStretch()
        
        self.tabla_destinos_finales = QTableWidget()
        self.tabla_destinos_finales.setColumnCount(DestinoFinalTab.COLUMN_COUNT)
        self.tabla_destinos_finales.setHorizontalHeaderLabels(["ID Registro", "Destino Legal", "Fecha Ejecución", "Folio Expediente", "Asunto", "Justificación / Oficio", "Acciones"])
        self.tabla_destinos_finales.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla_destinos_finales.setSelectionMode(QTableWidget.SingleSelection)
        self.tabla_destinos_finales.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla_destinos_finales.setAlternatingRowColors(True)
        self.tabla_destinos_finales.verticalHeader().setVisible(False)
        
        header = self.tabla_destinos_finales.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setSectionResizeMode(DestinoFinalTab.ASUNTO, QHeaderView.Stretch)
        header.setSectionResizeMode(DestinoFinalTab.OBSERVACIONES, QHeaderView.Stretch)
        
        layout.addWidget(btn_group)
        layout.addWidget(self.tabla_destinos_finales, 1)
        
        self.cargar_historial_destino_final()
        
        return widget

    def cargar_historial_destino_final(self):
        """Llena la tabla de los expedientes que ya causaron baja o son históricos."""
        if not hasattr(self, 'tabla_destinos_finales'): return
        
        # Congelamos la tabla para que no parpadee al llenarse
        self.tabla_destinos_finales.setUpdatesEnabled(False)
        
        datos = self.expediente_service.obtener_historial_destino_final()
        self.tabla_destinos_finales.setRowCount(len(datos))
        
        for i, reg in enumerate(datos):
            self.tabla_destinos_finales.setItem(i, DestinoFinalTab.ID_REGISTRO, QTableWidgetItem(str(reg['destino_id'])))
            
            # Ponemos color al Tipo de Destino para que resalte
            item_tipo = QTableWidgetItem(reg['tipo_destino'])
            if "BAJA" in reg['tipo_destino']: 
                item_tipo.setForeground(QColor("#c0392b")) # Rojo para destrucción
            else: 
                item_tipo.setForeground(QColor("#2980b9")) # Azul para histórico
                
            font = item_tipo.font()
            font.setBold(True)
            item_tipo.setFont(font)
            
            self.tabla_destinos_finales.setItem(i, DestinoFinalTab.TIPO_DESTINO, item_tipo)
            self.tabla_destinos_finales.setItem(i, DestinoFinalTab.FECHA, QTableWidgetItem(str(reg['fecha_ejecucion'])))
            self.tabla_destinos_finales.setItem(i, DestinoFinalTab.FOLIO, QTableWidgetItem(reg['folio']))
            self.tabla_destinos_finales.setItem(i, DestinoFinalTab.ASUNTO, QTableWidgetItem(reg['asunto']))
            self.tabla_destinos_finales.setItem(i, DestinoFinalTab.OBSERVACIONES, QTableWidgetItem(reg['observaciones']))
            
            # --- DIBUJAR EL BOTÓN DE ACCIONES ---
            widget_acciones = self._crear_boton_acciones(self.tabla_destinos_finales, i)
            self.tabla_destinos_finales.setCellWidget(i, DestinoFinalTab.ACCIONES, widget_acciones)
            
        self.tabla_destinos_finales.setUpdatesEnabled(True)

    def create_dictamenes_sub_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        
        title_label = QLabel("LOTES EN ESPERA DE DICTAMEN DEL GRUPO INTERDISCIPLINARIO")
        title_label.setObjectName("title_label")
        layout.addWidget(title_label)
        
        btn_group = QGroupBox("Resolución del Comité")
        btn_layout = QHBoxLayout(btn_group)
        
        self.btn_actualizar_dictamenes = QPushButton("🔄 Actualizar Tabla")
        self.btn_actualizar_dictamenes.clicked.connect(self.cargar_lotes_valoracion)
        
        self.btn_generar_formato_baja = QPushButton("🖨️ Generar Acta/Inventario")
        self.btn_generar_formato_baja.clicked.connect(self.imprimir_formato_baja_lote)
        
        self.btn_rechazar_dictamen = QPushButton("❌ Registrar Rechazo")
        self.btn_rechazar_dictamen.setObjectName("btn_peligro")
        self.btn_rechazar_dictamen.clicked.connect(self.rechazar_lote_valoracion)
        
        self.btn_aprobar_dictamen = QPushButton("✅ Registrar Aprobación")
        self.btn_aprobar_dictamen.setObjectName("btn_exito")
        self.btn_aprobar_dictamen.clicked.connect(self.aprobar_lote_valoracion)
        
        btn_layout.addWidget(self.btn_actualizar_dictamenes)
        btn_layout.addWidget(self.btn_generar_formato_baja)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_rechazar_dictamen)
        btn_layout.addWidget(self.btn_aprobar_dictamen)
        
        self.tabla_dictamenes = QTableWidget()
        self.tabla_dictamenes.setColumnCount(4)
        self.tabla_dictamenes.setHorizontalHeaderLabels(["ID", "Folio del Lote", "Tipo de Propuesta", "Fecha Creación"])
        self.tabla_dictamenes.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla_dictamenes.setSelectionMode(QTableWidget.SingleSelection)
        self.tabla_dictamenes.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla_dictamenes.setAlternatingRowColors(True)
        self.tabla_dictamenes.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        layout.addWidget(btn_group)
        layout.addWidget(self.tabla_dictamenes, 1)
        
        self.cargar_lotes_valoracion()
        return widget

    def cargar_lotes_valoracion(self):
        if not hasattr(self, 'tabla_dictamenes'): return
        lotes = self.expediente_service.obtener_lotes_valoracion_activos()
        self.tabla_dictamenes.setRowCount(0)
        for i, lote in enumerate(lotes):
            self.tabla_dictamenes.insertRow(i)
            self.tabla_dictamenes.setItem(i, 0, QTableWidgetItem(str(lote['id'])))
            self.tabla_dictamenes.setItem(i, 1, QTableWidgetItem(lote['folio_lote']))
            
            # Colorcito para la propuesta
            item_tipo = QTableWidgetItem(lote['tipo_propuesta'])
            if "BAJA" in lote['tipo_propuesta']: item_tipo.setForeground(QColor("#c0392b"))
            else: item_tipo.setForeground(QColor("#2980b9"))
            font = item_tipo.font(); font.setBold(True); item_tipo.setFont(font)
            
            self.tabla_dictamenes.setItem(i, 2, item_tipo)
            self.tabla_dictamenes.setItem(i, 3, QTableWidgetItem(str(lote['fecha_creacion'])))

    def crear_lote_valoracion_seleccionados(self):
        selected_rows = self.tabla_concentracion.selectionModel().selectedRows()
        if not selected_rows:
            mostrar_mensaje(self, "Aviso", "Seleccione los expedientes que desea proponer para valoración.", QMessageBox.Warning)
            return
            
        ids_seleccionados = [int(self.tabla_concentracion.item(row.row(), ConcentracionTab.ID).text()) for row in selected_rows]
        
        opciones = OPCIONES_VALORACION
        destino, ok = QInputDialog.getItem(self, "Proponer Valoración", f"Se agruparán {len(ids_seleccionados)} expedientes.\nSeleccione qué destino propondrá al Comité:", opciones, 0, False)
        
        if ok and destino:
            success, msg = self.expediente_service.crear_lote_valoracion(ids_seleccionados, destino)
            if success:
                mostrar_mensaje(self, "Lote Creado", msg, QMessageBox.Information)
                self.buscar_expedientes_en_concentracion() # Desaparecen de bodega
                if hasattr(self, 'cargar_lotes_valoracion'):
                    self.cargar_lotes_valoracion() # Aparecen en el puente
            else:
                mostrar_mensaje(self, "Error", msg, QMessageBox.Warning)

    def rechazar_lote_valoracion(self):
        selected_rows = self.tabla_dictamenes.selectionModel().selectedRows()
        if not selected_rows: return
        
        id_lote = int(self.tabla_dictamenes.item(selected_rows[0].row(), 0).text())
        folio = self.tabla_dictamenes.item(selected_rows[0].row(), 1).text()
        
        if QMessageBox.question(self, 'Rechazar', f"¿Seguro que desea registrar el RECHAZO del lote {folio}?\nLos expedientes volverán a su estado normal.", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            success, msg = self.expediente_service.rechazar_lote_valoracion(id_lote, folio)
            mostrar_mensaje(self, "Resultado", msg)
            self.cargar_lotes_valoracion()
            self.buscar_expedientes_en_concentracion()

    def aprobar_lote_valoracion(self):
        selected_rows = self.tabla_dictamenes.selectionModel().selectedRows()
        if not selected_rows: return
        
        id_lote = int(self.tabla_dictamenes.item(selected_rows[0].row(), 0).text())
        folio = self.tabla_dictamenes.item(selected_rows[0].row(), 1).text()
        
        obs, ok_obs = QInputDialog.getText(self, "Aprobar Dictamen", f"Aprobando {folio}\nIngrese el número de Acta o Dictamen de autorización:")
        
        if ok_obs:
            ruta_pdf, _ = QFileDialog.getOpenFileName(self, "Opcional: Seleccionar Acta Firmada en PDF", "", "PDF (*.pdf)")
            
            success, msg = self.expediente_service.aprobar_lote_valoracion(id_lote, folio, ruta_pdf, obs)
            if success:
                mostrar_mensaje(self, "¡Aprobado!", msg, QMessageBox.Information)
                self.cargar_lotes_valoracion()
                if hasattr(self, 'cargar_historial_destino_final'):
                    self.cargar_historial_destino_final() # Aparecen en la pestaña final
            else:
                mostrar_mensaje(self, "Error", msg, QMessageBox.Warning)
    
    def revertir_destino_menu(self, destino_id):
        """Handler que recibe el ID directamente desde el menú de acciones."""
        # Buscamos los datos exactos en la memoria
        datos_historial = self.expediente_service.obtener_historial_destino_final()
        registro = next((item for item in datos_historial if item['destino_id'] == destino_id), None)
        
        if not registro:
            mostrar_mensaje(self, "Error", "No se encontraron los datos del registro.", QMessageBox.Critical)
            return
            
        exp_id = registro['exp_id']
        folio = registro['folio']
        
        reply = QMessageBox.question(self, 'Confirmar Reversión', 
                                     f"¿Está seguro de que desea DEVOLVER el expediente {folio} al Archivo de Concentración?\n\nEsta acción borrará su acta de destrucción o transferencia histórica.", 
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                                     
        if reply == QMessageBox.Yes:
            success, msg = self.expediente_service.revertir_destino_final(destino_id, exp_id, folio)
            if success:
                mostrar_mensaje(self, "Reversión Exitosa", msg, QMessageBox.Information)
                self.cargar_historial_destino_final() 
                if hasattr(self, 'buscar_expedientes_en_concentracion'):
                    self.buscar_expedientes_en_concentracion()
            else:
                mostrar_mensaje(self, "Error", msg, QMessageBox.Warning)
    
    def imprimir_formato_baja_lote(self):
        """Genera el Inventario en Excel para el proceso de Destino Final."""
        selected_rows = self.tabla_dictamenes.selectionModel().selectedRows()
        if not selected_rows:
            mostrar_mensaje(self, "Aviso", "Seleccione un lote de la tabla para generar su inventario.", QMessageBox.Warning)
            return
            
        id_lote = int(self.tabla_dictamenes.item(selected_rows[0].row(), 0).text())
        folio = self.tabla_dictamenes.item(selected_rows[0].row(), 1).text()
        tipo_propuesta = self.tabla_dictamenes.item(selected_rows[0].row(), 2).text()
        
        # 1. Traer los IDs ocultos de la base de datos
        ids_expedientes = self.expediente_service.obtener_ids_por_lote_valoracion(id_lote)
        if not ids_expedientes:
            mostrar_mensaje(self, "Error", "Este lote está vacío o hubo un error al leerlo.", QMessageBox.Warning)
            return
            
        # 2. Elegir ruta de guardado
        nombre_default = f"Inventario_{tipo_propuesta.replace(' ', '_')}_{folio}.xlsx"
        ruta_guardado, _ = QFileDialog.getSaveFileName(
            self, "Guardar Inventario", nombre_default, "Archivos de Excel (*.xlsx)"
        )
        
        if ruta_guardado:
            ruta_plantilla = os.path.abspath(os.path.join("templates", "plantilla_destino_final.xlsx"))
            if not os.path.exists(ruta_plantilla):
                QMessageBox.critical(self, "Error", f"No se encontró el archivo '{ruta_plantilla}'.\n\nSolución: Duplica tu plantilla de transferencia y ponle ese nombre.")
                return

            self.statusBar().showMessage(f"Generando inventario para {folio}...")
            self.btn_generar_formato_baja.setEnabled(False)
            
            # --- SELLO DE AUDITORÍA ---
            self.expediente_service.registrar_evento_externo("GENERAR_ACTA_BAJA", f"Se exportó a Excel el Inventario Oficial para el lote {folio} ({tipo_propuesta}) preparándolo para el Comité.")
            
            # 3. Lanzar motor Excel reciclado en segundo plano (DRY!)
            self._ejecutar_en_hilo(
                self.excel_service.generar_inventario_transferencia, # ¡Reciclamos esta función maestra!
                self._on_inventario_baja_finalizado,
                self.expediente_service,
                ids_expedientes,
                ruta_plantilla,
                ruta_guardado
            )

    def _on_inventario_baja_finalizado(self, resultado):
        """Callback silencioso para abrir el Excel cuando esté listo."""
        self.btn_generar_formato_baja.setEnabled(True)
        self.on_exportacion_finalizada(resultado) # Manda la palomita verde
        
        success, ruta = resultado
        if success:
            try:
                import os, platform, subprocess
                if platform.system() == "Windows": os.startfile(ruta)
                elif platform.system() == "Darwin": subprocess.Popen(["open", ruta])
                else: subprocess.Popen(["xdg-open", ruta])
            except Exception as e:
                print(f"No se pudo abrir Excel automáticamente: {e}")
    
    def create_prestamos_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)
        
        title_label = QLabel("CONTROL DE PRÉSTAMOS FÍSICOS ACTIVOS")
        title_label.setObjectName("title_label")
        layout.addWidget(title_label)
        
        btn_group = QGroupBox("Opciones")
        btn_layout = QHBoxLayout(btn_group)
        
        self.btn_actualizar_prestamos = QPushButton("🔄 Actualizar Tabla")
        self.btn_actualizar_prestamos.clicked.connect(self.cargar_prestamos)
        
        btn_layout.addWidget(self.btn_actualizar_prestamos)
        btn_layout.addStretch()
        
        self.tabla_prestamos = QTableWidget()
        self.tabla_prestamos.setColumnCount(PrestamosTab.COLUMN_COUNT)
        self.tabla_prestamos.setHorizontalHeaderLabels([
            "ID Préstamo", "ID Exp.", "Folio", "Asunto", "Clasificación", 
            "Solicitante", "Área", "Fecha Préstamo", "Fecha Límite", "Estatus", "Observaciones", "Acciones"
        ])
        self.tabla_prestamos.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla_prestamos.setSelectionMode(QTableWidget.SingleSelection)
        self.tabla_prestamos.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla_prestamos.setAlternatingRowColors(True)
        self.tabla_prestamos.verticalHeader().setVisible(False)
        self.tabla_prestamos.setWordWrap(True)
        self.tabla_prestamos.verticalHeader().setDefaultSectionSize(60)
        
        header = self.tabla_prestamos.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(PrestamosTab.ASUNTO, QHeaderView.Stretch)
        header.setSectionResizeMode(PrestamosTab.OBSERVACIONES, QHeaderView.Stretch)
        
        self.tabla_prestamos.setColumnHidden(PrestamosTab.EXPEDIENTE_ID, True)
        
        layout.addWidget(btn_group)
        layout.addWidget(self.tabla_prestamos, 1)
        
        self.cargar_prestamos()
        return widget

    def cargar_prestamos(self):
        if not hasattr(self, 'tabla_prestamos'): return
        
        datos = self.expediente_service.obtener_lista_prestamos()
        
        config = [
            {'key': 'prestamo_id', 'type': 'numeric'},
            {'key': 'expediente_id', 'type': 'numeric'},
            {'key': 'folio', 'type': 'text'},
            {'key': 'asunto', 'type': 'text'},
            {'key': 'clasificacion', 'type': 'text'},
            {'key': 'solicitante', 'type': 'text'},
            {'key': 'area_solicitante', 'type': 'text'},
            {'key': 'fecha_prestamo', 'type': 'date'},
            {'key': 'fecha_vencimiento', 'type': 'date'},
            {'key': 'dias_restantes', 'type': 'numeric'}, # Aquí calculamos el estatus
            {'key': 'observaciones', 'type': 'text'},
        ]
        
        self.tabla_prestamos.setUpdatesEnabled(False)
        self._poblar_tabla(self.tabla_prestamos, datos, config, PrestamosTab.ACCIONES, callback_estilo=self._estilos_prestamos)
        self.tabla_prestamos.setUpdatesEnabled(True)

    def _estilos_prestamos(self, item, clave, valor, fila_datos):
        """Pinta de rojo o verde dependiendo de los días restantes."""
        if clave == 'dias_restantes':
            if isinstance(valor, int):
                if valor < 0:
                    item.setText(f"¡VENCIDO! (hace {abs(valor)} días)")
                    item.setForeground(QColor("red"))
                elif valor == 0:
                    item.setText("Vence HOY")
                    item.setForeground(QColor("#d35400")) # Naranja
                else:
                    item.setText(f"A tiempo ({valor} días)")
                    item.setForeground(QColor("green"))
            font = item.font()
            font.setBold(True)
            item.setFont(font)

    def abrir_dialogo_prestamo(self, expediente_id):
        """Abre la ventana para llenar los datos de quién se lleva el expediente."""
        if self.expediente_service.expediente_esta_prestado(expediente_id):
            mostrar_mensaje(self, "Expediente No Disponible", 
                            "Este expediente ya se encuentra prestado físicamente.\n\nDebe registrar su devolución en la pestaña de 'Préstamos Físicos' antes de volver a prestarlo.", 
                            QMessageBox.Warning)
            return

        success, contactos = self.email_service.leer_contactos_excel()
        lista_contactos = contactos if success else []
        dialog = PrestamoDialog(lista_contactos, self)

        if dialog.exec_() == QDialog.Accepted:
            datos = dialog.get_datos()
            fecha_actual = QDate.currentDate().toString("yyyy-MM-dd")
            success, msg = self.expediente_service.registrar_prestamo_fisico(
                expediente_id, datos['solicitante'], datos['area'], 
                fecha_actual, datos['fecha_vencimiento'], datos['observaciones']
            )
            
            if success:
                import os
                self.cargar_expedientes() 
                self.cargar_prestamos()
                QApplication.processEvents()
                datos_exp = self.expediente_service.obtener_datos_expediente(expediente_id)
                clasificacion = datos_exp.get('clasificacion', 'S/C')
                asunto = datos_exp.get('asunto', 'Sin Asunto')
                ruta_plantilla = os.path.abspath(os.path.join("templates", "plantilla_vale_prestamo.xlsx"))
                responsable_archivo = self.expediente_service.usuario_actual
                self.statusBar().showMessage("Generando Vale de Préstamo en Excel... Por favor espere.")
                self.setCursor(Qt.WaitCursor)
                self._ejecutar_en_hilo(
                    self.excel_service.generar_vale_prestamo_desde_plantilla,
                    lambda resultado: self._on_vale_generado(resultado, msg), # Callback
                    ruta_plantilla, clasificacion, asunto, datos['solicitante'], 
                    datos['area'], fecha_actual, datos['fecha_vencimiento'], responsable_archivo
                )
            else:
                mostrar_mensaje(self, "Error", msg, QMessageBox.Warning)
    
    def _on_vale_generado(self, resultado, msg_bd):
        """Callback que se ejecuta cuando el hilo de Excel termina de hacer el Vale."""
        self.unsetCursor()
        self.statusBar().showMessage("Listo")
        excel_ok, mensaje_o_ruta = resultado
        
        if excel_ok:
            mostrar_mensaje(self, "Préstamo Registrado", 
                           f"{msg_bd}\n\nSe ha generado el Vale de Préstamo.", 
                           QMessageBox.Information)
            try:
                if platform.system() == "Windows":
                    os.startfile(mensaje_o_ruta)
                elif platform.system() == "Darwin":
                    subprocess.Popen(["open", mensaje_o_ruta])
                else:
                    subprocess.Popen(["xdg-open", mensaje_o_ruta])
            except Exception as e:
                print(f"Error al abrir Excel automáticamente: {e}")
                self.statusBar().showMessage("El vale se creó, pero no se pudo abrir automáticamente.")
        else:
            mostrar_mensaje(self, "Préstamo Registrado (Sin Vale)", 
                           f"{msg_bd}\n\nADVERTENCIA: No se pudo generar el Vale Excel.\nDetalle: {mensaje_o_ruta}", 
                           QMessageBox.Warning)

    def registrar_devolucion(self, prestamo_id):
        """Marca el préstamo como devuelto."""
        fila = self._buscar_fila_por_id(self.tabla_prestamos, prestamo_id, PrestamosTab.ID_PRESTAMO)
        
        if fila == -1:
            mostrar_mensaje(self, "Error", "No se pudo localizar el registro en la tabla.", QMessageBox.Warning)
            return
        exp_id = int(self.tabla_prestamos.item(fila, PrestamosTab.EXPEDIENTE_ID).text())
        folio = self.tabla_prestamos.item(fila, PrestamosTab.FOLIO).text()
        solicitante = self.tabla_prestamos.item(fila, PrestamosTab.SOLICITANTE).text()
        reply = QMessageBox.question(self, 'Confirmar Devolución', 
                                     f"¿Confirma que {solicitante} ha devuelto físicamente el expediente {folio}?", 
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                                     
        if reply == QMessageBox.Yes:
            success, msg = self.expediente_service.registrar_devolucion_fisica(prestamo_id, exp_id, "Devolución registrada por sistema.")
            if success:
                self.cargar_prestamos()
                self.cargar_expedientes()
                mostrar_mensaje(self, "Devuelto", msg, QMessageBox.Information)
            else:
                mostrar_mensaje(self, "Error", msg, QMessageBox.Warning)
    
    def reimprimir_vale(self, prestamo_id):
        """Genera de nuevo el Vale en Excel en caso de extravío."""
        fila = self._buscar_fila_por_id(self.tabla_prestamos, prestamo_id, PrestamosTab.ID_PRESTAMO)
        if fila == -1: return
        
        clasificacion = self.tabla_prestamos.item(fila, PrestamosTab.CLASIFICACION).text()
        asunto = self.tabla_prestamos.item(fila, PrestamosTab.ASUNTO).text()
        solicitante = self.tabla_prestamos.item(fila, PrestamosTab.SOLICITANTE).text()
        area = self.tabla_prestamos.item(fila, PrestamosTab.AREA).text()
        f_prestamo = self.tabla_prestamos.item(fila, PrestamosTab.FECHA_PRESTAMO).text()
        f_vence = self.tabla_prestamos.item(fila, PrestamosTab.FECHA_VENCIMIENTO).text()
        
        ruta_plantilla = os.path.abspath(os.path.join("templates", "plantilla_vale_prestamo.xlsx"))
        responsable_archivo = self.expediente_service.usuario_actual
        
        excel_ok, mensaje_o_ruta = self.excel_service.generar_vale_prestamo_desde_plantilla(
            ruta_plantilla, clasificacion, asunto, solicitante, area, f_prestamo, f_vence, responsable_archivo
        )
        
        if excel_ok:
            try: os.startfile(mensaje_o_ruta)
            except: pass
        else:
            mostrar_mensaje(self, "Error al Reimprimir", mensaje_o_ruta, QMessageBox.Warning)
            
    def closeEvent(self, event):
        """
        Intercepta el cierre de la ventana (tanto de la 'X' como del menú Archivo -> Salir).
        Garantiza un cierre perfecto, liberando memoria y protegiendo la Base de Datos.
        """
        respuesta = QMessageBox.question(
            self, 'Confirmar Salida', 
            "¿Está seguro de que desea salir del Sistema de Gestión de Expedientes?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if respuesta == QMessageBox.Yes:
            self.statusBar().showMessage("Cerrando conexiones y limpiando memoria...")
            QApplication.processEvents() # Forzar que se pinte el mensaje
            
            try:
                # 1. Vaciar el Pool de Hilos (Evita que tareas pendientes arranquen en la oscuridad)
                from PyQt5.QtCore import QThreadPool
                QThreadPool.globalInstance().clear()
                
                # 2. Cerrar la conexión de la Base de Datos con extrema elegancia
                if hasattr(self, 'expediente_service') and self.expediente_service:
                    self.expediente_service.registrar_evento_externo("LOGOUT", "El usuario cerró sesión y salió del sistema de manera segura.")
                    repo = getattr(self.expediente_service, '_repository', None)
                    if repo:
                        repo.close_connection()
                        
                # 3. (Opcional) Registrar la salida en el log local
                import logging
                logging.info(f"El usuario {self.usuario_actual} ha cerrado el sistema correctamente.")
                
            except Exception as e:
                print(f"Error menor durante el cierre limpio: {e}")
                
            # 4. Conceder el permiso para destruir la ventana y matar el proceso
            event.accept()
        else:
            # 5. El usuario se arrepintió, cancelamos el cierre de la ventana
            event.ignore()