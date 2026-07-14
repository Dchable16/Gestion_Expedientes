# -*- coding: utf-8 -*-
"""
Created on Thu Jul 31 13:21:55 2025

@author: dchable
"""

# negocio/import_service.py


import pandas as pd
import logging
import sqlite3
import shutil
import abc
import os

from typing import Tuple, Dict, Any, List
from datetime import datetime

from datos.expediente_repository import ExpedienteRepository
from .expediente_service import ExpedienteService
from .backup_service import BackupService

class ImportStrategy(abc.ABC):
    """Clase base abstracta para las estrategias de importación."""
    
    @abc.abstractmethod
    def build_query(self, datos: dict, tabla: str) -> Tuple[str, tuple]:
        """
        Construye la consulta SQL y los parámetros para una estrategia de importación específica.
        
        Returns:
            Una tupla conteniendo la cadena de la consulta (str) y los parámetros (tuple).
        """
        pass

class InsertIgnoreStrategy(ImportStrategy):
    """Estrategia para "Mantener existentes": ignora los registros duplicados."""
    def build_query(self, datos: dict, tabla: str) -> Tuple[str, tuple]:
        columnas = ', '.join(datos.keys())
        placeholders = ', '.join(['?'] * len(datos))
        params = tuple(datos.values())
        query = f"INSERT OR IGNORE INTO {tabla} ({columnas}) VALUES ({placeholders})"
        return query, params

class InsertOrReplaceStrategy(ImportStrategy):
    """Estrategia para "Sobrescribir": actualiza los registros existentes."""
    def build_query(self, datos: dict, tabla: str) -> Tuple[str, tuple]:
        # Asegurarnos que 'id' es una columna para la cláusula ON CONFLICT
        if 'id' not in datos:
            # Si no hay ID, no podemos sobrescribir, así que usamos la estrategia de ignorar.
            return InsertIgnoreStrategy().build_query(datos, tabla)

        columnas = ', '.join(datos.keys())
        placeholders = ', '.join(['?'] * len(datos))
        
        update_clause = ', '.join([f"{col} = ?" for col in datos if col != 'id'])
        params_update = tuple(v for k, v in datos.items() if k != 'id')
        params = tuple(datos.values())
        
        query = f"""
            INSERT INTO {tabla} ({columnas}) VALUES ({placeholders})
            ON CONFLICT(id) DO UPDATE SET {update_clause}
        """
        return query, params + params_update

class InsertAsNewStrategy(ImportStrategy):
    """Estrategia para "Renombrar": importa todos los registros como nuevos, ignorando el ID original."""
    def build_query(self, datos: dict, tabla: str) -> Tuple[str, tuple]:
        datos_sin_id = datos.copy()
        datos_sin_id.pop('id', None) # Eliminamos el ID si existe
        
        columnas = ', '.join(datos_sin_id.keys())
        placeholders = ', '.join(['?'] * len(datos_sin_id))
        params = tuple(datos_sin_id.values())
        
        query = f"INSERT INTO {tabla} ({columnas}) VALUES ({placeholders})"
        return query, params
    
