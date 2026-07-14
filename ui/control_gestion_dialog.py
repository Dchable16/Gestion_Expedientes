# -*- coding: utf-8 -*-
"""
Created on Tue Jan 13 14:07:45 2026

@author: dchable
"""

# ui/control_gestion_dialog.py
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, 
                             QLineEdit, QComboBox, QDateEdit, QTextEdit, 
                             QPushButton, QScrollArea, QWidget, QMessageBox, QLabel)
from PyQt5.QtCore import QDate, Qt

class ControlGestionDialog(QDialog):
    def __init__(self, service, parent=None, cg_id=None):
        super().__init__(parent)
        self.service = service
        self.cg_id = cg_id
        self.folio_original = ""
        self.setWindowTitle("Formulario de Control de Gestión")
        self.setMinimumSize(600, 750)
        self.init_ui()
        
        if self.cg_id:
            self.cargar_datos()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        # Área de Scroll para que quepan todos los campos
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_widget = QWidget()
        form_layout = QFormLayout(content_widget)
        
        # --- CAMPOS ---
        
        self.origen = QComboBox()
        self.origen.addItems(["DG", "SGT", "GAS"])
        self.origen.currentIndexChanged.connect(self.auto_generar_folio)
        self.txt_folio = QLineEdit()
        self.dt_fecha = QDateEdit(QDate.currentDate())
        self.dt_fecha.setCalendarPopup(True)
        self.dt_fecha.setDisplayFormat("dd-MM-yyyy")
        
        self.dict_funcionarios = {
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
        
        # 2. Extraemos SOLO los nombres (las llaves) y añadimos el espacio vacío al inicio
        nombres_opciones = [""] + list(self.dict_funcionarios.keys())
        
        turnado_container = QWidget()
        turnado_layout = QVBoxLayout(turnado_container)
        turnado_layout.setContentsMargins(0, 0, 0, 0)
        turnado_layout.setSpacing(5)

        # 3. Llenamos los 4 combos usando la lista de nombres_opciones
        self.cmb_turnado_1 = QComboBox()
        self.cmb_turnado_1.addItems(nombres_opciones)
        
        self.cmb_turnado_2 = QComboBox()
        self.cmb_turnado_2.addItems(nombres_opciones)
        
        self.cmb_turnado_3 = QComboBox()
        self.cmb_turnado_3.addItems(nombres_opciones)
        
        self.cmb_turnado_4 = QComboBox()
        self.cmb_turnado_4.addItems(nombres_opciones)
        self.cmb_turnado_4.setEditable(True)
        self.cmb_turnado_4.setInsertPolicy(QComboBox.NoInsert)

        # Agregamos los combos al layout del contenedor
        turnado_layout.addWidget(self.cmb_turnado_1)
        turnado_layout.addWidget(self.cmb_turnado_2)
        turnado_layout.addWidget(self.cmb_turnado_3)
        turnado_layout.addWidget(self.cmb_turnado_4)
        
        self.txt_remitente = QTextEdit()
        self.txt_remitente.setMaximumHeight(60)
        self.txt_area = QLineEdit()
        self.txt_referencia = QLineEdit()
        
        self.dt_fecha_doc = QDateEdit(QDate.currentDate())
        self.dt_fecha_doc.setCalendarPopup(True)
        self.dt_fecha_doc.setDisplayFormat("dd-MM-yyyy")
        
        self.txt_asunto = QTextEdit()
        self.txt_asunto.setMaximumHeight(80)
        
        self.cmb_prioridad = QComboBox()
        self.cmb_prioridad.addItems(["NORMAL", "URGENTE"])
        
        self.dt_fecha_limite = QDateEdit(QDate.currentDate().addDays(3))
        self.dt_fecha_limite.setCalendarPopup(True)
        self.dt_fecha_limite.setDisplayFormat("dd-MM-yyyy")
        
        self.cmb_tipo_instruccion = QComboBox()
        self.cmb_tipo_instruccion.addItems([
            "ATENCIÓN PROCEDENTE", "ATENCIÓN COORDINADA", 
            "ATENCIÓN GRUPAL", "PARA SU CONOCIMIENTO"
        ])
        
        self.txt_detalle_instruccion = QTextEdit()
        self.txt_detalle_instruccion.setMaximumHeight(80)
        
        self.txt_observaciones = QTextEdit()
        self.txt_observaciones.setMaximumHeight(60)
        
        self.cmb_anexos = QComboBox()
        self.cmb_anexos.addItems(["NO", "SI"])
        
        self.cmb_respuesta = QComboBox()
        self.cmb_respuesta.addItems(["NO", "SI"])
        
        self.txt_recibio = QTextEdit()
        self.txt_recibio.setMaximumHeight(60)
        self.txt_ccp =QTextEdit()
        self.txt_ccp.setMaximumHeight(60)
        
        self.cmb_archivado = QComboBox()
        self.cmb_archivado.addItems([
            "PENDIENTE", "CONCLUIDO", "CANCELADO"])

        # Agregar filas al formulario
        form_layout.addRow("Origen:", self.origen)
        form_layout.addRow("Folio:", self.txt_folio)
        form_layout.addRow("Fecha:", self.dt_fecha)
        form_layout.addRow("Turnado a:", turnado_container)
        form_layout.addRow("Remitente:", self.txt_remitente)
        form_layout.addRow("Procedencia:", self.txt_area)
        form_layout.addRow("Referencia:", self.txt_referencia)
        form_layout.addRow("Fecha del Documento:", self.dt_fecha_doc)
        form_layout.addRow("Asunto:", self.txt_asunto)
        form_layout.addRow("Prioridad:", self.cmb_prioridad)
        form_layout.addRow("Fecha Límite de Atención:", self.dt_fecha_limite)
        form_layout.addRow("Tipo Instrucción:", self.cmb_tipo_instruccion)
        form_layout.addRow("Detalle de la Instrucción:", self.txt_detalle_instruccion)
        form_layout.addRow("Observaciones:", self.txt_observaciones)
        form_layout.addRow("Documentos Anexos:", self.cmb_anexos)
        form_layout.addRow("Requiere Respuesta:", self.cmb_respuesta)
        form_layout.addRow("Recibió:", self.txt_recibio)
        form_layout.addRow("C.C.P:", self.txt_ccp)
        form_layout.addRow("Estado:", self.cmb_archivado)

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

        # Botones
        btn_layout = QHBoxLayout()
        btn_guardar = QPushButton("Guardar")
        btn_guardar.setAutoDefault(False) 
        btn_guardar.setDefault(False)
        btn_guardar.clicked.connect(self.guardar)
        
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.setObjectName("btn_cancelar") 
        btn_cancelar.setAutoDefault(False)
        btn_cancelar.setCursor(Qt.PointingHandCursor)
        btn_cancelar.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancelar)
        btn_layout.addWidget(btn_guardar)
        main_layout.addLayout(btn_layout)
        
        campos_a_bloquear = [
            self.origen,
            self.dt_fecha,
            self.cmb_turnado_1, 
            self.cmb_turnado_2, 
            self.cmb_turnado_3, 
            self.cmb_turnado_4,
            self.dt_fecha_doc,
            self.cmb_prioridad,
            self.dt_fecha_limite,
            self.cmb_tipo_instruccion,
            self.cmb_anexos,
            self.cmb_respuesta,
            self.cmb_archivado
        ]
        
        for widget in campos_a_bloquear:
            self.bloquear_rueda(widget)
    def bloquear_rueda(self, widget):
        """
        Sobrescribe el evento de rueda del ratón del widget para que lo ignore.
        Al ignorarlo, el evento 'sube' al padre (el ScrollArea) y permite hacer scroll.
        """
        widget.wheelEvent = lambda event: event.ignore()

    def guardar(self):
        folio_ingresado = self.txt_folio.text().strip()
        
        if not folio_ingresado:
            QMessageBox.warning(self, "Atención", "El campo Folio es obligatorio.")
            self.txt_folio.setFocus()
            return

        if not self.cg_id or folio_ingresado != self.folio_original:
            id_existente = self.service.obtener_id_por_folio_cg(folio_ingresado)
            if id_existente:
                QMessageBox.warning(self, "Folio Duplicado", 
                                    f"El folio '{folio_ingresado}' ya se encuentra registrado.\n\n"
                                    f"📌 Pertenece al Control de Gestión con ID: {id_existente}\n\n"
                                    "Por favor, busque ese ID para editarlo o ingrese un folio diferente.")
                self.txt_folio.setFocus()
                return
            
        nombres_seleccionados = []
        combos = [self.cmb_turnado_1, self.cmb_turnado_2, self.cmb_turnado_3, self.cmb_turnado_4]
        
        for cmb in combos:
            texto = cmb.currentText().strip()
            if texto:
                nombres_seleccionados.append(texto)
        turnado_texto_final = "\n".join(nombres_seleccionados)
        
        data = {
            'origen': self.origen.currentText(),
            'folio': self.txt_folio.text(),
            'fecha': self.dt_fecha.date().toString("yyyy-MM-dd"),
            'turnado_a': turnado_texto_final,
            'remitente': self.txt_remitente.toPlainText(),
            'area': self.txt_area.text(),
            'referencia': self.txt_referencia.text(),
            'fecha_documento': self.dt_fecha_doc.date().toString("yyyy-MM-dd"),
            'asunto': self.txt_asunto.toPlainText(),
            'prioridad': self.cmb_prioridad.currentText(),
            'fecha_limite': self.dt_fecha_limite.date().toString("yyyy-MM-dd"),
            'tipo_instruccion': self.cmb_tipo_instruccion.currentText(),
            'detalle_instruccion': self.txt_detalle_instruccion.toPlainText(),
            'observaciones': self.txt_observaciones.toPlainText(),
            'documentos_anexos': self.cmb_anexos.currentText(),
            'requiere_respuesta': self.cmb_respuesta.currentText(),
            'recibio': self.txt_recibio.toPlainText(),
            'ccp': self.txt_ccp.toPlainText(),
            'archivado': self.cmb_archivado.currentText(),
        }
        
        success, msg = self.service.guardar_control_gestion(data, self.cg_id)
        if success:
            QMessageBox.information(self, "Éxito", msg)
            self.accept()
        else:
            QMessageBox.warning(self, "Error", msg)

    def cargar_datos(self):
        data = self.service.obtener_control_gestion_por_id(self.cg_id)
        if not data: return
        
        self.origen.setCurrentText(data.get('origen'))
        self.folio_original = data.get('folio', '').strip()
        self.txt_folio.setText(self.folio_original)
        self.dt_fecha.setDate(QDate.fromString(data.get('fecha'), "yyyy-MM-dd"))
        
        # --- NUEVA LÓGICA DE EXTRACCIÓN A PRUEBA DE BALAS ---
        turnado_raw = data.get('turnado_a', '')
        if turnado_raw:
            # Dividimos por el salto de línea simple
            nombres = [n.strip() for n in turnado_raw.split('\n') if n.strip()]
            
            if len(nombres) > 0: self.cmb_turnado_1.setCurrentText(nombres[0])
            if len(nombres) > 1: self.cmb_turnado_2.setCurrentText(nombres[1])
            if len(nombres) > 2: self.cmb_turnado_3.setCurrentText(nombres[2])
            if len(nombres) > 3: self.cmb_turnado_4.setCurrentText(nombres[3])
            
        self.txt_remitente.setPlainText(data.get('remitente', ''))
        
        self.txt_area.setText(data.get('area', ''))
        self.txt_referencia.setText(data.get('referencia', ''))
        self.dt_fecha_doc.setDate(QDate.fromString(data.get('fecha_documento'), "yyyy-MM-dd"))
        
        self.txt_asunto.setPlainText(data.get('asunto', ''))
        
        self.cmb_prioridad.setCurrentText(data.get('prioridad', 'NORMAL'))
        self.dt_fecha_limite.setDate(QDate.fromString(data.get('fecha_limite'), "yyyy-MM-dd"))
        self.cmb_tipo_instruccion.setCurrentText(data.get('tipo_instruccion', ''))
        
        self.txt_detalle_instruccion.setPlainText(data.get('detalle_instruccion', ''))
        self.txt_observaciones.setPlainText(data.get('observaciones', ''))
        
        self.cmb_anexos.setCurrentText(data.get('documentos_anexos', 'NO'))
        self.cmb_respuesta.setCurrentText(data.get('requiere_respuesta', 'NO'))
        
        self.txt_recibio.setPlainText(data.get('recibio', ''))
        self.txt_ccp.setPlainText(data.get('ccp', ''))
        
        self.cmb_archivado.setCurrentText(data.get('archivado', 'PENDIENTE'))
        
    def auto_generar_folio(self):
        """Si es un registro nuevo y seleccionan GAS, genera el folio automático."""
        if not self.cg_id:
            origen_seleccionado = self.origen.currentText()
            
            if origen_seleccionado == "GAS":
                nuevo_folio = self.service.generar_siguiente_folio_cg(origen_seleccionado)
                self.txt_folio.setText(nuevo_folio)
                # Opcional: Bloquear la caja para que no lo borren por accidente
                # self.txt_folio.setReadOnly(True) 
            else:
                # Si cambian de opinión y regresan a DG o SGT, limpiamos la caja
                self.txt_folio.clear()
                # self.txt_folio.setReadOnly(False)