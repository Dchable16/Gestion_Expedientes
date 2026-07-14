# -*- coding: utf-8 -*-
# ui/visualizador_expediente.py

import os
import sys
import webbrowser
import platform
import subprocess
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QSplitter, QTabWidget, QTextBrowser,
                             QListWidget, QListWidgetItem, QPushButton, QLabel, QFileDialog, QFrame,
                             QMessageBox, QWidget, QGridLayout, QSizePolicy, QStyle)
                           
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import Qt, QUrl, QSize
from PyQt5.QtGui import QIcon

from datetime import datetime

from negocio.expediente_service import ExpedienteService
from ui.gestor_anexos_dialog import GestorAnexosDialog
from utils.config_manager import get_plano_path
from .dialog_helpers import mostrar_mensaje

# --- IMPORTAMOS NUESTRA NUEVA CLASE ---
from ui.exportar_dialog import ExportarDialog

class VisualizadorExpediente(QDialog):
    def __init__(self, expediente_service: ExpedienteService, expediente_id: int, parent=None):
        super().__init__(parent)
        self.expediente_service = expediente_service
        self.expediente_id = expediente_id
        self.plano_ubicacion_pdf = get_plano_path()
        self.ruta_anexos_actual = ""
        self.setWindowTitle(f"Visualizador de Expediente #{self.expediente_id}")
        self.setMinimumSize(1024, 768)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)
        self.init_ui()
        self.cargar_datos_completos()

    def init_ui(self):
        
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        header_frame = self.crear_encabezado()
        
        splitter = QSplitter(Qt.Horizontal)
        self.lista_documentos = QListWidget()
        self.lista_documentos.setMaximumWidth(400)
        self.lista_documentos.itemClicked.connect(self.mostrar_documento)
        
        self.visor = self.crear_visor()
        
        splitter.addWidget(self.lista_documentos)
        splitter.addWidget(self.visor)
        splitter.setSizes([250, 750])
        
        self.btn_abrir_anexos = QPushButton("📁 Abrir Anexos")
        self.btn_abrir_anexos.setObjectName("btn_abrir_anexos")
        self.btn_abrir_anexos.setCursor(Qt.PointingHandCursor)
        self.btn_abrir_anexos.clicked.connect(self.abrir_carpeta_anexos_actual)
        self.btn_abrir_anexos.setFixedHeight(32)
        
        self.btn_exportar = QPushButton("📤 Exportar / Compartir")
        self.btn_exportar.setObjectName("btn_exportar_main")
        self.btn_exportar.setCursor(Qt.PointingHandCursor)
        self.btn_exportar.clicked.connect(self.abrir_exportacion)
        self.btn_exportar.setFixedHeight(32)
        
        btn_plano = QPushButton("Ver Plano de Ubicación")
        btn_plano.clicked.connect(self.mostrar_plano_ubicacion)
        btn_plano.setFixedHeight(32)
        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.setObjectName("btn_cancelar")
        btn_cerrar.clicked.connect(self.accept)
        btn_cerrar.setFixedHeight(32)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.btn_abrir_anexos)
        btn_layout.addWidget(self.btn_exportar) 
        btn_layout.addStretch()
        btn_layout.addWidget(btn_plano)
        btn_layout.addWidget(btn_cerrar)
        
        main_layout.addWidget(header_frame)
        main_layout.addWidget(splitter, 1)
        main_layout.addLayout(btn_layout)

    def crear_encabezado(self):
        header_frame = QFrame()
        header_frame.setFrameShape(QFrame.StyledPanel)
        header_frame.setObjectName("header_frame_visualizador")
        header_layout = QGridLayout(header_frame)
        header_layout.setSpacing(1)
        header_layout.setContentsMargins(3, 3, 3, 3)
        
        title_label = QLabel("INFORMACIÓN DEL EXPEDIENTE")
        title_label.setObjectName("title_label") 
        header_layout.addWidget(title_label, 0, 0, 1, 2)
        
        self.lbl_expediente = QLabel("<b>Expediente:</b>")
        self.lbl_periodo = QLabel("<b>Período del Trámite:</b>")
        self.lbl_clasificacion = QLabel("<b>Clasificación Archivistica:</b>")
        self.lbl_valor_doc = QLabel("<b>Valor Documental:</b>")
        self.lbl_folios = QLabel("<b>Folios:</b>")
        self.lbl_vigencia = QLabel("<b>Vigencia documental:</b>")
        self.lbl_acceso = QLabel("<b>Condiciones de Acceso:</b>")
        self.lbl_tradicion = QLabel("<b>Tradición Documental:</b>")

        header_layout.addWidget(self.lbl_expediente, 1, 0)
        header_layout.addWidget(self.lbl_periodo, 1, 1)
        header_layout.addWidget(self.lbl_clasificacion, 2, 0)
        header_layout.addWidget(self.lbl_valor_doc, 2, 1)
        header_layout.addWidget(self.lbl_folios, 3, 0)
        header_layout.addWidget(self.lbl_vigencia, 3, 1)
        header_layout.addWidget(self.lbl_acceso, 4, 0)
        header_layout.addWidget(self.lbl_tradicion, 4, 1)
        header_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        return header_frame

    def crear_visor(self):
        visor = QTabWidget()
        self.metadatos_widget = QTextBrowser()
        self.metadatos_widget.setObjectName("metadatos_browser")
        self.visor_pdf = QWebEngineView()
        self.visor_pdf.settings().setAttribute(self.visor_pdf.settings().PluginsEnabled, True)
        self.visor_pdf.settings().setAttribute(self.visor_pdf.settings().PdfViewerEnabled, True)
        self.visor_pdf.setHtml("<body style='background-color:#f0f0f0'><p style='text-align:center;color:#555;margin-top:20px;'>Seleccione un documento para previsualizar</p></body>")
        visor.addTab(self.metadatos_widget, "Metadatos")
        visor.addTab(self.visor_pdf, "Vista Previa")
        return visor

    def cargar_datos_completos(self):
        vista_data = self.expediente_service.obtener_vista_completa_expediente(self.expediente_id)
        if not vista_data:
            mostrar_mensaje(self, "No se pudo cargar la información del expediente.", QMessageBox.Critical)
            self.reject()
            return

        self.poblar_encabezado(vista_data.get("expediente", {}), vista_data.get("info_serie", {}), vista_data.get("respuestas", []))
        self.poblar_lista_documentos(vista_data.get("expediente", {}), vista_data.get("respuestas", []))
        
        if self.lista_documentos.count() > 0:
            self.lista_documentos.setCurrentRow(0)
            self.mostrar_documento(self.lista_documentos.item(0))

    def poblar_encabezado(self, expediente, info_serie, respuestas):
        clasificacion = expediente.get('clasificacion', 'N/A')
        num_expediente = clasificacion.split('/')[2] if len(clasificacion.split('/')) > 2 else "N/A"
        self.lbl_expediente.setText(f"<b>Expediente:</b> {num_expediente}")
        self.lbl_periodo.setText(f"<b>Período:</b> {expediente.get('apertura', 'N/A')} - {expediente.get('cierre') or 'Abierto'}")
        self.lbl_clasificacion.setText(f"<b>Clasificación:</b> {clasificacion}")
        
        total_folios = expediente.get('paginas', 0) or 0
        for r in respuestas:
            total_folios += r.get('paginas', 0) or 0
        self.lbl_folios.setText(f"<b>Folios:</b> {total_folios}")
        
        if info_serie:
            valor_doc = [v for k, v in {"administrativo": "Administrativo", "legal": "Legal", "fiscal": "Fiscal"}.items() if info_serie.get(k) == 'X']
            self.lbl_valor_doc.setText(f"<b>Valor Documental:</b> {', '.join(valor_doc) or 'No especificado'}")

            vigencia = [f"{v} ({info_serie.get(k)} año{'s' if int(info_serie.get(k, 0)) > 1 else ''})" 
                        for k, v in {"tramite": "Trámite", "concentracion": "Concentración", "total": "Total"}.
                        items() if info_serie.get(k) and str(info_serie.get(k)).isdigit() and int(info_serie.get(k)) > 0]
            self.lbl_vigencia.setText(f"<b>Vigencia:</b> {', '.join(vigencia) or 'No especificada'}")

            acceso = [v for k, v in {"publica": "Pública", "reservada": "Reservada", "confidencial": "Confidencial"}.items() if info_serie.get(k) == 'X']
            self.lbl_acceso.setText(f"<b>Acceso:</b> {', '.join(acceso) or 'No especificado'}")

            tradicion = [v for k, v in {"original": "Original", "copia": "Copia"}.items() if info_serie.get(k) == 'X']
            self.lbl_tradicion.setText(f"<b>Tradición:</b> {', '.join(tradicion) or 'No especificada'}")

    def poblar_lista_documentos(self, expediente, respuestas):
        """
        Organiza todos los documentos del expediente de manera CRONOLÓGICA (Del más antiguo al más reciente).
        Asigna nombres archivísticos profesionales para formar la Línea de Vida del Trámite.
        """
        self.lista_documentos.clear()
        
        # 1. Unificamos todos los documentos en una sola lista temporal
        lista_ordenada = []
        
        # --- A) El Documento que aperturó el Expediente (El Raíz) ---
        fecha_raiz = expediente.get('fecha', '1900-01-01') 
        lista_ordenada.append({
            'es_raiz': True,
            'fecha_orden': fecha_raiz,
            'folio': expediente.get('folio', 'S/F'),
            'paginas': expediente.get('paginas', '0'),
            'datos': expediente
        })
        
        # --- B) Todos los documentos subsecuentes (Las "Respuestas") ---
        for resp in respuestas:
            lista_ordenada.append({
                'es_raiz': False,
                'fecha_orden': resp.get('fecha_respuesta', '2099-01-01'), 
                'folio': resp.get('folio', 'S/F'),
                'tipo': resp.get('tipo_documento', 'Trámite'),
                'paginas': resp.get('paginas', '0'),
                'datos': resp
            })
            
        # 2. ORDENACIÓN CRONOLÓGICA REAL
        lista_ordenada.sort(key=lambda x: x['fecha_orden'])
        
        # 3. Dibujar en la pantalla la "Línea de Vida" del Expediente
        folio_acumulado = 0
        
        for idx, doc in enumerate(lista_ordenada, 1):
            paginas = int(doc['paginas']) if str(doc['paginas']).isdigit() else 0
            folio_acumulado += paginas
            fojas_txt = f"({paginas} fojas)" if paginas > 0 else ""

            if doc['es_raiz']:
                titulo = f"{idx}. Oficio Inicial / Apertura\nFolio: {doc['folio']} {fojas_txt}"
                icono = self.style().standardIcon(QStyle.SP_DirOpenIcon) 
                item = QListWidgetItem(QIcon(icono), titulo)
                item.setData(Qt.UserRole, {'tipo': 'expediente', 'datos': doc['datos']})
                
            else:
                tipo_txt = doc['tipo'].capitalize() if doc['tipo'] != "RESPUESTA" else "Oficio de Trámite"
                titulo = f"{idx}. {tipo_txt}\nFolio: {doc['folio']} {fojas_txt}"
                icono = self.style().standardIcon(QStyle.SP_FileIcon) 
                item = QListWidgetItem(QIcon(icono), titulo)
                item.setData(Qt.UserRole, {'tipo': 'respuesta', 'datos': doc['datos']})

            font = item.font()
            font.setBold(doc['es_raiz']) 
            item.setFont(font)
            
            self.lista_documentos.addItem(item)
            
            # Espaciador visual invisible entre oficios
            espaciador = QListWidgetItem("")
            espaciador.setFlags(Qt.NoItemFlags)
            # AQUI ESTA LA CORRECCION MÁGICA DE QSize
            espaciador.setSizeHint(QSize(10, 5)) 
            self.lista_documentos.addItem(espaciador)

    def mostrar_documento(self, item):
        if not item: return
        data = item.data(Qt.UserRole)
        
        # Validación extra: si es un ítem de espaciador, ignorar.
        if data is None: return
        
        tipo = data['tipo']
        datos = data['datos'] 
        
        self.mostrar_metadatos(datos, tipo)
        
        ruta_documento = datos.get('documento_respaldo') if tipo == 'expediente' else datos.get('documento_respuesta')
        self.actualizar_visor_pdf(ruta_documento)
        
        if tipo == 'expediente':
            self.ruta_anexos_actual = os.path.abspath(os.path.join(os.getcwd(), "documentos", f"EXP_{self.expediente_id}", "anexos_principales"))
        else:
            respuesta_id = datos.get('id')
            self.ruta_anexos_actual = os.path.abspath(os.path.join(os.getcwd(), "documentos", f"EXP_{self.expediente_id}", "respuestas", f"RES_{respuesta_id}", "anexos_respuesta"))

    def mostrar_metadatos(self, datos, tipo):
        html = "<h3>Metadatos del Documento</h3><table>"
        campos = []
        if tipo == 'expediente':
            campos = [("ID", "id"), ("Tipo", "tipo_documento"), ("Categoría", "categoria_documental"), 
                      ("Folio", "folio"), ("Fecha", "fecha"), ("Asunto", "asunto"), ("Serie", "serie_documental"), 
                      ("Carpeta", "carpeta"), ("Páginas", "paginas"), ("Documento", "documento_respaldo")]
        else: # es respuesta
            campos = [("ID", "id"), ("Tipo", "tipo_documento"), ("Categoría", "categoria_documental"), 
                      ("Folio", "folio"), ("Fecha", "fecha_respuesta"), ("Asunto", "asunto_respuesta"), ("Serie", "serie_documental"), 
                      ("Carpeta", "carpeta"), ("Páginas", "paginas"), ("Documento", "documento_respuesta")]
        
        for campo, key in campos:
            valor = datos.get(key, "No especificado")
            if key in ('fecha', 'fecha_respuesta') and valor:
                try:
                    fecha_obj = datetime.strptime(str(valor), '%Y-%m-%d')
                    valor = fecha_obj.strftime('%d-%m-%Y')
                except ValueError:
                    pass
            html += f"<tr><td style='font-weight:bold;padding-right:10px;'>{campo}:</td><td>{valor}</td></tr>"
        html += "</table>"
        self.metadatos_widget.setHtml(html)

    def actualizar_visor_pdf(self, ruta_documento):
        estilo_base = "font-family: Arial; text-align: center; margin-top: 50px; color: #555;"
        
        if not ruta_documento or not str(ruta_documento).strip():
            self.visor_pdf.setHtml(f"<body style='{estilo_base}'>No hay un documento principal (PDF) adjunto.</body>")
            return
        
        ruta_final = None
        if os.path.isabs(ruta_documento) and os.path.exists(ruta_documento):
            ruta_final = ruta_documento
        else:
            try:
                base_path = os.path.dirname(os.path.abspath(sys.argv[0]))
                ruta_relativa = os.path.join(base_path, ruta_documento)
                if os.path.exists(ruta_relativa):
                    ruta_final = ruta_relativa
            except Exception:
                pass 

        if ruta_final:
            if ruta_final.lower().endswith('.pdf'):
                self.visor_pdf.setUrl(QUrl.fromLocalFile(os.path.abspath(ruta_final)))
            else:
                self.visor_pdf.setHtml(f"<body style='{estilo_base}'>La vista previa solo está disponible para archivos PDF.<br>Use la carpeta de Anexos para otros formatos.</body>")
        else:
            self.visor_pdf.setHtml(f"<body style='{estilo_base} color: red;'>Error: No se encontró el archivo:<br><b>{ruta_documento}</b></body>")
    
    def abrir_carpeta_anexos_actual(self):
        if not self.ruta_anexos_actual: 
            return
        dialogo_anexos = GestorAnexosDialog(self.ruta_anexos_actual, self, modo_lectura=True)
        dialogo_anexos.exec_()

    def abrir_exportacion(self):
        dialogo = ExportarDialog(self.expediente_service, self.expediente_id, self)
        dialogo.exec_()

    def mostrar_plano_ubicacion(self):
        if not os.path.exists(self.plano_ubicacion_pdf):
            mostrar_mensaje(self,"Error", f"No se encontró el archivo del plano en:\n{self.plano_ubicacion_pdf}", QMessageBox.Warning)
        else:
            self.actualizar_visor_pdf(self.plano_ubicacion_pdf)
            self.visor.setCurrentWidget(self.visor_pdf)