# -*- coding: utf-8 -*-
"""
Created on Wed Jul 30 11:11:31 2025

@author: dchable
"""

# ui/contacto_dialog.py

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QPushButton, QLineEdit,
                             QLabel, QAbstractItemView, QMessageBox, QTableWidgetItem, QHeaderView,
                             QGroupBox)
from PyQt5.QtCore import Qt

from constants import ContactoDialogTab


class ContactoDialog(QDialog):
    def __init__(self, contacts, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Seleccionar Destinatario")
        self.setMinimumSize(600, 500)
        
        self.sorted_contacts = sorted(contacts, key=lambda x: x['nombre'].lower())
        self.selected_email = None

        self.init_ui()

    def init_ui(self):

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
               
        title_label = QLabel("SELECCIÓN DE DESTINATARIO")
        title_label.setObjectName("title_label")
        layout.addWidget(title_label)

        search_group = QGroupBox("Buscar Contacto")
        search_group.setProperty("filterGroup", True) 
        search_layout = QHBoxLayout(search_group)
        self.search_input = QLineEdit(placeholderText="Escriba para buscar...")
        search_layout.addWidget(QLabel("Buscar:"))
        search_layout.addWidget(self.search_input,1)

        self.contact_table = QTableWidget()
        self.configurar_tabla()
        self.poblar_tabla(self.sorted_contacts)

        button_layout = QHBoxLayout()
        seleccionar_button = QPushButton("Seleccionar")
        cancelar_button = QPushButton("Cancelar")
        cancelar_button.setObjectName("btn_cancelar")
        button_layout.addStretch()
        button_layout.addWidget(seleccionar_button)
        button_layout.addWidget(cancelar_button)
        
        layout.addWidget(search_group)
        layout.addWidget(self.contact_table, 1)
        layout.addLayout(button_layout)

        seleccionar_button.clicked.connect(self.on_seleccionar)
        cancelar_button.clicked.connect(self.reject)
        self.search_input.textChanged.connect(self.filtrar_tabla)

    def configurar_tabla(self):
        self.contact_table.setColumnCount(ContactoDialogTab.COLUMN_COUNT) 
        self.contact_table.setHorizontalHeaderLabels(["NOMBRE", "CORREO ELECTRÓNICO"])
        self.contact_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.contact_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.contact_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.contact_table.setAlternatingRowColors(True)
        self.contact_table.verticalHeader().setVisible(False)
        self.contact_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.contact_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

    def poblar_tabla(self, contacts):
        self.contact_table.setRowCount(0)
        self.contact_table.setRowCount(len(contacts))
        for i, contact in enumerate(contacts):
            self.contact_table.setItem(i, ContactoDialogTab.NOMBRE, QTableWidgetItem(contact['nombre']))
            self.contact_table.setItem(i, ContactoDialogTab.CORREO, QTableWidgetItem(contact['correo']))
    
    def filtrar_tabla(self):
        filter_text = self.search_input.text().lower()
        if not filter_text:
            self.poblar_tabla(self.sorted_contacts)
            return
            
        filtered_contacts = [
            c for c in self.sorted_contacts 
            if filter_text in c['nombre'].lower() or filter_text in c['correo'].lower()
        ]
        self.poblar_tabla(filtered_contacts)

    def on_seleccionar(self):
        selected_row = self.contact_table.currentRow()
        if selected_row >= 0:
            self.selected_email = self.contact_table.item(selected_row, ContactoDialogTab.CORREO).text()
            self.accept()
        else:
            QMessageBox.warning(self, "Advertencia", "Por favor, seleccione un contacto.")
            
    def get_selected_email(self):
        return self.selected_email