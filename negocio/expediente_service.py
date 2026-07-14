# -*- coding: utf-8 -*-
"""
Created on Thu Jul 17 15:32:50 2025

@author: dchable
"""
# negocio/expediente_service.py

import logging
import math
import os
import re
import shutil # <--- IMPORTANTE PARA LA AUTO-LIMPIEZA

from typing import Dict, Any, Tuple, Optional, List
from datetime import datetime, timedelta
from PyQt5.QtCore import QObject, pyqtSignal
from datos.expediente_repository import ExpedienteRepository
from utils.config_manager import get_series_folder_path


class ExpedienteSignals(QObject):
    """Clase auxiliar para manejar señales sin alterar la herencia del servicio."""
    datos_actualizados = pyqtSignal()

class ExpedienteService:
    def __init__(self, repository: ExpedienteRepository, usuario_actual: str = "sistema"):
        self._repository = repository
        self.usuario_actual = usuario_actual
        self.signals = ExpedienteSignals()

    def obtener_expedientes_para_ui(self, pagina: int, por_pagina: int, texto_busqueda: str = None) -> Tuple[List[Dict], int]:
        """
        Obtiene una página de expedientes y el total de registros que coinciden.
        Devuelve una tupla: (lista_de_expedientes, total_de_registros).
        """
        if pagina < 1:
            pagina = 1
        
        texto_busqueda_limpio = texto_busqueda.strip() if texto_busqueda else None
            
        total_expedientes = self._repository.contar_expedientes(texto_busqueda_limpio)
        if total_expedientes == 0:
            return [], 0
        
        expedientes_data = self._repository.obtener_expedientes_paginados(pagina, por_pagina, texto_busqueda_limpio)
        expedientes = [dict(row) for row in expedientes_data]
        
        return expedientes, total_expedientes
    
    def obtener_datos_para_reporte_respuestas(self, filtros: Dict) -> List[Dict]:
        """
        Obtiene todos los datos de respuestas filtradas para la generación de reportes.
        """
        respuestas_data = self._repository.get_respuestas_para_reporte(filtros)
        return [dict(row) for row in respuestas_data]
    
    def buscar_en_concentracion(self, filtros=None):
        """
        Busca expedientes en el archivo de concentración.
        Filtros opcionales: texto_busqueda, categoria, serie, anio, fecha_inicio, fecha_fin
        """
        try:
            return self._repository.buscar_en_concentracion(filtros)
        except Exception as e:
            logging.error("Error al buscar en concentración: {e}", exc_info=True)
            print(f"Error al buscar en concentración: {e}")
            return []
    
    def obtener_datos_expediente(self, expediente_id: int) -> Optional[Dict]:
        """
        Obtiene los datos de un único expediente para ser mostrados en el diálogo de edición.
        """
        expediente_data = self._repository.get_expediente(expediente_id)
        if expediente_data:
            # get_expediente devuelve una lista, tomamos el primer elemento.
            return dict(expediente_data[0])
        return None

    def guardar_expediente(self, datos_expediente: Dict[str, Any], expediente_id: Optional[int] = None) -> Tuple[bool, Any]:
        datos_expediente = self._convertir_datos_a_mayusculas(datos_expediente)
        if expediente_id:
            if self._repository.is_expediente_cerrado(expediente_id):
                return False, "Un expediente que ya ha sido cerrado no puede ser modificado."
    
        ejecutar_validacion_completa = False
    
        if not expediente_id:
            ejecutar_validacion_completa = True
        else:
            expediente_actual = self._repository.get_expediente(expediente_id)
            if not expediente_actual:
                return False, f"Error: El expediente con ID {expediente_id} no existe."
            
            tipo_documento_actual = dict(expediente_actual[0]).get('tipo_documento')
    
            if tipo_documento_actual != 'Conocimiento':
                ejecutar_validacion_completa = True
    
        if ejecutar_validacion_completa:
            campos_requeridos = {
                'tipo_documento': 'Tipo de Documento', 'categoria_documental': 'Categoría Documental',
                'folio': 'Folio', 'fecha': 'Fecha', 'asunto': 'Asunto',
                'carpeta': 'Carpeta', 'paginas': 'Páginas' # Se quita validación estricta de documento_respaldo aquí
            }
            for key, nombre_campo in campos_requeridos.items():
                if key in datos_expediente and (datos_expediente.get(key) is None or str(datos_expediente.get(key)).strip() == ""):
                    return False, f"El campo '{nombre_campo}' no puede estar vacío."
    
            if datos_expediente.get('tipo_documento') != 'Conocimiento':
                if 'serie_documental' in datos_expediente and not datos_expediente.get('serie_documental'):
                    return False, "El campo 'Serie Documental' es obligatorio para este tipo de expediente."
    
            if 'paginas' in datos_expediente and not str(datos_expediente.get('paginas', '')).isdigit():
                return False, "El campo 'Páginas' debe ser un número válido."
    
        try:
            if expediente_id:
                success, message = self._repository.update_expediente(datos_expediente, expediente_id)
                if success:
                    self._repository.registrar_accion(
                        self.usuario_actual, 
                        "EDITAR", 
                        f"Se editó el expediente ID {expediente_id} (Folio: {datos_expediente.get('folio')})"
                    )
                    return True, expediente_id # --- DEVUELVE EL ID ---
                else:
                    return False, f"Error al actualizar: {message}"
            
            else:
                fecha = datos_expediente.get('fecha')
                year = int(fecha.split('-')[0]) if fecha and fecha.split('-')[0].isdigit() else None
                
                datos_expediente['apertura'] = year
                
                tipo_documento = datos_expediente.get('tipo_documento')
                if tipo_documento == "Conocimiento":
                    datos_expediente['serie_documental'] = "Conocimiento"
                    datos_expediente['clasificacion'] = ""
                else:
                    serie_documental = datos_expediente.get('serie_documental')
                    next_number = self._repository.get_next_expediente_number(serie_documental, year)
                    
                    clasificacion = f"B00.7.01/{serie_documental}/{next_number}/{year}" if all([serie_documental, year]) else ""
                    datos_expediente['clasificacion'] = clasificacion
    
                # --- GUARDAMOS Y OBTENEMOS EL ID ---
                nuevo_id = self._repository.insert_expediente(datos_expediente)
                
                if nuevo_id:
                    # --- CREACIÓN DE CARPETA MAESTRA ---
                    carpeta_maestra = os.path.abspath(os.path.join("documentos", f"EXP_{nuevo_id}"))
                    os.makedirs(os.path.join(carpeta_maestra, "anexos_principales"), exist_ok=True)
                    os.makedirs(os.path.join(carpeta_maestra, "respuestas"), exist_ok=True)
                    
                    self._repository.registrar_accion(
                        self.usuario_actual, 
                        "CREAR", 
                        f"Se creó nuevo expediente ID {nuevo_id} (Folio: {datos_expediente.get('folio')})"
                    )
                    return True, nuevo_id # --- DEVUELVE EL ID ---
                else:
                    return False, "Ocurrió un error al guardar el nuevo expediente."
    
        except Exception as e:
            logging.error("Error inesperado al guardar expediente: %s", e, exc_info=True)
            return False, "Ocurrió un error inesperado al contactar la base de datos."

    def eliminar_expediente(self, expediente_id: int) -> Tuple[bool, str]:
        datos = self.obtener_datos_expediente(expediente_id)
        folio = datos.get('folio', 'S/F') if datos else 'Desconocido'

        try:
            self._repository.begin_transaction()
            self._repository.delete_expediente(expediente_id)
            self._repository.commit_transaction()
            
            # --- AUTO-LIMPIEZA DE CARPETA MAESTRA ---
            ruta_maestra = os.path.abspath(os.path.join("documentos", f"EXP_{expediente_id}"))
            if os.path.exists(ruta_maestra):
                shutil.rmtree(ruta_maestra, ignore_errors=True)
            # ----------------------------------------
            
            self._repository.registrar_accion(
                self.usuario_actual, 
                "ELIMINAR", 
                f"Se eliminó el expediente ID {expediente_id} (Folio: {folio}) y todos sus archivos asociados."
            )
            return True, "Expediente y archivos eliminados correctamente."
        except Exception as e:
            logging.error("Error al eliminar expediente %s, revirtiendo cambios: %s", expediente_id, e, exc_info=True)
            self._repository.rollback_transaction()
            return False, "No se pudo eliminar el expediente debido a un error interno."

    def cerrar_expediente(self, expediente_id: int) -> Tuple[bool, str]:
        try:
            expediente_result = self._repository.get_expediente(expediente_id)
            if not expediente_result:
                return False, f"No se encontró el expediente con ID {expediente_id}."

            expediente_data = dict(expediente_result[0])
            serie_documental = expediente_data.get('serie_documental')
            
            if not serie_documental:
                 return False, "Faltan datos de la serie documental para calcular el cierre."

            serie_info_result = self._repository.get_serie_documental(serie_documental)
            if not serie_info_result:
                return False, f"No se encontró la serie documental '{serie_documental}'."
            
            tramite = dict(serie_info_result[0]).get('tramite')
            if tramite is None:
                return False, f"La serie documental '{serie_documental}' no tiene un valor de trámite definido."

            fecha_base_str = self._repository.get_fecha_ultima_respuesta(expediente_id)

            if not fecha_base_str:
                fecha_base_str = expediente_data.get('fecha')

            if not fecha_base_str:
                return False, "No se pudo determinar una fecha base (ni de expediente ni de respuesta) para el cálculo."

            fecha_base_dt = datetime.strptime(fecha_base_str, '%Y-%m-%d')
            ano_base = fecha_base_dt.year
            
            nuevo_cierre = ano_base + tramite
            vencimiento_dt = fecha_base_dt.replace(year=fecha_base_dt.year + tramite)
            vencimiento = vencimiento_dt.strftime('%Y-%m-%d')
            
            if self._repository.actualizar_cierre_y_vencimiento(expediente_id, nuevo_cierre, vencimiento):
                # [HISTORIAL] Registro de cierre
                self._repository.registrar_accion(
                    self.usuario_actual, 
                    "CERRAR", 
                    f"Se cerró el expediente ID {expediente_id} (Cierre: {nuevo_cierre})"
                )
                return True, f"Expediente cerrado. Cierre: {nuevo_cierre}, Vencimiento: {vencimiento}"
            else:
                return False, "Error al actualizar la base de datos."

        except Exception as e:
            logging.error("Error al cerrar expediente %s: %s", expediente_id, e, exc_info=True)
            return False, f"Error inesperado al cerrar el expediente: {e}"

    def cancelar_cierre_expediente(self, expediente_id: int) -> Tuple[bool, str]:
        if not self._repository.is_expediente_cerrado(expediente_id):
            return False, "El expediente no está cerrado."
            
        success, message = self._repository.cancelar_cierre_expediente(expediente_id)
        
        if success:
            # [HISTORIAL] Registro de cancelación de cierre
            self._repository.registrar_accion(
                self.usuario_actual, 
                "CANCELAR_CIERRE", 
                f"Se canceló el cierre del expediente ID {expediente_id}"
            )
            
        return success, message

    def obtener_series_documentales(self) -> List:
        """Obtiene todas las series documentales para poblar ComboBoxes en la UI."""
        return self._repository.get_series_documentales()
    
    def obtener_respuestas(self, expediente_id: int) -> List[Dict]:
        """Obtiene todas las respuestas de un expediente específico."""
        respuestas_data = self._repository.get_respuestas(expediente_id)
        return [dict(row) for row in respuestas_data]

    def guardar_respuesta(self, datos_respuesta: Dict, expediente_id: int, respuesta_id: Optional[int] = None) -> Tuple[bool, Any]:
        datos_respuesta = self._convertir_datos_a_mayusculas(datos_respuesta)
        campos_requeridos = {
            'categoria_documental': 'Categoría Documental',
            'folio': 'Folio',
            'fecha_respuesta': 'Fecha de Respuesta',
            'asunto_respuesta': 'Asunto de la Respuesta',
            'paginas': 'Páginas' # Se quita validación estricta de documento_respuesta aquí
        }
        for key, nombre in campos_requeridos.items():
            if not datos_respuesta.get(key) or not str(datos_respuesta[key]).strip():
                return False, f"El campo '{nombre}' no puede estar vacío."
        
        if not str(datos_respuesta.get('paginas', '')).isdigit():
            return False, "El campo 'Páginas' debe ser un número."

        folio_actual = datos_respuesta.get('folio', 'S/F')

        try:
            if respuesta_id:
                if self._repository.update_respuesta(respuesta_id, datos_respuesta):
                    self._repository.registrar_accion(
                        self.usuario_actual, "EDITAR_RESPUESTA", 
                        f"Se editó la respuesta ID {respuesta_id} (Folio: {folio_actual}) del Expediente ID {expediente_id}"
                    )
                    return True, respuesta_id # --- DEVUELVE EL ID ---
                else:
                    return False, "Error al actualizar la respuesta en la base de datos."
            else:
                datos_respuesta['expediente_id'] = expediente_id
                datos_respuesta['tipo_documento'] = 'RESPUESTA' 
                
                nueva_resp_id = self._repository.insert_respuesta(datos_respuesta)
                if nueva_resp_id:
                    # --- CREACIÓN DE CARPETA MAESTRA PARA RESPUESTA ---
                    carpeta_respuesta = os.path.abspath(os.path.join("documentos", f"EXP_{expediente_id}", "respuestas", f"RES_{nueva_resp_id}"))
                    os.makedirs(os.path.join(carpeta_respuesta, "anexos_respuesta"), exist_ok=True)
                    
                    self._repository.registrar_accion(
                        self.usuario_actual, "CREAR_RESPUESTA", 
                        f"Nueva respuesta ID {nueva_resp_id} Folio: ({folio_actual}) agregada al Expediente ID {expediente_id}"
                    )
                    return True, nueva_resp_id # --- DEVUELVE EL ID ---
                else:
                    return False, "Error al crear la nueva respuesta en la base de datos."
        except Exception as e:
            logging.error("Error en ExpedienteService.guardar_respuesta: %s", e, exc_info=True)
            return False, f"Error inesperado al guardar la respuesta."

    def eliminar_respuesta(self, respuesta_id: int) -> Tuple[bool, str]:
        datos_resp = self.obtener_datos_respuesta(respuesta_id)
        expediente_padre_id = datos_resp.get('expediente_id') if datos_resp else None
        folio_respuesta = datos_resp.get('folio', 'S/F') if datos_resp else 'Desconocido'
        
        if self._repository.delete_respuesta(respuesta_id):
            
            # --- AUTO-LIMPIEZA DE CARPETA DE RESPUESTA ---
            if expediente_padre_id:
                ruta_respuesta = os.path.abspath(os.path.join("documentos", f"EXP_{expediente_padre_id}", "respuestas", f"RES_{respuesta_id}"))
                if os.path.exists(ruta_respuesta):
                    shutil.rmtree(ruta_respuesta, ignore_errors=True)
            # ---------------------------------------------
            
            descripcion = f"Se eliminó la respuesta ID {respuesta_id} (Folio: {folio_respuesta}) y sus archivos físicos"
            if expediente_padre_id:
                descripcion += f" perteneciente al Expediente ID {expediente_padre_id}"
            self._repository.registrar_accion(
                self.usuario_actual, 
                "ELIMINAR_RESPUESTA", 
                descripcion
            )
            return True, "Respuesta eliminada correctamente."
        else:
            return False, "No se pudo eliminar la respuesta."
        
    def obtener_vista_completa_expediente(self, expediente_id: int) -> Optional[Dict[str, Any]]:
        expediente_data = self.obtener_datos_expediente(expediente_id)
        if not expediente_data:
            return None

        respuestas_data = self.obtener_respuestas(expediente_id)
        
        info_serie = None
        codigo_serie = expediente_data.get('serie_documental')
        if codigo_serie:
            serie_data = self._repository.get_serie_documental(codigo_serie)
            if serie_data:
                info_serie = dict(serie_data[0])

        return {
            "expediente": expediente_data,
            "respuestas": respuestas_data,
            "info_serie": info_serie
        }
    
    def obtener_datos_para_reporte(self, filtros: Dict) -> List[Dict]:
        expedientes_raw = self._repository.get_expedientes(filtros)
        expedientes_data = [dict(row) for row in expedientes_raw]
    
        for expediente in expedientes_data:
            expediente_id = expediente.get('id')
            if expediente_id:
                paginas_respuestas = self._repository.get_total_paginas_respuestas(expediente_id)
                paginas_expediente = expediente.get('paginas', 0) or 0
                expediente['paginas'] = paginas_expediente + paginas_respuestas
    
        return expedientes_data
    
    def buscar_respuestas_paginado(self, filtros: dict, pagina: int, por_pagina: int) -> Tuple[List[Dict], int]:
        total_respuestas = self._repository.contar_respuestas_avanzada(filtros)
        if total_respuestas == 0:
            return [], 0
        
        respuestas_data = self._repository.get_respuestas_avanzada(filtros, pagina, por_pagina)
        respuestas = [dict(row) for row in respuestas_data]
    
        return respuestas, total_respuestas
    
    def obtener_expedientes_para_archivar(self, filtros: dict = None) -> List[Dict]:
        data = self._repository.get_expedientes_vencidos_para_archivado(filtros)
        return [dict(row) for row in data]

    def mover_expedientes_a_concentracion(self, expedientes_ids: list, ubicacion_dict: dict) -> tuple:
        """Mueve expedientes sueltos a concentración."""
        exitos = 0
        for exp_id in expedientes_ids:
            if self._repository.agregar_a_concentracion(exp_id, ubicacion_dict):
                exitos += 1
                
        if exitos > 0:
            for exp_id in expedientes_ids:
                self.registrar_evento_externo("MOVER_A_CONCENTRACION", f"El expediente ID {exp_id} fue trasladado a Concentración.")
            self.signals.datos_actualizados.emit()
            return True, f"Se movieron {exitos} expedientes a concentración exitosamente."
        return False, "No se pudo mover ningún expediente."

    def buscar_en_concentracion(self, filtros: dict = None) -> List[Dict]:
        data = self._repository.get_expedientes_en_concentracion(filtros)
        return [dict(row) for row in data]
    
    def restaurar_expediente(self, expediente_id: int) -> Tuple[bool, str]:
        success = self._repository.restaurar_de_concentracion(expediente_id)
        if success:
            self._repository.registrar_accion(
                self.usuario_actual, "RESTAURAR_TRAMITE", 
                f"Se restauró a trámite el expediente ID {expediente_id}"
            )
            return True, f"El expediente {expediente_id} ha sido restaurado a trámite."
        else:
            return False, f"Error al restaurar el expediente {expediente_id}."
    
    def buscar_series_documentales(self, filtros: dict = None) -> List[Dict]:
        """Busca y filtra series documentales."""
        data = self._repository.get_series_documentales_filtradas(filtros)
        return [dict(row) for row in data]
    
    def obtener_ruta_pdf_serie(self, codigo_serie: str) -> Tuple[bool, str]:
        try:
            nombre_archivo = f"{codigo_serie}.pdf"
            base_path = get_series_folder_path()

            ruta_directa = os.path.abspath(os.path.join(base_path, nombre_archivo))
            if os.path.exists(ruta_directa):
                return True, ruta_directa

            for dirpath, dirnames, filenames in os.walk(base_path):
                if nombre_archivo in filenames:
                    ruta_encontrada = os.path.abspath(os.path.join(dirpath, nombre_archivo))
                    return True, ruta_encontrada
            
            return False, f"No se encontró el archivo '{nombre_archivo}' en la carpeta '{base_path}' ni en sus subcarpetas."

        except Exception as e:
            logging.error("Ocurrió un error al buscar el archivo PDF: %s", e, exc_info=True)
            return False, f"Ocurrió un error al buscar el archivo PDF: {e}"
    
    def obtener_ruta_pdf_expediente(self, expediente_id: int):
        ruta_documento = self._repository.get_document_path(expediente_id)
        
        if not ruta_documento or not str(ruta_documento).strip():
            return False, "El expediente no tiene un documento de respaldo adjunto."
            
        ruta_absoluta = os.path.abspath(ruta_documento)
        
        if not os.path.exists(ruta_absoluta):
            return False, f"El archivo no se encontró en la ruta: {ruta_absoluta}"
            
        return True, ruta_absoluta
    
    def obtener_ruta_pdf_respuesta(self, respuesta_id: int) -> Tuple[bool, str]:
            ruta_documento = self._repository.get_response_document_path(respuesta_id)
            
            if not ruta_documento or not str(ruta_documento).strip():
                return False, "La respuesta no tiene un documento de respaldo adjunto."
                
            ruta_absoluta = os.path.abspath(ruta_documento)
            
            if not os.path.exists(ruta_absoluta):
                return False, f"El archivo no se encontró en la ruta: {ruta_absoluta}"
                
            return True, ruta_absoluta
    
    def obtener_nombre_serie(self, codigo_serie: str) -> str:
        if not codigo_serie:
            return ""
        
        resultado = self._repository.get_serie_by_codigo(codigo_serie)
        if resultado:
            return dict(resultado).get('nombre_serie', '')
        return ""

    def obtener_o_crear_expediente_conocimiento_anual(self, anio: int, carpeta: str):
        try:
            expediente_existente = self._repository.buscar_expediente_conocimiento_por_anio(anio)
            if expediente_existente:
                return True, expediente_existente['id']
    
            datos_nuevo_maestro = {
                "tipo_documento": "Conocimiento",
                "categoria_documental": "",
                "folio": f"CONOC-{anio}",
                "fecha": f"{anio}-01-01",
                "asunto": f"DOCUMENTACIÓN DE CONOCIMIENTO {anio}",
                "serie_documental": "Conocimiento",
                "carpeta": carpeta,
                "paginas": "",
                "documento_respaldo": "",
                "clasificacion": "",
                "apertura": anio
            }
            
            nuevo_id = self._repository.insert_expediente(datos_nuevo_maestro)
            if nuevo_id:
                # --- CREAR CARPETA MAESTRA PARA CONOCIMIENTO ---
                carpeta_maestra = os.path.abspath(os.path.join("documentos", f"EXP_{nuevo_id}"))
                os.makedirs(os.path.join(carpeta_maestra, "anexos_principales"), exist_ok=True)
                os.makedirs(os.path.join(carpeta_maestra, "respuestas"), exist_ok=True)
                
                return True, nuevo_id
            else:
                return False, "No se pudo insertar el nuevo expediente maestro en la base de datos."
    
        except Exception as e:
            logging.error(f"Error al obtener o crear el expediente maestro para el año {anio}: {e}", exc_info=True)
            return False, f"Error inesperado en el servidor: {e}"
    
    def buscar_expediente_conocimiento_por_anio(self, anio: int) -> dict:
        expediente = self._repository.buscar_expediente_conocimiento_por_anio(anio)
        if expediente:
            return {"existe": True, "datos": expediente}
        return {"existe": False, "datos": None}
    
    def _convertir_datos_a_mayusculas(self, datos: Dict[str, Any]) -> Dict[str, Any]:
        datos_mayusculas = {}
        for clave, valor in datos.items():
            if isinstance(valor, str):
                datos_mayusculas[clave] = valor.upper()
            else:
                datos_mayusculas[clave] = valor
        return datos_mayusculas
    
    def obtener_info_serie(self, codigo_serie: str) -> Optional[Dict]:
        serie_data = self._repository.get_serie_by_codigo(codigo_serie)
        return dict(serie_data) if serie_data else None
    
    def registrar_evento_externo(self, accion: str, descripcion: str) -> None:
        try:
            self._repository.registrar_accion(self.usuario_actual, accion, descripcion)
        except Exception as e:
            logging.error(f"No se pudo registrar evento externo: {e}")
    
    def obtener_datos_respuesta(self, respuesta_id: int) -> Optional[Dict]:
        rows = self._repository.get_respuesta(respuesta_id)
        return dict(rows[0]) if rows else None
    
    # --- MÉTODOS PARA CONTROL DE GESTIÓN ---
    def guardar_control_gestion(self, data: Dict, cg_id: Optional[int] = None) -> Tuple[bool, str]:
        data = self._convertir_datos_a_mayusculas(data)
        
        if not data.get('folio') or not data.get('asunto'):
             return False, "El Folio y el Asunto son obligatorios."
        
        try:
            exito = False
            accion = ""
            detalle = ""

            if cg_id:
                if self._repository.update_control_gestion(cg_id, data):
                    exito = True
                    accion = "EDITAR_CG"
                    detalle = f"Editó gestión Folio: {data.get('folio')} (ID {cg_id})"
            else:
                new_id = self._repository.insert_control_gestion(data)
                if new_id:
                    exito = True
                    accion = "CREAR_CG"
                    detalle = f"Creó gestión Folio: {data.get('folio')} (ID {new_id})"
            
            if exito:
                self._repository.registrar_accion(self.usuario_actual, accion, detalle)
                self.signals.datos_actualizados.emit() 
                return True, "Registro guardado correctamente."
            
            return False, "Error al guardar en base de datos."
            
        except Exception as e:
            return False, f"Error inesperado: {e}"

    def obtener_lista_control_gestion(self, pagina, limite, filtros: dict = None):
        registros = self._repository.obtener_control_gestion_paginado(pagina, limite, filtros)
        total = self._repository.contar_control_gestion_filtrado(filtros)
        return [dict(row) for row in registros], total

    def obtener_control_gestion_por_id(self, cg_id):
        row = self._repository.get_control_gestion_by_id(cg_id)
        return dict(row) if row else None

    def eliminar_control_gestion(self, cg_id):
        if self._repository.delete_control_gestion(cg_id):
            self._repository.registrar_accion(
                self.usuario_actual, 
                "ELIMINAR_CG", 
                f"Eliminó registro Gestión ID {cg_id}"
            )
            self.signals.datos_actualizados.emit()
            return True, "Eliminado correctamente."
        return False, "Error al eliminar."
    
    def obtener_todo_control_gestion(self, filtro_texto=None) -> List[Dict]:
        rows = self._repository.get_all_control_gestion(filtro_texto)
        return [dict(row) for row in rows]
    
    def obtener_reporte_por_rango(self, f_inicio, f_fin):
        if hasattr(self, '_repository') and self._repository:
            return self._repository.obtener_reporte_por_rango(f_inicio, f_fin)
        else:
            raise AttributeError("CRÍTICO: No se encuentra 'self._repository' en ExpedienteService.")
    
    def obtener_folios_usados(self):
        """Devuelve una lista con todos los folios que ya fueron utilizados en expedientes y respuestas."""
        try:
            # Llamamos al nuevo método optimizado del repositorio
            return self._repository.obtener_todos_los_folios_usados()
        except Exception as e:
            logging.error(f"Error en el servicio al obtener folios usados: {e}")
            return []
    
    def verificar_existencia_cg(self, folio: str) -> bool:
        """Comunica la interfaz con la base de datos para verificar si un folio ya existe."""
        try:
            return self._repository.verificar_existencia_cg(folio)
        except Exception as e:
            logging.error(f"Error en el servicio al verificar folio CG duplicado: {e}")
            return False
    
    def obtener_id_por_folio_cg(self, folio: str):
        """Obtiene el ID de un registro de Control de Gestión a partir de su folio."""
        try:
            return self._repository.obtener_id_por_folio_cg(folio)
        except Exception as e:
            logging.error(f"Error en el servicio al buscar ID por folio CG: {e}")
            return None
    
    def generar_siguiente_folio_cg(self, origen: str) -> str:
        """Calcula el siguiente folio automáticamente para el formato B00.7.01."""
        if origen != "GAS":
            return "" # Por ahora solo automatizamos GAS
            
        import re
        from datetime import datetime
        
        try:
            folios_existentes = self._repository.obtener_folios_por_origen(origen)
        except Exception:
            folios_existentes = []
            
        max_consecutivo = 0
        anio_actual = datetime.now().year

        for folio in folios_existentes:
            match = re.search(r'(\d+)$', folio.strip())
            if match:
                try:
                    num = int(match.group(1)) # Convierte "0000057" en 57
                    if num > max_consecutivo:
                        max_consecutivo = num
                except ValueError:
                    pass

        siguiente_numero = max_consecutivo + 1
        
        return f"{anio_actual}-B00.7.01.-{siguiente_numero:07d}"
    
    def crear_lote_transferencia(self, ids_expedientes: list) -> tuple:
        """Crea un lote nuevo verificando primero que ningún expediente esté en préstamo."""
        if not ids_expedientes:
            return False, "No se proporcionaron expedientes para el lote."

        prestados = []
        for eid in ids_expedientes:
            if self.expediente_esta_prestado(eid):

                datos = self.obtener_datos_expediente(eid)
                folio = datos.get('folio', f"ID: {eid}") if datos else f"ID: {eid}"
                prestados.append(folio)

        if prestados:
            lista_folios = "\n- ".join(prestados)
            return False, f"No se puede crear el lote porque los siguientes expedientes están en PRÉSTAMO:\n\n- {lista_folios}\n\nDebe registrar su devolución antes de transferirlos."
 
        success, lote_id, folio_lote = self._repository.crear_lote_transferencia(self.usuario_actual)
        if not success:
            return False, "No se pudo crear el lote en la base de datos."

        asignado = self._repository.asignar_expedientes_a_lote(lote_id, ids_expedientes)
        if not asignado:
            return False, "Se creó el lote, pero falló la asignación de expedientes."

        for exp_id in ids_expedientes:
            self.registrar_evento_externo(
                "TRANSFERENCIA", 
                f"El expediente ID {exp_id} fue empaquetado en el lote de transferencia: {folio_lote}"
            )

        self.signals.datos_actualizados.emit()
        return True, f"Lote '{folio_lote}' creado exitosamente con {len(ids_expedientes)} expedientes."

    def obtener_lotes_activos(self) -> list:
        """Devuelve la lista de lotes que están en tránsito."""
        return self._repository.obtener_lotes_activos()

    def confirmar_entrega_lote(self, id_lote: int, folio_lote: str, ubicacion_dict: dict, ruta_pdf_original: str = None) -> tuple:
        """Marca el lote como entregado y guarda una copia segura del Acuse PDF."""
        import os
        import shutil
        
        ruta_final_pdf = None
        
        if ruta_pdf_original and os.path.exists(ruta_pdf_original):
            carpeta_acuses = os.path.abspath(os.path.join("documentos", "acuses"))
            os.makedirs(carpeta_acuses, exist_ok=True)
            nombre_archivo = f"Acuse_{folio_lote}.pdf"
            ruta_final_pdf = os.path.join(carpeta_acuses, nombre_archivo)
            try:
                shutil.copy2(ruta_pdf_original, ruta_final_pdf)
            except Exception as e:
                import logging
                logging.error(f"Error al copiar el PDF del acuse: {e}")
                return False, f"Se entregó el lote, pero falló la copia del PDF: {e}"

        # Le pasamos el DICCIONARIO a la base de datos
        success, msg = self._repository.marcar_lote_entregado(id_lote, ubicacion_dict, ruta_final_pdf)
        
        if success:
            self.registrar_evento_externo("LOTE_ENTREGADO", f"Se confirmó la entrega física del lote {folio_lote}.")
            self.signals.datos_actualizados.emit()
            
        return success, msg
    
    def obtener_ids_por_lote(self, id_lote: int) -> list:
        """Devuelve una lista de IDs de expedientes vinculados a un lote."""
        return self._repository.obtener_ids_por_lote(id_lote)
    
    def cancelar_lote_transferencia(self, id_lote: int, folio_lote: str) -> tuple:
        """Pide a la base de datos cancelar un lote y registra el evento."""
        success = self._repository.cancelar_lote_transferencia(id_lote)
        
        if success:
            self.registrar_evento_externo(
                "LOTE_CANCELADO", 
                f"Se canceló el lote de transferencia {folio_lote}. Sus expedientes regresaron a la bandeja de Vencidos."
            )
            self.signals.datos_actualizados.emit()
            return True, f"El paquete {folio_lote} ha sido desarmado con éxito."
            
        return False, "Ocurrió un error al intentar cancelar el paquete en la base de datos."
    
    def obtener_lotes_entregados(self) -> list:
        """Devuelve la lista de lotes históricos ya entregados."""
        return self._repository.obtener_lotes_entregados()
    
    def crear_lote_valoracion(self, expedientes_ids: list, tipo_propuesta: str) -> tuple:
        """Crea un paquete de valoración verificando primero que no haya préstamos activos."""
        if not expedientes_ids:
            return False, "No se seleccionaron expedientes."

        prestados = []
        for eid in expedientes_ids:
            if self.expediente_esta_prestado(eid):
                # Obtenemos el folio para indicar exactamente cuál falta
                datos = self.obtener_datos_expediente(eid)
                folio = datos.get('folio', f"ID: {eid}") if datos else f"ID: {eid}"
                prestados.append(folio)

        if prestados:
            lista_folios = "\n- ".join(prestados)
            return False, f"OPERACIÓN CANCELADA:\nNo se puede proponer para {tipo_propuesta} porque los siguientes expedientes están en PRÉSTAMO:\n\n- {lista_folios}\n\nDebe recuperar físicamente las carpetas y registrar su devolución antes de proceder."

        usuario = getattr(self, 'usuario_actual', 'admin') 
        success, msg = self._repository.crear_lote_valoracion(expedientes_ids, tipo_propuesta, usuario)
        
        if success:
            self.registrar_evento_externo("LOTE_VALORACION_CREADO", f"Se propusieron {len(expedientes_ids)} expedientes para {tipo_propuesta}.")
            self.signals.datos_actualizados.emit()
            
        return success, msg

    def obtener_lotes_valoracion_activos(self) -> list:
        """Obtiene los lotes que están esperando dictamen."""
        return self._repository.obtener_lotes_valoracion_activos()

    def rechazar_lote_valoracion(self, lote_id: int, folio_lote: str) -> tuple:
        """El comité rechazó la propuesta. Los expedientes regresan a concentración."""
        success, msg = self._repository.rechazar_lote_valoracion(lote_id)
        if success:
            self.registrar_evento_externo("DICTAMEN_RECHAZADO", f"Se rechazó el lote de valoración {folio_lote}.")
            self.signals.datos_actualizados.emit()
        return success, msg

    def aprobar_lote_valoracion(self, lote_id: int, folio_lote: str, acta_pdf: str, observaciones: str) -> tuple:
        """El comité aprobó la propuesta. Pasan al destino final."""
        success, msg = self._repository.aprobar_lote_valoracion(lote_id, acta_pdf, observaciones)
        if success:
            self.registrar_evento_externo("DICTAMEN_APROBADO", f"Se autorizó el lote {folio_lote}. Justificación: {observaciones}")
            self.signals.datos_actualizados.emit()
        return success, msg

    def obtener_historial_destino_final(self) -> list:
        """Obtiene la lista de los expedientes destruidos o históricos."""
        return self._repository.obtener_historial_destino_final()
    
    def revertir_destino_final(self, destino_id: int, expediente_id: int, folio: str) -> tuple:
        """Revierte un destino final aplicado por error."""
        success, msg = self._repository.revertir_destino_final(destino_id, expediente_id)
        if success:
            self.registrar_evento_externo(
                "REVERTIR_DESTINO", 
                f"Se revirtió el destino final del expediente ID {expediente_id} (Folio: {folio}). Regresa a Concentración."
            )
            self.signals.datos_actualizados.emit()
        return success, msg
    
    def obtener_ids_por_lote_valoracion(self, id_lote: int) -> list:
        """Devuelve una lista de IDs de expedientes en valoración para generar su inventario."""
        return self._repository.obtener_ids_por_lote_valoracion(id_lote)
    
    def registrar_prestamo_fisico(self, expediente_id: int, solicitante: str, area: str, fecha_prestamo: str, fecha_vencimiento: str, observaciones: str) -> tuple:
        """
        Valida los datos, registra el préstamo en la BD y deja huella en el historial.
        """
        if not solicitante.strip() or not fecha_vencimiento.strip():
            return False, "El nombre del solicitante y la fecha de vencimiento son obligatorios."

        datos_prestamo = {
            'expediente_id': expediente_id,
            'solicitante': solicitante.strip(),
            'area_solicitante': area.strip(),
            'fecha_prestamo': fecha_prestamo,
            'fecha_vencimiento': fecha_vencimiento,
            'observaciones': observaciones.strip(),
            'usuario_registro': self.usuario_actual
        }

        success, msg = self._repository.registrar_prestamo(datos_prestamo)
        
        if success:
            # Dejar huella en el historial
            datos_exp = self.obtener_datos_expediente(expediente_id)
            folio = datos_exp.get('folio', 'S/F') if datos_exp else 'Desconocido'
            
            self.registrar_evento_externo(
                "PRÉSTAMO_FÍSICO", 
                f"Se prestó el expediente ID {expediente_id} (Folio: {folio}) a {solicitante} ({area}). Devolución esperada: {fecha_vencimiento}."
            )
            self.signals.datos_actualizados.emit()
            
        return success, msg

    def registrar_devolucion_fisica(self, prestamo_id: int, expediente_id: int, observaciones: str) -> tuple:
        """
        Marca el expediente como devuelto en la BD y registra la acción en el historial.
        """
        success, msg = self._repository.registrar_devolucion(prestamo_id, observaciones)
        
        if success:
            datos_exp = self.obtener_datos_expediente(expediente_id)
            folio = datos_exp.get('folio', 'S/F') if datos_exp else 'Desconocido'
            
            self.registrar_evento_externo(
                "DEVOLUCIÓN_FÍSICA", 
                f"El expediente ID {expediente_id} (Folio: {folio}) fue devuelto físicamente al archivo."
            )
            self.signals.datos_actualizados.emit()
            
        return success, msg

    def obtener_lista_prestamos(self) -> list:
        """
        Obtiene la lista de préstamos activos para mostrarla en la tabla.
        """
        return self._repository.obtener_prestamos_activos()
    
    def expediente_esta_prestado(self, expediente_id: int) -> bool:
        """Consulta al repositorio si el expediente ya está fuera del archivo."""
        return self._repository.esta_prestado(expediente_id)
    
    def obtener_arbol_clasificacion(self) -> dict:
        """
        Construye una jerarquía estructurada (Fondo > Sección > Serie > Expedientes)
        para alimentar el QTreeWidget del Cuadro General de Clasificación.
        """
        arbol = {}
        
        try:
            # 1. Traer todos los datos activos de la base de datos
            series_raw = self._repository.get_series_documentales()
            expedientes_raw = self._repository.get_expedientes({"estado": "Todos"}) # Todos los activos
            
            # 2. Agrupar expedientes por su código de serie para acceso rápido
            exp_por_serie = {}
            for exp in expedientes_raw:
                cod_serie = exp['serie_documental']
                if cod_serie not in exp_por_serie:
                    exp_por_serie[cod_serie] = []
                exp_por_serie[cod_serie].append(dict(exp))
                
            # 3. Construir las Ramas (Sección > Serie)
            for serie in series_raw:
                seccion = serie['seccion'] if serie['seccion'] else "SIN SECCIÓN DEFINIDA"
                cod_serie = serie['codigo_serie']
                
                # Inicializar la sección si no existe en el árbol
                if seccion not in arbol:
                    arbol[seccion] = {}
                    
                # Meter la serie dentro de su sección
                arbol[seccion][cod_serie] = {
                    "datos_serie": dict(serie),
                    "expedientes": exp_por_serie.get(cod_serie, []) # Hojas (Nietos)
                }
                
        except Exception as e:
            import logging
            logging.error(f"Error al construir el Árbol de Clasificación: {e}")
            
        return arbol