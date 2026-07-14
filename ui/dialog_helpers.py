# -*- coding: utf-8 -*-
"""
Created on Tue Aug 12 16:20:20 2025

@author: dchable
"""

# ui/dialog_helpers.py

from PyQt5.QtWidgets import QMessageBox

def mostrar_mensaje(parent, titulo: str, mensaje: str, icono: QMessageBox.Icon = QMessageBox.Information):
    """
    Muestra un cuadro de diálogo de mensaje modal.
    Esta función centraliza la creación de QMessageBox para un estilo consistente.

    Args:
        parent (QWidget): El widget padre sobre el cual se mostrará el diálogo.
        titulo (str): El título de la ventana del mensaje.
        mensaje (str): El texto principal del mensaje.
        icono (QMessageBox.Icon): El icono a mostrar (Information, Warning, etc.).
    """
    msg_box = QMessageBox(parent)
    msg_box.setIcon(icono)
    msg_box.setWindowTitle(titulo)
    msg_box.setText(mensaje)
    msg_box.exec_()

