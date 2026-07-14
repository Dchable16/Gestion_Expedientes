# -*- coding: utf-8 -*-
"""
Created on Fri Aug  8 17:12:23 2025

@author: dchable
"""

# -*- coding: utf-8 -*-
"""
Created on Fri Aug  8 17:12:23 2025

@author: dchable
"""

# utils/config_manager.py
import configparser
import os

_config = None
_get_resource_path_func = None      # Para archivos internos (dentro de _internal o temp)
_get_external_data_path_func = None # Para archivos externos (junto al .exe)

def init_config(config_path, resource_path_func, external_data_path_func):
    """
    Inicializa la configuración global y guarda las funciones de ruta.
    """
    global _config, _get_resource_path_func, _get_external_data_path_func
    if _config is None:
        _config = configparser.ConfigParser()
        _config.read(config_path)
        _get_resource_path_func = resource_path_func
        _get_external_data_path_func = external_data_path_func

def get_config():
    """Devuelve el objeto de configuración."""
    if _config is None:
        raise Exception("ConfigManager no inicializado. Llama a init_config() primero.")
    return _config

def _get_path_from_config(section, key, fallback):
    """Auxiliar para rutas EMPAQUETADAS (usa resource_path_func)"""
    config = get_config()
    relative_path = config.get(section, key, fallback=fallback)
    if not relative_path:
        return ""
    return _get_resource_path_func(relative_path)

def _get_external_path_from_config(section, key, fallback):
    """
    Auxiliar para rutas EXTERNAS (usa external_data_path_func).
    Recibe los 3 argumentos, llama a la función base (0 argumentos) y une la ruta.
    """
    config = get_config()
    relative_path = config.get(section, key, fallback=fallback)
    if not relative_path:
        return ""
    # AQUÍ ESTABA LA CONFUSIÓN: Llamamos a la función sin argumentos y unimos la ruta
    base_dir = _get_external_data_path_func() 
    return os.path.join(base_dir, relative_path)

# --- Funciones de Rutas ---

def get_db_path():
    """Obtiene ruta a la BD (EXTERNA para que guarde cambios)"""
    return _get_external_path_from_config('Database', 'db_name', 'expedientes.db')

def get_contactos_path():
    """Obtiene ruta a Contactos (EXTERNA para poder editar)"""
    # Esta es la línea que fallaba. Asegúrate de usar _get_external_path_from_config
    return _get_external_path_from_config('Paths', 'contactos_excel', 'destinatarios.xlsx')

def get_documentos_folder_path():
    """Obtiene ruta a la carpeta de PDFs (EXTERNA)"""
    return _get_external_path_from_config('Paths', 'documentos_folder', 'documentos')

# --- Rutas Internas (Empaquetadas) ---

def get_template_cg_path():
    # Plantilla dentro de _internal/templates
    return _get_path_from_config('Paths', 'template_cg', os.path.join('templates', 'plantilla_cg.xlsx'))

def get_template_path():
    return _get_path_from_config('Paths', 'template_inventario', 'plantilla_inventario.xlsx')

def get_plano_path():
    return _get_path_from_config('Paths', 'plano_ubicacion', '')

def get_series_folder_path():
    return _get_path_from_config('Paths', 'series_folder', 'Series')

def get_logo_semarnat_path():
    return _get_path_from_config('Paths', 'logo_semarnat', 'logo_medio_ambiente.png')

def get_logo_conagua_path():
    return _get_path_from_config('Paths', 'logo_conagua', 'logo_conagua.png')

def get_series_data_csv_path():
    return _get_path_from_config('Paths', 'series_data_csv', 'series_documentales.csv')

def get_splash_logo_path():
    return _get_path_from_config('Paths', 'splash_logo', 'splash_logo.png')

def get_window_icon_path():
    return _get_path_from_config('Paths', 'window_icon', 'expediente.ico')

# --- API Keys ---

def get_google_api_key():
    config = get_config()
    clave = config.get('API_Keys', 'google_api_key', fallback=None)
    # El strip() es vital para que la llave sea válida
    return clave.strip() if clave else None

def get_gemini_model_name():
    config = get_config()
    # Actualizamos el fallback al nuevo alias universal y estable
    modelo = config.get('API_Keys', 'GEMINI_MODEL_NAME', fallback='gemini-flash-latest')
    return modelo.strip() if modelo else 'gemini-flash-latest'