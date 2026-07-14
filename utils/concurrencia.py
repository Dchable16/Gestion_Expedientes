# -*- coding: utf-8 -*-
"""
Created on Tue Apr  7 17:52:46 2026

@author: dchable
"""

# -*- coding: utf-8 -*-
# utils/concurrencia.py

import sys
import traceback
from typing import Callable, Any

from PyQt5.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot, QThreadPool

class SenalesTrabajador(QObject):
    """
    Agrupa todas las señales que un hilo en segundo plano puede emitir
    hacia la interfaz gráfica (Hilo Principal).
    """
    terminado = pyqtSignal()
    error = pyqtSignal(tuple)
    resultado = pyqtSignal(object)
    progreso = pyqtSignal(int)
    mensaje = pyqtSignal(str)

class TrabajadorGenerico(QRunnable):
    """
    Trabajador genérico de un solo uso para ejecutar funciones pesadas
    (Excel, base de datos, correos) sin congelar la interfaz.
    Se apoya en QThreadPool para gestión automática de memoria.
    """
    def __init__(self, funcion: Callable[..., Any], *args, **kwargs):
        super().__init__()
        self.funcion = funcion
        self.args = args
        self.kwargs = kwargs
        self.senales = SenalesTrabajador()

    @pyqtSlot()
    def run(self):
        """
        Método invocado automáticamente por el QThreadPool.
        (Debe llamarse 'run' en inglés porque sobrescribe el método interno de Qt).
        """
        try:
            # Ejecuta la función objetivo desempaquetando los argumentos
            resultado_funcion = self.funcion(*self.args, **self.kwargs)
            
            # Si todo salió bien, emitimos el resultado
            self.senales.resultado.emit(resultado_funcion)
            
        except Exception:
            # Captura de errores crudos para evitar cierres abruptos de la aplicación
            traceback.print_exc()
            tipo_excepcion, valor = sys.exc_info()[:2]
            self.senales.error.emit((tipo_excepcion, valor, traceback.format_exc()))
            
        finally:
            # Siempre avisa que terminó, sea con éxito o fracaso
            self.senales.terminado.emit()

class GestorTareas:
    """
    Controlador estático para enviar tareas a la piscina de hilos (ThreadPool) de la aplicación.
    """
    @staticmethod
    def ejecutar_en_segundo_plano(funcion: Callable, callback_exito: Callable = None, *args, **kwargs):
        """
        Inicia una tarea en un hilo libre y conecta su finalización al callback indicado.
        """
        trabajador = TrabajadorGenerico(funcion, *args, **kwargs)
        
        if callback_exito:
            trabajador.senales.resultado.connect(callback_exito)
            
        # Pasa el trabajador al manejador global de hilos de Qt
        QThreadPool.globalInstance().start(trabajador)