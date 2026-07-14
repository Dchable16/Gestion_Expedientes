
import logging
import sqlite3
import csv
import os
import re

from datetime import datetime, timedelta
from typing import Dict, List

from utils.config_manager import get_series_data_csv_path


class ExpedienteRepository:
    def __init__(self, db_name='expedientes.db'):
       self.db_name = os.path.abspath(db_name)
       self.conn = None
       self.cursor = None
       try:
           self.connect()
           self.create_tables()
           self.verificar_esquema()
           self.insertar_datos_iniciales()
       except Exception as e:
           raise RuntimeError(f"No se pudo inicializar la base de datos: {str(e)}")
    
    def connect(self):
        """Establece una nueva conexión a la base de datos."""
        if self.conn is None:
            try:
                self.conn = sqlite3.connect(self.db_name, timeout=10, check_same_thread=False)
                self.conn.row_factory = sqlite3.Row
                self.cursor = self.conn.cursor()
            except sqlite3.Error as e:
                logging.error(f"Error al conectar con la base de datos: {e}", exc_info=True)
                self.conn = None
                self.cursor = None
    
    def close_connection(self):
        """Cierra la conexión a la base de datos."""
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None

    def execute_query(self, query: str, params: tuple = ()):
        """Ejecuta una consulta aislada, abriendo un cursor temporal."""
        try:
            cursor_temp = self.conn.cursor() 
            cursor_temp.execute(query, params)
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            import logging
            logging.error(f"Error en execute_query: {e}")
            if self.conn: self.conn.rollback()
            return False

    def fetch_all(self, query: str, params: tuple = ()):
        """Obtiene todos los resultados de forma concurrente."""
        cursor_temp = self.conn.cursor() 
        cursor_temp.execute(query, params)
        return cursor_temp.fetchall()

    def fetch_one(self, query: str, params: tuple = ()):
        """Obtiene un solo resultado de forma concurrente."""
        cursor_temp = self.conn.cursor() 
        cursor_temp.execute(query, params)
        return cursor_temp.fetchone()
    
    def create_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS control_gestion (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                origen TEXT,
                folio TEXT,
                fecha DATE,
                turnado_a TEXT,
                remitente TEXT,
                area TEXT,
                referencia TEXT,
                fecha_documento DATE,
                asunto TEXT,
                prioridad TEXT,
                fecha_limite DATE,
                tipo_instruccion TEXT,
                detalle_instruccion TEXT,
                observaciones TEXT,
                documentos_anexos TEXT,
                requiere_respuesta TEXT,
                recibio TEXT,
                ccp TEXT,
                archivado TEXT
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS expedientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo_documento TEXT,
                categoria_documental TEXT,
                folio TEXT,
                fecha DATE,
                asunto TEXT,
                serie_documental TEXT,
                carpeta TEXT,
                paginas INTEGER,
                documento_respaldo TEXT,
                clasificacion TEXT,
                apertura INTEGER,
                cierre INTEGER,
                vencimiento DATE
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS respuestas (
                id INTEGER PRIMARY KEY AUTOINCREMENT, expediente_id INTEGER,
                tipo_documento TEXT, categoria_documental TEXT, folio TEXT,
                fecha_respuesta DATE, asunto_respuesta TEXT, serie_documental TEXT,
                carpeta TEXT, paginas INTEGER, documento_respuesta TEXT,
                clasificacion TEXT, apertura INTEGER, cierre INTEGER,
                vencimiento DATE,
                FOREIGN KEY (expediente_id) REFERENCES expedientes (id)
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS series_documentales (
                codigo_serie TEXT PRIMARY KEY, nombre_serie TEXT, descripcion_serie TEXT, area_administrativa TEXT,
                administrativo TEXT, legal TEXT, fiscal TEXT, tramite INTEGER, concentracion INTEGER,
                total INTEGER, publica TEXT, reservada TEXT, confidencial TEXT, original TEXT, copia TEXT, seccion TEXT
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS archivo_concentracion (
                id INTEGER PRIMARY KEY AUTOINCREMENT, expediente_id INTEGER,
                fecha_ingreso DATE, ubicacion TEXT,
                FOREIGN KEY (expediente_id) REFERENCES expedientes (id)
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS historial (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT,
                accion TEXT,           -- Ej: CREAR, EDITAR, ELIMINAR, LOGIN
                descripcion TEXT,      -- Detalles: "Se eliminó expediente X"
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS lotes_transferencia (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                folio_lote TEXT UNIQUE NOT NULL,
                fecha_creacion DATE DEFAULT CURRENT_DATE,
                usuario_creador TEXT,
                entregado BOOLEAN DEFAULT 0,
                fecha_entrega DATE,
                archivo_inventario_pdf TEXT
            )
        ''')
        
        self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS lotes_valoracion (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    folio_lote TEXT UNIQUE,
                    tipo_propuesta TEXT,
                    fecha_creacion DATE,
                    usuario_creador TEXT,
                    estatus TEXT DEFAULT 'EN_VALORACION'
                )
            ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS destino_final (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                expediente_id INTEGER UNIQUE,
                tipo_destino TEXT,      -- 'BAJA DOCUMENTAL' o 'ARCHIVO HISTÓRICO'
                fecha_ejecucion DATE,
                acta_pdf TEXT,          -- Para guardar el acta de destrucción futura
                observaciones TEXT,
                FOREIGN KEY (expediente_id) REFERENCES expedientes (id)
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS prestamos_fisicos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expediente_id INTEGER NOT NULL,
                solicitante TEXT NOT NULL,
                area_solicitante TEXT,
                fecha_prestamo DATE NOT NULL,
                fecha_vencimiento DATE NOT NULL,
                fecha_devolucion DATE,
                estatus TEXT DEFAULT 'ACTIVO',
                observaciones TEXT,
                usuario_registro TEXT,
                FOREIGN KEY (expediente_id) REFERENCES expedientes (id)
            )
        ''')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_prestamos_estatus ON prestamos_fisicos (estatus)')
        
        try:
            self.cursor.execute("ALTER TABLE expedientes ADD COLUMN id_lote_transferencia INTEGER")
        except sqlite3.OperationalError:
            pass # La columna ya existe, no hacemos nada
        
        self.conn.commit()
        self._crear_usuario_admin_si_no_existe()
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_expedientes_asunto ON expedientes (asunto)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_expedientes_serie ON expedientes (serie_documental)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_expedientes_fecha ON expedientes (fecha)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_expedientes_vencimiento ON expedientes (vencimiento)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_expedientes_folio ON expedientes (folio)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_expedientes_categoria ON expedientes (categoria_documental)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_expedientes_apertura ON expedientes (apertura)')

        # Índices para la tabla 'respuestas' (usados en Búsqueda Avanzada)
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_respuestas_expediente_id ON respuestas (expediente_id)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_respuestas_asunto ON respuestas (asunto_respuesta)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_respuestas_fecha ON respuestas (fecha_respuesta)')

        # Índices para la tabla 'archivo_concentracion' (usados en la pestaña de Archivo)
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_concentracion_expediente_id ON archivo_concentracion (expediente_id)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_concentracion_fecha ON archivo_concentracion (fecha_ingreso)')
        
        # Índices para la tabla 'series_documentales' (usados en la pestaña de Consulta Series)
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_series_nombre ON series_documentales (nombre_serie)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_series_area ON series_documentales (area_administrativa)')
        
    
    def _crear_usuario_admin_si_no_existe(self):
        """Crea un usuario admin/admin solo si la tabla está vacía"""
        self.cursor.execute("SELECT COUNT(*) FROM usuarios")
        if self.cursor.fetchone()[0] == 0:
            # NOTA: En producción, usa hash para la contraseña. 
            # Aquí usamos texto plano para simplificar el ejemplo.
            self.cursor.execute("INSERT INTO usuarios (username, password) VALUES (?, ?)", 
                                ('admin', 'admin'))
            self.conn.commit()

    def validar_usuario(self, username, password):
        """Verifica si las credenciales son correctas"""
        query = "SELECT * FROM usuarios WHERE username = ? AND password = ?"
        # Si usas hashing, aquí deberías buscar el usuario y comparar el hash
        result = self.fetch_one(query, (username, password))
        return True if result else False
    
    def obtener_usuarios(self):
        """Obtiene la lista de todos los usuarios registrados."""
        query = "SELECT id, username FROM usuarios"
        return self.fetch_all(query)

    def crear_usuario(self, username, password):
        """Crea un nuevo usuario. Retorna (True, mensaje) o (False, error)."""
        try:
            # Verifica si ya existe
            query_check = "SELECT id FROM usuarios WHERE username = ?"
            if self.fetch_one(query_check, (username,)):
                return False, f"El usuario '{username}' ya existe."

            query_insert = "INSERT INTO usuarios (username, password) VALUES (?, ?)"
            self.execute_query(query_insert, (username, password))
            return True, "Usuario creado exitosamente."
        except Exception as e:
            return False, f"Error al crear usuario: {e}"

    def eliminar_usuario(self, usuario_id):
        """Elimina un usuario por ID (evitando borrar al admin principal si se desea)."""
        # Opcional: Evitar borrar al usuario 'admin' (id 1 usualmente)
        if usuario_id == 1: 
             return False, "No se puede eliminar al administrador principal."
             
        query = "DELETE FROM usuarios WHERE id = ?"
        if self.execute_query(query, (usuario_id,)):
            return True, "Usuario eliminado."
        return False, "No se pudo eliminar el usuario."
    
    def cambiar_password(self, usuario_id, nueva_password):
        """Actualiza la contraseña de un usuario específico."""
        try:
            query = "UPDATE usuarios SET password = ? WHERE id = ?"
            return self.execute_query(query, (nueva_password, usuario_id))
        except Exception as e:
            return False
    
    def registrar_accion(self, usuario, accion, descripcion):
        """Guarda un evento en el historial."""
        try:
            query = "INSERT INTO historial (usuario, accion, descripcion) VALUES (?, ?, ?)"
            self.cursor.execute(query, (usuario, accion, descripcion))
            self.conn.commit()
        except Exception as e:
            print(f"Error al guardar historial: {e}")
    
    def obtener_historial(self, limite=100):
        """Obtiene los últimos N eventos."""
        query = "SELECT * FROM historial ORDER BY fecha DESC LIMIT ?"
        return self.fetch_all(query, (limite,))
    
    def obtener_historial_filtrado(self, texto_a_buscar):
        """Busca eventos en el historial que contengan cierto texto (ej. un ID)."""
        query = "SELECT * FROM historial WHERE descripcion LIKE ? ORDER BY fecha DESC"
        search_term = f"%{texto_a_buscar}%"
        resultados_raw = self.fetch_all(query, (search_term,))
        match_id = re.search(r'ID\s+(\d+)', texto_a_buscar)
        
        if match_id:
            numero_id = match_id.group(1)
            resultados_filtrados = []
            patron = re.compile(f"ID {numero_id}(\\D|$)")
            
            for row in resultados_raw:
                desc = row['descripcion']
                if patron.search(desc):
                    resultados_filtrados.append(row)
                    
            return resultados_filtrados
        return resultados_raw
    
    def insertar_datos_iniciales(self):
        """
        Sincroniza los datos desde el archivo CSV a la base de datos.
        - Inserta series nuevas.
        - Actualiza las series existentes.
        - Borra las series que han sido eliminadas del CSV.
        """
        archivo_csv = get_series_data_csv_path()
        
        if not os.path.exists(archivo_csv):
            logging.warning(f"ADVERTENCIA: No se encontró el archivo '{archivo_csv}'.")
            return

        try:
            with open(archivo_csv, mode='r', encoding='latin-1') as f:
                lector_csv = csv.reader(f)
                encabezados = next(lector_csv)
                series_data = list(lector_csv)

            if series_data:
                columnas = ", ".join(encabezados)
                placeholders = ", ".join(["?"] * len(encabezados))
                update_clause = ", ".join([f"{col} = excluded.{col}" for col in encabezados if col != 'codigo_serie'])

                query_upsert = f'''
                    INSERT INTO series_documentales ({columnas})
                    VALUES ({placeholders})
                    ON CONFLICT(codigo_serie) DO UPDATE SET
                        {update_clause}
                '''
                
                for fila in series_data:
                    if not fila: continue
                    if len(fila) == len(encabezados):
                        self.cursor.execute(query_upsert, tuple(fila))

            logging.info("Iniciando fase de limpieza de series documentales obsoletas.")
            
            codigos_en_csv = {fila[0] for fila in series_data if fila}
            
            if not codigos_en_csv:
                logging.warning("El archivo CSV está vacío, no se realizará ninguna operación de borrado.")
                self.conn.commit()
                return

            placeholders_delete = ', '.join('?' for _ in codigos_en_csv)
            
            query_delete = f"DELETE FROM series_documentales WHERE codigo_serie NOT IN ({placeholders_delete})"
            
            self.cursor.execute(query_delete, tuple(codigos_en_csv))
            
            logging.info(f"{self.cursor.rowcount} series obsoletas eliminadas de la base de datos.")
            
            self.conn.commit()
            logging.info(f"Datos de series documentales sincronizados desde '{archivo_csv}' exitosamente.")

        except Exception as e:
            logging.error(f"Error crítico al sincronizar desde el archivo CSV '{archivo_csv}': {e}", exc_info=True)
            if self.conn:
                self.conn.rollback()
    
    def verificar_esquema(self):
        """Verifica y actualiza el esquema de la base de datos si es necesario."""
        try:
            self.cursor.execute("PRAGMA table_info(expedientes)")
            columnas = [col[1] for col in self.cursor.fetchall()]
            
            columnas_necesarias = [
                ('archivo_concentracion', 'INTEGER DEFAULT 0'),
                ('fecha_ingreso', 'TEXT'),
                ('ubicacion', 'TEXT')
            ]
            
            for col_name, col_type in columnas_necesarias:
                if col_name not in columnas:
                    self.cursor.execute(f"ALTER TABLE expedientes ADD COLUMN {col_name} {col_type}")
                    self.conn.commit()
            
            self.cursor.execute("PRAGMA table_info(series_documentales)")
            columnas_actuales = [info[1] for info in self.cursor.fetchall()]
            
            if 'descripcion_serie' not in columnas_actuales:
                self.cursor.execute("ALTER TABLE series_documentales ADD COLUMN descripcion_serie TEXT")
                logging.info("Columna 'descripcion_serie' añadida a la tabla 'series_documentales'.")
    
            if 'seccion' not in columnas_actuales:
                self.cursor.execute("ALTER TABLE series_documentales ADD COLUMN seccion TEXT")
                logging.info("Columna 'seccion' añadida a la tabla 'series_documentales'.")
            
            self.cursor.execute("PRAGMA table_info(archivo_concentracion)")
            columnas_conc = [col[1] for col in self.cursor.fetchall()]
            nuevas_cols = ['ubicacion_area', 'ubicacion_pasillo', 'ubicacion_anaquel', 'ubicacion_charola']
            for col in nuevas_cols:
                if col not in columnas_conc:
                    self.cursor.execute(f"ALTER TABLE archivo_concentracion ADD COLUMN {col} TEXT")
                    logging.info(f"Columna '{col}' añadida a archivo_concentracion.")
            
            self.cursor.execute("PRAGMA table_info(archivo_concentracion)")
            columnas_conc = [col[1] for col in self.cursor.fetchall()]
            if 'id_lote_valoracion' not in columnas_conc:
                self.cursor.execute("ALTER TABLE archivo_concentracion ADD COLUMN id_lote_valoracion INTEGER REFERENCES lotes_valoracion(id)")
                logging.info("Columna 'id_lote_valoracion' añadida a archivo_concentracion.")
        
            self.conn.commit()
            
        except sqlite3.Error as e:
            print(f"Error al verificar/actualizar el esquema: {e}")
            if self.conn:
                self.conn.rollback()
    
    def obtener_expedientes_paginados(self, pagina: int, por_pagina: int, texto_busqueda: str = None):
        offset = (pagina - 1) * por_pagina
        query = """
            SELECT *,
                   (SELECT 1 FROM prestamos_fisicos WHERE expediente_id = expedientes.id AND estatus = 'ACTIVO' LIMIT 1) AS esta_prestado
            FROM expedientes
        """
        params = []
        exclusion_query = "id NOT IN (SELECT expediente_id FROM archivo_concentracion) AND id NOT IN (SELECT expediente_id FROM destino_final)"

        if texto_busqueda:
            search_term = f'%{texto_busqueda}%'
            # 🚀 Ampliamos la consulta a 7 campos de texto en total
            query += f""" WHERE ({exclusion_query}) AND 
                          (folio LIKE ? 
                           OR asunto LIKE ? 
                           OR categoria_documental LIKE ? 
                           OR serie_documental LIKE ?
                           OR tipo_documento LIKE ?
                           OR carpeta LIKE ?
                           OR clasificacion LIKE ?)"""
            # Pasamos 7 parámetros iguales para sustituir cada signo '?'
            params.extend([search_term] * 7)
        else:
            query += f" WHERE {exclusion_query}"

        query += " ORDER BY id ASC LIMIT ? OFFSET ?"
        params.extend([por_pagina, offset])
        return self.fetch_all(query, tuple(params))
    
    def contar_expedientes(self, texto_busqueda: str = None) -> int:
       """
       Cuenta el total de expedientes activos (no en concentración) que coinciden
       con un texto de búsqueda opcional.
       """
       query = "SELECT COUNT(id) AS total FROM expedientes"
       params = []
       exclusion_query = "id NOT IN (SELECT expediente_id FROM archivo_concentracion) AND id NOT IN (SELECT expediente_id FROM destino_final)"
       
       if texto_busqueda:
           search_term = f'%{texto_busqueda}%'
           # 🚀 Ampliamos la consulta a los mismos 7 campos
           query += f""" WHERE ({exclusion_query}) AND 
                          (folio LIKE ? 
                           OR asunto LIKE ? 
                           OR categoria_documental LIKE ? 
                           OR serie_documental LIKE ?
                           OR tipo_documento LIKE ?
                           OR carpeta LIKE ?
                           OR clasificacion LIKE ?)"""
           params.extend([search_term] * 7)
       else:
           query += f" WHERE {exclusion_query}"
           
       result = self.fetch_one(query, tuple(params))
       
       return result['total'] if result else 0
    
    def get_next_expediente_number(self, serie_documental, year):
        query = 'SELECT COUNT(*) FROM expedientes WHERE serie_documental = ? AND strftime("%Y", fecha) = ?'
        result = self.fetch_one(query, (serie_documental, str(year)))
        return (result[0] if result else 0) + 1
   
    def get_series_documentales(self) -> List:
        """Obtiene todas las series documentales asegurando estabilidad multihilo."""
        if not self.conn: return []
        try:
            # Burbuja Aislada
            cursor_aislado = self.conn.cursor()
            query = "SELECT * FROM series_documentales ORDER BY codigo_serie"
            cursor_aislado.execute(query)
            resultados = cursor_aislado.fetchall()
            return resultados
        except sqlite3.Error as e:
            import logging
            logging.error(f"Error al obtener series: {e}")
            return []
    
    def insert_expediente(self, data: dict) -> int:
        """
        Inserta un nuevo expediente con los datos iniciales (11 columnas)
        y devuelve su nuevo ID.
        """
        query = '''
            INSERT INTO expedientes (
                tipo_documento, categoria_documental, folio, fecha,
                asunto, serie_documental, carpeta, paginas, documento_respaldo,
                clasificacion, apertura
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        params = (
            data.get('tipo_documento'), data.get('categoria_documental'),
            data.get('folio'), data.get('fecha'), data.get('asunto'),
            data.get('serie_documental'), data.get('carpeta'),
            data.get('paginas'), data.get('documento_respaldo'),
            data.get('clasificacion'), data.get('apertura')
        )
        try:
            self.cursor.execute(query, params)
            self.conn.commit()
            return self.cursor.lastrowid # Devuelve el ID del registro recién creado.
        except sqlite3.Error as e:
            logging.error(f"Error al insertar expediente: {e}", exc_info=True)
            if self.conn: self.conn.rollback()
            return None

    def update_expediente(self, data: dict, expediente_id: int):
        try:
            existing = self.get_expediente(expediente_id)
            if not existing:
                return False, "Expediente no encontrado"

            existing_row = dict(existing[0])
            
            new_fecha = data.get('fecha', '')
            if existing_row.get('fecha') and new_fecha:
                current_year = existing_row['fecha'].split('-')[0]
                new_year = new_fecha.split('-')[0]
                if current_year != new_year:
                    return False, "No se puede cambiar el año de la fecha."

            tipo_documento = data.get('tipo_documento', '')
            serie_documental = data.get('serie_documental', '')
            # La clasificación no se recalcula en una actualización para mantener el número original
            clasificacion = existing_row.get('clasificacion', '')

            # Lógica para manejar el caso especial "Conocimiento"
            if tipo_documento == "Conocimiento":
                serie_documental = "Conocimiento"
                clasificacion = "" # Los expedientes de conocimiento no tienen clasificación

            query = '''
                UPDATE expedientes SET
                    tipo_documento = ?, categoria_documental = ?, folio = ?, fecha = ?,
                    asunto = ?, serie_documental = ?, carpeta = ?, paginas = ?,
                    documento_respaldo = ?, clasificacion = ?
                WHERE id = ?
            '''
            values = (
                tipo_documento,
                data.get('categoria_documental', ''),
                data.get('folio', ''),
                new_fecha,
                data.get('asunto', ''),
                serie_documental,
                data.get('carpeta', ''),
                data.get('paginas', 0),
                data.get('documento_respaldo', ''),
                clasificacion,
                expediente_id
            )
            
            if self.execute_query(query, values):
                return True, "Expediente actualizado correctamente"
            else:
                return False, "Error al ejecutar la actualización en la base de datos"

        except Exception as e:
            return False, f"Error inesperado: {str(e)}"
    
    def get_expedientes(self, filtros: dict = None) -> List:
        """
        Obtiene expedientes filtrados, uniendo la información de la serie documental.
        """
        query = """
            SELECT 
                e.*,
                s.nombre_serie,s.administrativo, s.legal, s.fiscal,
                s.tramite, s.concentracion, s.total,
                s.publica, s.reservada, s.confidencial,
                s.original, s.copia,
                s.seccion,
                COALESCE(CAST(julianday(e.vencimiento) - julianday('now') AS INTEGER), NULL) as dias_vencido
            FROM expedientes e
            LEFT JOIN series_documentales s ON e.serie_documental = s.codigo_serie
            WHERE 1=1
        """
        params = []
        
        if filtros:
            if filtros.get('fecha_inicio') and filtros.get('fecha_fin'):
                query += " AND e.fecha BETWEEN ? AND ?"
                params.extend([filtros['fecha_inicio'], filtros['fecha_fin']])
            
            if filtros.get('serie_documental') and filtros.get('serie_documental') != "Todas":
                query += " AND e.serie_documental = ?"
                params.append(filtros['serie_documental'])
                
            if filtros.get('categoria_documental') and filtros.get('categoria_documental') != "Todas":
                query += " AND e.categoria_documental = ?"
                params.append(filtros['categoria_documental'])

            estado = filtros.get('estado')
            if estado and estado != "Todos":
                if estado == "Abierto":
                    query += " AND (e.cierre IS NULL OR e.cierre = '')"
                elif estado == "Cerrado":
                    query += " AND (e.cierre IS NOT NULL AND e.cierre != '') AND (e.vencimiento IS NULL OR e.vencimiento = '' OR DATE(e.vencimiento) >= DATE('now'))"
                elif estado == "Vencido":
                    query += " AND (e.vencimiento IS NOT NULL AND e.vencimiento != '' AND DATE(e.vencimiento) < DATE('now'))"

        query += " ORDER BY e.id ASC"
        return self.fetch_all(query, tuple(params))

    def get_expediente(self, expediente_id):
        query = 'SELECT * FROM expedientes WHERE id = ?'
        return self.fetch_all(query, (expediente_id,))
    
    def begin_transaction(self):
        """Inicia una transacción."""
        if self.conn:
            self.cursor.execute('BEGIN')

    def commit_transaction(self):
        """Confirma los cambios de la transacción actual."""
        if self.conn:
            self.conn.commit()

    def rollback_transaction(self):
        """Revierte los cambios de la transacción actual."""
        if self.conn:
            self.conn.rollback()
    
    def get_document_path(self, expediente_id: int) -> str:
        """Obtiene la ruta del documento de respaldo de un expediente."""
        query = "SELECT documento_respaldo FROM expedientes WHERE id = ?"
        result = self.fetch_one(query, (expediente_id,))
        return result['documento_respaldo'] if result and result['documento_respaldo'] else None
    
    def get_response_document_path(self, respuesta_id: int) -> str:
        """Obtiene la ruta del documento de una respuesta específica."""
        query = "SELECT documento_respuesta FROM respuestas WHERE id = ?"
        result = self.fetch_one(query, (respuesta_id,))
        return result['documento_respuesta'] if result and result['documento_respuesta'] else None
    
    def get_serie_documental(self, codigo_serie: str) -> List:
        """Obtiene los detalles de una serie documental específica por su código."""
        query = "SELECT * FROM series_documentales WHERE codigo_serie = ?"
        return self.fetch_all(query, (codigo_serie,))

    def get_vencidos(self):
        query = '''
            SELECT * FROM expedientes
            WHERE vencimiento IS NOT NULL AND vencimiento <= ?
            ORDER BY vencimiento
        '''
        return self.fetch_all(query, (datetime.now().strftime('%d-%m-%Y'),))

    def insert_respuesta(self, data: Dict) -> int:
        """Inserta una nueva respuesta y devuelve su ID."""
        query = '''
            INSERT INTO respuestas (
                expediente_id, tipo_documento, categoria_documental, folio,
                fecha_respuesta, asunto_respuesta, paginas, documento_respuesta
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        '''
        values = (
            data.get('expediente_id'),
            data.get('tipo_documento'),
            data.get('categoria_documental'),
            data.get('folio'),
            data.get('fecha_respuesta'),
            data.get('asunto_respuesta'),
            data.get('paginas'),
            data.get('documento_respuesta'),
        )
        try:
            self.cursor.execute(query, values)
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.Error as e:
            logging.error("Error en insert_respuesta: %s", e, exc_info=True)
            self.conn.rollback()
            return None

    def get_respuestas(self, expediente_id: int):
        query = """
            SELECT
                r.id, r.expediente_id, r.tipo_documento, r.categoria_documental,
                r.folio, r.fecha_respuesta, r.asunto_respuesta, r.paginas,
                r.documento_respuesta,
                e.serie_documental, 
                e.carpeta
            FROM respuestas r
            JOIN expedientes e ON r.expediente_id = e.id
            WHERE r.expediente_id = ?
            ORDER BY r.fecha_respuesta DESC
        """
        return self.fetch_all(query, (expediente_id,))
    
    def get_fecha_ultima_respuesta(self, expediente_id: int):
        """Obtiene la fecha de la última respuesta (la más reciente) para un expediente."""
        query = "SELECT MAX(fecha_respuesta) AS fecha_maxima FROM respuestas WHERE expediente_id = ?"
        result = self.fetch_one(query, (expediente_id,))
        
        return result['fecha_maxima'] if result and result['fecha_maxima'] else None

    def delete_respuesta(self, respuesta_id: int):
        query = 'DELETE FROM respuestas WHERE id = ?'
        return self.execute_query(query, (respuesta_id,))

    def get_respuestas_avanzada(self, filtros: dict = None, pagina: int = 1, por_pagina: int = 50) -> List:
        """
        Obtiene respuestas filtradas para la búsqueda avanzada con paginación.
        """
        offset = (pagina - 1) * por_pagina
        
        query = """
            SELECT
                r.expediente_id, r.id, r.tipo_documento, r.categoria_documental,
                r.folio, r.fecha_respuesta, r.asunto_respuesta, e.serie_documental,
                e.carpeta, r.paginas, r.documento_respuesta, e.clasificacion,
                e.apertura, e.cierre, e.vencimiento
            FROM respuestas r
            JOIN expedientes e ON r.expediente_id = e.id
        """
        params = []
        where_clauses = ["e.id NOT IN (SELECT expediente_id FROM archivo_concentracion) AND e.id NOT IN (SELECT expediente_id FROM destino_final)"]
        
        if filtros:
            if filtros.get('texto'):
                search_term = f"%{filtros['texto']}%"
                where_clauses.append("(r.asunto_respuesta LIKE ? OR r.folio LIKE ?)")
                params.extend([search_term, search_term])
            
            if filtros.get('categoria_documental'):
                where_clauses.append("r.categoria_documental = ?")
                params.append(filtros['categoria_documental'])

            if filtros.get('fecha_inicio') and filtros.get('fecha_fin'):
                where_clauses.append("r.fecha_respuesta BETWEEN ? AND ?")
                params.extend([filtros['fecha_inicio'], filtros['fecha_fin']])

            if filtros.get('serie_documental'):
                where_clauses.append("e.serie_documental = ?")
                params.append(filtros['serie_documental'])
                
            if filtros.get('apertura'):
                where_clauses.append("e.apertura = ?")
                params.append(filtros['apertura'])
        
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        query += " ORDER BY r.id ASC LIMIT ? OFFSET ?"
        params.extend([por_pagina, offset])
        
        return self.fetch_all(query, tuple(params))
    
    def contar_respuestas_avanzada(self, filtros: dict = None) -> int:
        """Cuenta el total de resultados para la búsqueda avanzada."""
        query = "SELECT COUNT(r.id) AS total FROM respuestas r JOIN expedientes e ON r.expediente_id = e.id"
        params = []
        where_clauses = ["e.id NOT IN (SELECT expediente_id FROM archivo_concentracion) AND e.id NOT IN (SELECT expediente_id FROM destino_final)"]
        
        if filtros:
            if filtros.get('texto'):
                search_term = f"%{filtros['texto']}%"
                where_clauses.append("(r.asunto_respuesta LIKE ? OR r.folio LIKE ?)")
                params.extend([search_term, search_term])
            
            if filtros.get('categoria_documental'):
                where_clauses.append("r.categoria_documental = ?")
                params.append(filtros['categoria_documental'])

            if filtros.get('fecha_inicio') and filtros.get('fecha_fin'):
                where_clauses.append("r.fecha_respuesta BETWEEN ? AND ?")
                params.extend([filtros['fecha_inicio'], filtros['fecha_fin']])

            if filtros.get('serie_documental'):
                where_clauses.append("e.serie_documental = ?")
                params.append(filtros['serie_documental'])
                
            if filtros.get('apertura'):
                where_clauses.append("e.apertura = ?")
                params.append(filtros['apertura'])

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
            
        result = self.fetch_one(query, tuple(params))
        
        return result['total'] if result else 0

    def get_respuesta(self, respuesta_id):
        query = '''
            SELECT * FROM respuestas
            WHERE id = ?
        '''
        return self.fetch_all(query, (respuesta_id,))

    def update_respuesta(self, respuesta_id: int, data: dict):
        query = '''
            UPDATE respuestas SET
                categoria_documental = ?, folio = ?, fecha_respuesta = ?,
                asunto_respuesta = ?, paginas = ?, documento_respuesta = ?
            WHERE id = ?
        '''
        values = (
            data.get('categoria_documental', ''),
            data.get('folio', ''),
            data.get('fecha_respuesta', ''),
            data.get('asunto_respuesta', ''),
            data.get('paginas', 0),
            data.get('documento_respuesta', ''),
            respuesta_id
        )
        return self.execute_query(query, values)
    
    def delete_expediente(self, expediente_id: int):
        """
        Ejecuta las sentencias DELETE para un expediente.
        La transacción debe ser manejada por la capa de servicio.
        """
        self.cursor.execute('DELETE FROM respuestas WHERE expediente_id = ?', (expediente_id,))
        self.cursor.execute('DELETE FROM archivo_concentracion WHERE expediente_id = ?', (expediente_id,))
        self.cursor.execute('DELETE FROM expedientes WHERE id = ?', (expediente_id,))
        return True

    def actualizar_cierre_y_vencimiento(self, expediente_id: int, cierre: int, vencimiento: str):
        """Actualiza los campos de cierre y vencimiento de un expediente."""
        query = "UPDATE expedientes SET cierre = ?, vencimiento = ? WHERE id = ?"
        return self.execute_query(query, (cierre, vencimiento, expediente_id))

    def cancelar_cierre_expediente(self, expediente_id):
        try:
            query = '''
                UPDATE expedientes SET
                    cierre = ?, vencimiento = ?
                WHERE id = ?
            '''
            values = ("", "", expediente_id,)
            
            if self.execute_query(query, values):
                return True, "Cierre cancelado correctamente"
            else:
                return False, "Error al cancelar el cierre"
        except Exception as e:
            return False, f"Error inesperado: {str(e)}"

    def is_expediente_cerrado(self, expediente_id):
        """
        Verifica si un expediente tiene una fecha de cierre válida.
        """
        try:
            query = "SELECT cierre FROM expedientes WHERE id = ?"
            result = self.fetch_one(query, (expediente_id,))
            if result and result['cierre']:
                    return True
            else:
                return False
                
        except Exception as e:
            logging.error(f"Error al verificar cierre del expediente {expediente_id}: {e}", exc_info=True)
            return False
    
    def get_respuestas_para_reporte(self, filtros: dict = None) -> List:
        """
        Obtiene TODAS las respuestas filtradas para un reporte, sin paginación.
        """
        query = """
            SELECT
                r.id, r.expediente_id, r.tipo_documento, r.categoria_documental,
                r.folio, r.fecha_respuesta, r.asunto_respuesta, e.serie_documental,
                e.carpeta, r.paginas, r.documento_respuesta, e.clasificacion,
                e.apertura, e.cierre, e.vencimiento,
                COALESCE(CAST(julianday(e.vencimiento) - julianday('now') AS INTEGER), NULL) as dias_vencido
            FROM respuestas r
            JOIN expedientes e ON r.expediente_id = e.id
        """
        params = []
        where_clauses = []
        
        if filtros:
            # (Aquí se aplican los mismos filtros que en la búsqueda avanzada)
            if filtros.get('fecha_inicio') and filtros.get('fecha_fin'):
                where_clauses.append("r.fecha_respuesta BETWEEN ? AND ?")
                params.extend([filtros['fecha_inicio'], filtros['fecha_fin']])
            
            if filtros.get('serie_documental') and filtros.get('serie_documental') != "Todas":
                where_clauses.append("e.serie_documental = ?")
                params.append(filtros['serie_documental'])
                
            if filtros.get('categoria_documental') and filtros.get('categoria_documental') != "Todas":
                where_clauses.append("r.categoria_documental = ?")
                params.append(filtros['categoria_documental'])
        
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        query += " ORDER BY r.id ASC"
        return self.fetch_all(query, tuple(params))
    
    def get_expedientes_vencidos_para_archivado(self, filtros: dict = None) -> List:
        query = """
            SELECT 
                e.id, e.tipo_documento, e.categoria_documental, e.folio, e.fecha, 
                e.asunto, e.serie_documental, e.carpeta, e.paginas, 
                e.documento_respaldo, e.clasificacion, e.apertura, e.cierre, 
                e.vencimiento,
                CAST(julianday('now') - julianday(e.vencimiento) AS INTEGER) as dias_vencido
            FROM expedientes e
            WHERE e.vencimiento IS NOT NULL AND e.vencimiento != ''
              AND DATE(e.vencimiento) < DATE('now')
              AND e.id NOT IN (SELECT expediente_id FROM archivo_concentracion)
              AND e.id NOT IN (SELECT expediente_id FROM destino_final) -- <--- IGNORA LOS DESTRUIDOS/HISTÓRICOS
              AND e.id_lote_transferencia IS NULL
        """
        params = []
        
        if filtros:
            if filtros.get('texto_busqueda'):
                query += " AND (e.asunto LIKE ? OR e.folio LIKE ?)"
                params.extend([f"%{filtros['texto_busqueda']}%", f"%{filtros['texto_busqueda']}%"])
            
            if filtros.get('categoria') and filtros.get('categoria') != "":
                query += " AND e.categoria_documental = ?"
                params.append(filtros['categoria'])
            
            if filtros.get('serie') and filtros.get('serie') != "":
                query += " AND e.serie_documental = ?"
                params.append(filtros['serie'])

            if filtros.get('anio') and filtros.get('anio') != "":
                query += " AND strftime('%Y', e.vencimiento) = ?"
                params.append(filtros['anio'])

            if filtros.get('fecha_inicio') and filtros.get('fecha_fin'):
                query += " AND e.vencimiento BETWEEN ? AND ?"
                params.extend([filtros['fecha_inicio'], filtros['fecha_fin']])

        query += " ORDER BY e.id ASC"
        return self.fetch_all(query, tuple(params))

    def agregar_a_concentracion(self, expediente_id: int, ubi: dict) -> bool:
        query = '''INSERT INTO archivo_concentracion 
                   (expediente_id, fecha_ingreso, ubicacion_area, ubicacion_pasillo, ubicacion_anaquel, ubicacion_charola) 
                   VALUES (?, DATE('now'), ?, ?, ?, ?)'''
        return self.execute_query(query, (expediente_id, ubi.get('area',''), ubi.get('pasillo',''), ubi.get('anaquel',''), ubi.get('charola','')))

    def get_expedientes_en_concentracion(self, filtros: dict = None) -> List:
        query = """
            SELECT 
                e.id, e.tipo_documento, e.categoria_documental, e.folio, e.fecha, 
                e.asunto, e.serie_documental, e.carpeta, e.paginas, 
                e.documento_respaldo, e.clasificacion, e.apertura, e.cierre, e.vencimiento,
                ac.fecha_ingreso, 
                lt.folio_lote AS lote_origen,
                ac.ubicacion_area, ac.ubicacion_pasillo, ac.ubicacion_anaquel, ac.ubicacion_charola,
                CAST(julianday(ac.fecha_ingreso, '+' || s.concentracion || ' Year') - julianday('now') AS INTEGER) as dias_para_baja,
                
                -- NUEVA COLUMNA INVISIBLE:
                (SELECT 1 FROM prestamos_fisicos WHERE expediente_id = e.id AND estatus = 'ACTIVO' LIMIT 1) AS esta_prestado
                
            FROM archivo_concentracion ac
            JOIN expedientes e ON ac.expediente_id = e.id
            LEFT JOIN series_documentales s ON e.serie_documental = s.codigo_serie
            LEFT JOIN lotes_transferencia lt ON e.id_lote_transferencia = lt.id
            WHERE 1=1 AND ac.id_lote_valoracion IS NULL
        """
        params = []
        if filtros:
            if filtros.get('texto_busqueda'):
                search_term = f"%{filtros['texto_busqueda']}%"
                # <--- NUEVA BÚSQUEDA CRUZADA --->
                query += " AND (e.asunto LIKE ? OR e.folio LIKE ? OR ac.ubicacion_area LIKE ? OR ac.ubicacion_pasillo LIKE ?)"
                params.extend([search_term, search_term, search_term, search_term])
            
            if filtros.get('categoria') and filtros.get('categoria') != "":
                query += " AND e.categoria_documental = ?"
                params.append(filtros['categoria'])
            
            if filtros.get('serie') and filtros.get('serie') != "":
                query += " AND e.serie_documental = ?"
                params.append(filtros['serie'])
            
            if filtros.get('anio') and filtros.get('anio') != "":
                query += " AND e.apertura = ?"
                params.append(filtros['anio'])

            if filtros.get('fecha_inicio') and filtros.get('fecha_fin'):
                query += " AND ac.fecha_ingreso BETWEEN ? AND ?"
                params.extend([filtros['fecha_inicio'], filtros['fecha_fin']])

        query += " ORDER BY e.id ASC"
        return self.fetch_all(query, tuple(params))
    
    def restaurar_de_concentracion(self, expediente_id: int) -> bool:
        """
        Saca el expediente de concentración y le quita la etiqueta del lote,
        conservando intactas sus fechas de cierre y vencimiento originales.
        """
        try:
            self.cursor.execute("DELETE FROM archivo_concentracion WHERE expediente_id = ?", (expediente_id,))
            
            self.cursor.execute('''
                UPDATE expedientes 
                SET id_lote_transferencia = NULL
                WHERE id = ?
            ''', (expediente_id,))
            
            self.conn.commit()
            return True
            
        except sqlite3.Error as e:
            import logging
            logging.error(f"Error al restaurar expediente {expediente_id}: {e}")
            self.conn.rollback() # Deshacemos en caso de error
            return False
        
    def get_series_documentales_filtradas(self, filtros: dict = None) -> List:
        """Busca y filtra en la tabla de series documentales."""
        query = "SELECT * FROM series_documentales WHERE 1=1"
        params = []
        
        if filtros:

            if filtros.get('codigo') and filtros.get('codigo') != "Todas":
                query += " AND codigo_serie LIKE ?"
                params.append(f"%{filtros['codigo']}%")
            
            if filtros.get('nombre'):
                query += " AND nombre_serie LIKE ?"
                params.append(f"%{filtros['nombre']}%")
                
            if filtros.get('area'):
                query += " AND area_administrativa LIKE ?"
                params.append(f"%{filtros['area']}%")
        
        query += " ORDER BY codigo_serie ASC"
        return self.fetch_all(query, tuple(params))
    
    def get_serie_by_codigo(self, codigo_serie: str):
       """Obtiene todos los datos de una serie documental por su código."""
       query = "SELECT * FROM series_documentales WHERE codigo_serie = ?"
       return self.fetch_one(query, (codigo_serie,))
    
    def get_all_closed_expedientes_ids(self):
       """Devuelve una lista de IDs de todos los expedientes que ya están cerrados."""
       query = "SELECT id FROM expedientes WHERE cierre IS NOT NULL AND cierre != ''"
       results = self.fetch_all(query)
       return [row['id'] for row in results]
   
    def buscar_expediente_conocimiento_por_anio(self, anio: int):
        """Busca un expediente maestro de 'Conocimiento' por año. AÑADIDO."""
        query = "SELECT * FROM expedientes WHERE tipo_documento = 'Conocimiento' AND apertura = ? LIMIT 1"
        return self.fetch_one(query, (anio,))
    
    def get_total_paginas_respuestas(self, expediente_id: int) -> int:
        """Suma las páginas de todas las respuestas de un expediente."""
        query = "SELECT SUM(paginas) as total FROM respuestas WHERE expediente_id = ?"
        result = self.fetch_one(query, (expediente_id,))
        return result['total'] if result and result['total'] else 0
    
    # --- MÉTODOS PARA CONTROL DE GESTIÓN ---
    def insert_control_gestion(self, data: Dict) -> int:
        query = '''
            INSERT INTO control_gestion (
                origen, folio, fecha, turnado_a, remitente, area, referencia, fecha_documento,
                asunto, prioridad, fecha_limite, tipo_instruccion, detalle_instruccion,
                observaciones, documentos_anexos, requiere_respuesta, recibio, ccp, archivado
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        values = (
            data.get('origen'), data.get('folio'), data.get('fecha'), data.get('turnado_a'), data.get('remitente'),
            data.get('area'), data.get('referencia'), data.get('fecha_documento'),
            data.get('asunto'), data.get('prioridad'), data.get('fecha_limite'),
            data.get('tipo_instruccion'), data.get('detalle_instruccion'),
            data.get('observaciones'), data.get('documentos_anexos'),
            data.get('requiere_respuesta'), data.get('recibio'), data.get('ccp'),
            data.get('archivado')
        )
        try:
            self.cursor.execute(query, values)
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.Error as e:
            logging.error(f"Error insertando en control_gestion: {e}")
            return None

    def update_control_gestion(self, cg_id: int, data: Dict) -> bool:
        query = '''
            UPDATE control_gestion SET
                origen=?, folio=?, fecha=?, turnado_a=?, remitente=?, area=?, referencia=?, fecha_documento=?,
                asunto=?, prioridad=?, fecha_limite=?, tipo_instruccion=?, detalle_instruccion=?,
                observaciones=?, documentos_anexos=?, requiere_respuesta=?, recibio=?, ccp=?, archivado=?
            WHERE id=?
        '''
        values = (
            data.get('origen'), data.get('folio'), data.get('fecha'), data.get('turnado_a'), data.get('remitente'),
            data.get('area'), data.get('referencia'), data.get('fecha_documento'),
            data.get('asunto'), data.get('prioridad'), data.get('fecha_limite'),
            data.get('tipo_instruccion'), data.get('detalle_instruccion'),
            data.get('observaciones'), data.get('documentos_anexos'),
            data.get('requiere_respuesta'), data.get('recibio'), data.get('ccp'),
            data.get('archivado'), cg_id
        )
        return self.execute_query(query, values)

    def get_all_control_gestion(self, filtro_texto=None):
        query = "SELECT * FROM control_gestion"
        params = []
        if filtro_texto:
            query += " WHERE folio LIKE ? OR asunto LIKE ? OR remitente LIKE ?"
            term = f"%{filtro_texto}%"
            params = [term, term, term]
        
        query += " ORDER BY id DESC"
        return self.fetch_all(query, tuple(params))

    def get_control_gestion_by_id(self, cg_id):
        return self.fetch_one("SELECT * FROM control_gestion WHERE id = ?", (cg_id,))

    def delete_control_gestion(self, cg_id):
        return self.execute_query("DELETE FROM control_gestion WHERE id = ?", (cg_id,))
    
    def contar_control_gestion_filtrado(self, filtros: dict = None) -> int:
        """Cuenta el total de registros que coinciden con los filtros (para el paginador)."""
        query = "SELECT COUNT(id) as total FROM control_gestion WHERE 1=1"
        params = []
        
        if filtros:
            # 1. Filtro Texto (Cubre la función del método antiguo)
            if filtros.get('texto'):
                texto = f"%{filtros['texto']}%"
                query += " AND (folio LIKE ? OR asunto LIKE ? OR remitente LIKE ?)"
                params.extend([texto, texto, texto])
            
            # 2. Filtro Origen
            if filtros.get('origen') and filtros['origen'] != "Todos":
                query += " AND origen = ?"
                params.append(filtros['origen'])

            # 3. Filtro Estatus
            if filtros.get('estatus') and filtros['estatus'] != "Todos":
                if filtros['estatus'] == "PENDIENTE":
                    query += " AND (archivado IS NULL OR archivado = '' OR (archivado != 'CONCLUIDO' AND archivado != 'CANCELADO'))"
                else:
                    query += " AND archivado = ?"
                    params.append(filtros['estatus'])

            # 4. Filtro Año
            if filtros.get('anio') and filtros['anio'] != "Todos":
                query += " AND strftime('%Y', fecha) = ?"
                params.append(filtros['anio'])
        
        result = self.fetch_one(query, tuple(params))
        return result['total'] if result else 0

    def obtener_control_gestion_paginado(self, pagina: int, por_pagina: int, filtros: dict = None):
        """
        Obtiene una página de registros aplicando múltiples filtros (Año, Origen, Estatus, Texto).
        """
        offset = (pagina - 1) * por_pagina
        
        # Consulta base
        query = "SELECT * FROM control_gestion WHERE 1=1"
        params = []
        
        # Aplicamos filtros dinámicos si existen
        if filtros:
            # 1. Filtro de Texto (Busca en Folio, Asunto, Remitente)
            if filtros.get('texto'):
                texto = f"%{filtros['texto']}%"
                query += " AND (folio LIKE ? OR asunto LIKE ? OR remitente LIKE ?)"
                params.extend([texto, texto, texto])
            
            # 2. Filtro de Origen
            if filtros.get('origen') and filtros['origen'] != "Todos":
                query += " AND origen = ?"
                params.append(filtros['origen'])
            
            # 3. Filtro de Estatus (Archivado)
            if filtros.get('estatus') and filtros['estatus'] != "Todos":
                if filtros['estatus'] == "PENDIENTE":
                    # Pendiente es cuando NO está concluido ni cancelado
                    query += " AND (archivado IS NULL OR archivado = '' OR (archivado != 'CONCLUIDO' AND archivado != 'CANCELADO'))"
                else:
                    query += " AND archivado = ?"
                    params.append(filtros['estatus'])

            # 4. Filtro de Año (usando SQLite strftime)
            if filtros.get('anio') and filtros['anio'] != "Todos":
                query += " AND strftime('%Y', fecha) = ?"
                params.append(filtros['anio'])
        
        query += " ORDER BY id ASC LIMIT ? OFFSET ?"
        params.extend([por_pagina, offset])
        
        return self.fetch_all(query, tuple(params))
    
    def verificar_existencia_cg(self, folio: str) -> bool:
        """Verifica si ya existe un registro de control de gestión con el folio dado."""
        if not folio: return False
        try:
            # Nota: No usamos self.mutex aquí porque SQLite maneja la concurrencia básica
            query = "SELECT COUNT(*) FROM control_gestion WHERE folio = ?"
            self.cursor.execute(query, (folio,))
            count = self.cursor.fetchone()[0]
            return count > 0
        except Exception as e:
            logging.error(f"Error al verificar existencia CG: {e}")
            return False
    
    def obtener_datos_dashboard(self) -> Dict:
        """
        Obtiene estadísticas separadas:
        - Control de Gestión (Prioridad)
        - Expedientes (Secundario)
        """
        stats = {
            # Sección Gestión
            'cg_pendientes': 0,
            'cg_urgentes': 0,
            'cg_recibidos_mes': 0,
            'grafica_cg_estatus': {},
            'grafica_cg_areas': {},
            
            # Sección Expedientes
            'exp_activos': 0,
            'exp_por_vencer': 0,
            'exp_total_anio': 0
        }
        
        try:
            # =========================================
            # 1. INDICADORES DE CONTROL DE GESTIÓN
            # =========================================
            
            # A) Pendientes (Todo lo que no sea CONCLUIDO)
            query_pendientes = """
                SELECT COUNT(*) FROM control_gestion 
                WHERE archivado IS NULL 
                   OR archivado = '' 
                   OR (UPPER(archivado) NOT LIKE '%CONCLUIDO%' AND UPPER(archivado) NOT LIKE '%ARCHIVADO%')
            """
            stats['cg_pendientes'] = self.conn.execute(query_pendientes).fetchone()[0]
            
            # B) Urgentes (Prioridad Alta y Pendientes)
            query_urgentes = """
                SELECT COUNT(*) FROM control_gestion 
                WHERE UPPER(prioridad) LIKE '%URGENTE%' 
                  AND (archivado IS NULL OR UPPER(archivado) NOT LIKE '%CONCLUIDO%')
            """
            stats['cg_urgentes'] = self.conn.execute(query_urgentes).fetchone()[0]
            
            # C) Recibidos este Mes (Carga de trabajo reciente)
            mes_actual = datetime.now().strftime('%Y-%m')
            query_mes = f"SELECT COUNT(*) FROM control_gestion WHERE strftime('%Y-%m', fecha) = '{mes_actual}'"
            stats['cg_recibidos_mes'] = self.conn.execute(query_mes).fetchone()[0]

            # D) Gráfica Pastel: Estatus Global
            query_graf_estatus = """
                SELECT 
                    CASE WHEN archivado IS NULL OR archivado = '' THEN 'PENDIENTE' ELSE UPPER(archivado) END,
                    COUNT(*) 
                FROM control_gestion 
                GROUP BY 1
            """
            for row in self.conn.execute(query_graf_estatus).fetchall():
                stats['grafica_cg_estatus'][row[0]] = row[1]

            # E) Gráfica Barras: Carga Pendiente por Área (Top 5)
            query_graf_personas = """
                SELECT turnado_a, COUNT(*) 
                FROM control_gestion 
                WHERE (archivado IS NULL OR UPPER(archivado) NOT LIKE '%CONCLUIDO%')
                GROUP BY turnado_a 
                ORDER BY COUNT(*) DESC 
                LIMIT 5
            """
            for row in self.conn.execute(query_graf_personas).fetchall():
                persona = row[0] if row[0] else "SIN ASIGNAR"
                
                # LIMPIEZA DE NOMBRE:
                # A veces el excel trae "NOMBRE \n CARGO". Nos quedamos solo con el nombre (lo de antes del salto de línea)
                if '\n' in persona:
                    persona = persona.split('\n')[0]
                
                persona = persona.strip()
                
                # Acortar nombre si sigue siendo muy largo
                if len(persona) > 20:
                    persona = persona[:18] + ".."
                
                # Guardamos en la misma clave 'grafica_cg_areas' para no romper el widget, 
                # aunque ahora son personas.
                stats['grafica_cg_areas'][persona] = row[1]

            # =========================================
            # 2. INDICADORES DE EXPEDIENTES
            # =========================================
            
            # A) Expedientes Activos (Sin fecha de cierre)
            query_activos = "SELECT COUNT(*) FROM expedientes WHERE cierre IS NULL OR cierre = ''"
            stats['exp_activos'] = self.conn.execute(query_activos).fetchone()[0]
            
            # B) Por Vencer (Próximos 7 días)
            fecha_hoy = datetime.now().strftime('%Y-%m-%d')
            fecha_limite = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
            query_vencer = f"""
                SELECT COUNT(*) FROM expedientes 
                WHERE vencimiento BETWEEN '{fecha_hoy}' AND '{fecha_limite}' 
                AND (cierre IS NULL OR cierre = '')
            """
            stats['exp_por_vencer'] = self.conn.execute(query_vencer).fetchone()[0]
            
            # C) Total Aperturados este Año
            anio_actual = datetime.now().year
            query_anio = f"SELECT COUNT(*) FROM expedientes WHERE apertura = '{anio_actual}'"
            stats['exp_total_anio'] = self.conn.execute(query_anio).fetchone()[0]

        except Exception as e:
            logging.error(f"Error calculando dashboard: {e}")
        
        return stats
    
    def obtener_reporte_por_rango(self, f_inicio_str, f_fin_str):
        """
        Calcula estadísticas basado en un rango seleccionado por el usuario.
        Calcula automáticamente el periodo anterior para comparar.
        """
        from datetime import datetime, timedelta

        # Convertir strings a objetos fecha para calcular la diferencia
        fmt = '%Y-%m-%d'
        dt_inicio = datetime.strptime(f_inicio_str, fmt)
        dt_fin = datetime.strptime(f_fin_str, fmt)

        # 1. Calcular duración del periodo seleccionado
        delta = dt_fin - dt_inicio
        dias_duracion = delta.days + 1 # +1 para incluir el día final

        # 2. Calcular el periodo ANTERIOR (Misma duración, justo antes del inicio)
        dt_fin_ant = dt_inicio - timedelta(days=1)
        dt_inicio_ant = dt_fin_ant - timedelta(days=dias_duracion - 1)

        f_inicio_ant = dt_inicio_ant.strftime(fmt)
        f_fin_ant = dt_fin_ant.strftime(fmt)

        # Formato bonito para mostrar en el texto (DD/MM/YYYY)
        texto_actual = f"Del {dt_inicio.strftime('%d/%m/%Y')} al {dt_fin.strftime('%d/%m/%Y')}"
        texto_anterior = f"Del {dt_inicio_ant.strftime('%d/%m/%Y')} al {dt_fin_ant.strftime('%d/%m/%Y')}"

        stats = {
            'periodo_actual_texto': texto_actual,
            'periodo_anterior_texto': texto_anterior,
            'cant_actual': 0,
            'cant_anterior': 0,
            'total_acumulado': 0
        }

        try:
            # A) Total Acumulado
            stats['total_acumulado'] = self.conn.execute("SELECT COUNT(*) FROM expedientes").fetchone()[0]

            # B) Periodo Seleccionado
            query_actual = f"SELECT COUNT(*) FROM expedientes WHERE fecha BETWEEN '{f_inicio_str}' AND '{f_fin_str}'"
            stats['cant_actual'] = self.conn.execute(query_actual).fetchone()[0]

            # C) Periodo Anterior (Calculado)
            query_anterior = f"SELECT COUNT(*) FROM expedientes WHERE fecha BETWEEN '{f_inicio_ant}' AND '{f_fin_ant}'"
            stats['cant_anterior'] = self.conn.execute(query_anterior).fetchone()[0]

        except Exception as e:
            logging.error(f"Error generando reporte por rango: {e}")
        
        return stats
    
    def obtener_todos_los_folios_usados(self) -> List[str]:
        """Obtiene una lista de todos los folios usados en expedientes y respuestas mediante UNION."""
        query = """
            SELECT folio FROM expedientes WHERE folio IS NOT NULL AND folio != ''
            UNION
            SELECT folio FROM respuestas WHERE folio IS NOT NULL AND folio != ''
        """
        try:
            resultados = self.fetch_all(query)
            # Extraemos solo el texto del folio y lo limpiamos de espacios vacíos
            return [str(row['folio']).strip() for row in resultados if row['folio']]
        except Exception as e:
            logging.error(f"Error al obtener folios usados mediante UNION: {e}")
            return []
    
    def obtener_id_por_folio_cg(self, folio: str):
        """Busca un folio en Control de Gestión y devuelve su ID si existe."""
        if not folio: return None
        try:
            query = "SELECT id FROM control_gestion WHERE folio = ?"
            result = self.fetch_one(query, (folio,))
            return result['id'] if result else None
        except Exception as e:
            logging.error(f"Error al buscar ID por folio en CG: {e}")
            return None
    
    def obtener_folios_por_origen(self, origen: str) -> list:
        """Obtiene una lista de todos los folios registrados bajo un origen específico."""
        query = "SELECT folio FROM control_gestion WHERE origen = ?"
        try:
            resultados = self.fetch_all(query, (origen,))
            return [str(row['folio']).strip() for row in resultados if row['folio']]
        except Exception as e:
            import logging
            logging.error(f"Error al obtener folios por origen {origen}: {e}")
            return []
    
    def crear_lote_transferencia(self, usuario: str) -> tuple:
        """Crea un nuevo lote y genera su folio automáticamente."""
        try:
            anio = datetime.now().year
            self.cursor.execute("SELECT COUNT(*) FROM lotes_transferencia WHERE strftime('%Y', fecha_creacion) = ?", (str(anio),))
            consecutivo = self.cursor.fetchone()[0] + 1
            folio_lote = f"TRANS-{anio}-{consecutivo:03d}"

            self.cursor.execute('''
                INSERT INTO lotes_transferencia (folio_lote, usuario_creador)
                VALUES (?, ?)
            ''', (folio_lote, usuario))
            self.conn.commit()
            
            lote_id = self.cursor.lastrowid
            return True, lote_id, folio_lote
        except sqlite3.Error as e:
            logging.error(f"Error al crear lote de transferencia: {e}", exc_info=True)
            return False, 0, str(e)

    def asignar_expedientes_a_lote(self, id_lote: int, ids_expedientes: list) -> bool:
        """Vincula una lista de expedientes a un lote de transferencia."""
        try:
            placeholders = ','.join('?' * len(ids_expedientes))
            
            sql = f"UPDATE expedientes SET id_lote_transferencia = ? WHERE id IN ({placeholders})"
            
            parametros = [id_lote] + ids_expedientes
            self.cursor.execute(sql, parametros)
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logging.error(f"Error al asignar expedientes al lote {id_lote}: {e}", exc_info=True)
            return False

    def obtener_lotes_activos(self) -> list:
        """Devuelve los lotes que están en tránsito (no entregados)."""
        try:
            self.cursor.execute('''
                SELECT * FROM lotes_transferencia 
                WHERE entregado = 0 
                ORDER BY id DESC
            ''')
            return [dict(row) for row in self.cursor.fetchall()]
        except sqlite3.Error as e:
            logging.error(f"Error al obtener lotes activos: {e}")
            return []

    def marcar_lote_entregado(self, id_lote: int, ubi: dict, ruta_pdf: str = None) -> tuple:
        try:
            fecha_hoy = datetime.now().strftime("%Y-%m-%d")
            self.cursor.execute('''
                UPDATE lotes_transferencia 
                SET entregado = 1, fecha_entrega = ?, archivo_inventario_pdf = ?
                WHERE id = ?
            ''', (fecha_hoy, ruta_pdf, id_lote))

            self.cursor.execute("SELECT id FROM expedientes WHERE id_lote_transferencia = ?", (id_lote,))
            expedientes_del_lote = self.cursor.fetchall()

            for exp in expedientes_del_lote:
                # Insertamos las 4 columnas nuevas
                self.cursor.execute('''
                    INSERT INTO archivo_concentracion 
                    (expediente_id, fecha_ingreso, ubicacion_area, ubicacion_pasillo, ubicacion_anaquel, ubicacion_charola)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (exp['id'], fecha_hoy, ubi.get('area',''), ubi.get('pasillo',''), ubi.get('anaquel',''), ubi.get('charola','')))
            
            self.conn.commit()
            return True, "Lote entregado y expedientes archivados con éxito."
        except sqlite3.Error as e:
            self.conn.rollback()
            return False, str(e)
    
    def obtener_ids_por_lote(self, id_lote: int) -> list:
        """Busca todos los expedientes que pertenecen a un paquete/lote específico."""
        query = "SELECT id FROM expedientes WHERE id_lote_transferencia = ?"
        try:
            resultados = self.fetch_all(query, (id_lote,))
            return [row['id'] for row in resultados]
        except Exception as e:
            import logging
            logging.error(f"Error al obtener ids por lote: {e}")
            return []
    
    def cancelar_lote_transferencia(self, id_lote: int) -> bool:
        """
        Deshace un lote de transferencia: libera los expedientes y elimina el registro del lote.
        """
        try:
            self.cursor.execute('''
                UPDATE expedientes 
                SET id_lote_transferencia = NULL 
                WHERE id_lote_transferencia = ?
            ''', (id_lote,))
            
            self.cursor.execute("DELETE FROM lotes_transferencia WHERE id = ?", (id_lote,))
            
            self.conn.commit()
            return True
            
        except sqlite3.Error as e:
            import logging
            logging.error(f"Error al cancelar lote {id_lote}: {e}", exc_info=True)
            self.conn.rollback() # Si algo falla, deshace todo por seguridad
            return False
    
    def obtener_lotes_entregados(self) -> list:
        """Devuelve los lotes que ya fueron entregados al Archivo de Concentración."""
        try:
            self.cursor.execute('''
                SELECT * FROM lotes_transferencia 
                WHERE entregado = 1 
                ORDER BY fecha_entrega DESC, id DESC
            ''')
            return [dict(row) for row in self.cursor.fetchall()]
        except sqlite3.Error as e:
            import logging
            logging.error(f"Error al obtener lotes entregados: {e}")
            return []
    
    def obtener_historial_destino_final(self) -> list:
        """Obtiene la lista de todos los expedientes que ya causaron baja o se fueron al histórico."""
        query = """
            SELECT 
                df.id as destino_id, df.tipo_destino, df.fecha_ejecucion, df.acta_pdf, df.observaciones,
                e.id as exp_id, e.folio, e.asunto, e.serie_documental, e.clasificacion
            FROM destino_final df
            JOIN expedientes e ON df.expediente_id = e.id
            ORDER BY df.fecha_ejecucion DESC, df.id DESC
        """
        try:
            return self.fetch_all(query)
        except Exception as e:
            import logging
            logging.error(f"Error al obtener historial de destino final: {e}")
            return []
    
    def crear_lote_valoracion(self, expedientes_ids: list, tipo_propuesta: str, usuario: str) -> tuple:
        """Crea un lote (puente) y le asigna los expedientes seleccionados de concentración."""
        try:
            fecha_hoy = datetime.now().strftime("%Y-%m-%d")
            anio = datetime.now().year
            
            # Generar folio (Ej. VAL-2026-001)
            self.cursor.execute("SELECT COUNT(*) FROM lotes_valoracion WHERE strftime('%Y', fecha_creacion) = ?", (str(anio),))
            count = self.cursor.fetchone()[0] + 1
            folio_lote = f"VAL-{anio}-{count:03d}"
            
            self.cursor.execute('''
                INSERT INTO lotes_valoracion (folio_lote, tipo_propuesta, fecha_creacion, usuario_creador, estatus)
                VALUES (?, ?, ?, ?, 'EN_VALORACION')
            ''', (folio_lote, tipo_propuesta, fecha_hoy, usuario))
            
            lote_id = self.cursor.lastrowid
            
            # Etiquetamos los expedientes con el ID de este lote
            for exp_id in expedientes_ids:
                self.cursor.execute('''
                    UPDATE archivo_concentracion 
                    SET id_lote_valoracion = ? 
                    WHERE expediente_id = ?
                ''', (lote_id, exp_id))
                
            self.conn.commit()
            return True, f"Lote de valoración '{folio_lote}' creado con éxito.\nEn espera de dictamen."
            
        except sqlite3.Error as e:
            self.conn.rollback()
            return False, f"Error en BD al crear lote de valoración: {e}"
    def obtener_ids_por_lote_valoracion(self, id_lote: int) -> list:
        """Obtiene los expedientes vinculados a un lote en el puente de valoración."""
        query = "SELECT expediente_id FROM archivo_concentracion WHERE id_lote_valoracion = ?"
        try:
            resultados = self.fetch_all(query, (id_lote,))
            return [row['expediente_id'] for row in resultados]
        except Exception as e:
            import logging
            logging.error(f"Error al obtener ids por lote de valoración: {e}")
            return []

    def obtener_lotes_valoracion_activos(self) -> list:
        """Devuelve los lotes que están en el puente esperando respuesta del comité."""
        try:
            self.cursor.execute('''
                SELECT * FROM lotes_valoracion 
                WHERE estatus = 'EN_VALORACION' 
                ORDER BY id DESC
            ''')
            return [dict(row) for row in self.cursor.fetchall()]
        except sqlite3.Error:
            return []

    def rechazar_lote_valoracion(self, lote_id: int) -> tuple:
        """El comité dijo que NO. Se cancela el lote y los expedientes regresan a la normalidad en la bodega."""
        try:
            # 1. Quitamos la etiqueta de los expedientes (los liberamos del lote)
            self.cursor.execute("UPDATE archivo_concentracion SET id_lote_valoracion = NULL WHERE id_lote_valoracion = ?", (lote_id,))
            # 2. Marcamos el lote como rechazado para la historia
            self.cursor.execute("UPDATE lotes_valoracion SET estatus = 'RECHAZADO' WHERE id = ?", (lote_id,))
            self.conn.commit()
            return True, "El dictamen ha sido rechazado.\nLos expedientes regresaron a su estado normal en Concentración."
        except sqlite3.Error as e:
            self.conn.rollback()
            return False, str(e)

    def aprobar_lote_valoracion(self, lote_id: int, acta_pdf: str, observaciones: str) -> tuple:
        """El comité dijo que SÍ. Todos los expedientes del lote viajan juntos al Destino Final."""
        try:
            fecha_hoy = datetime.now().strftime("%Y-%m-%d")
            
            # 1. ¿De qué era este lote? (Baja o Histórico)
            self.cursor.execute("SELECT tipo_propuesta FROM lotes_valoracion WHERE id = ?", (lote_id,))
            lote = self.cursor.fetchone()
            if not lote: return False, "Lote no encontrado."
            tipo_destino = lote['tipo_propuesta']
            
            # 2. ¿Qué expedientes viajaban en la caja?
            self.cursor.execute("SELECT expediente_id FROM archivo_concentracion WHERE id_lote_valoracion = ?", (lote_id,))
            expedientes = self.cursor.fetchall()
            
            # 3. La ejecución: Inscribirlos en el Destino Final y borrarlos de Concentración
            for exp in expedientes:
                exp_id = exp['expediente_id']
                self.cursor.execute('''
                    INSERT INTO destino_final (expediente_id, tipo_destino, fecha_ejecucion, acta_pdf, observaciones)
                    VALUES (?, ?, ?, ?, ?)
                ''', (exp_id, tipo_destino, fecha_hoy, acta_pdf, observaciones))
                
                self.cursor.execute("DELETE FROM archivo_concentracion WHERE expediente_id = ?", (exp_id,))
                
            # 4. Marcamos la caja como "Caso Cerrado"
            self.cursor.execute("UPDATE lotes_valoracion SET estatus = 'APROBADO' WHERE id = ?", (lote_id,))
            
            self.conn.commit()
            return True, f"¡Dictamen aprobado!\n{len(expedientes)} expedientes pasaron a su Destino Final."
            
        except sqlite3.IntegrityError:
            self.conn.rollback()
            return False, "Un expediente del lote ya tenía destino final asignado previamente."
        except sqlite3.Error as e:
            self.conn.rollback()
            return False, str(e)
    
    def revertir_destino_final(self, destino_id: int, expediente_id: int) -> tuple:
        """Saca el expediente del destino final y lo regresa al Archivo de Concentración."""
        try:
            # 1. Lo borramos del registro de Destinos Finales
            self.cursor.execute("DELETE FROM destino_final WHERE id = ?", (destino_id,))
            
            # 2. Lo reingresamos a la bodega de Concentración (sin lote asignado)
            self.cursor.execute('''
                INSERT INTO archivo_concentracion (expediente_id, fecha_ingreso) 
                VALUES (?, DATE('now'))
            ''', (expediente_id,))
            
            self.conn.commit()
            return True, "El expediente ha sido rescatado y devuelto a Concentración."
        except sqlite3.Error as e:
            self.conn.rollback()
            return False, f"Error al revertir destino final: {e}"
    
    def registrar_prestamo(self, datos: dict) -> tuple:
        """Inserta un nuevo registro de préstamo en la base de datos."""
        query = '''
            INSERT INTO prestamos_fisicos (
                expediente_id, solicitante, area_solicitante, 
                fecha_prestamo, fecha_vencimiento, estatus, 
                observaciones, usuario_registro
            ) VALUES (?, ?, ?, ?, ?, 'ACTIVO', ?, ?)
        '''
        valores = (
            datos.get('expediente_id'),
            datos.get('solicitante'),
            datos.get('area_solicitante'),
            datos.get('fecha_prestamo'),
            datos.get('fecha_vencimiento'),
            datos.get('observaciones', ''),
            datos.get('usuario_registro', 'sistema')
        )
        try:
            self.cursor.execute(query, valores)
            self.conn.commit()
            return True, "Préstamo registrado correctamente."
        except sqlite3.Error as e:
            self.conn.rollback()
            import logging
            logging.error(f"Error al registrar préstamo: {e}")
            return False, f"Error en BD al registrar préstamo: {e}"

    def registrar_devolucion(self, prestamo_id: int, observaciones_entrega: str = "") -> tuple:
        """Marca un préstamo como DEVUELTO y estampa la fecha actual."""
        query = '''
            UPDATE prestamos_fisicos 
            SET estatus = 'DEVUELTO', 
                fecha_devolucion = DATE('now'),
                observaciones = observaciones || char(10) || 'DEVOLUCIÓN: ' || ?
            WHERE id = ?
        '''
        try:
            self.cursor.execute(query, (observaciones_entrega, prestamo_id))
            self.conn.commit()
            return True, "Expediente devuelto exitosamente al archivo."
        except sqlite3.Error as e:
            self.conn.rollback()
            return False, f"Error al registrar devolución: {e}"

    def obtener_prestamos_activos(self) -> list:
        """
        Obtiene todos los préstamos que no han sido devueltos.
        Hace un JOIN con expedientes para traer el Folio y el Asunto.
        Calcula dinámicamente si está A TIEMPO o VENCIDO.
        """
        query = """
            SELECT 
                p.id as prestamo_id, p.expediente_id, p.solicitante, p.area_solicitante,
                p.fecha_prestamo, p.fecha_vencimiento, p.observaciones,
                e.folio, e.asunto, e.clasificacion,
                CAST(julianday(p.fecha_vencimiento) - julianday('now') AS INTEGER) as dias_restantes
            FROM prestamos_fisicos p
            JOIN expedientes e ON p.expediente_id = e.id
            WHERE p.estatus = 'ACTIVO'
            ORDER BY p.fecha_vencimiento ASC
        """
        try:
            resultados = self.fetch_all(query)
            # ¡AQUÍ ESTÁ LA MAGIA! Convertimos el sqlite3.Row a un Diccionario normal
            return [dict(row) for row in resultados] if resultados else []
        except Exception as e:
            import logging
            logging.error(f"Error al obtener préstamos activos: {e}")
            return []
    
    def esta_prestado(self, expediente_id: int) -> bool:
        """Verifica si un expediente específico ya tiene un préstamo activo."""
        query = "SELECT COUNT(*) FROM prestamos_fisicos WHERE expediente_id = ? AND estatus = 'ACTIVO'"
        try:
            self.cursor.execute(query, (expediente_id,))
            return self.cursor.fetchone()[0] > 0
        except Exception:
            return False