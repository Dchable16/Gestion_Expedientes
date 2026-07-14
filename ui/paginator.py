# -*- coding: utf-8 -*-
"""
Created on Tue Aug 12 15:58:33 2025

@author: dchable
"""

# ui/paginator.py

import math

from PyQt5.QtCore import QObject, pyqtSignal

class Paginator(QObject):
    """
    Gestiona el estado de la paginación y emite una señal cuando la página cambia.
    """
    pagina_cambiada = pyqtSignal(int)

    def __init__(self, registros_por_pagina_default=50):
        super().__init__()
        self.pagina_actual = 1
        self.total_paginas = 1
        self.total_registros = 0
        self.por_pagina = registros_por_pagina_default

    def actualizar_estado(self, total_registros: int, por_pagina: int):
        """
        Recalcula el estado de la paginación basado en los nuevos totales.
        Esta función es llamada por MainWindow después de obtener datos del servicio.
        """
        self.total_registros = total_registros
        self.por_pagina = por_pagina
        
        if self.total_registros > 0 and self.por_pagina > 0:
            self.total_paginas = math.ceil(self.total_registros / self.por_pagina)
        else:
            self.total_paginas = 1
            
        if self.pagina_actual > self.total_paginas:
            self.pagina_actual = self.total_paginas

    def ir_a_pagina(self, num_pagina: int):
        """
        Establece la página actual y emite la señal para recargar los datos.
        """
        if 1 <= num_pagina <= self.total_paginas:
            self.pagina_actual = num_pagina
            self.pagina_cambiada.emit(self.pagina_actual)

    def primera(self):
        if self.pagina_actual > 1:
            self.ir_a_pagina(1)

    def anterior(self):
        if self.pagina_actual > 1:
            self.ir_a_pagina(self.pagina_actual - 1)

    def siguiente(self):
        if self.pagina_actual < self.total_paginas:
            self.ir_a_pagina(self.pagina_actual + 1)

    def ultima(self):
        if self.pagina_actual < self.total_paginas:
            self.ir_a_pagina(self.total_paginas)

    def forzar_recarga(self):
        """
        Vuelve a emitir la señal para la página actual, útil después de un
        cambio de filtros o una búsqueda.
        """
        self.pagina_cambiada.emit(self.pagina_actual)