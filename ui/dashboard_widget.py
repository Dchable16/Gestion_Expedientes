# -*- coding: utf-8 -*-
# ui/dashboard_widget.py

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QFrame, QGridLayout, QSizePolicy, QScrollArea)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.ticker import MaxNLocator
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

class TarjetaKPI(QFrame):
    def __init__(self, titulo, valor, color_fondo, subtitulo=""):
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {color_fondo};
                border-radius: 8px;
                color: white;
            }}
        """)
        self.setMinimumHeight(90)
        self.setMaximumHeight(110)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        
        lbl_valor = QLabel(str(valor))
        lbl_valor.setFont(QFont("Arial", 22, QFont.Bold))
        lbl_valor.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        lbl_valor.setStyleSheet("border: none; background: transparent;")
        
        lbl_titulo = QLabel(titulo)
        lbl_titulo.setFont(QFont("Arial", 11, QFont.Bold))
        lbl_titulo.setAlignment(Qt.AlignLeft)
        lbl_titulo.setStyleSheet("border: none; background: transparent;")
        
        layout.addWidget(lbl_valor)
        layout.addWidget(lbl_titulo)
        
        if subtitulo:
            lbl_sub = QLabel(subtitulo)
            lbl_sub.setFont(QFont("Arial", 9))
            lbl_sub.setStyleSheet("border: none; background: transparent; opacity: 0.8;")
            layout.addWidget(lbl_sub)

class SeparadorSeccion(QWidget):
    def __init__(self, texto):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 20, 0, 10)
        
        lbl = QLabel(texto)
        lbl.setFont(QFont("Arial", 14, QFont.Bold))
        lbl.setStyleSheet("color: #2c3e50;")
        
        linea = QFrame()
        linea.setFrameShape(QFrame.HLine)
        linea.setFrameShadow(QFrame.Sunken)
        linea.setStyleSheet("color: #bdc3c7;")
        
        layout.addWidget(lbl)
        layout.addWidget(linea)

class DashboardWidget(QWidget):
    def __init__(self, repositorio):
        super().__init__()
        self.repo = repositorio
        self.init_ui()
        self.cargar_datos()

    def init_ui(self):
        # Layout principal con scroll por si la pantalla es pequeña
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0,0,0,0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        content_widget = QWidget()
        self.layout_content = QVBoxLayout(content_widget)
        self.layout_content.setContentsMargins(20, 20, 20, 20)
        self.layout_content.setSpacing(15)
        
        # --- SECCIÓN 1: CONTROL DE GESTIÓN ---
        self.layout_content.addWidget(SeparadorSeccion("CONTROL DE GESTIÓN"))
        
        # Fila de Tarjetas CG
        self.layout_kpi_cg = QHBoxLayout()
        self.layout_content.addLayout(self.layout_kpi_cg)
        
        # Fila de Gráficas CG
        self.layout_graficas = QHBoxLayout()
        self.layout_graficas.setSpacing(20)
        self.layout_content.addLayout(self.layout_graficas)
        
        # --- SECCIÓN 2: EXPEDIENTES ---
        self.layout_content.addWidget(SeparadorSeccion("ARCHIVO DE TRÁMITE"))
        
        # Fila de Tarjetas Expedientes
        self.layout_kpi_exp = QHBoxLayout()
        self.layout_content.addLayout(self.layout_kpi_exp)
        
        self.layout_content.addStretch() # Empujar todo hacia arriba
        
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

    def cargar_datos(self):
        stats = self.repo.obtener_datos_dashboard()
        
        # 1. Limpiar layouts
        self._limpiar_layout(self.layout_kpi_cg)
        self._limpiar_layout(self.layout_graficas)
        self._limpiar_layout(self.layout_kpi_exp)
        
        # 2. Tarjetas Control de Gestión
        # Pendientes (Naranja - Alerta media)
        self.layout_kpi_cg.addWidget(TarjetaKPI("Oficios Pendientes", stats['cg_pendientes'], "#f39c12", "Requieren atención"))
        # Urgentes (Rojo - Alerta alta)
        self.layout_kpi_cg.addWidget(TarjetaKPI("Trámites Urgentes", stats['cg_urgentes'], "#c0392b", "Prioridad Alta"))
        # Recibidos (Verde - Informativo)
        self.layout_kpi_cg.addWidget(TarjetaKPI("Recibidos este Mes", stats['cg_recibidos_mes'], "#27ae60", "Volumen de entrada"))
        
        # 3. Gráficas Control de Gestión
        self.layout_graficas.addWidget(self.crear_grafica_pastel(stats['grafica_cg_estatus']))
        self.layout_graficas.addWidget(self.crear_grafica_barras(stats['grafica_cg_areas']))
        
        # 4. Tarjetas Expedientes
        # Activos (Azul - Informativo)
        self.layout_kpi_exp.addWidget(TarjetaKPI("Expedientes Activos", stats['exp_activos'], "#2980b9", "En trámite actual"))
        # Por Vencer (Morado - Alerta legal)
        self.layout_kpi_exp.addWidget(TarjetaKPI("Vencen esta Semana", stats['exp_por_vencer'], "#8e44ad", "Términos fatales"))
        # Total Año (Gris - Estadística)
        self.layout_kpi_exp.addWidget(TarjetaKPI("Aperturados (Año)", stats['exp_total_anio'], "#7f8c8d", "Acumulado anual"))

    def _limpiar_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget: widget.deleteLater()

    def crear_grafica_pastel(self, datos):
        fig = Figure(figsize=(4, 3), dpi=90)
        ax = fig.add_subplot(111)
        
        if not datos:
            ax.text(0.5, 0.5, "Sin datos", ha='center')
        else:
            etiquetas = list(datos.keys())
            valores = list(datos.values())
            colores = ['#FFB3BA', '#BAFFC9', '#BAE1FF', '#FFFFBA', '#FFDFBA']
            ax.pie(valores, labels=etiquetas, autopct='%1.0f%%', startangle=90, colors=colores)
            ax.set_title("Estatus Global", fontsize=9, fontweight='bold')
        
        fig.tight_layout()
        return FigureCanvas(fig)

    def crear_grafica_barras(self, datos):
        fig = Figure(figsize=(5, 3), dpi=90)
        ax = fig.add_subplot(111)
        
        if not datos:
            ax.text(0.5, 0.5, "Sin datos", ha='center')
        else:
            nombres = list(datos.keys())
            cantidades = list(datos.values())
            y_pos = range(len(nombres))
            
            # Barras color verde azulado
            ax.barh(y_pos, cantidades, align='center', color='#1abc9c')
            ax.set_yticks(y_pos)
            ax.set_yticklabels(nombres, fontsize=8)
            ax.invert_yaxis() # La barra más grande arriba
            
            # --- CORRECCIÓN: FORZAR NÚMEROS ENTEROS EN EL EJE X ---
            # Esto evita que aparezca 0.5, 1.5, etc.
            from matplotlib.ticker import MaxNLocator
            ax.xaxis.set_major_locator(MaxNLocator(integer=True))
            
            ax.set_title("Carga de Trabajo por Persona (Top 5)", fontsize=9, fontweight='bold')
            ax.spines['right'].set_visible(False)
            ax.spines['top'].set_visible(False)
        
        fig.tight_layout()
        return FigureCanvas(fig)