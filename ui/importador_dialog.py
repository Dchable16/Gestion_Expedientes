# -*- coding: utf-8 -*-
"""
Created on Thu Jul 31 13:38:44 2025

@author: dchable
"""

# ui/importador_dialog.py

import pandas as pd
import logging
import os

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QLabel, QProgressBar,
                             QMessageBox, QRadioButton, QCheckBox, QGroupBox, QLineEdit, QTextEdit, QComboBox,
                             QApplication, QSizePolicy)

from PyQt5.QtCore import Qt, pyqtSignal
from datetime import datetime

from datos.expediente_repository import ExpedienteRepository
from negocio.expediente_service import ExpedienteService
from logging.handlers import RotatingFileHandler
from negocio.import_service import ImportService
from utils.concurrencia import GestorTareas
from .dialog_helpers import mostrar_mensaje

class ImportadorDialog(QDialog):
    
    senal_progreso = pyqtSignal(int)
    senal_mensaje = pyqtSignal(str)
    senal_terminado = pyqtSignal(bool, str)
    
    def __init__(self, import_service: ImportService, parent=None):
        super().__init__(parent)
        self.import_service = import_service
        self.parent_window = parent
        self.import_service_background = None
        self.setWindowTitle("Importar Base de Datos")
        self.setMinimumSize(800, 600)
        
        self.init_ui()
        self.connect_signals()
        self.actualizar_ui_por_tipo('sqlite')

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        grp_tipo = QGroupBox("Tipo de archivo")
        layout_tipo = QHBoxLayout(grp_tipo)
        self.radio_sqlite = QRadioButton("SQLite (.db)")
        self.radio_excel = QRadioButton("Excel (.xlsx)")
        self.radio_csv = QRadioButton("CSV (.csv)")
        self.radio_sqlite.setChecked(True)
        layout_tipo.addWidget(self.radio_sqlite)
        layout_tipo.addWidget(self.radio_excel)
        layout_tipo.addWidget(self.radio_csv)
        
        grp_origen = QGroupBox("Origen de datos")
        layout_origen = QVBoxLayout(grp_origen)
        layout_origen_archivo = QHBoxLayout()
        self.txt_origen = QLineEdit(readOnly=True)
        self.btn_examinar_origen = QPushButton("Examinar...")
        layout_origen_archivo.addWidget(QLabel("Archivo origen:"))
        layout_origen_archivo.addWidget(self.txt_origen, 1)
        layout_origen_archivo.addWidget(self.btn_examinar_origen)
        
        layout_especificas = QHBoxLayout()
        self.lbl_hoja = QLabel("Hoja:")
        self.cmb_hoja = QComboBox()
        self.lbl_separador = QLabel("Separador:")
        self.txt_separador = QLineEdit(",")
        self.txt_separador.setMaximumWidth(50)
        
        layout_especificas.addWidget(self.lbl_hoja)
        layout_especificas.addWidget(self.cmb_hoja)
        layout_especificas.addWidget(self.lbl_separador)
        layout_especificas.addWidget(self.txt_separador)
        layout_especificas.addStretch()
        
        layout_origen.addLayout(layout_origen_archivo)
        layout_origen.addLayout(layout_especificas)

        layout_opciones_hor = QHBoxLayout()
        
        self.grp_tipo_datos = QGroupBox("Datos a importar (Excel/CSV)")
        layout_tipo_datos = QVBoxLayout(self.grp_tipo_datos)
        self.radio_importar_expedientes = QRadioButton("Importar Expedientes")
        self.radio_importar_respuestas = QRadioButton("Importar Respuestas")
        self.radio_importar_conocimiento = QRadioButton("Importar Documentos de Conocimiento")
        self.radio_importar_cg = QRadioButton("Importar Control de Gestión")
        self.radio_importar_expedientes.setChecked(True)
        layout_tipo_datos.addWidget(self.radio_importar_expedientes)
        layout_tipo_datos.addWidget(self.radio_importar_respuestas)
        layout_tipo_datos.addWidget(self.radio_importar_conocimiento)
        layout_tipo_datos.addWidget(self.radio_importar_cg)
        layout_opciones_hor.addWidget(self.grp_tipo_datos)
        
        grp_conflictos = QGroupBox("Resolución de conflictos")
        layout_conflictos = QVBoxLayout(grp_conflictos)
        self.radio_mantener = QRadioButton("Mantener existentes")
        self.radio_sobrescribir = QRadioButton("Sobrescribir existentes")
        self.radio_renombrar = QRadioButton("Importar como nuevos")
        self.radio_mantener.setChecked(True)
        layout_conflictos.addWidget(self.radio_mantener)
        layout_conflictos.addWidget(self.radio_sobrescribir)
        layout_conflictos.addWidget(self.radio_renombrar)
        layout_opciones_hor.addWidget(grp_conflictos)
        
        grp_opciones_adicionales = QGroupBox("Opciones adicionales")
        layout_opciones_adicionales = QVBoxLayout(grp_opciones_adicionales)
        self.chk_validar_rutas = QCheckBox("Validar rutas de documentos")
        self.chk_copiar_documentos = QCheckBox("Copiar documentos a la carpeta local")
        self.chk_hacer_backup = QCheckBox("Crear copia de seguridad")
        self.chk_hacer_backup.setChecked(True)
        layout_opciones_adicionales.addWidget(self.chk_validar_rutas)
        layout_opciones_adicionales.addWidget(self.chk_copiar_documentos)
        layout_opciones_adicionales.addWidget(self.chk_hacer_backup)
        layout_opciones_hor.addWidget(grp_opciones_adicionales)

        self.txt_log = QTextEdit(readOnly=True)
        self.progress_bar = QProgressBar()
        
        size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.progress_bar.setSizePolicy(size_policy)

        layout_botones = QHBoxLayout()
        self.btn_importar = QPushButton("Iniciar Importación")
        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.setObjectName("btn_eliminar")
        self.btn_cerrar = QPushButton("Cerrar")
        self.btn_cerrar.setObjectName("btn_limpiar")
        self.btn_cancelar.setEnabled(False)
        layout_botones.addStretch()
        layout_botones.addWidget(self.btn_importar)
        layout_botones.addWidget(self.btn_cancelar)
        layout_botones.addWidget(self.btn_cerrar)

        layout.addWidget(grp_tipo)
        layout.addWidget(grp_origen)
        layout.addLayout(layout_opciones_hor)
        layout.addWidget(QLabel("Registro de actividad:"))
        layout.addWidget(self.txt_log, 1)
        layout.addWidget(self.progress_bar)
        layout.addLayout(layout_botones)

    def connect_signals(self):
        self.btn_examinar_origen.clicked.connect(self.seleccionar_origen)
        self.btn_importar.clicked.connect(self.iniciar_importacion)
        self.btn_cancelar.clicked.connect(self.cancelar_importacion)
        self.btn_cerrar.clicked.connect(self.accept)
        
        self.radio_sqlite.toggled.connect(lambda: self.actualizar_ui_por_tipo('sqlite'))
        self.radio_excel.toggled.connect(lambda: self.actualizar_ui_por_tipo('excel'))
        self.radio_csv.toggled.connect(lambda: self.actualizar_ui_por_tipo('csv'))
        
        self.senal_progreso.connect(self.progress_bar.setValue)
        self.senal_mensaje.connect(self.actualizar_log)
        self.senal_terminado.connect(self.on_importacion_finalizada)

    def actualizar_log(self, mensaje):
        log_entry = f"[{datetime.now().strftime('%H:%M:%S')}] {mensaje}"
        self.txt_log.append(log_entry)
        QApplication.processEvents()

    def actualizar_ui_por_tipo(self, tipo):
        es_excel = (tipo == 'excel')
        es_csv = (tipo == 'csv')
        
        self.lbl_hoja.setVisible(es_excel)
        self.cmb_hoja.setVisible(es_excel)
        self.lbl_separador.setVisible(es_csv)
        self.txt_separador.setVisible(es_csv)
        self.grp_tipo_datos.setVisible(es_excel or es_csv)
        
        self.txt_origen.clear()
        self.cmb_hoja.clear()

    def seleccionar_origen(self):
        if self.radio_sqlite.isChecked(): filtro = "Bases de datos SQLite (*.db)"
        elif self.radio_excel.isChecked(): filtro = "Archivos Excel (*.xlsx)"
        else: filtro = "Archivos CSV (*.csv)"
        ruta, _ = QFileDialog.getOpenFileName(self, "Seleccionar archivo", "", filtro)
        if ruta:
            self.txt_origen.setText(ruta)
            if self.radio_excel.isChecked():
                self.cargar_hojas_excel(ruta)

    def cargar_hojas_excel(self, ruta_excel):
        try:
            xls = pd.ExcelFile(ruta_excel)
            self.cmb_hoja.addItems(xls.sheet_names)
        except Exception as e:
            logging.error("No se pudieron cargar las hojas del archivo Excel: %s", e, exc_info=True)
            mostrar_mensaje(self,"Error", f"No se pudieron cargar las hojas del archivo Excel: {e}", QMessageBox.Warning)

    def iniciar_importacion(self):
        ruta_origen = self.txt_origen.text().strip()
        if not ruta_origen:
            mostrar_mensaje(self, "Error", "Debe seleccionar un archivo de origen.", QMessageBox.Warning)
            return

        # Construimos el diccionario de opciones
        opciones = {
            'tipo_importacion': 'excel' if self.radio_excel.isChecked() else 'csv' if self.radio_csv.isChecked() else 'sqlite',
            'hoja_excel': self.cmb_hoja.currentText(),
            'separador_csv': self.txt_separador.text(),
            'hacer_backup': self.chk_hacer_backup.isChecked(),
            'validar_rutas': self.chk_validar_rutas.isChecked(),
            'copiar_documentos': self.chk_copiar_documentos.isChecked(),
            'importar_respuestas': self.radio_importar_respuestas.isChecked(),
            'importar_conocimiento': self.radio_importar_conocimiento.isChecked(),
            'importar_cg': self.radio_importar_cg.isChecked(),
            'resolucion_conflictos': 'sobrescribir' if self.radio_sobrescribir.isChecked() else 'renombrar' if self.radio_renombrar.isChecked() else 'mantener',
        }

        # --- VALIDACIÓN DE COLUMNAS FLEXIBLE ---
        if opciones['tipo_importacion'] in ['excel', 'csv']:
            try:
                # 1. Leer encabezados
                if opciones['tipo_importacion'] == 'excel':
                    if not opciones['hoja_excel']:
                        mostrar_mensaje(self, "Error", "Debe seleccionar una hoja.", QMessageBox.Warning)
                        return
                    df_header = pd.read_excel(ruta_origen, sheet_name=opciones['hoja_excel'], nrows=0)
                else:
                    sep = opciones['separador_csv'] if opciones['separador_csv'] else ','
                    df_header = pd.read_csv(ruta_origen, sep=sep, nrows=0)

                # 2. Normalizar nombres de columnas del archivo (minúsculas y sin espacios extra)
                columnas_archivo = [str(col).lower().strip() for col in df_header.columns]

                # 3. Definir variantes aceptadas
                variantes = {
                    'folio': ['folio', 'num_oficio', 'oficio', 'numero', 'expediente'],
                    'fecha': ['fecha', 'fecha_recepcion','fecha recepción', 'recepcion', 'fecha_respuesta', 'fecha_apertura' ], 
                    'remitente': ['remitente', 'enviado_por', 'origen'],
                    'asunto': ['asunto', 'descripcion', 'tema', 'asunto_respuesta'],
                    'expediente_id': ['expediente_id', 'id_expediente', 'id_padre'],
                    'serie_documental': ['serie', 'serie_documental', 'codigo_serie'],
                    'tipo_documento': ['tipo', 'tipo_documento'],
                    'categoria_documental': ['categoria', 'categoria_documental'],
                    'carpeta': ['carpeta', 'ubicacion_fisica']
                }

                columnas_requeridas = []
                tipo_datos = ""

                # 4. Definir qué buscamos y qué NO DEBE ESTAR (Seguridad)
                columna_prohibida = None
                variantes_prohibidas = []

                if opciones['importar_respuestas']:
                    columnas_requeridas = ['expediente_id', 'fecha', 'asunto']
                    tipo_datos = "Respuestas"
                
                elif opciones['importar_conocimiento']:
                    columnas_requeridas = ['folio', 'asunto']
                    # SEGURIDAD: Un archivo de Conocimiento NO debe tener instrucciones ni turnados
                    columna_prohibida = 'instruccion' 
                    variantes_prohibidas = ['instruccion', 'instrucción', 'turnado_a', 'turnado',
                                            'serie_documental', 'serie', 'codigo_serie']
                    tipo_datos = "Conocimiento"
                
                elif opciones['importar_cg']:
                    columnas_requeridas = ['folio', 'fecha', 'asunto', 'remitente']
                    tipo_datos = "Control de Gestión"
                
                else: # Expedientes
                    columnas_requeridas = ['folio', 'fecha', 'asunto', 'serie_documental']
                    # SEGURIDAD: Un expediente maestro NO debe tener ID de padre
                    columna_prohibida = 'expediente_id'
                    variantes_prohibidas = ['expediente_id', 'id_expediente']
                    tipo_datos = "Expedientes"

                # PASO 4.5: VALIDACIÓN DE SEGURIDAD EXTRA
                # Si estamos importando Expedientes, pero el archivo tiene 'expediente_id',
                # es 99% seguro que es un archivo de Respuestas seleccionado por error.
                if columna_prohibida:
                    tiene_prohibida = False
                    
                    # 1. Buscamos la prohibida exacta
                    if columna_prohibida in columnas_archivo:
                        tiene_prohibida = True
                    
                    # 2. Buscamos en las variantes prohibidas manuales
                    if not tiene_prohibida:
                        for prohibida in variantes_prohibidas:
                            # Normalizamos la prohibida para comparar
                            p_norm = str(prohibida).lower().strip()
                            if p_norm in columnas_archivo:
                                tiene_prohibida = True
                                break
                    
                    # 3. Buscamos en el diccionario de variantes general (fallback)
                    if not tiene_prohibida and columna_prohibida in variantes:
                        for var in variantes[columna_prohibida]:
                            if var in columnas_archivo:
                                tiene_prohibida = True
                                break
                    
                    if tiene_prohibida:
                        msg = (f"⚠️ <b>¡ALERTA DE SEGURIDAD!</b><br><br>"
                               f"Estás intentando importar <b>{tipo_datos}</b>, pero el archivo seleccionado parece incorrecto.<br>"
                               f"Detectamos columnas exclusivas de otro tipo de datos (ej. '{columna_prohibida}' o similares).<br><br>"
                               f"Por favor verifica que seleccionaste la opción correcta en el menú.")
                        mostrar_mensaje(self, "Archivo Incorrecto", msg, QMessageBox.Critical)
                        return

                # 5. Validación de Columnas Faltantes (Normal)
                columnas_faltantes = []
                for col_req in columnas_requeridas:
                    encontrado = False
                    if col_req in columnas_archivo:
                        encontrado = True
                    elif col_req in variantes:
                        for var in variantes[col_req]:
                            if var in columnas_archivo:
                                encontrado = True
                                break
                    if not encontrado:
                        columnas_faltantes.append(col_req)

                if columnas_faltantes:
                    msg = (f"El archivo no parece válido para importar <b>{tipo_datos}</b>.<br><br>"
                           f"No se encontraron las siguientes columnas (ni sus variantes):<br>"
                           f"<b>{', '.join(columnas_faltantes)}</b><br><br>"
                           f"Columnas detectadas: {', '.join(df_header.columns)}")
                    mostrar_mensaje(self, "Error de Columnas", msg, QMessageBox.Critical)
                    return

            except Exception as e:
                logging.error("Error validando columnas: %s", e, exc_info=True)
                mostrar_mensaje(self, "Error de Lectura", f"No se pudo leer el archivo:\n{e}", QMessageBox.Critical)
                return
        
        # --- INICIO DEL PROCESO ---
        self.btn_importar.setEnabled(False)
        self.btn_cancelar.setEnabled(True)
        self.txt_log.clear()

        db_path = self.import_service.ruta_destino
        senales_dict = {
            'progreso': self.senal_progreso,
            'mensaje': self.senal_mensaje,
            'terminado': self.senal_terminado
        }
        
        GestorTareas.ejecutar_en_segundo_plano(self._ejecutar_importacion_aislada, None, db_path, ruta_origen, opciones, senales_dict)
    
    def _ejecutar_importacion_aislada(self, db_path, ruta_origen, opciones, senales_dict):
        """
        Ejecución limpia que vive en el ThreadPool.
        Maneja su propia instancia SQLite para garantizar concurrencia libre de riesgos.
        """
        repo = None
        try:
            repo = ExpedienteRepository(db_name=db_path)
            exp_service = ExpedienteService(repo)
            self.import_service_background = ImportService(db_path, exp_service, repo)
            self.import_service_background.iniciar_importacion(ruta_origen, opciones, senales_dict)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            senales_dict['terminado'].emit(False, f"Error en hilo de fondo: {str(e)}")
        finally:
            if repo:
                repo.close_connection()
    
    def cancelar_importacion(self):
        """
        Envía una orden pacífica al hilo del fondo (import_service_background) para detener 
        el proceso de inserción y hacer rollback de la transacción SQLite.
        """
        self.actualizar_log("Solicitando cancelación de la importación...")
        self.btn_cancelar.setEnabled(False) # Para que no presione 100 veces "cancelar"
        
        if self.import_service_background:
            self.import_service_background.cancelar()

    def on_importacion_finalizada(self, exito, mensaje):
        """Slot llamado mágicamente por el ThreadPool al terminar/cancelar."""
        self.actualizar_log(mensaje)
        
        self.btn_importar.setEnabled(True)
        self.btn_cancelar.setEnabled(False)
        
        if exito:
            QMessageBox.information(self, "Proceso Completado", "Importación completada exitosamente.")
            self.accept() # Cerrar el diálogo y que todo el sistema (MainWindow) se refresque
        else:
            QMessageBox.critical(self, "Error o Interrupción", mensaje)
