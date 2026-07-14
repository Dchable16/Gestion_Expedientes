# ui/pdf_viewer_dialog.py

import os

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QMessageBox
from PyQt5.QtWebEngineWidgets import QWebEngineView
# --- CAMBIO 1: Importar Qt ---
from PyQt5.QtCore import QUrl, Qt 

class PdfViewerDialog(QDialog):
    """
    Un diálogo simple para mostrar un archivo PDF dentro de la aplicación.
    """
    def __init__(self, pdf_path: str, parent=None):
        super().__init__(parent)
        
        self.pdf_path = pdf_path
        self.setWindowTitle(f"Visor de PDF - {os.path.basename(pdf_path)}")
        self.setMinimumSize(800, 600)
        
        # --- CAMBIO 2: Habilitar todos los controles de ventana ---
        # Esto agrega los botones de Minimizar y Maximizar que faltaban.
        # Usamos Qt.Window para que se comporte como una ventana completa.
        self.setWindowFlags(
            Qt.Window |
            Qt.WindowMinimizeButtonHint | 
            Qt.WindowMaximizeButtonHint | 
            Qt.WindowCloseButtonHint
        )
        # ----------------------------------------------------------
        
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        self.visor_pdf = QWebEngineView()
        
        # Estas configuraciones ya habilitan las herramientas internas del PDF (Zoom, Imprimir, Rotar)
        # Al poder Maximizar la ventana, estas herramientas serán más visibles en la barra superior del visor.
        self.visor_pdf.settings().setAttribute(self.visor_pdf.settings().PluginsEnabled, True)
        self.visor_pdf.settings().setAttribute(self.visor_pdf.settings().PdfViewerEnabled, True)
        
        layout.addWidget(self.visor_pdf)
        
        self.cargar_pdf()

    def cargar_pdf(self):
        """
        Carga el PDF en el visor, verificando primero si el archivo existe.
        """
        if self.pdf_path and os.path.exists(self.pdf_path):
            url = QUrl.fromLocalFile(os.path.abspath(self.pdf_path))
            self.visor_pdf.setUrl(url)
        else:
            html_error = f"""
            <body style='font-family: sans-serif; text-align: center; padding-top: 50px;'>
                <h2>Error: Archivo no encontrado</h2>
                <p>No se pudo encontrar el archivo PDF en la siguiente ruta:</p>
                <p><b>{self.pdf_path}</b></p>
            </body>
            """
            self.visor_pdf.setHtml(html_error)