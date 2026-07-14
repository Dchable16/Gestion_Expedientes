# -*- coding: utf-8 -*-
"""
Created on Mon Jan 12 12:26:10 2026

@author: dchable
"""

# ui/login_dialog.py
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QMessageBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
# Asegúrate de importar tu repositorio o pasarlo como dependencia

class LoginDialog(QDialog):
    def __init__(self, repository, parent=None):
        super().__init__(parent)
        self.repository = repository
        self.setWindowTitle("Inicio de Sesión")
        self.setFixedSize(300, 180)
        
        # Ocultar el botón de ayuda (?) de la barra de título
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.usuario_autenticado = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Usuario
        layout.addWidget(QLabel("Usuario:"))
        self.txt_user = QLineEdit()
        self.txt_user.setPlaceholderText("admin")
        layout.addWidget(self.txt_user)
        
        # Contraseña
        layout.addWidget(QLabel("Contraseña:"))
        self.txt_pass = QLineEdit()
        self.txt_pass.setEchoMode(QLineEdit.Password) # Ocultar caracteres
        self.txt_pass.setPlaceholderText("admin")
        layout.addWidget(self.txt_pass)
        
        layout.addSpacing(10)
        
        # Botón Ingresar
        self.btn_login = QPushButton("Ingresar")
        self.btn_login.setObjectName("btn_nuevo") # o tu identificador verde preferido
        self.btn_login.setCursor(Qt.PointingHandCursor)
        self.btn_login.clicked.connect(self.validar)
        layout.addWidget(self.btn_login)

    def validar(self):
        user = self.txt_user.text().strip()
        password = self.txt_pass.text().strip()
        
        if self.repository.validar_usuario(user, password):
            self.usuario_autenticado = user
            self.accept() # Cierra el diálogo y retorna QDialog.Accepted
        else:
            QMessageBox.warning(self, "Error", "Usuario o contraseña incorrectos.")
            self.txt_pass.clear()
            self.txt_pass.setFocus()