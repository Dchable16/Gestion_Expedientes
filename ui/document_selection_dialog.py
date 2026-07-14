# -*- coding: utf-8 -*-
"""
Created on Tue Jan 13 12:52:03 2026

@author: dchable
"""

# ui/document_selection_dialog.py
import os
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QCheckBox, QPushButton, 
                             QHBoxLayout, QLabel, QScrollArea, QWidget, QMessageBox)

class DocumentSelectionDialog(QDialog):
    def __init__(self, documentos_disponibles, parent=None):
        """
        documentos_disponibles: Lista de diccionarios 
        [{'descripcion':Str, 'path':Str, 'folio':Str}]
        """
        super().__init__(parent)
        self.setWindowTitle("Seleccionar Documentos para Enviar")
        self.setMinimumSize(450, 400)
        self.documentos = documentos_disponibles
        self.checkboxes = []
        
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        main_layout.addWidget(QLabel("Seleccione los documentos que desea adjuntar:"))

        # --- Área de Scroll para la lista (por si son muchos) ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_widget = QWidget()
        self.vbox_checks = QVBoxLayout(content_widget)
        
        if not self.documentos:
            self.vbox_checks.addWidget(QLabel("No se encontraron documentos físicos asociados."))
        else:
            for doc in self.documentos:
                # Verificar que el archivo realmente existe en disco
                if os.path.exists(doc['path']):
                    nombre_archivo = os.path.basename(doc['path'])
                    texto_mostrar = f"{doc['descripcion']} (Folio: {doc['folio']})\nArchivo: {nombre_archivo}"
                    
                    chk = QCheckBox(texto_mostrar)
                    chk.setChecked(True) # Marcado por defecto
                    # Guardamos la ruta en una propiedad del checkbox para recuperarla luego
                    chk.setProperty("filepath", doc['path']) 
                    
                    self.vbox_checks.addWidget(chk)
                    self.checkboxes.append(chk)
                else:
                    lbl_error = QLabel(f"❌ Archivo no encontrado: {doc['descripcion']}")
                    lbl_error.setStyleSheet("color: red; font-size: 10px;")
                    self.vbox_checks.addWidget(lbl_error)

        self.vbox_checks.addStretch()
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

        # --- Botones de Seleccionar Todo / Nada ---
        btn_tools_layout = QHBoxLayout()
        btn_all = QPushButton("Marcar Todos")
        btn_all.clicked.connect(self.marcar_todos)
        btn_none = QPushButton("Desmarcar Todos")
        btn_none.clicked.connect(self.desmarcar_todos)
        
        btn_tools_layout.addWidget(btn_all)
        btn_tools_layout.addWidget(btn_none)
        main_layout.addLayout(btn_tools_layout)

        # --- Botones de Acción ---
        action_layout = QHBoxLayout()
        self.btn_enviar = QPushButton("Enviar Seleccionados")
        self.btn_enviar.clicked.connect(self.validar_y_aceptar)
        self.btn_enviar.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 8px;")
        
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(self.reject)
        
        action_layout.addStretch()
        action_layout.addWidget(btn_cancelar)
        action_layout.addWidget(self.btn_enviar)
        
        main_layout.addLayout(action_layout)

    def marcar_todos(self):
        for chk in self.checkboxes: chk.setChecked(True)

    def desmarcar_todos(self):
        for chk in self.checkboxes: chk.setChecked(False)

    def validar_y_aceptar(self):
        seleccionados = self.get_selected_files()
        if not seleccionados:
            QMessageBox.warning(self, "Atención", "No ha seleccionado ningún documento para enviar.")
            return
        self.accept()

    def get_selected_files(self):
        rutas = []
        for chk in self.checkboxes:
            if chk.isChecked():
                rutas.append(chk.property("filepath"))
        return rutas