
# -*- coding: utf-8 -*-
# ui/exportar_dialog.py

import os
import shutil
import tempfile
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QCheckBox, QMessageBox, QFileDialog, QScrollArea, QWidget, QLabel)
from PyQt5.QtCore import Qt

from negocio.email_service import EmailService
from ui.contacto_dialog import ContactoDialog
from .dialog_helpers import mostrar_mensaje

class ExportarDialog(QDialog):
    def __init__(self, expediente_service, expediente_id, parent=None):
        super().__init__(parent)
        self.expediente_service = expediente_service
        self.expediente_id = expediente_id
        
        self.vista_data = self.expediente_service.obtener_vista_completa_expediente(self.expediente_id)
        self.expediente_data = self.vista_data.get("expediente", {}) if self.vista_data else {}
        
        self.clasificacion = self.expediente_data.get('clasificacion', 'No asignada')
        self.asunto = self.expediente_data.get('asunto', 'Sin descripción')
            
        self.setWindowTitle(f"Exportar Expediente ID: {self.expediente_id}")
        self.setMinimumSize(450, 500)
        
        self.items_exportables = []
        self.init_ui()
        self.cargar_opciones()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Título conectado a estilos.qss (title_label)
        texto_titulo = (f"Expediente ID: {self.expediente_id}\n"
                        f"Clasificación: {self.clasificacion}\n\n"
                        f"Seleccione los documentos a incluir:")
                        
        lbl_titulo = QLabel(texto_titulo)
        lbl_titulo.setObjectName("title_label") # Usa el estilo global
        layout.addWidget(lbl_titulo)
        
        # Área con scroll conectada a estilos.qss
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("area_exportacion")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_area.setWidget(self.scroll_content)
        layout.addWidget(self.scroll_area)
        
        # Botones de Acción
        btn_layout = QHBoxLayout()
        
        self.btn_zip = QPushButton("💾 Guardar como ZIP")
        self.btn_zip.setObjectName("btn_zip") # Usa el color verde de tu QSS
        self.btn_zip.clicked.connect(self.guardar_como_zip)
        
        self.btn_correo = QPushButton("📧 Enviar por Correo")
        self.btn_correo.setObjectName("btn_correo") # Usa el nuevo color oscuro de tu QSS
        self.btn_correo.clicked.connect(self.enviar_por_correo)
        
        btn_layout.addWidget(self.btn_zip)
        btn_layout.addWidget(self.btn_correo)
        
        layout.addLayout(btn_layout)

    def cargar_opciones(self):
        if not self.vista_data: return
        
        expediente = self.expediente_data
        respuestas = self.vista_data.get("respuestas", [])
        
        # 1. Documento Principal
        ruta_doc_princ = expediente.get('documento_respaldo')
        if ruta_doc_princ:
            self.agregar_checkbox("📄 Documento Principal (Oficio Inicial)", ruta_doc_princ, is_folder=False)
            
        # 2. Anexos Principales
        ruta_anexos_princ = os.path.abspath(os.path.join(os.getcwd(), "documentos", f"EXP_{self.expediente_id}", "anexos_principales"))
        if os.path.exists(ruta_anexos_princ) and os.listdir(ruta_anexos_princ):
            self.agregar_checkbox("📁 Anexos del Documento Principal", ruta_anexos_princ, is_folder=True)
            
        # 3. Respuestas
        for resp in respuestas:
            resp_id = resp.get('id')
            folio_resp = resp.get('folio', f'ID-{resp_id}')
            
            ruta_doc_resp = resp.get('documento_respuesta')
            if ruta_doc_resp:
                self.agregar_checkbox(f"📄 Respuesta: {folio_resp}", ruta_doc_resp, is_folder=False)
                
            ruta_anexos_resp = os.path.abspath(os.path.join(os.getcwd(), "documentos", f"EXP_{self.expediente_id}", "respuestas", f"RES_{resp_id}", "anexos_respuesta"))
            if os.path.exists(ruta_anexos_resp) and os.listdir(ruta_anexos_resp):
                self.agregar_checkbox(f"📁 Anexos de la Respuesta: {folio_resp}", ruta_anexos_resp, is_folder=True)
        
        self.scroll_layout.addStretch()

    def agregar_checkbox(self, texto, ruta, is_folder):
        chk = QCheckBox(texto)
        chk.setChecked(True)
        self.scroll_layout.addWidget(chk)
        self.items_exportables.append({
            "checkbox": chk,
            "ruta": os.path.abspath(ruta) if not os.path.isabs(ruta) else ruta,
            "is_folder": is_folder,
            "nombre": texto.replace("📄 ", "").replace("📁 ", "").replace(":", "-")
        })

    def ensamblar_carpeta_temporal(self):
        seleccionados = [item for item in self.items_exportables if item["checkbox"].isChecked()]
        if not seleccionados:
            return None
            
        temp_dir = tempfile.mkdtemp(prefix=f"Export_EXP_{self.expediente_id}_")
        
        for item in seleccionados:
            ruta_origen = item["ruta"]
            nombre_limpio = item["nombre"]
            
            if not os.path.exists(ruta_origen): continue
            
            if item["is_folder"]:
                ruta_destino = os.path.join(temp_dir, nombre_limpio)
                shutil.copytree(ruta_origen, ruta_destino)
            else:
                nombre_archivo = os.path.basename(ruta_origen)
                shutil.copy2(ruta_origen, os.path.join(temp_dir, nombre_archivo))
                
        return temp_dir

    def guardar_como_zip(self):
        temp_dir = self.ensamblar_carpeta_temporal()
        if not temp_dir:
            mostrar_mensaje(self, "Atención", "Debe seleccionar al menos un documento.", QMessageBox.Warning)
            return
            
        nombre_sugerido = f"Expediente_{self.expediente_id}.zip"
        ruta_guardado, _ = QFileDialog.getSaveFileName(self, "Guardar Archivo ZIP", nombre_sugerido, "Archivos ZIP (*.zip)")
        
        if ruta_guardado:
            try:
                base_name = ruta_guardado.replace('.zip', '')
                shutil.make_archive(base_name, 'zip', temp_dir)
                mostrar_mensaje(self, "Éxito", "Archivo ZIP creado correctamente.", QMessageBox.Information)
            except Exception as e:
                mostrar_mensaje(self, "Error", f"No se pudo crear el ZIP: {e}", QMessageBox.Critical)
                
        shutil.rmtree(temp_dir, ignore_errors=True)

    def enviar_por_correo(self):
        temp_dir = self.ensamblar_carpeta_temporal()
        if not temp_dir:
            mostrar_mensaje(self, "Atención", "Debe seleccionar al menos un documento.", QMessageBox.Warning)
            return
            
        email_service = EmailService()
        if not email_service.outlook:
            mostrar_mensaje(self, "Error", "Outlook no está disponible en este sistema.", QMessageBox.Critical)
            shutil.rmtree(temp_dir, ignore_errors=True)
            return
            
        exito, contactos = email_service.leer_contactos_excel()
        if not exito:
            mostrar_mensaje(self, "Error", str(contactos), QMessageBox.Warning)
            shutil.rmtree(temp_dir, ignore_errors=True)
            return
            
        dialogo = ContactoDialog(contactos, self)
        if dialogo.exec_() == QDialog.Accepted and dialogo.selected_email:
            destinatario = dialogo.selected_email
            
            try:
                nombre_zip = f"Expediente_{self.expediente_id}.zip"
                zip_path = os.path.join(tempfile.gettempdir(), nombre_zip)
                
                if os.path.exists(zip_path): os.remove(zip_path)
                shutil.make_archive(zip_path.replace('.zip', ''), 'zip', temp_dir)
                
                fecha_exp = self.expediente_data.get('fecha', 'No especificada')
                serie_doc = self.expediente_data.get('serie_documental', 'No especificada')
                
                asunto = f"Documentación del Expediente ID: {self.expediente_id} ({self.clasificacion})"
                
                cuerpo = (
                    f"Estimado/a,\n\n"
                    f"Le envío adjuntos los documentos seleccionados relacionados con el expediente con clasificación {self.clasificacion}\n\n"
                    f"Detalles del expediente:\n"
                    f"• ID: {self.expediente_id}\n"
                    f"• Fecha: {fecha_exp}\n"
                    f"• Asunto: {self.asunto}\n"
                    f"• Serie Documental: {serie_doc}\n\n"
                    f"Atentamente,\n"
                    f"Sistema de Gestión de Expedientes\n"
                )
                
                exito_envio, msg = email_service.enviar_correo_con_adjuntos(destinatario, asunto, cuerpo, [zip_path])
                
                if exito_envio:
                    mostrar_mensaje(self, "Éxito", "El correo con el ZIP adjunto ha sido enviado a Outlook.", QMessageBox.Information)
                    self.accept()
                else:
                    mostrar_mensaje(self, "Error", msg, QMessageBox.Critical)
                    
            except Exception as e:
                mostrar_mensaje(self, "Error", f"Fallo al procesar el envío: {e}", QMessageBox.Critical)
        
        shutil.rmtree(temp_dir, ignore_errors=True)