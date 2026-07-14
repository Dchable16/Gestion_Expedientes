# -*- coding: utf-8 -*-
"""
Created on Tue Jul 22 10:31:07 2025

@author: dchable
"""

# negocio/backup_service.py

import logging
import shutil
import os

from typing import Tuple, List
from datetime import datetime

class BackupService:
    def __init__(self, db_path: str):
        self.db_path = db_path
        # La carpeta de backups estará junto al ejecutable o script principal
        self.backup_dir = os.path.join(os.path.dirname(os.path.abspath(db_path)), 'backups')
        os.makedirs(self.backup_dir, exist_ok=True)

    def crear_backup(self, nombre_personalizado: str = None) -> Tuple[bool, str]:
        """
        Crea una copia de seguridad de la base de datos principal.
        Devuelve (éxito, mensaje_o_ruta_del_archivo).
        """
        try:
            if not os.path.exists(self.db_path):
                return False, "El archivo de la base de datos no existe."

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            db_name = os.path.basename(self.db_path)
            
            if nombre_personalizado:
                backup_name = f"{timestamp}_{nombre_personalizado.strip()}.db.bak"
            else:
                backup_name = f"{db_name}_{timestamp}.bak"
                
            backup_path = os.path.join(self.backup_dir, backup_name)
            
            shutil.copy2(self.db_path, backup_path)
            
            if os.path.exists(backup_path):
                return True, f"Copia de seguridad creada exitosamente en: {backup_path}"
            else:
                return False, "Error desconocido: no se pudo crear el archivo de copia de seguridad."
                
        except Exception as e:
            logging.error("ERROR en BackupService.crear_backup: %s", e, exc_info=True)
            print(f"ERROR en BackupService.crear_backup: {e}")
            return False, f"Ocurrió un error al crear la copia de seguridad: {e}"
    
    def restaurar_backup(self, ruta_backup: str) -> Tuple[bool, str]:
        """
        Reemplaza la base de datos actual con el archivo de backup seleccionado.
        Devuelve (éxito, mensaje).
        """
        try:
            if not os.path.exists(ruta_backup):
                return False, "El archivo de copia de seguridad seleccionado no existe."

            # La lógica es una simple copia de archivos
            shutil.copy2(ruta_backup, self.db_path)
            
            return True, "Base de datos restaurada exitosamente."

        except Exception as e:
            logging.error("ERROR en BackupService.restaurar_backup: %s", e, exc_info=True)
            print(f"ERROR en BackupService.restaurar_backup: {e}")
            return False, f"Ocurrió un error al restaurar la base de datos: {e}"

    def listar_backups(self) -> List[dict]:
        """
        Lista todas las copias de seguridad disponibles, ordenadas por fecha.
        Devuelve una lista de diccionarios con 'nombre' y 'ruta'.
        """
        backups = []
        try:
            for filename in os.listdir(self.backup_dir):
                if filename.endswith(('.bak', '.db.bak')):
                    filepath = os.path.join(self.backup_dir, filename)
                    backups.append({'nombre': filename, 'ruta': filepath})
            
            # Ordenar por nombre (que incluye el timestamp) de más reciente a más antiguo
            backups.sort(key=lambda x: x['nombre'], reverse=True)
            return backups
        except Exception as e:
            logging.error("ERROR en BackupService.listar_backups: %s", e, exc_info=True)
            print(f"ERROR en BackupService.listar_backups: {e}")
            return []