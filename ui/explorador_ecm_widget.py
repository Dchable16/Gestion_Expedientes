# -*- coding: utf-8 -*-
"""
Created on Fri Apr 10 12:34:17 2026

@author: dchable
"""

# ui/explorador_ecm_widget.py
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTreeWidget, 
                             QTreeWidgetItem, QHeaderView)
from PyQt5.QtCore import Qt

class ExploradorECMWidget(QWidget):
    def __init__(self, expediente_service, parent=None):
        super().__init__(parent)
        self.expediente_service = expediente_service
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0) # Ajustar a la pestaña

        # 1. Configurar el Árbol Principal
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Estructura Documental", "Folio / Clave", "Fecha", "Estado"])
        
        # Ajustar anchos de columna para mejor lectura
        self.tree.setColumnWidth(0, 400)
        self.tree.header().setSectionResizeMode(0, QHeaderView.Interactive)
        self.tree.setAlternatingRowColors(True)

        self.layout.addWidget(self.tree)

        # Conectar el evento de clic para interactuar con los nodos
        self.tree.itemClicked.connect(self.al_seleccionar_nodo)

    def cargar_arbol(self):
        """
        Construye la jerarquía leyendo desde la capa de negocio.
        """
        self.tree.clear()

        # Nivel 1: Fondo / Sección (Nodo Raíz Fijo)
        # Aquí representamos la estructura principal, como la Gerencia de Aguas Subterráneas
        nodo_raiz = QTreeWidgetItem(self.tree, ["Fondo Documental Principal", "F-01", "", ""])
        # self.set_icon(nodo_raiz, "ruta/al/icono_edificio.png") # Si tienes iconos en resources_rc
        nodo_raiz.setExpanded(True)

        # Nivel 2: Series Documentales
        # (Asumiendo que tienes un método obtener_series en tu service)
        series = self.expediente_service.obtener_todas_las_series() 
        
        for serie in series:
            nodo_serie = QTreeWidgetItem(nodo_raiz, [
                f"📁 {serie['nombre_serie']}", 
                serie['codigo_serie'], 
                "", 
                ""
            ])
            
            # Nivel 3: Expedientes dentro de la Serie
            expedientes = self.expediente_service.obtener_expedientes_por_serie(serie['id'])
            for exp in expedientes:
                nodo_exp = QTreeWidgetItem(nodo_serie, [
                    f"📂 {exp['asunto']}", 
                    exp['folio'], 
                    exp.get('fecha', ''), 
                    exp.get('estado', 'Activo')
                ])

                # Nivel 4: Documentos / Respuestas dentro del Expediente
                documentos = self.expediente_service.obtener_respuestas_por_expediente(exp['id'])
                for doc in documentos:
                    QTreeWidgetItem(nodo_exp, [
                        f"📄 {doc['asunto_respuesta']}", 
                        doc.get('folio_respuesta', ''), 
                        doc.get('fecha_respuesta', ''), 
                        ""
                    ])

    def al_seleccionar_nodo(self, item, column):
        """
        Detecta qué nivel del árbol tocó el usuario para mostrar detalles.
        """
        texto_nodo = item.text(0)
        folio = item.text(1)
        
        # Aquí se puede emitir una señal para que la ventana principal 
        # muestre un panel lateral con los metadatos o el PDF del documento.
        print(f"Seleccionado: {texto_nodo} | Folio/Clave: {folio}")