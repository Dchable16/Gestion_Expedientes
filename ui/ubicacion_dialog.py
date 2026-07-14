# -*- coding: utf-8 -*-
"""
Created on Tue Jun  3 11:19:37 2025

@author: dchable
"""

import os
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QFileDialog, QFormLayout)
from PyQt5.QtCore import Qt

class UbicacionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Confirmar Ubicación y Acuse")
        self.setMinimumWidth(400)
        self.pdf_path = None
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)

        # --- 1. Formulario de Topografía (Las 4 cajitas nuevas) ---
        form_layout = QFormLayout()

        self.input_area = QLineEdit()
        self.input_area.setPlaceholderText("Ej. Bodega Central")
        form_layout.addRow("Área:", self.input_area)

        self.input_pasillo = QLineEdit()
        self.input_pasillo.setPlaceholderText("Ej. A")
        form_layout.addRow("Pasillo:", self.input_pasillo)

        self.input_anaquel = QLineEdit()
        self.input_anaquel.setPlaceholderText("Ej. 12")
        form_layout.addRow("Anaquel:", self.input_anaquel)

        self.input_charola = QLineEdit()
        self.input_charola.setPlaceholderText("Ej. 3")
        form_layout.addRow("Charola:", self.input_charola)

        layout.addLayout(form_layout)

        # --- 2. Selección del Acuse PDF ---
        pdf_layout = QHBoxLayout()
        self.lbl_pdf = QLabel("Acuse firmado (Opcional):")
        self.btn_pdf = QPushButton("📂 Seleccionar PDF")
        self.btn_pdf.clicked.connect(self.seleccionar_pdf)
        pdf_layout.addWidget(self.lbl_pdf)
        pdf_layout.addWidget(self.btn_pdf)
        pdf_layout.addStretch()

        self.lbl_ruta_pdf = QLabel("Ningún archivo seleccionado")
        self.lbl_ruta_pdf.setStyleSheet("color: gray; font-style: italic;")

        layout.addLayout(pdf_layout)
        layout.addWidget(self.lbl_ruta_pdf)

        # --- 3. Botones de Acción ---
        btn_layout = QHBoxLayout()
        self.btn_aceptar = QPushButton("✅ Confirmar Entrega")
        self.btn_aceptar.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        self.btn_aceptar.clicked.connect(self.accept)

        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancelar)
        btn_layout.addWidget(self.btn_aceptar)

        layout.addLayout(btn_layout)

    def seleccionar_pdf(self):
        ruta, _ = QFileDialog.getOpenFileName(self, "Seleccionar Acuse PDF", "", "Archivos PDF (*.pdf)")
        if ruta:
            self.pdf_path = ruta
            self.lbl_ruta_pdf.setText(os.path.basename(ruta))
            self.lbl_ruta_pdf.setStyleSheet("color: black; font-weight: bold;")

    def get_ubicacion(self) -> dict:
        """Devuelve el diccionario estructurado con los 4 rubros."""
        return {
            'area': self.input_area.text().strip(),
            'pasillo': self.input_pasillo.text().strip(),
            'anaquel': self.input_anaquel.text().strip(),
            'charola': self.input_charola.text().strip()
        }

    def get_pdf_path(self):
        """Devuelve la ruta del archivo PDF seleccionado."""
        return self.pdf_path