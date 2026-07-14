# -*- coding: utf-8 -*-
# ui/respuestas_dialog.py

import os
import logging
import shutil

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QPushButton, QComboBox, QLineEdit, QDateEdit,
                             QMessageBox, QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView, QWidget, QLabel,QMenu,
                             QAction, QSizePolicy, QGroupBox, QTextEdit, QFrame, QProgressDialog, QApplication,
                             QListWidget)

from PyQt5.QtGui import QIcon, QColor
from PyQt5.QtWidgets import QStyle
from PyQt5.QtCore import Qt, QDate
from datetime import datetime

from constants import CATEGORIAS_DOCUMENTALES, RespuestasDialogTab
from negocio.expediente_service import ExpedienteService
from ui.gestor_anexos_dialog import GestorAnexosDialog
from .seleccionar_cg_dialog import SeleccionarCGDialog
from .custom_widgets import NumericTableWidgetItem
from .pdf_viewer_dialog import PdfViewerDialog
from .dialog_helpers import mostrar_mensaje
from utils.concurrencia import GestorTareas
from negocio.ai_service import AIService

class RespuestasDialog(QDialog):
    def __init__(self, expediente_service: ExpedienteService, expediente_id: int, parent=None):
        super().__init__(parent)
        self.expediente_service = expediente_service
        self.ai_service = AIService()
        self.expediente_id = expediente_id
        self.respuesta_id_actual = None
        self.ruta_pdf_temporal = None 
        
        # --- NUEVO: Carrito para las respuestas ---
        self.rutas_anexos_temporales = set() 
        
        self.setWindowTitle(f"Respuestas del Expediente #{self.expediente_id}")
        self.setGeometry(200, 200, 1200, 750) # Un poco más alto para los nuevos controles
        
        self.init_ui()
        self.connect_signals()
        self.cargar_respuestas_en_tabla()
        
        # Inicializar el estado de la UI
        self.set_form_enabled(False)
        self.configurar_modo_hibrido(is_edit_mode=False)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        title = QLabel(f"RESPUESTAS DEL EXPEDIENTE #{self.expediente_id}")
        title.setObjectName("title_label")
        main_layout.addWidget(title)

        table_group = QGroupBox("Lista de Respuestas")
        table_layout = QVBoxLayout(table_group)
        self.tabla_respuestas = QTableWidget()
        self.configurar_tabla()
        table_layout.addWidget(self.tabla_respuestas)
        main_layout.addWidget(table_group, 1)

        form_group = self.crear_formulario()
        main_layout.addWidget(form_group)

    def configurar_tabla(self):
        self.tabla_respuestas.setColumnCount(RespuestasDialogTab.COLUMN_COUNT)
        self.tabla_respuestas.setHorizontalHeaderLabels(["ID", "Tipo", "Categoría", "Folio", "Fecha", "Asunto", "Carpeta", "Páginas", "Documento", "Clasificación", "Acciones"])
        header = self.tabla_respuestas.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(RespuestasDialogTab.ASUNTO, QHeaderView.Stretch)
        header.setSectionResizeMode(RespuestasDialogTab.DOCUMENTO, QHeaderView.Interactive)
        header.resizeSection(8, 200)
        self.tabla_respuestas.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla_respuestas.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla_respuestas.setSelectionMode(QTableWidget.SingleSelection)
        self.tabla_respuestas.verticalHeader().setVisible(False)
        self.tabla_respuestas.setAlternatingRowColors(True)

    def crear_formulario(self):
        form_group = QGroupBox("Datos de la Respuesta")
        main_form_layout = QVBoxLayout(form_group)
        
        top_bar_layout = QHBoxLayout()
        top_bar_layout.setContentsMargins(0, 0, 0, 0)
        top_bar_layout.addStretch()
        
        self.btn_importar_cg = QPushButton(" Cargar de Gestión")
        self.btn_importar_cg.setObjectName("btn_importar")
        self.btn_importar_cg.setCursor(Qt.PointingHandCursor)
        self.btn_importar_cg.setVisible(False)
        if hasattr(QIcon, "fromTheme"): 
            self.btn_importar_cg.setIcon(QIcon(":/icons/search.png"))             
        self.btn_importar_cg.clicked.connect(self.abrir_seleccion_gestion)        
        top_bar_layout.addWidget(self.btn_importar_cg)
        main_form_layout.addLayout(top_bar_layout)
        
        form_layout = QFormLayout()
        form_layout.setVerticalSpacing(12)
        
        row1_layout = QHBoxLayout()
        self.categoria_documental = QComboBox()
        self.categoria_documental.addItems(CATEGORIAS_DOCUMENTALES)
        self.folio = QLineEdit()
        self.fecha_respuesta = QDateEdit(calendarPopup=True)
        self.fecha_respuesta.setDate(QDate.currentDate())
        self.fecha_respuesta.setDisplayFormat("dd-MM-yyyy")
        self.paginas = QLineEdit()
        
        for label, widget in [("Categoría:", self.categoria_documental), ("Folio:", self.folio), ("Fecha:", self.fecha_respuesta), ("Páginas:", self.paginas)]:
            v = QVBoxLayout()
            v.addWidget(QLabel(label))
            v.addWidget(widget)
            row1_layout.addLayout(v)
        form_layout.addRow(row1_layout)

        self.asunto_respuesta = QTextEdit(self)
        self.asunto_respuesta.setMaximumHeight(80)
        
        form_layout.addRow(QLabel("Asunto de la Respuesta:"))
        
        gemini_icon = QIcon(":/icons/gemini.png")
        self.btn_sugerir_asunto = QPushButton(gemini_icon, " Sugerir Asunto (IA)")
        
        asunto_layout = QHBoxLayout()
        asunto_layout.setSpacing(2)
        asunto_layout.addWidget(self.asunto_respuesta)
        asunto_layout.addWidget(self.btn_sugerir_asunto)
        form_layout.addRow(asunto_layout)

        doc_layout = QHBoxLayout()
        self.documento_respuesta = QLineEdit()
        self.documento_respuesta.setReadOnly(True)
        self.documento_respuesta.setPlaceholderText("Nombre del PDF...")
        
        self.btn_seleccionar_archivo = QPushButton("Adjuntar PDF")
        self.btn_seleccionar_archivo.setObjectName("btn_secondary")
        
        doc_layout.addWidget(self.documento_respuesta)
        doc_layout.addWidget(self.btn_seleccionar_archivo)
        
        form_layout.addRow(QLabel("Documento Principal (PDF):"))
        form_layout.addRow(doc_layout)

        # --- NUEVA SECCIÓN DE ANEXOS HÍBRIDA ---
        anexos_layout = QVBoxLayout()
        self.lbl_anexos = QLabel("Documentos Anexos (Opcional):")
        
        # 1. Carrito (Modo Creación)
        self.lista_anexos_ui = QListWidget()
        self.lista_anexos_ui.setMaximumHeight(70)
        self.lista_anexos_ui.setToolTip("Archivos listos para guardarse")
        
        btn_carrito_layout = QHBoxLayout()
        self.btn_add_anexo = QPushButton("➕ Añadir Anexos")
        self.btn_add_anexo.setObjectName("btn_agregar_anexo")
        self.btn_del_anexo = QPushButton("🗑️ Quitar")
        self.btn_del_anexo.setObjectName("btn_eliminar_anexo")
        btn_carrito_layout.addWidget(self.btn_add_anexo)
        btn_carrito_layout.addWidget(self.btn_del_anexo)
        btn_carrito_layout.addStretch()

        # 2. Gestor (Modo Edición)
        self.btn_gestor_anexos = QPushButton("📁 Abrir Gestor de Anexos")
        self.btn_gestor_anexos.setObjectName("btn_gestor_anexos")
        
        anexos_layout.addWidget(self.lbl_anexos)
        anexos_layout.addWidget(self.lista_anexos_ui)
        anexos_layout.addLayout(btn_carrito_layout)
        anexos_layout.addWidget(self.btn_gestor_anexos)
        
        form_layout.addRow(anexos_layout)
        # ---------------------------------------

        main_form_layout.addLayout(form_layout)
        main_form_layout.addSpacing(20)

        button_layout = QHBoxLayout()
        self.btn_nueva_respuesta = QPushButton("Nueva Respuesta")
        self.btn_nueva_respuesta.setObjectName("btn_nuevo")
        self.btn_guardar = QPushButton("Guardar")
        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.setObjectName("btn_eliminar")
        
        button_layout.addStretch()
        button_layout.addWidget(self.btn_nueva_respuesta)
        button_layout.addWidget(self.btn_guardar)
        button_layout.addWidget(self.btn_cancelar)
        main_form_layout.addLayout(button_layout)
        
        return form_group

    def connect_signals(self):
        self.btn_guardar.clicked.connect(self.guardar_o_crear_respuesta)
        self.btn_nueva_respuesta.clicked.connect(self.preparar_para_crear)
        self.btn_cancelar.clicked.connect(self.reject)
        self.btn_seleccionar_archivo.clicked.connect(self.seleccionar_archivo)
        self.btn_sugerir_asunto.clicked.connect(self.on_sugerir_asunto) 
        
        # Conexiones del carrito y gestor de anexos
        self.btn_add_anexo.clicked.connect(self.agregar_anexos_temporales)
        self.btn_del_anexo.clicked.connect(self.quitar_anexo_temporal)
        self.btn_gestor_anexos.clicked.connect(self.abrir_carpeta_anexos)

    def configurar_modo_hibrido(self, is_edit_mode: bool):
        """Alterna los controles del carrito vs el gestor de anexos."""
        if is_edit_mode:
            self.lista_anexos_ui.setVisible(False)
            self.btn_add_anexo.setVisible(False)
            self.btn_del_anexo.setVisible(False)
            self.btn_gestor_anexos.setVisible(True)
        else:
            self.lista_anexos_ui.setVisible(True)
            self.btn_add_anexo.setVisible(True)
            self.btn_del_anexo.setVisible(True)
            self.btn_gestor_anexos.setVisible(False)

    # --- FUNCIONES DEL CARRITO DE ANEXOS ---
    def agregar_anexos_temporales(self):
        filtro = "Documentos y Comprimidos (*.pdf *.zip *.rar *.7z *.xlsx *.xls *.docx *.doc *.jpg *.png)"
        rutas, _ = QFileDialog.getOpenFileNames(self, "Seleccionar Anexos", "", filtro)
        
        if rutas:
            for ruta in rutas:
                if ruta not in self.rutas_anexos_temporales:
                    self.rutas_anexos_temporales.add(ruta)
                    self.lista_anexos_ui.addItem(os.path.basename(ruta))

    def quitar_anexo_temporal(self):
        item_seleccionado = self.lista_anexos_ui.currentItem()
        if not item_seleccionado: return
        
        nombre_archivo = item_seleccionado.text()
        
        ruta_a_borrar = None
        for ruta in self.rutas_anexos_temporales:
            if os.path.basename(ruta) == nombre_archivo:
                ruta_a_borrar = ruta
                break
                
        if ruta_a_borrar:
            self.rutas_anexos_temporales.remove(ruta_a_borrar)
            
        fila = self.lista_anexos_ui.row(item_seleccionado)
        self.lista_anexos_ui.takeItem(fila)
    # ---------------------------------------

    def cargar_respuestas_en_tabla(self):
        try:
            self.tabla_respuestas.setSortingEnabled(False)
            respuestas = self.expediente_service.obtener_respuestas(self.expediente_id)
            self.tabla_respuestas.setRowCount(0)
            self.tabla_respuestas.setRowCount(len(respuestas))
            for i, data in enumerate(respuestas):

                self.tabla_respuestas.setItem(i, RespuestasDialogTab.ID, NumericTableWidgetItem(str(data.get('id')), data.get('id')))
                self.tabla_respuestas.setItem(i, RespuestasDialogTab.PAGINAS, NumericTableWidgetItem(str(data.get('paginas')), data.get('paginas')))
                self.tabla_respuestas.setItem(i, RespuestasDialogTab.TIPO, QTableWidgetItem(data.get('tipo_documento')))
                self.tabla_respuestas.setItem(i, RespuestasDialogTab.CATEGORIA, QTableWidgetItem(data.get('categoria_documental')))
                self.tabla_respuestas.setItem(i, RespuestasDialogTab.FOLIO, QTableWidgetItem(data.get('folio')))
                self.tabla_respuestas.setItem(i, RespuestasDialogTab.ASUNTO, QTableWidgetItem(data.get('asunto_respuesta')))
                self.tabla_respuestas.setItem(i, RespuestasDialogTab.CARPETA, QTableWidgetItem(data.get('carpeta')))
                self.tabla_respuestas.setItem(i, RespuestasDialogTab.DOCUMENTO, QTableWidgetItem(data.get('documento_respuesta')))
                self.tabla_respuestas.setItem(i, RespuestasDialogTab.CLASIFICACION, QTableWidgetItem(data.get('clasificacion')))
                fecha_db = data.get('fecha_respuesta')
                fecha_formateada = ""
                if fecha_db:
                    try: 
                        fecha_formateada = datetime.strptime(fecha_db, '%Y-%m-%d').strftime('%d-%m-%Y')
                    except ValueError: 
                        fecha_formateada = fecha_db
                self.tabla_respuestas.setItem(i, RespuestasDialogTab.FECHA, QTableWidgetItem(fecha_formateada))
                self.crear_boton_acciones(i, data)
            
            self.tabla_respuestas.setSortingEnabled(True)
        except Exception as e:
            mostrar_mensaje(self, "Error", f"No se pudieron cargar las respuestas: {str(e)}", QMessageBox.Critical)

    def crear_boton_acciones(self, row, data):
        respuesta_id = data.get("id")
        documento_path = data.get("documento_respuesta")

        menu_btn = QPushButton()
        menu_btn.setIcon(self.style().standardIcon(getattr(QStyle, 'SP_FileDialogDetailedView')))
        menu_btn.setObjectName("action_menu_btn")
        menu = QMenu(self)
        
        ver_action = menu.addAction("📄 Ver Documento")
        ver_action.triggered.connect(lambda: self.ver_documento(documento_path))
        
        editar_action = menu.addAction("📝 Editar")
        editar_action.triggered.connect(lambda: self.preparar_para_editar(data))
        
        eliminar_action = menu.addAction("🗑️ Eliminar")
        eliminar_action.triggered.connect(lambda: self.eliminar_respuesta(respuesta_id))

        if not documento_path or not str(documento_path).strip():
            ver_action.setEnabled(False)

        menu_btn.setMenu(menu)
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(menu_btn)
        layout.setAlignment(Qt.AlignCenter)
        self.tabla_respuestas.setCellWidget(row, RespuestasDialogTab.ACCIONES, container)

    def guardar_o_crear_respuesta(self):
        datos_formulario = {
            'categoria_documental': self.categoria_documental.currentText(),
            'folio': self.folio.text().strip(),
            'fecha_respuesta': self.fecha_respuesta.date().toString("yyyy-MM-dd"),
            'asunto_respuesta': self.asunto_respuesta.toPlainText().strip(),
            'paginas': self.paginas.text().strip(),
            'documento_respuesta': self.documento_respuesta.text().strip()
        }
        
        es_modo_edicion = (self.respuesta_id_actual is not None)
        success, resultado = self.expediente_service.guardar_respuesta(datos_formulario, self.expediente_id, self.respuesta_id_actual)
        
        if success:
            resp_id = resultado 
            
            # --- PASO 1: GUARDAR EL PDF PRINCIPAL ---
            if self.ruta_pdf_temporal and os.path.exists(self.ruta_pdf_temporal):
                try:
                    if es_modo_edicion:
                        datos_viejos = self.expediente_service.obtener_datos_respuesta(resp_id)
                        ruta_vieja_relativa = datos_viejos.get('documento_respuesta') if datos_viejos else None
                        if ruta_vieja_relativa:
                            ruta_vieja_absoluta = os.path.abspath(os.path.join(os.getcwd(), ruta_vieja_relativa))
                            if os.path.exists(ruta_vieja_absoluta):
                                os.remove(ruta_vieja_absoluta)

                    carpeta_destino = os.path.abspath(os.path.join(os.getcwd(), "documentos", f"EXP_{self.expediente_id}", "respuestas", f"RES_{resp_id}"))
                    os.makedirs(carpeta_destino, exist_ok=True)
                    
                    nombre_archivo = os.path.basename(self.ruta_pdf_temporal)
                    ruta_destino = os.path.join(carpeta_destino, nombre_archivo)
                    
                    if self.ruta_pdf_temporal != ruta_destino:
                        shutil.copy2(self.ruta_pdf_temporal, ruta_destino)
                    
                    ruta_relativa = os.path.join("documentos", f"EXP_{self.expediente_id}", "respuestas", f"RES_{resp_id}", nombre_archivo).replace("\\", "/")
                    datos_formulario["documento_respuesta"] = ruta_relativa
                    self.expediente_service._repository.update_respuesta(resp_id, datos_formulario)
                    
                except Exception as e:
                    logging.error("Error al mover/borrar PDF de respuesta: %s", e)

            # --- PASO 2: GUARDAR LOS ANEXOS DEL CARRITO (Solo Creación) ---
            if not es_modo_edicion and self.rutas_anexos_temporales:
                carpeta_anexos = os.path.abspath(os.path.join(os.getcwd(), "documentos", f"EXP_{self.expediente_id}", "respuestas", f"RES_{resp_id}", "anexos_respuesta"))
                os.makedirs(carpeta_anexos, exist_ok=True)
                
                for ruta_anexo in self.rutas_anexos_temporales:
                    if os.path.exists(ruta_anexo):
                        try:
                            shutil.copy2(ruta_anexo, os.path.join(carpeta_anexos, os.path.basename(ruta_anexo)))
                        except Exception as e:
                            logging.error("Error al copiar el anexo %s: %s", ruta_anexo, e)

            mostrar_mensaje(self,"Éxito", "Respuesta guardada correctamente.", QMessageBox.Information)
            self.cargar_respuestas_en_tabla()
            self.limpiar_formulario()
            self.set_form_enabled(False)
        else:
            mostrar_mensaje(self, "Error al guardar", str(resultado), QMessageBox.Warning)

    def eliminar_respuesta(self, respuesta_id: int):
        reply = QMessageBox.question(self, 'Confirmar', '¿Seguro que desea eliminar esta respuesta y sus archivos físicos?', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            success, message = self.expediente_service.eliminar_respuesta(respuesta_id)
            if success:
                mostrar_mensaje(self,"Éxito", message, QMessageBox.Information)
                self.limpiar_formulario()
                self.cargar_respuestas_en_tabla()
            else:
                mostrar_mensaje(self,"Error", message, QMessageBox.Warning)
    
    def limpiar_formulario(self):
        self.respuesta_id_actual = None
        self.ruta_pdf_temporal = None
        self.rutas_anexos_temporales.clear()
        self.lista_anexos_ui.clear()
        
        self.categoria_documental.setCurrentIndex(0)
        self.folio.clear()
        self.fecha_respuesta.setDate(QDate.currentDate())
        self.asunto_respuesta.clear()
        self.paginas.clear()
        self.documento_respuesta.clear()
        self.tabla_respuestas.clearSelection()
    
    def set_form_enabled(self, enabled: bool):
        self.categoria_documental.setEnabled(enabled)
        self.folio.setEnabled(enabled)
        self.fecha_respuesta.setEnabled(enabled)
        self.paginas.setEnabled(enabled)
        self.asunto_respuesta.setEnabled(enabled)
        self.documento_respuesta.setEnabled(enabled)
        
        self.btn_seleccionar_archivo.setEnabled(enabled)
        self.btn_add_anexo.setEnabled(enabled)
        self.btn_del_anexo.setEnabled(enabled)
        self.btn_gestor_anexos.setEnabled(enabled)
        
        self.btn_guardar.setEnabled(enabled)
        self.btn_nueva_respuesta.setVisible(not enabled)
        
        if not enabled:
            self.btn_importar_cg.setVisible(False)
            self.btn_guardar.setText("Guardar")
            self.configurar_modo_hibrido(is_edit_mode=False) # Se resetea visualmente al estado default
    
    def preparar_para_crear(self):
        self.limpiar_formulario()
        self.btn_guardar.setText("Crear Respuesta")
        self.set_form_enabled(True)
        self.configurar_modo_hibrido(is_edit_mode=False)
        self.categoria_documental.setFocus()
        self.btn_importar_cg.setVisible(True)

    def preparar_para_editar(self, data: dict):
        self.respuesta_id_actual = data.get('id')
        self.ruta_pdf_temporal = None
        
        self.categoria_documental.setCurrentText(data.get('categoria_documental', ''))
        self.folio.setText(data.get('folio', ''))
        self.fecha_respuesta.setDate(QDate.fromString(data.get('fecha_respuesta', ''), "yyyy-MM-dd"))
        self.asunto_respuesta.setPlainText(data.get('asunto_respuesta', ''))
        self.paginas.setText(str(data.get('paginas', '')))
        self.documento_respuesta.setText(data.get('documento_respuesta', ''))
        
        self.btn_guardar.setText("Guardar Cambios")
        self.set_form_enabled(True)
        self.configurar_modo_hibrido(is_edit_mode=True)
        self.btn_importar_cg.setVisible(False)
    
    def seleccionar_archivo(self):
        ruta_origen, _ = QFileDialog.getOpenFileName(self, "Seleccionar Documento de Respuesta", "", "Archivos PDF (*.pdf)")
        if not ruta_origen: return
        
        self.ruta_pdf_temporal = ruta_origen
        self.documento_respuesta.setText(os.path.basename(ruta_origen))

    def abrir_carpeta_anexos(self):
        """Abre el gestor de anexos para administrar archivos reales de una respuesta ya guardada."""
        ruta_carpeta = os.path.abspath(os.path.join(os.getcwd(), "documentos", f"EXP_{self.expediente_id}", "respuestas", f"RES_{self.respuesta_id_actual}", "anexos_respuesta"))
        dialogo_anexos = GestorAnexosDialog(ruta_carpeta, self)
        dialogo_anexos.exec_()

    def ver_documento(self, ruta_documento):
        if not ruta_documento or not os.path.exists(ruta_documento):
            mostrar_mensaje(self, "Error", "El archivo no existe o la ruta no es válida.", QMessageBox.Warning)
            return
        try:
            dialogo_visor = PdfViewerDialog(ruta_documento, self)
            dialogo_visor.exec_()
        except Exception as e:
            mostrar_mensaje(self, "Error", f"No se pudo abrir el archivo:\n{str(e)}", QMessageBox.Critical)
    
    def on_sugerir_asunto(self):
        ruta_doc_respuesta = self.ruta_pdf_temporal if self.ruta_pdf_temporal else self.documento_respuesta.text()
        
        if not ruta_doc_respuesta:
           mostrar_mensaje(self, "Información Faltante", "Por favor, selecciona primero el PDF (Adjuntar PDF) para que la IA lo lea.", QMessageBox.Warning)
           return
        
        datos_expediente_padre = self.expediente_service.obtener_datos_expediente(self.expediente_id)
        if not datos_expediente_padre: return
       
        codigo_serie = datos_expediente_padre.get('serie_documental')
        if not codigo_serie: return
       
        self.btn_sugerir_asunto.setEnabled(False)
       
        info_serie = self.expediente_service.obtener_info_serie(codigo_serie)
        nombre_serie = info_serie.get('nombre_serie', '') if info_serie else codigo_serie
        success_serie, ruta_pdf_serie = self.expediente_service.obtener_ruta_pdf_serie(codigo_serie)
   
        self.progress = QProgressDialog("Analizando documento con IA de Google Gemini...\nPor favor, espere.", None, 0, 0, self)
        self.progress.setWindowTitle("Inteligencia Artificial")
        self.progress.setModal(True)
        self.progress.show()
   
        GestorTareas.ejecutar_en_segundo_plano(
            self._procesar_ia_en_fondo,
            self._on_ia_finalizada,
            ruta_doc_respuesta,
            ruta_pdf_serie if success_serie else None,
            nombre_serie
        )

    def _procesar_ia_en_fondo(self, ruta_doc_respuesta: str, ruta_pdf_serie: str, nombre_serie: str):
        """Delega absolutamente todo al AI Service en el ThreadPool"""
        import os
        
        if not os.path.isabs(ruta_doc_respuesta): 
            ruta_doc_respuesta = os.path.join(os.getcwd(), ruta_doc_respuesta)
            
        # Magia Pura: El Servicio se encarga de subirlo, escanearlo y destruirlo remotamente.
        success, resultado = self.ai_service.analizar_documento_para_asunto(
            ruta_documento=ruta_doc_respuesta, 
            ruta_pdf_serie=ruta_pdf_serie, 
            nombre_serie=nombre_serie
        )
        return success, resultado

    def _on_ia_finalizada(self, resultado_tarea):
        self.progress.close()
        self.btn_sugerir_asunto.setEnabled(True)
        
        success, resultado = resultado_tarea
   
        if success and resultado:
            dialogo_opciones = QDialog(self)
            dialogo_opciones.setWindowTitle("Elige una Sugerencia de la IA")
            dialogo_opciones.setFixedSize(650, 250)
            
            layout = QVBoxLayout(dialogo_opciones)
            layout.addWidget(QLabel("Doble clic en la sugerencia que deseas utilizar:"))
            
            lista_sugerencias = QListWidget()
            lista_sugerencias.setWordWrap(True)
            lista_sugerencias.addItems(resultado)
            lista_sugerencias.itemDoubleClicked.connect(lambda item: (self.asunto_respuesta.setPlainText(item.text()), dialogo_opciones.accept()))
            
            layout.addWidget(lista_sugerencias)
            dialogo_opciones.exec_()
        else:
            mostrar_mensaje(self, "Error de IA", str(resultado), QMessageBox.Critical)
    
    def abrir_seleccion_gestion(self):
        dialog = SeleccionarCGDialog(self.expediente_service, self)
        if dialog.exec_() == QDialog.Accepted:
            datos = dialog.seleccionado
            if datos:
                if datos.get('folio'): self.folio.setText(datos['folio'])
                if datos.get('asunto'): self.asunto_respuesta.setPlainText(datos['asunto'])
                fecha_str = datos.get('fecha_documento')
                if fecha_str:
                    qdate = QDate.fromString(fecha_str, "yyyy-MM-dd")
                    if not qdate.isValid(): qdate = QDate.fromString(fecha_str, "dd/MM/yyyy")
                    if qdate.isValid(): self.fecha_respuesta.setDate(qdate)
                mostrar_mensaje(self, "Datos Cargados", "La información se importó correctamente desde Control de Gestión.")