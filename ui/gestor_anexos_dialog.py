# -*- coding: utf-8 -*-
"""
Created on Thu Mar 12 16:28:14 2026

@author: dchable
"""

# -*- coding: utf-8 -*-
# ui/gestor_anexos_dialog.py

import os
import shutil
import platform
import subprocess
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                             QListWidget, QMessageBox, QFileDialog, QLabel)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QStyle

class GestorAnexosDialog(QDialog):
    # --- AQUÍ RECIBIMOS EL MODO LECTURA ---
    def __init__(self, ruta_carpeta, parent=None, modo_lectura=False):
        super().__init__(parent)
        self.ruta_carpeta = ruta_carpeta
        self.modo_lectura = modo_lectura 
        self.setWindowTitle("Visor de Anexos" if modo_lectura else "Gestor de Anexos")
        self.setMinimumSize(600, 450)
        self.setWindowFlags(Qt.Window | Qt.WindowTitleHint | Qt.WindowCloseButtonHint | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)
        
        # Asegurarnos de que la carpeta exista físicamente
        os.makedirs(self.ruta_carpeta, exist_ok=True)
        
        self.init_ui()
        self.cargar_archivos()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        lbl_info = QLabel(f"📂 Carpeta de destino: {os.path.basename(self.ruta_carpeta)}")
        lbl_info.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 14px;")
        layout.addWidget(lbl_info)
        
        # Lista visual de los archivos
        self.lista_archivos = QListWidget()
        layout.addWidget(self.lista_archivos)
        
        # Botones de Acción
        btn_layout = QHBoxLayout()
        
        self.btn_agregar = QPushButton("➕ Añadir Archivos")
        self.btn_agregar.setObjectName("btn_agregar_anexo")
        self.btn_agregar.clicked.connect(self.agregar_archivos)
        
        self.btn_abrir = QPushButton("👁️ Ver Documento")
        self.btn_abrir.setObjectName("btn_ver_documento")
        self.btn_abrir.clicked.connect(self.abrir_archivo)
        
        self.btn_eliminar = QPushButton("🗑️ Eliminar")
        self.btn_eliminar.setObjectName("btn_eliminar_anexo")
        self.btn_eliminar.clicked.connect(self.eliminar_archivo)
        
        btn_layout.addWidget(self.btn_agregar)
        btn_layout.addWidget(self.btn_abrir)
        btn_layout.addWidget(self.btn_eliminar)
        
        # --- LA MAGIA VISUAL: OCULTAR BOTONES SI ES SOLO LECTURA ---
        if self.modo_lectura:
            self.btn_agregar.setVisible(False)
            self.btn_eliminar.setVisible(False)
            
        layout.addLayout(btn_layout)
        
        # Botón cerrar
        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.setObjectName("btn_cerrar_visor")
        btn_cerrar.clicked.connect(self.accept)
        layout.addWidget(btn_cerrar, alignment=Qt.AlignRight)

    def cargar_archivos(self):
        """Lee la carpeta en Windows y muestra los archivos en la lista."""
        self.lista_archivos.clear()
        if os.path.exists(self.ruta_carpeta):
            archivos = os.listdir(self.ruta_carpeta)
            for archivo in archivos:
                self.lista_archivos.addItem(archivo)

    def agregar_archivos(self):
        """Abre un seleccionador y copia los archivos a la carpeta de anexos."""
        # Candado de seguridad trasero
        if self.modo_lectura: return 
        
        rutas_origen, _ = QFileDialog.getOpenFileNames(self, "Seleccionar Anexos", "", "Todos los Archivos (*)")
        if not rutas_origen: return
        
        agregados = 0
        for ruta in rutas_origen:
            try:
                nombre_archivo = os.path.basename(ruta)
                ruta_destino = os.path.join(self.ruta_carpeta, nombre_archivo)
                # Copiar archivo si no es exactamente el mismo origen
                if ruta != ruta_destino:
                    shutil.copy2(ruta, ruta_destino)
                    agregados += 1
            except Exception as e:
                QMessageBox.warning(self, "Error", f"No se pudo copiar {nombre_archivo}: {e}")
        
        if agregados > 0:
            self.cargar_archivos() # Refrescar la lista

    def abrir_archivo(self):
        """Abre el archivo seleccionado con su programa predeterminado (PDF, Excel, JPG, etc)."""
        item = self.lista_archivos.currentItem()
        if not item:
            QMessageBox.warning(self, "Atención", "Seleccione un archivo de la lista primero.")
            return
        
        ruta_archivo = os.path.join(self.ruta_carpeta, item.text())
        try:
            if platform.system() == "Windows": os.startfile(ruta_archivo)
            elif platform.system() == "Darwin": subprocess.Popen(["open", ruta_archivo])
            else: subprocess.Popen(["xdg-open", ruta_archivo])
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def eliminar_archivo(self):
        """Elimina el archivo seleccionado de la carpeta."""
        # Candado de seguridad trasero
        if self.modo_lectura: return 
        
        item = self.lista_archivos.currentItem()
        if not item: return
        
        respuesta = QMessageBox.question(self, "Confirmar Eliminación", 
                                         f"¿Está seguro de eliminar '{item.text()}' de los anexos?\nEsta acción no se puede deshacer.",
                                         QMessageBox.Yes | QMessageBox.No)
        if respuesta == QMessageBox.Yes:
            ruta_archivo = os.path.join(self.ruta_carpeta, item.text())
            try:
                os.remove(ruta_archivo)
                self.cargar_archivos() # Refrescar la lista
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo eliminar: {e}")