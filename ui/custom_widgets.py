# -*- coding: utf-8 -*-
"""
Created on Tue Aug 12 16:19:51 2025

@author: dchable
"""

# ui/custom_widgets.py

from PyQt5.QtWidgets import QTableWidgetItem
from PyQt5.QtCore import QDate


class NumericTableWidgetItem(QTableWidgetItem):
    """
    Un QTableWidgetItem personalizado que permite el ordenamiento numérico correcto
    en una tabla. Si el valor no es numérico, lo ordena como texto.
    """
    def __init__(self, display_text: str, sort_key=None):
        """
        Args:
            display_text (str): El texto que se mostrará en la celda.
            sort_key (any, optional): El valor real (ej. un número) que se usará para ordenar.
                                      Si es None, se usará el mismo display_text para ordenar.
        """
        super().__init__(str(display_text))
        
        value_to_sort = sort_key if sort_key is not None else display_text
        
        try:
            self.sort_value = float(value_to_sort)
        except (ValueError, TypeError):
            self.sort_value = str(value_to_sort).lower()

    def __lt__(self, other):
        """
        Sobrescribe el operador "menor que" (<) que QTableWidget usa
        internamente para ordenar los ítems.
        """
        if isinstance(other, NumericTableWidgetItem):
            return self.sort_value < other.sort_value
        return super().__lt__(other)

class DateTableWidgetItem(QTableWidgetItem):
    """
    Un item de tabla personalizado que permite ordenar correctamente por fecha.
    """
    def __init__(self, date_str: str, date_obj: QDate):
        super().__init__(date_str)
        self.date_obj = date_obj

    def __lt__(self, other):
        return self.date_obj < other.date_obj