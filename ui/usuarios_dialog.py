# -*- coding: utf-8 -*-
"""
Created on Mon Jan 12 12:55:35 2026

@author: dchable
"""

# ui/usuarios_dialog.py
from PyQt5.QtWidgets import (QWidget, QInputDialog, QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QMessageBox, QGroupBox)
from PyQt5.QtCore import Qt

class UsuariosDialog(QDialog):
    def __init__(self, repository, parent=None):
        super().__init__(parent)
        self.repository = repository
        self.setWindowTitle("Gestión de Usuarios")
        self.setMinimumSize(600, 400)
        self.init_ui()
        self.cargar_usuarios()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # --- SECCIÓN 1: LISTA DE USUARIOS ---
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(3)
        self.tabla.setHorizontalHeaderLabels(["ID", "Usuario", "Acciones"])
        header = self.tabla.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents) # ID: Ancho mínimo necesario
        header.setSectionResizeMode(1, QHeaderView.Stretch)          # Usuario: Ocupa todo el espacio sobrante
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents) # Acciones: Se ensancha para que quepan los botones
        self.tabla.verticalHeader().setVisible(False)
        layout.addWidget(QLabel("Usuarios Registrados:"))
        layout.addWidget(self.tabla)

        # --- SECCIÓN 2: FORMULARIO NUEVO USUARIO ---
        group = QGroupBox("Crear Nuevo Usuario")
        form_layout = QHBoxLayout(group)
        
        self.txt_new_user = QLineEdit()
        self.txt_new_user.setPlaceholderText("Nombre de usuario")
        
        self.txt_new_pass = QLineEdit()
        self.txt_new_pass.setPlaceholderText("Contraseña")
        self.txt_new_pass.setEchoMode(QLineEdit.Password)
        
        btn_agregar = QPushButton("Agregar")
        btn_agregar.setObjectName("btn_nuevo") # Para que salga verde con tus estilos
        btn_agregar.clicked.connect(self.agregar_usuario)
        
        form_layout.addWidget(self.txt_new_user)
        form_layout.addWidget(self.txt_new_pass)
        form_layout.addWidget(btn_agregar)
        
        layout.addWidget(group)

    def cargar_usuarios(self):
        """Consulta la BD y llena la tabla"""
        usuarios = self.repository.obtener_usuarios()
        self.tabla.setRowCount(0)
        
        for i, row in enumerate(usuarios):
            self.tabla.insertRow(i)
            self.tabla.setItem(i, 0, QTableWidgetItem(str(row['id'])))
            self.tabla.setItem(i, 1, QTableWidgetItem(row['username']))
            
            # --- COLUMNA DE ACCIONES ---
            widget_acciones = QWidget()
            layout_acc = QHBoxLayout(widget_acciones)
            layout_acc.setContentsMargins(0, 0, 0, 0)
            layout_acc.setSpacing(5)

            # Botón Cambiar Password
            btn_pass = QPushButton("Cambiar Clave")
            btn_pass.clicked.connect(lambda _, r_id=row['id'], name=row['username']: self.cambiar_clave_usuario(r_id, name))
            
            # Botón Eliminar
            btn_delete = QPushButton("Eliminar")
            btn_delete.setObjectName("btn_eliminar") 
            btn_delete.clicked.connect(lambda _, r_id=row['id']: self.eliminar_usuario(r_id))
            
            layout_acc.addWidget(btn_pass)
            layout_acc.addWidget(btn_delete)
            
            self.tabla.setCellWidget(i, 2, widget_acciones)

    def agregar_usuario(self):
        user = self.txt_new_user.text().strip()
        pwd = self.txt_new_pass.text().strip()
        
        if not user or not pwd:
            QMessageBox.warning(self, "Aviso", "Debe escribir usuario y contraseña.")
            return

        success, msg = self.repository.crear_usuario(user, pwd)
        if success:
            self.repository.registrar_accion("admin", "CREAR_USUARIO", f"Se creó al usuario con acceso al sistema: {user}")
            QMessageBox.information(self, "Éxito", msg)
            self.txt_new_user.clear()
            self.txt_new_pass.clear()
            self.cargar_usuarios() # Recargar la lista
        else:
            QMessageBox.warning(self, "Error", msg)

    def eliminar_usuario(self, user_id):
        confirm = QMessageBox.question(self, "Confirmar", 
                                     "¿Seguro que desea eliminar este usuario?",
                                     QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            success, msg = self.repository.eliminar_usuario(user_id)
            if success:
                elf.repository.registrar_accion("admin", "ELIMINAR_USUARIO", f"Se eliminó permanentemente el acceso del usuario ID {user_id}")
                self.cargar_usuarios()
            else:
                QMessageBox.warning(self, "Error", msg)
                
    def cambiar_clave_usuario(self, user_id, username):
        pwd, ok = QInputDialog.getText(self, "Cambiar Contraseña", 
                                     f"Ingrese la nueva contraseña para '{username}':",
                                     QLineEdit.Password)
        if ok and pwd:
            if self.repository.cambiar_password(user_id, pwd):
                self.repository.registrar_accion("admin", "CAMBIO_CLAVE", f"Se reseteó la contraseña del usuario: {username}")
                QMessageBox.information(self, "Éxito", "Contraseña actualizada.")
            else:
                QMessageBox.warning(self, "Error", "No se pudo actualizar la contraseña.")