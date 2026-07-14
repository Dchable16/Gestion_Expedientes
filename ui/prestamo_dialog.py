# -*- coding: utf-8 -*-
"""
Created on Thu Mar 26 11:26:05 2026

@author: dchable
"""

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLineEdit, QDateEdit, QTextEdit, QDialogButtonBox, QMessageBox, QComboBox, QCompleter
from PyQt5.QtCore import QDate, Qt

from constants import DIAS_PRESTAMO_DEFAULT, COLUMNAS_DIRECTORIO

class PrestamoDialog(QDialog):
    def __init__(self, lista_contactos=None, parent=None):
        super().__init__(parent)
        self.lista_contactos = lista_contactos or []
        
        self.setWindowTitle("Registrar Préstamo Físico")
        self.resize(450, 320)
        layout = QVBoxLayout(self)

        # 1. Definir los campos visuales primero (evita errores de memoria)
        self.cmb_solicitante = QComboBox()
        self.cmb_solicitante.setEditable(True)
        
        self.txt_area = QLineEdit()
        self.txt_area.setPlaceholderText("Ej. Departamento Jurídico")

        self.txt_correo = QLineEdit()
        self.txt_correo.setPlaceholderText("correo@conagua.gob.mx")

        self.date_vencimiento = QDateEdit()
        self.date_vencimiento.setCalendarPopup(True)
        self.date_vencimiento.setDate(QDate.currentDate().addDays(DIAS_PRESTAMO_DEFAULT)) 
        self.date_vencimiento.setDisplayFormat("dd-MM-yyyy")

        self.txt_observaciones = QTextEdit()
        self.txt_observaciones.setPlaceholderText("Motivo del préstamo o condiciones de entrega...")

        # 2. Configurar buscador inteligente
        completer = self.cmb_solicitante.completer()
        if completer:
            completer.setFilterMode(Qt.MatchContains)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            completer.setCompletionMode(QCompleter.PopupCompletion)
            
        self.cmb_solicitante.addItem("")
        self.cmb_solicitante.lineEdit().setPlaceholderText("Seleccione del directorio o escriba un nombre...")

        # 3. Poblamos la lista y creamos un "Diccionario Secreto" en memoria
        self.diccionario_contactos = {}

        for contacto in self.lista_contactos:
            llaves = {str(k).lower().strip(): k for k in contacto.keys()}
            llave_nombre = next((ko for kc, ko in llaves.items() if 'nombre' in kc), None)
            nombre = contacto.get(llave_nombre, '') if llave_nombre else ''

            if not nombre and contacto.values():
                nombre = list(contacto.values())[0]

            nombre_texto = str(nombre).strip()
            if nombre_texto:
                self.cmb_solicitante.addItem(nombre_texto)
                # Vinculamos el texto exacto con sus datos
                self.diccionario_contactos[nombre_texto] = contacto 

        # 4. Diseño del Formulario
        form_layout = QFormLayout()
        form_layout.addRow("Solicitante (*):", self.cmb_solicitante)
        form_layout.addRow("Área / Puesto:", self.txt_area)
        form_layout.addRow("Correo:", self.txt_correo)
        form_layout.addRow("Fecha Límite (*):", self.date_vencimiento)
        form_layout.addRow("Observaciones:", self.txt_observaciones)
        layout.addLayout(form_layout)

        # 5. Botones
        self.btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        
        # Extraemos el botón OK, le cambiamos el texto y le ponemos el estilo VERDE
        btn_registrar = self.btn_box.button(QDialogButtonBox.Ok)
        btn_registrar.setText("Registrar Préstamo")
        btn_registrar.setObjectName("btn_exito")
        
        # Extraemos el botón Cancelar, le cambiamos el texto y le ponemos el estilo ROJO
        btn_cancelar = self.btn_box.button(QDialogButtonBox.Cancel)
        btn_cancelar.setText("Cancelar")
        btn_cancelar.setObjectName("btn_peligro")

        # Conectamos las acciones
        self.btn_box.accepted.connect(self.validar_y_aceptar)
        self.btn_box.rejected.connect(self.reject)
        layout.addWidget(self.btn_box)

        # 6. CONEXIONES CORRECTAS PARA EL RATÓN Y EL TABULADOR
        self.cmb_solicitante.completer().activated.connect(self.autocompletar_datos)
        self.cmb_solicitante.lineEdit().editingFinished.connect(self.forzar_actualizacion_tabulador)
        self.cmb_solicitante.activated[str].connect(self.autocompletar_datos)

    def forzar_actualizacion_tabulador(self):
        """Se activa al presionar TAB. Captura el texto final y autocompleta."""
        texto_final = self.cmb_solicitante.currentText()
        self.autocompletar_datos(texto_final)

    def autocompletar_datos(self, texto_seleccionado):
        """Busca el correo y el puesto directamente en el diccionario usando el texto exacto."""
        texto_limpio = str(texto_seleccionado).strip()
        contacto = self.diccionario_contactos.get(texto_limpio)
        
        # Si es alguien nuevo que no está en el Excel, limpiamos
        if not contacto:
            self.txt_correo.clear()
            self.txt_area.clear()
            return
            
        # Limpiamos las llaves del Excel quitando espacios extra
        contacto_exacto = {str(k).strip(): v for k, v in contacto.items()}
        
        # Extraer CORREO directo
        correo = contacto_exacto.get(COLUMNAS_DIRECTORIO["correo"], "")
        if str(correo).lower() in ["nan", "nat", "none", "null", ""]:
            self.txt_correo.clear()
        else:
            self.txt_correo.setText(str(correo).strip())
            
        # Extraer PUESTO directo
        puesto = contacto_exacto.get(COLUMNAS_DIRECTORIO["puesto"], "")
        if str(puesto).lower() in ["nan", "nat", "none", "null", ""]:
            self.txt_area.clear()
        else:
            self.txt_area.setText(str(puesto).strip())

    def validar_y_aceptar(self):
        if self.cmb_solicitante.currentText().strip() == "":
            QMessageBox.warning(self, "Error", "El nombre del solicitante es obligatorio.")
            return
        self.accept()

    def get_datos(self):
        """Empaqueta los datos para guardarlos en la base de datos."""
        obs_final = self.txt_observaciones.toPlainText().strip()
        correo = self.txt_correo.text().strip()
        
        if correo:
            obs_final = f"{obs_final}\n[Correo: {correo}]".strip()

        return {
            'solicitante': self.cmb_solicitante.currentText().strip(),
            'area': self.txt_area.text().strip(),
            'fecha_vencimiento': self.date_vencimiento.date().toString("yyyy-MM-dd"),
            'observaciones': obs_final
        }