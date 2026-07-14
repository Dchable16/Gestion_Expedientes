# -*- coding: utf-8 -*-
# ui/nuevo_expediente_dialog.py

import platform
import subprocess
import logging
import shutil
import os

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QPushButton, QComboBox, QLineEdit,
                            QDateEdit, QMessageBox, QFileDialog, QFrame, QGroupBox, QLabel, QTextEdit,
                            QProgressDialog, QApplication, QListWidget)

from PyQt5.QtGui import QPalette, QColor, QIcon
from PyQt5.QtCore import Qt, QDate

from constants import (CATEGORIAS_DOCUMENTALES, TIPOS_DOCUMENTO, SERIES_DOCUMENTALES)
from negocio.expediente_service import ExpedienteService
from .seleccionar_cg_dialog import SeleccionarCGDialog
from ui.gestor_anexos_dialog import GestorAnexosDialog
from .dialog_helpers import mostrar_mensaje
from utils.concurrencia import GestorTareas
from negocio.ai_service import AIService


class NuevoExpedienteDialog(QDialog):
    def __init__(self, expediente_service: ExpedienteService, parent=None, expediente_id=None):
        super().__init__(parent)
        self.expediente_id = expediente_id
        self.expediente_service = expediente_service
        self.ai_service = AIService()
        self.is_edit_mode = (expediente_id is not None)
        self._last_autofilled_asunto = ""
        self.ruta_pdf_temporal = None 
        
        # --- NUEVO: El carrito invisible para los anexos ---
        self.rutas_anexos_temporales = set() 
        
        self.setWindowTitle("Nuevo Expediente" if not expediente_id else "Editar Expediente")
        self.setGeometry(200, 200, 800, 600) # Ligeramente más alto para el recuadro
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)
        
        self.init_ui()

        if self.expediente_id:
            self.cargar_datos_expediente()

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        header_layout = QHBoxLayout()
        title_text = "DATOS DEL EXPEDIENTE" if not self.expediente_id else "EDITAR EXPEDIENTE"
        title = QLabel(title_text)
        title.setObjectName("title_label")
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        self.btn_importar_cg = QPushButton(" Cargar de Gestión")
        self.btn_importar_cg.setObjectName("btn_importar")
        if hasattr(QIcon, "fromTheme"):
             self.btn_importar_cg.setIcon(QIcon(":/icons/search.png"))        
        self.btn_importar_cg.setToolTip("Buscar y cargar datos desde Control de Gestión")
        self.btn_importar_cg.setCursor(Qt.PointingHandCursor)
        self.btn_importar_cg.clicked.connect(self.abrir_seleccion_gestion)
        header_layout.addWidget(self.btn_importar_cg)
        main_layout.addLayout(header_layout)
        
        info_group = QGroupBox("Información General")
        form_layout = QFormLayout()
        form_layout.setVerticalSpacing(12)
        form_layout.setHorizontalSpacing(20)
        form_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        info_group.setLayout(form_layout)

        row1_layout = QHBoxLayout()
        tipo_doc_layout = QVBoxLayout()
        tipo_doc_label = QLabel("Tipo de Documento:")
        self.tipo_documento = QComboBox()
        self.tipo_documento.addItems(TIPOS_DOCUMENTO)
        tipo_doc_layout.addWidget(tipo_doc_label)
        tipo_doc_layout.addWidget(self.tipo_documento)
        
        cat_doc_layout = QVBoxLayout()
        cat_doc_label = QLabel("Categoría Documental:")
        self.categoria_documental = QComboBox()
        self.categoria_documental.addItems(CATEGORIAS_DOCUMENTALES)
        cat_doc_layout.addWidget(cat_doc_label)
        cat_doc_layout.addWidget(self.categoria_documental)
        
        row1_layout.addLayout(tipo_doc_layout)
        row1_layout.addLayout(cat_doc_layout)
        form_layout.addRow(row1_layout)
        
        row2_layout = QHBoxLayout()
        folio_layout = QVBoxLayout()
        folio_label = QLabel("Folio:")
        self.folio = QLineEdit()
        folio_layout.addWidget(folio_label)
        folio_layout.addWidget(self.folio)
        
        fecha_layout = QVBoxLayout()
        fecha_label = QLabel("Fecha:")
        self.fecha = QDateEdit(calendarPopup=True)
        self.fecha.setDate(QDate.currentDate())
        self.fecha.setDisplayFormat("dd-MM-yyyy")
        fecha_layout.addWidget(fecha_label)
        fecha_layout.addWidget(self.fecha)
        
        row2_layout.addLayout(folio_layout)
        row2_layout.addLayout(fecha_layout)
        form_layout.addRow(row2_layout)
        
        asunto_layout_vertical = QVBoxLayout()
        asunto_label = QLabel("Asunto:")
        self.asunto = QTextEdit(self)
        self.asunto.setMaximumHeight(80)
        
        gemini_icon = QIcon(":/icons/gemini.png")
        self.btn_sugerir_asunto = QPushButton(gemini_icon, " Sugerir Asunto (IA)")
        
        asunto_input_layout = QHBoxLayout()
        asunto_input_layout.setSpacing(2)
        asunto_input_layout.addWidget(self.asunto)
        asunto_input_layout.addWidget(self.btn_sugerir_asunto)
        
        asunto_layout_vertical.addWidget(asunto_label)
        asunto_layout_vertical.addLayout(asunto_input_layout)
        form_layout.addRow(asunto_layout_vertical)
        
        row4_layout = QHBoxLayout()
        serie_layout = QVBoxLayout()
        serie_label = QLabel("Serie Documental:")
        self.serie_documental = QComboBox()
        self.serie_documental.addItems(SERIES_DOCUMENTALES)
        serie_layout.addWidget(serie_label)
        serie_layout.addWidget(self.serie_documental)
        
        carpeta_layout = QVBoxLayout()
        carpeta_label = QLabel("Carpeta Física:")
        self.carpeta = QLineEdit()
        carpeta_layout.addWidget(carpeta_label)
        carpeta_layout.addWidget(self.carpeta)
        
        paginas_layout = QVBoxLayout()
        paginas_label = QLabel("Páginas:")
        self.paginas = QLineEdit()
        paginas_layout.addWidget(paginas_label)
        paginas_layout.addWidget(self.paginas)
        
        row4_layout.addLayout(serie_layout)
        row4_layout.addLayout(carpeta_layout)
        row4_layout.addLayout(paginas_layout)
        form_layout.addRow(row4_layout)
        
        row5_layout = QHBoxLayout()
        doc_layout = QVBoxLayout()
        self.lbl_doc_principal = QLabel("Documento Principal (PDF):")
        
        doc_input_layout = QHBoxLayout()
        self.documento_respaldo = QLineEdit()
        self.documento_respaldo.setReadOnly(True)
        self.btn_seleccionar_archivo = QPushButton("Adjuntar PDF")
        self.btn_seleccionar_archivo.setObjectName("btn_secondary")
        
        doc_input_layout.addWidget(self.documento_respaldo)
        doc_input_layout.addWidget(self.btn_seleccionar_archivo)
        
        doc_layout.addWidget(self.lbl_doc_principal)
        doc_layout.addLayout(doc_input_layout)
        row5_layout.addLayout(doc_layout)
        form_layout.addRow(row5_layout)

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
        
        main_layout.addWidget(info_group)
        
        button_container = QFrame()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 20, 0, 0)
        
        self.btn_guardar = QPushButton("Guardar")
        self.btn_guardar.setMinimumWidth(120)
        button_layout.addStretch()
        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.setObjectName("btn_cancelar")
        self.btn_cancelar.setMinimumWidth(120)
        
        button_layout.addWidget(self.btn_guardar)
        button_layout.addWidget(self.btn_cancelar)
        
        main_layout.addWidget(button_container)
        main_layout.addStretch()
        self.setLayout(main_layout)
        
        # --- CONEXIONES ---
        self.btn_guardar.clicked.connect(self.guardar_expediente)
        self.btn_cancelar.clicked.connect(self.reject)
        self.btn_seleccionar_archivo.clicked.connect(self.seleccionar_archivo)
        self.btn_sugerir_asunto.clicked.connect(self.on_sugerir_asunto)
        
        # Conexiones de la nueva sección de Anexos
        self.btn_add_anexo.clicked.connect(self.agregar_anexos_temporales)
        self.btn_del_anexo.clicked.connect(self.quitar_anexo_temporal)
        self.btn_gestor_anexos.clicked.connect(self.abrir_carpeta_anexos)
        
        self.tipo_documento.currentTextChanged.connect(self.on_tipo_documento_change)
        self.fecha.dateChanged.connect(self.on_fecha_change)
        
        self.tipo_documento.setFocus()
        self.on_tipo_documento_change(self.tipo_documento.currentText())
        self.serie_documental.currentTextChanged.connect(self.on_serie_seleccionada)

        self.configurar_modo_hibrido()

    def configurar_modo_hibrido(self):
        """Muestra u oculta controles dependiendo si estamos creando o editando."""
        if self.is_edit_mode:
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
        # Filtro estricto: Solo documentos y comprimidos
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
        
        # Eliminar del set oculto
        ruta_a_borrar = None
        for ruta in self.rutas_anexos_temporales:
            if os.path.basename(ruta) == nombre_archivo:
                ruta_a_borrar = ruta
                break
                
        if ruta_a_borrar:
            self.rutas_anexos_temporales.remove(ruta_a_borrar)
            
        # Eliminar de la interfaz visual
        fila = self.lista_anexos_ui.row(item_seleccionado)
        self.lista_anexos_ui.takeItem(fila)
    # ---------------------------------------

    def on_tipo_documento_change(self, tipo):
        es_conocimiento = (tipo == "Conocimiento")
        campos_expediente_normal = [self.serie_documental, self.categoria_documental, 
                                    self.paginas, self.documento_respaldo, self.btn_seleccionar_archivo]
        campos_autogenerados = [self.folio, self.asunto]
    
        if es_conocimiento:
            for campo in campos_expediente_normal: campo.setEnabled(False)
            for campo in campos_autogenerados: campo.setReadOnly(True)
            self.fecha.setEnabled(True)
            self.carpeta.setEnabled(True)
            
            if self.is_edit_mode:
                self.fecha.setEnabled(False)
                self.btn_guardar.setEnabled(True)
            else:
                self.on_fecha_change(self.fecha.date())
        else:
            for campo in campos_expediente_normal: campo.setEnabled(True)
            for campo in campos_autogenerados:
                campo.setReadOnly(False)
                if not self.is_edit_mode: campo.setText("")
            
            self.fecha.setEnabled(True)
            self.carpeta.setEnabled(True)
            self.btn_guardar.setEnabled(True)
    
    def limpiar_y_deshabilitar_campos(self):
        self.folio.clear()
        self.asunto.clear()
        self.carpeta.clear()
        self.paginas.clear()
        self.documento_respaldo.clear()
        
        # Limpiar carritos
        self.ruta_pdf_temporal = None
        self.rutas_anexos_temporales.clear()
        self.lista_anexos_ui.clear()
        
        campos_a_deshabilitar = [self.categoria_documental, self.folio, self.asunto, 
                                  self.paginas, self.documento_respaldo, 
                                  self.btn_seleccionar_archivo, self.carpeta, self.btn_guardar,
                                  self.btn_add_anexo, self.btn_del_anexo]
        for campo in campos_a_deshabilitar:
            campo.setEnabled(False)

    def on_fecha_change(self, qdate):
        if self.is_edit_mode or self.tipo_documento.currentText() != "Conocimiento":
            return
        anio = qdate.year()
        resultado = self.expediente_service.buscar_expediente_conocimiento_por_anio(anio)

        if resultado["existe"]:
            datos = resultado["datos"]
            self.btn_guardar.setEnabled(False)
            QMessageBox.warning(self, "Expediente Existente",
                                  f"Ya existe un archivo de conocimiento para el año {anio} (Folio: {datos['folio']}).\n"
                                  "Use la opción 'Respuestas' para añadirle documentos.")
        else:
            self.btn_guardar.setEnabled(True)
            self.folio.setText(f"CONOC-{anio}")
            self.asunto.setText(f"DOCUMENTACIÓN DE CONOCIMIENTO {anio}")

    def cargar_datos_expediente(self):
        data = self.expediente_service.obtener_datos_expediente(self.expediente_id)
        if data:
            self.tipo_documento.blockSignals(True)
            self.fecha.blockSignals(True)

            self.tipo_documento.setCurrentText(data.get('tipo_documento', ''))
            self.categoria_documental.setCurrentText(data.get('categoria_documental', ''))
            self.folio.setText(data.get('folio', ''))
            if data.get('fecha'):
                self.fecha.setDate(QDate.fromString(data.get('fecha'), "yyyy-MM-dd"))
            self.asunto.setPlainText(data.get('asunto', ''))
            self.serie_documental.setCurrentText(data.get('serie_documental', ''))
            self.carpeta.setText(data.get('carpeta', ''))
            self.paginas.setText(str(data.get('paginas', '')))
            self.documento_respaldo.setText(data.get('documento_respaldo', ''))

            self.tipo_documento.blockSignals(False)
            self.fecha.blockSignals(False)
            self.on_tipo_documento_change(data.get('tipo_documento', ''))
        else:
            mostrar_mensaje(self, "Error", f"No se encontró el expediente con ID {self.expediente_id}", QMessageBox.Critical)
            self.reject()

    def guardar_expediente(self):
        try:
            if not self.is_edit_mode and self.tipo_documento.currentText() == "Conocimiento":
                anio = self.fecha.date().year()
                carpeta = self.carpeta.text().strip()
                if not carpeta:
                    mostrar_mensaje(self, "Campo Requerido", "La carpeta no puede estar vacía.", QMessageBox.Warning)
                    return
                success, message = self.expediente_service.obtener_o_crear_expediente_conocimiento_anual(anio, carpeta)
                if success:
                    mostrar_mensaje(self, "Éxito", f"Expediente maestro 'Conocimiento {anio}' creado.", QMessageBox.Information)
                    self.accept()
                else:
                    mostrar_mensaje(self, "Error", message, QMessageBox.Warning)
                return 

            # Recolectar datos y mandarlos al servicio
            datos_a_guardar = self.recolectar_datos_formulario()
            success, resultado = self.expediente_service.guardar_expediente(datos_a_guardar, self.expediente_id)
    
            if success:
                exp_id = resultado # El servicio ahora nos devuelve el ID
                
                # --- PASO 1: GUARDAR EL PDF PRINCIPAL ---
                if self.ruta_pdf_temporal and os.path.exists(self.ruta_pdf_temporal):
                    try:
                        if self.is_edit_mode:
                            datos_viejos = self.expediente_service.obtener_datos_expediente(self.expediente_id)
                            ruta_vieja_relativa = datos_viejos.get('documento_respaldo') if datos_viejos else None
                            if ruta_vieja_relativa:
                                ruta_vieja_absoluta = os.path.abspath(os.path.join(os.getcwd(), ruta_vieja_relativa))
                                if os.path.exists(ruta_vieja_absoluta):
                                    os.remove(ruta_vieja_absoluta)

                        carpeta_destino = os.path.abspath(os.path.join(os.getcwd(), "documentos", f"EXP_{exp_id}"))
                        os.makedirs(carpeta_destino, exist_ok=True)
                        
                        nombre_archivo = os.path.basename(self.ruta_pdf_temporal)
                        ruta_destino = os.path.join(carpeta_destino, nombre_archivo)
                        
                        if self.ruta_pdf_temporal != ruta_destino:
                            shutil.copy2(self.ruta_pdf_temporal, ruta_destino)
                        
                        ruta_relativa = os.path.join("documentos", f"EXP_{exp_id}", nombre_archivo).replace("\\", "/")
                        datos_a_guardar["documento_respaldo"] = ruta_relativa
                        self.expediente_service._repository.update_expediente(datos_a_guardar, exp_id)
                        
                    except Exception as e:
                        logging.error("Error al mover/borrar el PDF principal: %s", e)

                # --- PASO 2: GUARDAR LOS ANEXOS DEL CARRITO (Solo Creación) ---
                if not self.is_edit_mode and self.rutas_anexos_temporales:
                    carpeta_anexos = os.path.abspath(os.path.join(os.getcwd(), "documentos", f"EXP_{exp_id}", "anexos_principales"))
                    os.makedirs(carpeta_anexos, exist_ok=True)
                    
                    for ruta_anexo in self.rutas_anexos_temporales:
                        if os.path.exists(ruta_anexo):
                            try:
                                shutil.copy2(ruta_anexo, os.path.join(carpeta_anexos, os.path.basename(ruta_anexo)))
                            except Exception as e:
                                logging.error("Error al copiar el anexo %s: %s", ruta_anexo, e)
                
                mensaje_exito = "Expediente actualizado correctamente." if self.is_edit_mode else "Expediente creado con éxito."
                mostrar_mensaje(self, "Éxito", mensaje_exito, QMessageBox.Information)
                self.accept()
            else:
                mostrar_mensaje(self, "Error al Guardar", str(resultado), QMessageBox.Warning)
    
        except Exception as e:
            logging.error("Ocurrió un error en guardar_expediente: %s", e, exc_info=True)
            mostrar_mensaje(self, "Error Inesperado", f"Ocurrió un error: {str(e)}", QMessageBox.Critical)
    
    def recolectar_datos_formulario(self):
        return {
            "tipo_documento": self.tipo_documento.currentText(),
            "categoria_documental": self.categoria_documental.currentText(),
            "folio": self.folio.text().strip(),
            "fecha": self.fecha.date().toString("yyyy-MM-dd"),
            "asunto": self.asunto.toPlainText().strip(),
            "serie_documental": self.serie_documental.currentText(),
            "carpeta": self.carpeta.text().strip(),
            "paginas": self.paginas.text().strip(),
            "documento_respaldo": self.documento_respaldo.text().strip()
        }

    def seleccionar_archivo(self):  
        """Solo escoge el archivo temporalmente."""
        ruta_origen, _ = QFileDialog.getOpenFileName(self, "Seleccionar Documento Principal (PDF)", "", "Archivos PDF (*.pdf)")
        if not ruta_origen:
            return
        
        self.ruta_pdf_temporal = ruta_origen
        self.documento_respaldo.setText(os.path.basename(ruta_origen))
    
    def abrir_carpeta_anexos(self):
        """Abre el gestor de anexos para editar archivos."""
        ruta_carpeta = os.path.abspath(os.path.join(os.getcwd(), "documentos", f"EXP_{self.expediente_id}", "anexos_principales"))
        dialogo_anexos = GestorAnexosDialog(ruta_carpeta, self)
        dialogo_anexos.exec_()
    
    def handle_tipo_documento_change(self, tipo):
        is_conocimiento = (tipo == "Conocimiento")
        self.serie_documental.setEnabled(not is_conocimiento)
        
        palette = self.serie_documental.palette()
        bg_color = QColor(240, 240, 240) if is_conocimiento else QColor(255, 255, 255)
        palette.setColor(QPalette.Base, bg_color)
        self.serie_documental.setPalette(palette)
        
        if is_conocimiento:
            self.serie_documental.setCurrentIndex(-1)
            mostrar_mensaje(self, "Información", "Para documentos de tipo Conocimiento no se permiten respuestas.", QMessageBox.Information)
            
    def on_serie_seleccionada(self, codigo_serie_seleccionado: str):
        current_asunto = self.asunto.toPlainText().strip()
        nuevo_nombre_serie = ""
        
        if codigo_serie_seleccionado and codigo_serie_seleccionado != "Conocimiento":
            nuevo_nombre_serie = self.expediente_service.obtener_nombre_serie(codigo_serie_seleccionado)
            if nuevo_nombre_serie:
                nuevo_nombre_serie = nuevo_nombre_serie.strip().upper()

        if not current_asunto or current_asunto == self._last_autofilled_asunto:
            self.asunto.setPlainText(nuevo_nombre_serie)
        else:
            if self._last_autofilled_asunto and current_asunto.startswith(self._last_autofilled_asunto):
                resto_del_asunto = current_asunto[len(self._last_autofilled_asunto):].strip()
                if resto_del_asunto.startswith("-"):
                    resto_del_asunto = resto_del_asunto[1:].strip()
                
                if nuevo_nombre_serie:
                    self.asunto.setPlainText(f"{nuevo_nombre_serie} - {resto_del_asunto}")
                else:
                    self.asunto.setPlainText(resto_del_asunto)
            else:
                if nuevo_nombre_serie:
                    self.asunto.setPlainText(f"{nuevo_nombre_serie} - {current_asunto}")

        self._last_autofilled_asunto = nuevo_nombre_serie
    
    def on_sugerir_asunto(self):
        ruta_doc_respaldo = self.ruta_pdf_temporal if self.ruta_pdf_temporal else self.documento_respaldo.text()
        codigo_serie = self.serie_documental.currentText()
    
        if not ruta_doc_respaldo:
            QMessageBox.warning(self, "Información", "Selecciona primero el PDF para que la IA lo lea.")
            return
        if not codigo_serie:
            QMessageBox.warning(self, "Información", "Selecciona primero la 'Serie Documental'.")
            return
            
        # Deshabilitamos el botón para evitar doble clic
        self.btn_sugerir_asunto.setEnabled(False)
    
        info_serie = self.expediente_service.obtener_info_serie(codigo_serie)
        if not info_serie: 
            self.btn_sugerir_asunto.setEnabled(True)
            return
            
        nombre_serie = info_serie.get('nombre_serie', '')
        success_serie, ruta_pdf_serie = self.expediente_service.obtener_ruta_pdf_serie(codigo_serie)
    
        # Mostramos diálogo de espera INDEFINIDA (bloqueando la ventana)
        self.progress = QProgressDialog("Leyendo documentos y consultando a Google Gemini...\nPor favor, espere.", None, 0, 0, self)
        self.progress.setWindowTitle("Inteligencia Artificial")
        self.progress.setModal(True) # Hace que el usuario no pueda tocar el formulario mientras espera
        self.progress.show()
    
        # ¡Magia! Enviamos el trabajo pesado a las sombras
        GestorTareas.ejecutar_en_segundo_plano(
            self._procesar_ia_en_fondo,
            self._on_ia_finalizada,
            ruta_doc_respaldo,
            ruta_pdf_serie if success_serie else None,
            nombre_serie
        )

    def _procesar_ia_en_fondo(self, ruta_doc_respaldo: str, ruta_pdf_serie: str, nombre_serie: str):
        """Delega absolutamente todo al AI Service en el ThreadPool"""
        import os
        
        if not os.path.isabs(ruta_doc_respaldo):
             ruta_doc_respaldo = os.path.join(os.getcwd(), ruta_doc_respaldo)
             
        # Magia Pura: El Servicio se encarga de subirlo, escanearlo y destruirlo remotamente.
        success, resultado = self.ai_service.analizar_documento_para_asunto(
            ruta_documento=ruta_doc_respaldo, 
            ruta_pdf_serie=ruta_pdf_serie, 
            nombre_serie=nombre_serie
        )
        return success, resultado

    def _on_ia_finalizada(self, resultado_tarea):
        """Regresa al hilo principal para mostrar los resultados en pantalla"""
        # Limpiamos visuales
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
            for sug in resultado: 
                lista_sugerencias.addItem(sug)
                
            lista_sugerencias.itemDoubleClicked.connect(lambda item: (self.asunto.setPlainText(item.text()), dialogo_opciones.accept()))
            layout.addWidget(lista_sugerencias)
            dialogo_opciones.exec_()
        else:
            mostrar_mensaje(self, "Error de IA", "\n".join(resultado) if isinstance(resultado, list) else str(resultado), QMessageBox.Critical)
            
    def abrir_seleccion_gestion(self):
        dialog = SeleccionarCGDialog(self.expediente_service, self)
        if dialog.exec_() == QDialog.Accepted:
            datos = dialog.seleccionado
            if datos:
                if datos.get('folio'): self.folio.setText(datos['folio'])
                
                if datos.get('asunto'):
                    asunto_cg = datos['asunto'].strip()
                    current_asunto = self.asunto.toPlainText().strip()
                    
                    if not current_asunto:
                        self.asunto.setPlainText(asunto_cg)
                    elif current_asunto == self._last_autofilled_asunto:
                        self.asunto.setPlainText(f"{self._last_autofilled_asunto} - {asunto_cg}")
                    elif self._last_autofilled_asunto and current_asunto.startswith(self._last_autofilled_asunto):
                        self.asunto.setPlainText(f"{self._last_autofilled_asunto} - {asunto_cg}")
                    else:
                        self.asunto.setPlainText(asunto_cg)

                fecha_str = datos.get('fecha') or datos.get('fecha_documento')
                if fecha_str:
                    qdate = QDate.fromString(fecha_str, "yyyy-MM-dd")
                    if not qdate.isValid(): qdate = QDate.fromString(fecha_str, "dd/MM/yyyy")
                    if qdate.isValid(): self.fecha.setDate(qdate)
                mostrar_mensaje(self, "Cargado", "Datos de Gestión importados correctamente.")