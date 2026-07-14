# -*- coding: utf-8 -*-
"""
Created on Wed Jan 28 17:37:35 2026

@author: dchable
"""
# ui/seleccionar_cg_dialog.py

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, 
                             QPushButton, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QMessageBox, QLabel)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QBrush

class SeleccionarCGDialog(QDialog):
    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service = service
        self.seleccionado = None  # Aquí guardaremos el diccionario de datos
        self.folios_ya_usados = []
        
        self.setWindowTitle("Seleccionar Registro de Control de Gestión (Pendientes)")
        self.setMinimumSize(800, 500)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        lbl_titulo = QLabel("OFICIOS PENDIENTES DE ATENCIÓN")
        lbl_titulo.setObjectName("title_label") # Estilo de tu QSS
        layout.addWidget(lbl_titulo)
        
        # --- Buscador ---
        h_layout = QHBoxLayout()
        h_layout.addWidget(QLabel("Buscar oficio:"))
        self.txt_busqueda = QLineEdit()
        self.txt_busqueda.setPlaceholderText("Escribe folio, asunto o remitente...")
        self.txt_busqueda.textChanged.connect(self.cargar_datos) # Buscar al escribir
        h_layout.addWidget(self.txt_busqueda)
        layout.addLayout(h_layout)
        
        # --- Tabla ---
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(4)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.setHorizontalHeaderLabels(["Folio", "Recepción", "Asunto", "Remitente"])
        self.tabla.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setWordWrap(True)
        self.tabla.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        
        # Ajuste de columnas
        header = self.tabla.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents) # Folio
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents) # Fecha
        header.setSectionResizeMode(2, QHeaderView.Stretch)          # Asunto toma todo el espacio sobrante
        header.setSectionResizeMode(3, QHeaderView.Interactive)      # Remitente lo volvemos manual/interactivo
        self.tabla.setColumnWidth(3, 250)
        
        self.tabla.cellDoubleClicked.connect(self.seleccionar_registro)
        
        layout.addWidget(self.tabla)
        
        btn_layout = QHBoxLayout()
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.setObjectName("btn_cerrar_visor") # Estilo Gris Neutro del QSS
        btn_cancelar.clicked.connect(self.reject)
        
        btn_seleccionar = QPushButton("Seleccionar")
        btn_seleccionar.setObjectName("btn_ver_documento") # Estilo Azul Brillante del QSS
        btn_seleccionar.clicked.connect(self.seleccionar_registro)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancelar)
        btn_layout.addWidget(btn_seleccionar)
        layout.addLayout(btn_layout)
        
        self.cargar_datos()

    def cargar_datos(self):
        texto = self.txt_busqueda.text().strip()
        
        registros_crudos = self.service.obtener_todo_control_gestion(filtro_texto=texto)
        
        try:
            self.folios_usados = self.service.obtener_folios_usados()
        except AttributeError:
            self.folios_usados = []
        lista_negra = [str(f).strip() for f in self.folios_usados]
            
        self.datos_en_memoria = registros_crudos 
        self.tabla.setRowCount(0)
        
        for i, row in enumerate(registros_crudos):
            self.tabla.insertRow(i)
            
            folio_actual = str(row.get('folio', '')).strip()
            ya_usado = folio_actual in lista_negra
            texto_folio = f"{folio_actual} [ARCHIVADO]" if ya_usado else folio_actual
            item_folio = QTableWidgetItem(texto_folio)
            item_fecha = QTableWidgetItem(str(row.get('fecha', '')))
            item_asunto = QTableWidgetItem(str(row.get('asunto', '')))
            item_remitente = QTableWidgetItem(str(row.get('remitente', '')))
            if ya_usado:
                color_fondo = QBrush(QColor("#e0e0e0"))  # Gris claro
                color_texto = QBrush(QColor("#7f8c8d"))  # Gris oscuro
                
                for item in [item_folio, item_fecha, item_asunto, item_remitente]:
                    item.setBackground(color_fondo)
                    item.setForeground(color_texto)
            self.tabla.setItem(i, 0, item_folio)
            self.tabla.setItem(i, 1, item_fecha)
            self.tabla.setItem(i, 2, item_asunto)
            self.tabla.setItem(i, 3, item_remitente)

    def seleccionar_registro(self):
        fila = self.tabla.currentRow()
        if fila >= 0:
            registro_intentado = self.datos_en_memoria[fila]
            folio_real = str(registro_intentado.get('folio', '')).strip()
            lista_negra = [str(f).strip() for f in getattr(self, 'folios_usados', [])]
            
            if folio_real in lista_negra:
                QMessageBox.warning(self, "Documento No Disponible", 
                                    f"El oficio con folio '{folio_real}' ya fue archivado dentro de otro expediente.\n\n"
                                    "Por normativa, el documento físico original no puede duplicarse.")
                return 
                
            self.seleccionado = registro_intentado
            self.accept()
        else:
            QMessageBox.warning(self, "Aviso", "Por favor seleccione una fila.")