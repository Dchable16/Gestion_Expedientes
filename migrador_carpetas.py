# -*- coding: utf-8 -*-
"""
Created on Thu Mar 12 17:34:28 2026

@author: dchable
"""

# -*- coding: utf-8 -*-
# migrador_carpetas.py

import sqlite3
import os
import shutil

DB_PATH = 'expedientes.db'
BASE_DOCS_DIR = 'documentos'

def migrar_datos():
    print("Iniciando migración de expedientes a la nueva arquitectura Empresarial...")
    
    # Conectar a la base de datos
    if not os.path.exists(DB_PATH):
        print(f"❌ ERROR: No se encontró la base de datos en {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    expedientes_migrados = 0
    respuestas_migradas = 0

    # ==========================================
    # 1. MIGRAR EXPEDIENTES PRINCIPALES
    # ==========================================
    print("\n--- Procesando Expedientes Principales ---")
    cursor.execute("SELECT id, documento_respaldo FROM expedientes")
    expedientes = cursor.fetchall()

    for exp_id, doc_path in expedientes:
        # Crear la estructura de la Carpeta Maestra
        carpeta_maestra = os.path.join(BASE_DOCS_DIR, f"EXP_{exp_id}")
        os.makedirs(carpeta_maestra, exist_ok=True)
        
        # Crear subcarpetas listas para el futuro
        os.makedirs(os.path.join(carpeta_maestra, "anexos_principales"), exist_ok=True)
        os.makedirs(os.path.join(carpeta_maestra, "respuestas"), exist_ok=True)

        # Si el expediente tenía un PDF asociado, lo movemos
        if doc_path and str(doc_path).strip():
            vieja_ruta_absoluta = os.path.abspath(doc_path)
            
            if os.path.exists(vieja_ruta_absoluta):
                nombre_archivo = os.path.basename(doc_path)
                nueva_ruta_relativa = os.path.join("documentos", f"EXP_{exp_id}", nombre_archivo).replace("\\", "/")
                nueva_ruta_absoluta = os.path.abspath(nueva_ruta_relativa)

                # Si el archivo aún no está en la carpeta maestra, lo movemos
                if vieja_ruta_absoluta != nueva_ruta_absoluta:
                    try:
                        shutil.move(vieja_ruta_absoluta, nueva_ruta_absoluta)
                        # Actualizar la ruta en la base de datos
                        cursor.execute("UPDATE expedientes SET documento_respaldo = ? WHERE id = ?", (nueva_ruta_relativa, exp_id))
                        expedientes_migrados += 1
                    except Exception as e:
                        print(f"⚠️ Error al mover documento del Exp #{exp_id}: {e}")
            else:
                print(f"⚠️ Aviso: El archivo físico del Exp #{exp_id} no se encontró en {vieja_ruta_absoluta}")

    # ==========================================
    # 2. MIGRAR RESPUESTAS
    # ==========================================
    print("\n--- Procesando Respuestas ---")
    try:
        cursor.execute("SELECT id, expediente_id, documento_respuesta FROM respuestas")
        respuestas = cursor.fetchall()

        for resp_id, exp_id, doc_path in respuestas:
            # Crear la subcarpeta específica para esta respuesta dentro del Expediente Maestro
            carpeta_respuesta = os.path.join(BASE_DOCS_DIR, f"EXP_{exp_id}", "respuestas", f"RES_{resp_id}")
            os.makedirs(carpeta_respuesta, exist_ok=True)
            os.makedirs(os.path.join(carpeta_respuesta, "anexos_respuesta"), exist_ok=True)

            # Si la respuesta tenía un PDF asociado, lo movemos
            if doc_path and str(doc_path).strip():
                vieja_ruta_absoluta = os.path.abspath(doc_path)
                
                if os.path.exists(vieja_ruta_absoluta):
                    nombre_archivo = os.path.basename(doc_path)
                    nueva_ruta_relativa = os.path.join("documentos", f"EXP_{exp_id}", "respuestas", f"RES_{resp_id}", nombre_archivo).replace("\\", "/")
                    nueva_ruta_absoluta = os.path.abspath(nueva_ruta_relativa)

                    if vieja_ruta_absoluta != nueva_ruta_absoluta:
                        try:
                            shutil.move(vieja_ruta_absoluta, nueva_ruta_absoluta)
                            # Actualizar la ruta en la base de datos
                            cursor.execute("UPDATE respuestas SET documento_respuesta = ? WHERE id = ?", (nueva_ruta_relativa, resp_id))
                            respuestas_migradas += 1
                        except Exception as e:
                            print(f"⚠️ Error al mover documento de la Respuesta #{resp_id}: {e}")
                else:
                    print(f"⚠️ Aviso: El archivo físico de la Respuesta #{resp_id} no se encontró.")
    except sqlite3.OperationalError:
        print("⚠️ La tabla de 'respuestas' no existe o está vacía. Saltando paso.")

    # ==========================================
    # 3. FINALIZAR
    # ==========================================
    conn.commit()
    conn.close()
    
    print("\n=======================================================")
    print("✅ MIGRACIÓN COMPLETADA CON ÉXITO")
    print(f"   -> Expedientes principales movidos: {expedientes_migrados}")
    print(f"   -> Respuestas movidas: {respuestas_migradas}")
    print("=======================================================\n")
    print("Por favor revisa tu carpeta 'documentos/' para ver la nueva estructura.")

if __name__ == "__main__":
    migrar_datos()