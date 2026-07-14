# main.py
import sys
import os
import logging
import traceback
from logging.handlers import RotatingFileHandler

# --- 1. IMPORTACIONES RÁPIDAS UI Y MOTOR WEB ---
# QtWebEngine OBLIGA a importarse aquí para configurar el núcleo gráfico
# antes de que exista cualquier ventana (Regla de OpenGL).
from PyQt5.QtWidgets import QApplication, QMessageBox, QSplashScreen, QDialog
from PyQt5.QtCore import Qt, QTranslator, QLibraryInfo
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtCore import Qt

import resources_rc  # Recursos visuales (íconos, logos)
import utils.config_manager as config_manager
from utils.config_manager import (
    get_db_path, 
    get_splash_logo_path, 
    get_window_icon_path
)

from datos.expediente_repository import ExpedienteRepository
from ui.login_dialog import LoginDialog

# --- Funciones Auxiliares ---

def get_app_root_path():
    """
    Obtiene la ruta raíz para DATOS EXTERNOS (como la carpeta 'documentos').
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.abspath(".")

def resource_path(relative_path):
    """ 
    Obtiene la ruta absoluta a un recurso *EMPAQUETADO*.
    """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def setup_logging():
    log_file = 'app.log'
    handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')
    log_format = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
    formatter = logging.Formatter(log_format)
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.DEBUG)

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    traceback_details = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    logging.critical(f"Excepción no capturada:\n{traceback_details}")

    error_box = QMessageBox()
    error_box.setIcon(QMessageBox.Critical)
    error_box.setText("Ha ocurrido un error inesperado. Los detalles han sido guardados en app.log.")
    error_box.setDetailedText(traceback_details)
    error_box.setWindowTitle("Error Crítico")
    error_box.exec_()
    
# --- Punto de Entrada Principal ---

if __name__ == '__main__':
    setup_logging()
    sys.excepthook = handle_exception
    
    # 1. Configuración de Aceleración por Hardware (Vital para QtWebEngine y PDF)
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
    
    # 2. Levantar aplicación en RAM
    app = QApplication(sys.argv)
    translator = QTranslator()
    if getattr(sys, 'frozen', False):
        ruta_traducciones = resource_path("translations")
    else:
        ruta_traducciones = QLibraryInfo.location(QLibraryInfo.TranslationsPath)
    if translator.load("qtbase_es", ruta_traducciones) or translator.load("qt_es", ruta_traducciones):
        app.installTranslator(translator)
    else:
        logging.warning(f"No se encontraron los archivos de traducción en: {ruta_traducciones}")
    app.setStyle("Fusion")
    font = app.font()
    font.setPointSize(8) 
    app.setFont(font)
    
    try:
        ruta_config = resource_path("config.ini")
        config_manager.init_config(
            config_path=ruta_config, 
            resource_path_func=resource_path,
            external_data_path_func=get_app_root_path
        )
    except Exception as e:
        logging.critical(f"No se pudo cargar el archivo de configuración 'config.ini': {e}")
        QMessageBox.critical(None, "Error Crítico", f"No se pudo cargar 'config.ini': {e}")
        sys.exit(1)

    try:
        icon_path = get_window_icon_path() 
        app_icon = QIcon(icon_path)
        app.setWindowIcon(app_icon)
    except Exception as e:
        pass

    # =========================================================================
    # ¡NUEVO!: APLICAMOS EL ESTILO CORPORATIVO (.QSS) DESDE EL MINUTO 1
    # Para que el Login y todas las pantallas futuras nazcan con diseño
    # =========================================================================
    try:
        ruta_estilos = resource_path("estilos.qss")
        with open(ruta_estilos, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    except FileNotFoundError:
        pass
    except Exception as e:
        logging.warning(f"Error al cargar estilos.qss: {e}")

    # 3. Conectar BD ligera y Lanzar el LOGIN inmediatamente (Ya con estilo)
    try:
        db_path = get_db_path()
        repo_login = ExpedienteRepository(db_name=db_path)
    except Exception as e:
        QMessageBox.critical(None, "Error Crítico", f"No se pudo conectar a la base de datos para validar usuario: {e}")
        sys.exit(1)

    login_win = LoginDialog(repo_login)
    if login_win.exec_() != QDialog.Accepted:
        repo_login.close_connection()
        sys.exit(0)
    
    usuario_logueado = login_win.usuario_autenticado
    repo_login.close_connection()

    # 4. Lanzar Splash Screen (Ocultando la pesadez de Pandas/IA)
    splash = None 
    try:
        logo_path = get_splash_logo_path()
        pixmap = QPixmap(logo_path)
        splash = QSplashScreen(pixmap, Qt.WindowStaysOnTopHint)
        splash.setMask(pixmap.mask()) 
        splash.show()
        app.processEvents() 
    except Exception as e:
        logging.warning(f"No se pudo cargar el Splash Screen: {e}")

    if splash:
        splash.showMessage("Cargando sistema de gestión...", Qt.AlignBottom | Qt.AlignCenter, Qt.white)
        app.processEvents()

    # =========================================================================
    # 5. CARGA DIFERIDA (LAZY LOADING) DE CÓDIGO EXTERNO MASIVO
    # Solo retrasamos la importación del Código de Negocio (Pandas, Excel, Gemini)
    # =========================================================================
    from negocio.expediente_service import ExpedienteService
    from negocio.import_service import ImportService
    from negocio.backup_service import BackupService
    from negocio.excel_service import ExcelService
    from negocio.email_service import EmailService
    from ui.main_window import MainWindow

    if splash:
        splash.showMessage("Conectando y analizando estructura de bases de datos...", Qt.AlignBottom | Qt.AlignCenter, Qt.white)
        app.processEvents()

    db_path = get_db_path()
    expediente_repo = ExpedienteRepository(db_name=db_path)
    expediente_svc = ExpedienteService(repository=expediente_repo, usuario_actual=usuario_logueado)
    expediente_repo.registrar_accion(usuario_logueado, "LOGIN", "Inicio de sesión exitoso")
    
    backup_svc = BackupService(db_path=db_path)
    excel_svc = ExcelService()
    email_svc = EmailService()
    import_svc = ImportService(db_path=db_path, expediente_service=expediente_svc, expediente_repository=expediente_repo)
  
    if splash:
        splash.showMessage("Inciando interfaz...", Qt.AlignBottom | Qt.AlignCenter, Qt.white)
        app.processEvents()
        
    main_win = MainWindow(
        expediente_service=expediente_svc,
        backup_service=backup_svc,
        excel_service=excel_svc,
        email_service=email_svc,
        import_service=import_svc,
        usuario_actual=usuario_logueado
    )
    
    if splash:
        splash.finish(main_win)
        
    main_win.showMaximized()
    sys.exit(app.exec_())