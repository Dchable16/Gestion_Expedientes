# -*- coding: utf-8 -*-
"""
Created on Wed Jul 30 10:31:09 2025

@author: dchable
"""

# negocio/email_service.py

import pandas as pd
import logging
import os

from typing import List, Dict, Tuple

from utils.config_manager import get_contactos_path

class EmailService:
    def __init__(self):
        self.outlook = None
        try:
            import win32com.client
            self.outlook = win32com.client.Dispatch('Outlook.Application')
        except Exception as e:
            logging.error("Error al inicializar Outlook: %s", e, exc_info=True)
            print(f"Error al inicializar Outlook: {e}")

    def leer_contactos_excel(self):
        filename = get_contactos_path()
        contacts = []
        try:
            if not os.path.exists(filename):
                return False, f"No se encontró el archivo de destinatarios: {filename}"

            df = pd.read_excel(filename)
            df = df.fillna("")
            
            if 'NOMBRE' in df.columns and 'CORREO CONAGUA' in df.columns:
                for index, row in df.iterrows():
                    nombre = str(row['NOMBRE']).strip()
                    correo = str(row['CORREO CONAGUA']).strip()
                    
                    if nombre and correo:
                        contacto_completo = row.to_dict()
                        contacto_completo['nombre'] = nombre
                        contacto_completo['correo'] = correo
                        
                        contacts.append(contacto_completo)
                        
                return True, contacts
            else:
                return False, "El archivo de Excel debe contener las columnas 'NOMBRE' y 'CORREO CONAGUA'."
                
        except Exception as e:
            logging.error("Error al leer el archivo de Excel: %s", e, exc_info=True)
            return False, f"Error al leer el archivo de Excel: {e}"

    def enviar_correo_con_adjuntos(self, destinatario: str, asunto: str, cuerpo: str, adjuntos: List[str]) -> Tuple[bool, str]:
        try:
            import win32com.client
            outlook = win32com.client.Dispatch("Outlook.Application")
            mail = outlook.CreateItem(0)  # 0 = olMailItem
            
            mail.To = destinatario
            mail.Subject = asunto
            mail.Body = cuerpo
    
            for doc_path in adjuntos:
                if doc_path and os.path.exists(os.path.abspath(doc_path)):
                    mail.Attachments.Add(os.path.abspath(doc_path))
            
            mail.Send()
            return True, "Correo enviado exitosamente."
            
        except Exception as e:
            logging.error("Error al enviar el correo: %s", e, exc_info=True)
            return False, f"Error al enviar el correo: {str(e)}"