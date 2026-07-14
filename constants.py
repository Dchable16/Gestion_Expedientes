# -*- coding: utf-8 -*-
"""
Created on Fri Aug  8 13:57:02 2025

@author: dchable
"""

# constants.py
# Este archivo centraliza las listas y valores constantes de la aplicación.

# Usada en el diálogo de nuevo expediente
TIPOS_DOCUMENTO = ["EXPEDIENTE", "Conocimiento"]

# Usada en múltiples diálogos y filtros
CATEGORIAS_DOCUMENTALES = [
    "", "ACTA", "ANEXO", "NOTA INFORMATIVA", "CIRCULAR", "ESTÁDISTICAS",
    "FORMATO", "FOTO", "MEMORANDO", "MINUTA", "OFICIO",
    "RECIBO", "REPORTE", "PLANO", "TEXTO LIBRE",
    "CORREO ELECTRÓNICO", "EXPEDIENTE"
]

# Usada en múltiples diálogos y filtros
SERIES_DOCUMENTALES = [
    "", "10C.3", "12C.6", "1C.10", "2C.10", "2C.12", "2C.18", "2C.6", "2C.7",
    "2C.8", "2S.1", "2S.2", "2S.3", "2S.4", "2S.5", "2S.6", "2S.8", "3C.11",
    "3C.12", "3C.4", "4C.21", "4C.22", "4C.4", "4C.8", "5C.15", "5C.17",
    "5S.4", "5S.5", "6C.6", "7C.14", "7C.7", "8C.10", "8C.16", "8C.17",
    "8C.8", "Conocimiento"
]

# Usada en la pestaña de reportes
ESTADOS_EXPEDIENTE = ["Todos", "Abierto", "Cerrado", "Vencido"]

# Usada en el paginador de la tabla principal
REGISTROS_POR_PAGINA = ['10', '25', '50', '100']

class ExpedientesTab:
    ID = 0
    TIPO = 1
    CATEGORIA = 2
    FOLIO = 3
    FECHA = 4
    ASUNTO = 5
    SERIE = 6
    CARPETA = 7
    PAGINAS = 8
    RESPALDO = 9
    CLASIFICACION = 10
    APERTURA = 11
    CIERRE = 12
    VENCIMIENTO = 13
    ACCIONES = 14
    COLUMN_COUNT = 15

class BusquedaAvanzadaTab:
    ID_EXPEDIENTE = 0
    ID_RESPUESTA = 1
    TIPO = 2
    CATEGORIA = 3
    FOLIO = 4
    FECHA = 5
    ASUNTO = 6
    SERIE = 7
    CARPETA = 8
    PAGINAS = 9
    DOCUMENTO = 10
    CLASIFICACION = 11
    APERTURA = 12
    CIERRE = 13
    VENCIMIENTO = 14
    ACCIONES = 15
    COLUMN_COUNT = 16

class VencidosTab:
    ASUNTO = 5
    DOCUMENTO_RESPALDO = 9
    ACCIONES = 15
    COLUMN_COUNT = 16

class ConcentracionTab:
    ID = 0
    TIPO_DOCUMENTO = 1
    CATEGORIA_DOCUMENTAL = 2
    FOLIO = 3
    FECHA = 4
    ASUNTO = 5
    SERIE_DOCUMENTAL = 6
    CARPETA = 7
    PAGINAS = 8
    DOCUMENTO_RESPALDO = 9
    CLASIFICACION = 10
    APERTURA = 11
    CIERRE = 12
    VENCIMIENTO = 13
    FECHA_INGRESO = 14
    LOTE_ORIGEN = 15
    UBICACION_AREA = 16
    UBICACION_PASILLO = 17
    UBICACION_ANAQUEL = 18
    UBICACION_CHAROLA = 19
    DIAS_PARA_BAJA = 20
    ACCIONES = 21
    COLUMN_COUNT = 22

