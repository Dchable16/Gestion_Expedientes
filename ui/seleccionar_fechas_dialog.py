# -*- coding: utf-8 -*-
"""
Created on Thu Jan 29 17:50:17 2026

@author: dchable
"""

# -*- coding: utf-8 -*-
# ui/seleccionar_fechas_dialog.py

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QDateEdit, QPushButton, QGroupBox, QFormLayout)
from PyQt5.QtCore import Qt, QDate

class SeleccionarFechasDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Seleccionar Periodo del Reporte")
        self.setFixedSize(400, 200)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Grupo de Fechas
        group = QGroupBox("Rango de Fechas a Reportar")
        form = QFormLayout(group)
        form.setSpacing(15)

        # Fecha Inicio (Por defecto: el día 1 del mes actual)
        self.date_inicio = QDateEdit()
        self.date_inicio.setCalendarPopup(True)
        self.date_inicio.setDisplayFormat("dd-MM-yyyy")
        self.date_inicio.setDate(QDate(QDate.currentDate().year(), QDate.currentDate().month(), 1))

        # Fecha Fin (Por defecto: Hoy)
        self.date_fin = QDateEdit()
        self.date_fin.setCalendarPopup(True)
        self.date_fin.setDisplayFormat("dd-MM-yyyy")
        self.date_fin.setDate(QDate.currentDate())

        form.addRow("Fecha Inicio:", self.date_inicio)
        form.addRow("Fecha Fin:", self.date_fin)
        
        layout.addWidget(group)

        # Botones
        btn_layout = QHBoxLayout()
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(self.reject)
        
        btn_aceptar = QPushButton("Generar Reporte")
        btn_aceptar.setObjectName("btn_nuevo") # Para que salga verde si usas los estilos
        btn_aceptar.clicked.connect(self.accept)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancelar)
        btn_layout.addWidget(btn_aceptar)
        
        layout.addLayout(btn_layout)

    def get_fechas(self):
        """Retorna las fechas seleccionadas en formato string YYYY-MM-DD"""
        return (
            self.date_inicio.date().toString("yyyy-MM-dd"),
            self.date_fin.date().toString("yyyy-MM-dd")
        )