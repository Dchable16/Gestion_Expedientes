# -*- coding: utf-8 -*-
"""
Created on Mon Jan 12 16:50:08 2026

@author: dchable
"""
# ui/historial_dialog.py
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QLabel)
from PyQt5.QtCore import QDateTime, Qt

class HistorialDialog(QDialog):
    def __init__(self, repository, parent=None, filtro_texto=None):
        super().__init__(parent)
        self.repository = repository
        self.filtro_texto = filtro_texto # Guardamos el filtro
        
        titulo = "Historial de Actividad"
        if self.filtro_texto:
            titulo = f"Historial Filtrado: {self.filtro_texto}"
            
        self.setWindowTitle(titulo)
        self.setMinimumSize(800, 500)
        self.init_ui()
        self.cargar_datos()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        texto_info = "Últimos movimientos registrados:"
        if self.filtro_texto:
            texto_info = f"Movimientos relacionados con '{self.filtro_texto}':"
            
        layout.addWidget(QLabel(texto_info))

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(4)
        self.tabla.setHorizontalHeaderLabels(["Fecha/Hora", "Usuario", "Acción", "Descripción"])
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setAlternatingRowColors(True)
        
        header = self.tabla.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)

        layout.addWidget(self.tabla)

    def cargar_datos(self):
        # Si hay filtro, usamos el método de búsqueda, si no, traemos los últimos 100
        if self.filtro_texto:
            datos = self.repository.obtener_historial_filtrado(self.filtro_texto)
        else:
            datos = self.repository.obtener_historial(limite=100)
            
        self.tabla.setRowCount(0)
        for i, row in enumerate(datos):
            self.tabla.insertRow(i)
            fecha_utc_str = str(row['fecha'])
            fecha_qdt = QDateTime.fromString(fecha_utc_str, "yyyy-MM-dd HH:mm:ss")
            fecha_qdt.setTimeSpec(Qt.UTC)
            fecha_local_str = fecha_qdt.toLocalTime().toString("dd-MM-yyyy HH:mm:ss")
            
            self.tabla.setItem(i, 0, QTableWidgetItem(fecha_local_str))
            self.tabla.setItem(i, 1, QTableWidgetItem(str(row['usuario'])))
            self.tabla.setItem(i, 2, QTableWidgetItem(str(row['accion'])))
            self.tabla.setItem(i, 3, QTableWidgetItem(str(row['descripcion'])))