class SeriesTab:
    CODIGO_SERIE = 0
    NOMBRE_SERIE = 1
    DESCRIPCION_SERIE = 2
    AREA_ADMINISTRATIVA = 3
    ADM = 4
    LEGAL = 5
    FISCAL = 6
    TRAMITE = 7
    CONCENTRACION = 8
    TOTAL = 9
    PUBLICA = 10
    RESERVADA = 11
    CONFIDENCIAL = 12
    ORIGINAL = 13
    COPIA = 14
    SECCION = 15
    COLUMN_COUNT = 14

class ReportesTab:
    # Columnas de Expedientes
    ASUNTO_EXP = 5
    RESPALDO_EXP = 9
    
    # Columnas de Respuestas
    ASUNTO_RESP = 6
    
    # Columnas especiales de esta tabla
    ESTADO = 14
    DIAS_VENCIDO = 15
    COLUMN_COUNT = 16

class RespuestasDialogTab:
    ID = 0
    TIPO = 1
    CATEGORIA = 2
    FOLIO = 3
    FECHA = 4
    ASUNTO = 5
    CARPETA = 6
    PAGINAS = 7
    DOCUMENTO = 8
    CLASIFICACION = 9
    ACCIONES = 10
    COLUMN_COUNT = 11
    
class ContactoDialogTab:
    NOMBRE = 0
    CORREO = 1
    COLUMN_COUNT = 2

class ControlGestionTab:
    ID = 0
    ORIGEN = 1
    FOLIO = 2
    FECHA_RECEPCION = 3
    TURNADO_A = 4
    REMITENTE = 5
    AREA = 6
    REFERENCIA = 7
    FECHA_DOCUMENTO = 8
    ASUNTO = 9
    PRIORIDAD = 10
    FECHA_LIMITE = 11
    TIPO_INSTRUCCION = 12
    DETALLE_INSTRUCCION = 13
    OBSERVACIONES = 14
    ANEXOS = 15
    REQUIERE_RESPUESTA = 16
    RECIBIO = 17
    CCP = 18
    ESTATUS = 19
    ACCIONES = 20
    COLUMN_COUNT = 21

class LotesTab:
    ID = 0
    FOLIO = 1
    FECHA_CREACION = 2
    USUARIO = 3
    COLUMN_COUNT = 4

class HistorialLotesTab:
    ID = 0
    FOLIO = 1
    FECHA_CREACION = 2
    FECHA_ENTREGA = 3
    USUARIO = 4
    ACUSE = 5
    COLUMN_COUNT = 6

class DestinoFinalTab:
    ID_REGISTRO = 0
    TIPO_DESTINO = 1
    FECHA = 2
    FOLIO = 3
    ASUNTO = 4
    OBSERVACIONES = 5
    ACCIONES = 6
    COLUMN_COUNT = 7

class PrestamosTab:
    ID_PRESTAMO = 0
    EXPEDIENTE_ID = 1
    FOLIO = 2
    ASUNTO = 3
    CLASIFICACION = 4
    SOLICITANTE = 5
    AREA = 6
    FECHA_PRESTAMO = 7
    FECHA_VENCIMIENTO = 8
    DIAS_RESTANTES = 9
    OBSERVACIONES = 10
    ACCIONES = 11
    COLUMN_COUNT = 12

# --- Reglas de Préstamos Físicos ---
DIAS_PRESTAMO_DEFAULT = 15
COLUMNAS_DIRECTORIO = {
    "correo": "CORREO CONAGUA", 
    "puesto": "PUESTO"
}

# --- Fechas y Filtros Históricos ---
ANIO_INICIO_SISTEMA = 2017
ANIOS_ATRAS_FILTRO = -7

# --- Listas Desplegables de Control de Gestión ---
ORIGENES_CG = ["Todos", "DG", "SGT", "GAS"]
ESTATUS_CG = ["Todos", "PENDIENTE", "CONCLUIDO", "CANCELADO"]

# --- Opciones del Grupo Interdisciplinario ---
OPCIONES_VALORACION = ["BAJA DOCUMENTAL", "ARCHIVO HISTÓRICO"]