class ImportService:
    def __init__(self, db_path: str, expediente_service: ExpedienteService, expediente_repository: ExpedienteRepository):
        self.ruta_destino = db_path
        self.backup_service = BackupService(db_path)
        self.expediente_service = expediente_service
        self.expediente_repository = expediente_repository # <-- Añadir esta línea
        self.cancelado = False
        self.rutas_corregidas = []
        self.rutas_fallidas = []
        self.strategies = {
            'mantener': InsertIgnoreStrategy(),
            'sobrescribir': InsertOrReplaceStrategy(),
            'renombrar': InsertAsNewStrategy()
        }

    def iniciar_importacion(self, ruta_origen: str, opciones: Dict, signals: Dict):
        self.cancelado = False
        self.rutas_corregidas = []
        self.rutas_fallidas = []
        try:
            tipo_archivo = opciones.get('tipo_importacion')
            
            if opciones.get('hacer_backup'):
                signals['mensaje'].emit("Creando copia de seguridad...")
                success, message = self.backup_service.crear_backup()
                if not success:
                    raise Exception(f"No se pudo crear la copia de seguridad: {message}")
                signals['mensaje'].emit(f"Copia de seguridad creada: {os.path.basename(message)}")
            
            importar_conocimiento = opciones.get('importar_conocimiento', False)
    
            if tipo_archivo == 'sqlite':
                self._importar_desde_sqlite(ruta_origen, opciones, signals)
            
            elif tipo_archivo in ['excel', 'csv']:
                if tipo_archivo == 'excel':
                    df = pd.read_excel(ruta_origen, sheet_name=opciones.get('hoja_excel', 0), dtype=str).fillna('')
                else: 
                    df = pd.read_csv(ruta_origen, sep=opciones.get('separador_csv', ','), dtype=str, on_bad_lines='warn').fillna('')
                
                # --- DESPACHO INTELIGENTE ---
                if opciones.get('importar_cg'):
                    self._importar_cg_desde_df(df, self.expediente_repository, opciones, signals)
                    
                elif opciones.get('importar_respuestas'):
                    self._importar_respuestas_desde_df(df, self.expediente_repository, opciones, signals)
                    
                elif importar_conocimiento:
                    self._procesar_importacion_conocimiento(df, opciones, signals)
                    
                else:

                    self._importar_expedientes_desde_df(df, self.expediente_repository, opciones, signals)
            
            if not self.cancelado:
                self._generar_reporte_rutas(signals)
                signals['terminado'].emit(True, "Importación completada exitosamente.")
        except Exception as e:
            logging.error("Error durante la importación: %s", e, exc_info=True)
            signals['terminado'].emit(False, f"Error durante la importación: {str(e)}")

    def _importar_desde_sqlite(self, ruta_origen: str, opciones: Dict, signals: Dict):
        conn_origen = None
        conn_destino = None
        try:
            signals['mensaje'].emit(f"Conectando a la base de datos de origen: {ruta_origen}")
            conn_origen = sqlite3.connect(ruta_origen)
            cursor_origen = conn_origen.cursor()

            signals['mensaje'].emit(f"Conectando a la base de datos de destino: {self.ruta_destino}")
            conn_destino = sqlite3.connect(self.ruta_destino)
            cursor_destino = conn_destino.cursor()

            cursor_destino.execute("BEGIN TRANSACTION")
            sobrescribir = opciones.get('resolucion_conflictos') == 'sobrescribir'

            cursor_origen.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tablas_disponibles = [t[0] for t in cursor_origen.fetchall()]

            for tabla in ['series_documentales', 'control_gestion', 'expedientes', 'respuestas', 'archivo_concentracion']:
                if tabla in tablas_disponibles:
                    clave_primaria = 'id' if tabla != 'series_documentales' else 'codigo_serie'
                    self._importar_tabla(cursor_origen, cursor_destino, tabla, clave_primaria, sobrescribir, signals)

            conn_destino.commit()
        except Exception as e:
            logging.error("Error durante la importación SQLite", exc_info=True)
            if conn_destino: conn_destino.rollback()
            raise e
        finally:
            if conn_origen: conn_origen.close()
            if conn_destino: conn_destino.close()

    def _importar_tabla(self, cursor_origen, cursor_destino, nombre_tabla, clave_primaria, sobrescribir, signals):
        """Función de ayuda para importar una tabla específica."""
        signals['mensaje'].emit(f"Iniciando importación de la tabla: {nombre_tabla}...")
        
        cursor_origen.execute(f"SELECT * FROM {nombre_tabla}")
        filas = cursor_origen.fetchall()
        
        if not filas:
            signals['mensaje'].emit(f"No se encontraron datos en la tabla '{nombre_tabla}' del archivo de origen.")
            return

        columnas = [description[0] for description in cursor_origen.description]
        placeholders = ', '.join(['?'] * len(columnas))
        
        query = f"INSERT {'OR REPLACE' if sobrescribir else 'OR IGNORE'} INTO {nombre_tabla} ({', '.join(columnas)}) VALUES ({placeholders})"

        total = len(filas)
        for i, fila in enumerate(filas):
            if self.cancelado:
                signals['mensaje'].emit("Importación cancelada.")
                raise Exception("Proceso cancelado por el usuario")
            
            cursor_destino.execute(query, fila)
            
            if (i + 1) % 100 == 0 or (i + 1) == total:
                signals['progreso'].emit(int(((i + 1) / total) * 100))
                signals['mensaje'].emit(f"Procesando {nombre_tabla}: {i+1} de {total}...")
        
        signals['mensaje'].emit(f"Importación de la tabla '{nombre_tabla}' finalizada.")


    def _limpiar_fila(self, fila_dict: dict) -> dict:
        """Limpia, formatea y valida los datos de una fila. Devuelve None si la fila es inválida."""
        datos_limpios = {}
        date_columns = ['fecha', 'fecha_respuesta', 'vencimiento']
        
        if all(pd.isna(v) or str(v).strip() == '' for v in fila_dict.values()):
            return None 

        for key, value in fila_dict.items():
            if pd.isna(value) or str(value).strip().lower() in ['', 'nat', 'nan']:
                datos_limpios[key] = None if key in ['apertura', 'cierre', 'paginas'] else ""
                continue
            
            if key in date_columns:
                try:
                    datos_limpios[key] = pd.to_datetime(value).strftime('%Y-%m-%d')
                except (ValueError, TypeError):
                    datos_limpios[key] = "" 
            else:
                datos_limpios[key] = str(value).strip()
        
        return datos_limpios


    def _construir_query(self, datos: dict, tabla: str, conflicto: str) -> Tuple[str, tuple]:
        """
        Elige y ejecuta la estrategia de importación correcta usando el Patrón Strategy.
        Este método ahora es increíblemente simple.
        """
        datos_limpios = {k: v for k, v in datos.items() if v is not None}
        
        strategy = self.strategies.get(conflicto, self.strategies['mantener'])
        
        return strategy.build_query(datos_limpios, tabla)

    def _copiar_documentos(self, cursor, tabla_a_procesar: str):
        """Copia los documentos a la carpeta local y actualiza las rutas en la base de datos."""
        documentos_dir = 'documentos'
        expedientes_dir = os.path.join(documentos_dir, 'expedientes')
        respuestas_dir = os.path.join(documentos_dir, 'respuestas')
        os.makedirs(expedientes_dir, exist_ok=True)
        os.makedirs(respuestas_dir, exist_ok=True)
        
        if tabla_a_procesar == 'expedientes':
            cursor.execute("SELECT id, documento_respaldo FROM expedientes WHERE documento_respaldo IS NOT NULL AND documento_respaldo != ''")
            for record_id, ruta_origen in cursor.fetchall():
                if self.cancelado:
                    return
                self._procesar_y_copiar_archivo(cursor, "expedientes", "documento_respaldo", record_id, ruta_origen, expedientes_dir)
        
        elif tabla_a_procesar == 'respuestas':
            cursor.execute("SELECT id, documento_respuesta FROM respuestas WHERE documento_respuesta IS NOT NULL AND documento_respuesta != ''")
            for record_id, ruta_origen in cursor.fetchall():
                if self.cancelado:
                    return
                self._procesar_y_copiar_archivo(cursor, "respuestas", "documento_respuesta", record_id, ruta_origen, respuestas_dir)
            
    def _procesar_y_copiar_archivo(self, cursor, tabla, columna, record_id, ruta_origen, dir_destino):
        """Función para validar, copiar, y actualizar la ruta de un archivo, registrando los eventos."""
        ruta_origen_normalizada = os.path.normpath(ruta_origen)

        if not ruta_origen_normalizada or not str(ruta_origen_normalizada).strip() or not os.path.isabs(ruta_origen_normalizada):
            self.rutas_fallidas.append(f"Registro ID: {record_id} en tabla '{tabla}' - Ruta de origen inválida o vacía: '{ruta_origen}'")
            return 

        if os.path.exists(ruta_origen_normalizada):
            nombre_archivo = os.path.basename(ruta_origen_normalizada)
            ruta_destino_abs = os.path.abspath(os.path.join(dir_destino, nombre_archivo))
            
            contador = 1
            nombre_base, extension = os.path.splitext(nombre_archivo)
            while os.path.exists(ruta_destino_abs):
                nombre_archivo = f"{nombre_base}_{contador}{extension}"
                ruta_destino_abs = os.path.abspath(os.path.join(dir_destino, nombre_archivo))
                contador += 1

            shutil.copy2(ruta_origen_normalizada, ruta_destino_abs)
            
            ruta_destino_relativa = os.path.join("documentos", os.path.basename(dir_destino), nombre_archivo).replace('\\', '/')
            cursor.execute(f"UPDATE {tabla} SET {columna} = ? WHERE id = ?", (ruta_destino_relativa, record_id))
            
            self.rutas_corregidas.append(f"Registro ID: {record_id} en tabla '{tabla}' - Ruta corregida de '{ruta_origen}' a '{ruta_destino_relativa}'")
        else:
            self.rutas_fallidas.append(f"Registro ID: {record_id} en tabla '{tabla}' - Archivo no encontrado: '{ruta_origen}'")

    def _generar_reporte_rutas(self, signals):
        """Genera un archivo de reporte de las rutas procesadas."""
        if not self.rutas_corregidas and not self.rutas_fallidas:
            return

        reporte_dir = "reportes_importacion"
        os.makedirs(reporte_dir, exist_ok=True)
        fecha_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_reporte = f"reporte_rutas_{fecha_str}.txt"
        ruta_reporte = os.path.join(reporte_dir, nombre_reporte)

        with open(ruta_reporte, "w", encoding="utf-8") as f:
            f.write("--- REPORTE DE RUTAS PROCESADAS DURANTE LA IMPORTACIÓN ---\n")
            f.write(f"Fecha y Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("RUTAS CORREGIDAS Y COPIADAS:\n")
            if self.rutas_corregidas:
                for linea in self.rutas_corregidas:
                    f.write(f"- {linea}\n")
            else:
                f.write("- No se corrigieron rutas.\n")
            f.write("\n")

            f.write("RUTAS FALLIDAS (DOCUMENTO NO COPIADO):\n")
            if self.rutas_fallidas:
                for linea in self.rutas_fallidas:
                    f.write(f"- {linea}\n")
            else:
                f.write("- No hubo rutas fallidas.\n")
        
        signals['mensaje'].emit(f"Reporte de rutas generado en: {os.path.abspath(ruta_reporte)}")
    
    def _procesar_importacion_conocimiento(self, df: pd.DataFrame, opciones: Dict, signals: Dict):
        """
        Importa documentos de CONOCIMIENTO agrupándolos en Expedientes Maestros por año.
        Optimizado con TRANSACCIÓN ÚNICA y Caché de IDs.
        """
        total = len(df)
        signals['mensaje'].emit(f"Preparando importación de {total} registros de Conocimiento...")
        
        conn = None
        try:
            conn = sqlite3.connect(self.ruta_destino)
            cursor = conn.cursor()
            cursor.execute("BEGIN TRANSACTION")

            exito = 0
            omitidos = 0
            errores = 0
            
            # Cache para no consultar la BD repetidamente por el mismo año
            # Clave: Año (int), Valor: ID del Expediente Maestro (int)
            cache_maestros = {}

            # Mapeo de columnas del Excel
            mapa_columnas = {
                'fecha': ['fecha', 'fecha_recepcion', 'recepcion', 'fecha_registro', 'fecha_respuesta'],
                'asunto': ['asunto', 'descripcion', 'tema', 'asunto_respuesta'],
                'folio': ['folio', 'num_oficio', 'oficio'], # Folio del documento individual
                'documento': ['documento', 'archivo', 'ruta', 'path', 'documento_respuesta', 'documento_respaldo'],
                'paginas': ['paginas', 'hojas']
            }

            df.columns = [str(col).lower().strip() for col in df.columns]

            for index, row in df.iterrows():
                if self.cancelado:
                    conn.rollback()
                    signals['mensaje'].emit("Se detuvo la inserción a solicitud del usuario.")
                    signals['terminado'].emit(False, "Proceso de Importación CANCELADO por el usuario.")
                    return

                try:
                    # 1. Extracción de datos
                    datos = {}
                    for campo, posibles in mapa_columnas.items():
                        valor = ""
                        for nombre_excel in posibles:
                            if nombre_excel in df.columns:
                                val_raw = row[nombre_excel]
                                if pd.notna(val_raw) and str(val_raw).strip() not in ["", "nan", "NaT"]:
                                    valor = str(val_raw).strip()
                                break
                        datos[campo] = valor

                    # Validar fecha para determinar el año
                    anio_actual = datetime.now().year
                    if datos['fecha']:
                        try:
                            fecha_dt = pd.to_datetime(datos['fecha'])
                            datos['fecha'] = fecha_dt.strftime('%Y-%m-%d')
                            anio = fecha_dt.year
                        except:
                            anio = anio_actual
                    else:
                        anio = anio_actual
                        datos['fecha'] = datetime.now().strftime('%Y-%m-%d')

                    # 2. OBTENER O CREAR EXPEDIENTE MAESTRO (Lógica de agrupación)
                    if anio not in cache_maestros:
                        # Buscamos si ya existe la carpeta maestra para este año
                        folio_maestro = f"CONOCIMIENTO-{anio}"
                        cursor.execute("SELECT id FROM expedientes WHERE folio = ?", (folio_maestro,))
                        resultado = cursor.fetchone()

                        if resultado:
                            cache_maestros[anio] = resultado[0]
                        else:
                            # Crear Expediente Maestro si no existe
                            query_maestro = """
                                INSERT INTO expedientes (
                                    tipo_documento, categoria_documental, folio, fecha,
                                    asunto, serie_documental, carpeta, clasificacion, apertura
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """
                            asunto_maestro = f"CARPETA GENERAL DE CONOCIMIENTO AÑO {anio}"
                            # La fecha del maestro es el 1 de enero de ese año
                            fecha_maestro = f"{anio}-01-01" 
                            
                            cursor.execute(query_maestro, (
                                'Conocimiento', 'Conocimiento', folio_maestro, fecha_maestro,
                                asunto_maestro, 'Conocimiento', f"Carpeta Anual {anio}", 'Pública', anio
                            ))
                            cache_maestros[anio] = cursor.lastrowid

                    id_padre = cache_maestros[anio]

                    # 3. INSERTAR EL DOCUMENTO COMO RESPUESTA (Hijo)
                    if not datos['folio']: # Si no tiene folio el documento, generamos uno temporal o saltamos
                        datos['folio'] = "S/N"

                    query_respuesta = """
                        INSERT INTO respuestas (
                            expediente_id, tipo_documento, categoria_documental, folio,
                            fecha_respuesta, asunto_respuesta, paginas, documento_respuesta
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """
                    
                    cursor.execute(query_respuesta, (
                        id_padre, 'RESPUESTA', 'Conocimiento', datos['folio'],
                        datos['fecha'], datos['asunto'], datos.get('paginas', 0), datos['documento']
                    ))
                    
                    exito += 1

                    if (index + 1) % 50 == 0:
                        signals['progreso'].emit(int(((index + 1) / total) * 100))

                except Exception as e:
                    errores += 1
                    signals['mensaje'].emit(f"Error fila {index+2}: {str(e)}")

            conn.commit()
            
            if opciones.get('copiar_documentos'):
                # Copiar documentos asociados a las respuestas insertadas
                self._copiar_documentos(cursor, 'respuestas')
                conn.commit()

            signals['mensaje'].emit(f"Conocimiento: {exito} documentos importados en Carpetas Anuales. Errores: {errores}")

        except Exception as e:
            if conn: conn.rollback()
            raise e
        finally:
            if conn: conn.close()

    def cancelar(self):
        self.cancelado = True

    def _copiar_documento_conocimiento(self, ruta_origen: str) -> str:
        """
        Copia un archivo de conocimiento a la carpeta 'documentos/conocimiento'
        y devuelve la ruta relativa.
        """
        if not ruta_origen:
            return ""
        
        try:
            # Se define la ruta de la carpeta 'conocimiento'
            directorio_base = os.getcwd()
            carpeta_conocimiento = os.path.join(directorio_base, "documentos", "conocimiento")
            os.makedirs(carpeta_conocimiento, exist_ok=True)
            
            nombre_archivo = os.path.basename(ruta_origen)
            ruta_destino = os.path.join(carpeta_conocimiento, nombre_archivo)
            
            # Solo copia el archivo si no existe ya en la ruta de destino
            if not os.path.exists(ruta_destino):
                shutil.copy2(ruta_origen, ruta_destino)
            
            # Devuelve la ruta relativa que se guardará en la base de datos
            ruta_relativa = os.path.join("documentos", "conocimiento", nombre_archivo)
            return ruta_relativa.replace("\\", "/")
            
        except Exception as e:
            logging.error(f"No se pudo copiar el archivo de conocimiento: {e}", exc_info=True)
            return ""
    
    def _importar_expedientes_desde_df(self, df: pd.DataFrame, repo, opciones: Dict, signals: Dict):
        """
        Importa Expedientes con TRANSACCIÓN ÚNICA (Optimizado para velocidad).
        """
        total = len(df)
        signals['mensaje'].emit(f"Preparando importación de {total} expedientes...")
        
        # --- USAMOS CONEXIÓN LOCAL PARA VELOCIDAD ---
        conn = None
        try:
            conn = sqlite3.connect(self.ruta_destino)
            cursor = conn.cursor()
            cursor.execute("BEGIN TRANSACTION") # Inicio del bloque masivo

            exito = 0
            omitidos = 0
            actualizados = 0
            errores = 0
            
            mapa_columnas = {
                'folio': ['folio', 'num_oficio', 'oficio', 'expediente'],
                'fecha': ['fecha', 'fecha_apertura', 'fecha_registro', 'apertura'],
                'asunto': ['asunto', 'descripcion', 'tema'],
                'tipo_documento': ['tipo', 'tipo_documento', 'tipo_doc'],
                'categoria_documental': ['categoria', 'categoria_documental'],
                'serie_documental': ['serie', 'serie_documental', 'codigo_serie'],
                'carpeta': ['carpeta', 'ubicacion_fisica'],
                'paginas': ['paginas', 'fojas', 'num_hojas'],
                'documento_respaldo': ['documento_respaldo', 'documento', 'archivo', 'ruta', 'path'],
                'clasificacion': ['clasificacion', 'nivel_acceso'],
                'apertura': ['anio_apertura', 'apertura_anio','apertura'], 
                'cierre': ['cierre', 'fecha_cierre'],
                'vencimiento': ['vencimiento', 'fecha_vencimiento']
            }

            df.columns = [str(col).lower().strip() for col in df.columns]

            for index, row in df.iterrows():
                if self.cancelado:
                    conn.rollback()
                    signals['mensaje'].emit("Se detuvo la inserción a solicitud del usuario.")
                    signals['terminado'].emit(False, "Proceso de Importación CANCELADO por el usuario.")
                    return

                try:
                    datos = {}
                    for campo_bd, posibles in mapa_columnas.items():
                        valor = ""
                        for nombre_excel in posibles:
                            if nombre_excel in df.columns:
                                val_raw = row[nombre_excel]
                                if pd.notna(val_raw) and str(val_raw).strip() not in ["", "nan", "NaT"]:
                                    valor = str(val_raw).strip()
                                    if campo_bd in ['fecha', 'cierre', 'vencimiento'] and (" " in valor or "/" in valor):
                                        try: valor = pd.to_datetime(valor).strftime('%Y-%m-%d')
                                        except: pass
                                break
                        datos[campo_bd] = valor

                    if not datos.get('folio'):
                        errores += 1
                        continue

                    # 1. Verificar existencia usando el cursor local (muy rápido)
                    cursor.execute("SELECT COUNT(*) FROM expedientes WHERE folio = ?", (datos['folio'],))
                    existe = cursor.fetchone()[0] > 0

                    # 2. Ejecutar INSERT/UPDATE sin commit intermedio
                    if existe:
                        resolucion = opciones.get('resolucion_conflictos', 'mantener')
                        if resolucion == 'mantener':
                            omitidos += 1
                        elif resolucion == 'sobrescribir':
                            query = """
                                UPDATE expedientes SET
                                    tipo_documento = ?, categoria_documental = ?, fecha = ?,
                                    asunto = ?, serie_documental = ?, carpeta = ?, paginas = ?,
                                    documento_respaldo = ?, clasificacion = ?, apertura = ?,
                                    cierre = ?, vencimiento = ?
                                WHERE folio = ?
                            """
                            vals = (
                                datos.get('tipo_documento'), datos.get('categoria_documental'),
                                datos.get('fecha'), datos.get('asunto'), datos.get('serie_documental'),
                                datos.get('carpeta'), datos.get('paginas'), datos.get('documento_respaldo'),
                                datos.get('clasificacion'), datos.get('apertura'), datos.get('cierre'),
                                datos.get('vencimiento'), datos['folio']
                            )
                            cursor.execute(query, vals)
                            actualizados += 1
                        elif resolucion == 'renombrar':
                            datos['folio'] = f"{datos['folio']}_IMP_{index}"
                            self._insertar_expediente_local(cursor, datos)
                            exito += 1
                    else:
                        self._insertar_expediente_local(cursor, datos)
                        exito += 1

                    if (index + 1) % 50 == 0: 
                        signals['progreso'].emit(int(((index + 1) / total) * 100))

                except Exception as e:
                    errores += 1
                    signals['mensaje'].emit(f"Error en fila {index+2}: {str(e)}")

            # --- COMMIT MASIVO AL FINAL ---
            conn.commit()
            
            if opciones.get('copiar_documentos'):
                self._copiar_documentos(cursor, 'expedientes')
                conn.commit()

            signals['mensaje'].emit(f"Expedientes: Nuevos {exito}, Actualizados {actualizados}, Omitidos {omitidos}, Errores {errores}")

        except Exception as e:
            if conn: conn.rollback()
            raise e
        finally:
            if conn: conn.close()
            
    def _insertar_expediente_local(self, cursor, datos):
        """Helper para insertar usando el cursor local de la transacción."""
        query = '''
            INSERT INTO expedientes (
                tipo_documento, categoria_documental, folio, fecha,
                asunto, serie_documental, carpeta, paginas, documento_respaldo,
                clasificacion, apertura, cierre, vencimiento
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        vals = (
            datos.get('tipo_documento'), datos.get('categoria_documental'),
            datos.get('folio'), datos.get('fecha'), datos.get('asunto'),
            datos.get('serie_documental'), datos.get('carpeta'),
            datos.get('paginas'), datos.get('documento_respaldo'),
            datos.get('clasificacion'), datos.get('apertura'),
            datos.get('cierre'), datos.get('vencimiento')
        )
        cursor.execute(query, vals)
        
    def _importar_respuestas_desde_df(self, df: pd.DataFrame, repo, opciones: Dict, signals: Dict):
        """
        Importa Respuestas con mapeo inteligente de columnas (fecha_respuesta, asunto_respuesta).
        """
        total = len(df)
        signals['mensaje'].emit(f"Preparando importación de {total} respuestas...")
        
        conn = None
        try:
            conn = sqlite3.connect(self.ruta_destino)
            cursor = conn.cursor()
            cursor.execute("BEGIN TRANSACTION")
            
            exito = 0
            errores = 0
            
            # --- MAPEO DE COLUMNAS PARA RESPUESTAS ---
            mapa_columnas = {
                'expediente_id': ['expediente_id', 'id_expediente', 'id_padre'],
                'fecha_respuesta': ['fecha_respuesta', 'fecha', 'recepcion'],
                'asunto_respuesta': ['asunto_respuesta', 'asunto', 'descripcion'],
                'folio': ['folio', 'oficio'],
                'tipo_documento': ['tipo_documento', 'tipo'],
                'categoria_documental': ['categoria_documental', 'categoria'],
                'paginas': ['paginas', 'hojas'],
                'documento_respuesta': ['documento_respuesta', 'documento', 'archivo', 'ruta']
            }
            
            # Normalizar columnas del DF
            df.columns = [str(col).lower().strip() for col in df.columns]

            for index, row in df.iterrows():
                if self.cancelado:
                    conn.rollback()
                    signals['mensaje'].emit("Se detuvo la inserción a solicitud del usuario.")
                    signals['terminado'].emit(False, "Proceso de Importación CANCELADO por el usuario.")
                    return

                try:
                    datos = {}
                    for campo_bd, posibles in mapa_columnas.items():
                        valor = ""
                        for nombre_excel in posibles:
                            if nombre_excel in df.columns:
                                val_raw = row[nombre_excel]
                                if pd.notna(val_raw) and str(val_raw).strip() not in ["", "nan", "NaT"]:
                                    valor = str(val_raw).strip()
                                    if "fecha" in campo_bd and (" " in valor or "/" in valor):
                                        try: valor = pd.to_datetime(valor).strftime('%Y-%m-%d')
                                        except: pass
                                break
                        datos[campo_bd] = valor

                    # Validaciones básicas
                    if not datos.get('expediente_id'):
                        # Intento opcional: Si no hay ID pero hay Folio del padre, buscar ID (requiere lógica extra)
                        errores += 1
                        continue

                    # Insertar respuesta
                    query = """
                        INSERT INTO respuestas (
                            expediente_id, tipo_documento, categoria_documental, folio,
                            fecha_respuesta, asunto_respuesta, paginas, documento_respuesta
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """
                    valores = (
                        datos.get('expediente_id'), datos.get('tipo_documento', 'RESPUESTA'),
                        datos.get('categoria_documental', ''), datos.get('folio', ''),
                        datos.get('fecha_respuesta'), datos.get('asunto_respuesta'),
                        datos.get('paginas', 0), datos.get('documento_respuesta', '')
                    )
                    
                    cursor.execute(query, valores)
                    exito += 1
                    
                    if (index + 1) % 10 == 0:
                        signals['progreso'].emit(int(((index + 1) / total) * 100))

                except Exception as e:
                    errores += 1
                    signals['mensaje'].emit(f"Error fila {index+2}: {str(e)}")

            conn.commit()
            if opciones.get('copiar_documentos'):
                self._copiar_documentos(cursor, 'respuestas')
                conn.commit()
                
            signals['mensaje'].emit(f"Importación Respuestas finalizada. Éxitos: {exito}, Errores: {errores}")

        except Exception as e:
            if conn: conn.rollback()
            raise e
        finally:
            if conn: conn.close()
    
    def _importar_cg_desde_df(self, df: pd.DataFrame, repo, opciones: Dict, signals: Dict):
        """
        Importa registros de Control de Gestión con TRANSACCIÓN ÚNICA (Optimizado).
        """
        total = len(df)
        signals['mensaje'].emit(f"Preparando importación de {total} registros de Control de Gestión...")
        
        # --- USAMOS CONEXIÓN LOCAL PARA VELOCIDAD ---
        conn = None
        try:
            conn = sqlite3.connect(self.ruta_destino)
            cursor = conn.cursor()
            cursor.execute("BEGIN TRANSACTION")

            exito = 0
            omitidos = 0
            actualizados = 0
            errores = 0
            
            mapa_columnas = {
                'id': ['id', 'ID', 'Id', 'no_consecutivo'],
                'origen': ['origen', 'procedencia', 'fuente'],
                'folio': ['folio', 'num_oficio', 'oficio'],
                'fecha': ['fecha', 'fecha_recepcion','fecha recepción', 'recepcion'],
                'turnado_a': ['turnado a', 'turnado_a', 'turnado', 'destinatario'],
                'remitente': ['remitente', 'enviado_por'],
                'area': ['área', 'area', 'departamento', 'unidad'],
                'referencia': ['referencia', 'ref'],
                'fecha_documento': ['fecha documento', 'fecha_documento', 'fecha_doc'],
                'asunto': ['asunto', 'descripcion', 'tema'],
                'prioridad': ['prioridad', 'urgencia'],
                'fecha_limite': ['fecha límite', 'fecha limite', 'fecha_limite', 'vencimiento'],
                'tipo_instruccion': ['instrucción', 'instruccion', 'tipo_instruccion'],
                'detalle_instruccion': ['detalle', 'detalle_instruccion', 'notas_instruccion'],
                'observaciones': ['observaciones', 'notas'],
                'documentos_anexos': ['anexos', 'documentos_anexos', 'archivos'],
                'requiere_respuesta': ['req. respuesta', 'requiere respuesta', 'requiere_respuesta', 'respuesta'],
                'recibio': ['recibió', 'recibio', 'persona_recibe'],
                'ccp': ['c.c.p.', 'ccp', 'copia para'],
                'archivado': ['estatus', 'archivado', 'estado']
            }

            df.columns = [str(col).lower().strip() for col in df.columns]

            for index, row in df.iterrows():
                if self.cancelado:
                    conn.rollback()
                    signals['mensaje'].emit("Se detuvo la inserción a solicitud del usuario.")
                    signals['terminado'].emit(False, "Proceso de Importación CANCELADO por el usuario.")
                    return

                try:
                    datos = {}
                    for campo_bd, posibles_nombres in mapa_columnas.items():
                        valor = ""
                        for nombre_excel in posibles_nombres:
                            if nombre_excel in df.columns:
                                val_raw = row[nombre_excel]
                                if pd.notna(val_raw) and str(val_raw).strip() not in ["", "nan", "NaT"]:
                                    valor = str(val_raw).strip()
                                    if "fecha" in campo_bd and (" " in valor or "/" in valor):
                                        try: valor = pd.to_datetime(valor).strftime('%Y-%m-%d')
                                        except: pass
                                break
                        datos[campo_bd] = valor

                    if not datos.get('folio'):
                        errores += 1
                        continue

                    # 1. Verificar existencia (Local)
                    cursor.execute("SELECT COUNT(*) FROM control_gestion WHERE folio = ?", (datos['folio'],))
                    existe = cursor.fetchone()[0] > 0

                    # 2. Operación (Local)
                    if existe:
                        resolucion = opciones.get('resolucion_conflictos', 'mantener')
                        if resolucion == 'mantener':
                            omitidos += 1
                            continue
                        
                        elif resolucion == 'sobrescribir':
                            query = """
                                UPDATE control_gestion SET
                                    origen = ?, fecha = ?, turnado_a = ?, remitente = ?, area = ?, referencia = ?,
                                    fecha_documento = ?, asunto = ?, prioridad = ?, fecha_limite = ?,
                                    tipo_instruccion = ?, detalle_instruccion = ?, observaciones = ?,
                                    documentos_anexos = ?, requiere_respuesta = ?, recibio = ?, ccp = ?,
                                    archivado = ?
                                WHERE folio = ?
                            """
                            vals = (
                                datos.get('origen'), datos.get('fecha'), datos.get('turnado_a'), datos.get('remitente'),
                                datos.get('area'), datos.get('referencia'), datos.get('fecha_documento'),
                                datos.get('asunto'), datos.get('prioridad'), datos.get('fecha_limite'),
                                datos.get('tipo_instruccion'), datos.get('detalle_instruccion'),
                                datos.get('observaciones'), datos.get('documentos_anexos'),
                                datos.get('requiere_respuesta'), datos.get('recibio'), datos.get('ccp'),
                                datos.get('archivado'), datos.get('folio')
                            )
                            cursor.execute(query, vals)
                            actualizados += 1
                        
                        elif resolucion == 'renombrar':
                            datos['folio'] = f"{datos['folio']}_IMP_{index}"
                            self._insertar_cg_local(cursor, datos)
                            exito += 1
                    else:
                        self._insertar_cg_local(cursor, datos)
                        exito += 1

                    if (index + 1) % 50 == 0:
                        signals['progreso'].emit(int(((index + 1) / total) * 100))

                except Exception as e:
                    errores += 1
                    signals['mensaje'].emit(f"Error en fila {index+2}: {str(e)}")

            conn.commit()
            signals['mensaje'].emit(f"Control Gestión: Nuevos {exito}, Actualizados {actualizados}, Omitidos {omitidos}, Errores {errores}")

        except Exception as e:
            if conn: conn.rollback()
            raise e
        finally:
            if conn: conn.close()

    def _insertar_cg_local(self, cursor, datos):
        """
        Inserta un registro en control_gestion.
        CORRECCIÓN: Ahora incluye el campo 'id' explícitamente para respetar
        la numeración que viene desde el archivo Excel/CSV.
        """
        
        # 1. Verificamos si el dato trae ID (del Excel/CSV)
        # Las columnas del CSV suelen llamarse "ID" (mayúscula) o "id"
        id_dato = datos.get('ID') or datos.get('id')
        
        if id_dato:
            # CASO A: Insertar CON ID específico (Respetar Excel)
            query = '''
                INSERT OR REPLACE INTO control_gestion (
                    id, origen, folio, fecha, turnado_a, remitente, area, referencia, fecha_documento,
                    asunto, prioridad, fecha_limite, tipo_instruccion, detalle_instruccion,
                    observaciones, documentos_anexos, requiere_respuesta, recibio, ccp, archivado
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            '''
            vals = (
                id_dato,  # <--- AQUÍ ESTÁ EL ID IMPORTADO
                datos.get('origen'), datos.get('folio'), datos.get('fecha'), datos.get('turnado_a'), 
                datos.get('remitente'), datos.get('area'), datos.get('referencia'), datos.get('fecha_documento'),
                datos.get('asunto'), datos.get('prioridad'), datos.get('fecha_limite'),
                datos.get('tipo_instruccion'), datos.get('detalle_instruccion'),
                datos.get('observaciones'), datos.get('documentos_anexos'), datos.get('requiere_respuesta'), 
                datos.get('recibio'), datos.get('ccp'), datos.get('archivado')
            )
        else:
            # CASO B: Insertar SIN ID (Dejar que la BD genere uno nuevo)
            # Esto pasa si la celda ID en Excel viene vacía
            query = '''
                INSERT INTO control_gestion (
                    origen, folio, fecha, turnado_a, remitente, area, referencia, fecha_documento,
                    asunto, prioridad, fecha_limite, tipo_instruccion, detalle_instruccion,
                    observaciones, documentos_anexos, requiere_respuesta, recibio, ccp, archivado
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            '''
            vals = (
                datos.get('origen'), datos.get('folio'), datos.get('fecha'), datos.get('turnado_a'), 
                datos.get('remitente'), datos.get('area'), datos.get('referencia'), datos.get('fecha_documento'),
                datos.get('asunto'), datos.get('prioridad'), datos.get('fecha_limite'),
                datos.get('tipo_instruccion'), datos.get('detalle_instruccion'),
                datos.get('observaciones'), datos.get('documentos_anexos'), datos.get('requiere_respuesta'), 
                datos.get('recibio'), datos.get('ccp'), datos.get('archivado')
            )

        cursor.execute(query, vals)