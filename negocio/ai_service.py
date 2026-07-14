# -*- coding: utf-8 -*-
"""
Created on Mon Sep  1 11:40:08 2025

@author: dchable
"""

# -*- coding: utf-8 -*-
# negocio/ai_service.py

from google import genai  # Nueva librería estable
import PyPDF2
import docx
import os
import time

from utils.config_manager import get_google_api_key, get_gemini_model_name
from typing import List, Tuple

class AIService:
    def __init__(self):
        self.api_key = get_google_api_key()
        self.model_name = get_gemini_model_name()
        
        if self.api_key and self.api_key != "TU_API_KEY_AQUI":
            try:
                # Inicialización limpia sin forzar v1. 
                # La librería elegirá el endpoint correcto para leer PDFs.
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                self.client = None
                print(f"ADVERTENCIA: Error al configurar el cliente: {e}")
        else:
            self.client = None
            print("ADVERTENCIA: API Key no configurada.")

    def _extraer_texto_pdf_nativo(self, ruta_archivo: str) -> str: 
        try:
            with open(ruta_archivo, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                return "".join(page.extract_text() for page in reader.pages if page.extract_text())[:15000]
        except Exception:
            return ""

    def _extraer_texto_docx(self, ruta_archivo: str) -> str:
        try:
            doc = docx.Document(ruta_archivo)
            return "\n".join([para.text for para in doc.paragraphs])[:15000]
        except Exception:
            return ""

    def analizar_documento_para_asunto(self, ruta_documento: str, ruta_pdf_serie: str, nombre_serie: str) -> Tuple[bool, List[str]]:
        if not self.client:
            return False, ["La IA no está configurada."]
        
        texto_descripcion_serie = self._extraer_texto_pdf_nativo(ruta_pdf_serie) if ruta_pdf_serie and os.path.exists(ruta_pdf_serie) else nombre_serie

        # --- MEGA PROMPT ARCHIVÍSTICO RECUPERADO ---
        prompt_base = f"""
        Actuarás como un archivista experto del Archivo General de la Nación de México, especializado en la descripción documental para archivos de trámite y concentración. Tu objetivo es generar descripciones que garanticen la localización expedita, la transparencia y la correcta valoración documental, cumpliendo rigurosamente con la normativa vigente.

        Tu misión es redactar dos (2) propuestas de descripción para el campo "Asunto" de un expediente, basándote en el análisis exhaustivo del documento que da origen al trámite.
        
        **## Contexto del Expediente**
        - **Serie Documental:** "{nombre_serie}"
        - **Descripción General de la Serie:** "{texto_descripcion_serie}"
        
        **## Instrucciones Detalladas**
        
        1.  **Análisis Profundo del Documento:** Realiza una lectura crítica del documento para extraer su quintaesencia. Identifica inequívocamente:
            * **La Acción Principal:** El verbo sustantivado que define el trámite (Ej: Solicitud, Autorización, Informe, Contratación, Notificación).
            * **El Tema Específico:** El objeto sobre el cual recae la acción (Ej: la modificación de un contrato, la asignación de recursos, la supervisión de una obra).
            * **Los Actores Clave:** Las unidades administrativas, personas físicas o morales, u organismos que inician, reciben o son parte fundamental del trámite.
            * **El Identificador Único:** El código alfanumérico del documento que formaliza el trámite (Ej: Número de Oficio, Folio de Memorando). **IMPORTANTE:** Ignora por completo los números de turno, folios de ventanilla o datos de control de correspondencia.
        
        2.  **Síntesis Archivística (No Resumen):** Construye la descripción respondiendo a la jerarquía de preguntas:
            * ¿Qué acción se realiza?
            * ¿Sobre qué o quién recae la acción?
            * ¿Quién o quiénes intervienen?
            * ¿Qué documento lo formaliza?
        
        3.  **Generación de Dos Propuestas Claras:** Redacta dos variantes de la descripción:
            * **Propuesta 1:** Directa, centrada en la acción y el tema.
            * **Propuesta 2:** Con mayor énfasis a los actores involucrados o al identificador del documento.
        
        **## Reglas Inquebrantables**
        
        - **Formato Inicial Obligatorio:** Toda propuesta DEBE comenzar con el nombre completo de la serie documental, seguido de un punto.
        - **CERO ABREVIATURAS NI SIGLAS:** Escribe todos los términos de forma completa. (Ej: "Secretaría de Medio Ambiente y Recursos Naturales" en lugar de "SEMARNAT").
        - **LENGUAJE TÉCNICO Y NEUTRO:** Utiliza un tono formal, objetivo y preciso.
        - **PRECISIÓN:** Cada palabra debe aportar valor. Elimina información superflua.
        
        **## Estructura Ideal de la Descripción**
        `[Nombre de la Serie]. [Acción Principal] sobre [Asunto o Tema Específico] que [presenta/solicita/envía] [Actor Origen] a [Actor Destino], mediante [Tipo de Documento e Identificador Único].`
        
        **## Formato de Salida Obligatorio**
        Genera ÚNICAMENTE las dos propuestas de asunto. NO incluyas introducciones, explicaciones ni viñetas adicionales. Separa cada propuesta con un salto de línea:
        
        Propuesta 1: 
        Propuesta 2: 
        """

        try:
            if ruta_documento.lower().endswith('.pdf'):
                # Subida de archivo con la nueva API Multimodal (OCR Nativo de Google)
                archivo_gemini = self.client.files.upload(file=ruta_documento)
                
                # Espera automática de procesamiento en los servidores de Google
                while archivo_gemini.state.name == "PROCESSING":
                    time.sleep(2)
                    archivo_gemini = self.client.files.get(name=archivo_gemini.name)
                
                # Generación de contenido multimodal mezclando Texto + Documento (Imagen)
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=[prompt_base, archivo_gemini]
                )
                
                # Limpieza de seguridad: Destruir el oficio confidencial del servidor de Google
                try:
                    self.client.files.delete(name=archivo_gemini.name)
                except Exception as e:
                    print(f"Nota: No se pudo eliminar el archivo remoto: {e}")
            
            else:
                # Caso para oficios en Word nativos locales
                texto_docx = self._extraer_texto_docx(ruta_documento)
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=f"{prompt_base}\n\n**Documento a procesar:**\n{texto_docx}"
                )

            sugerencias = [s.replace('Propuesta 1: ', '').replace('Propuesta 2: ', '').strip() for s in response.text.split('\n') if s.strip()]
            return True, sugerencias

        except Exception as e:
            # Captura robusta por si Google nos pone el bloqueo de 429 Limit Quota
            error_msg = str(e)
            if "429" in error_msg or "Quota exceeded" in error_msg:
                mensaje_amigable = [
                    "⚠️ Límite de consultas rápidas alcanzado.",
                    "Google tiene un límite de lecturas en la capa gratuita.",
                    "Por favor, espera 60 segundos antes de intentar con otro documento."
                ]
                return False, mensaje_amigable
                
            return False, [f"Error al contactar los servidores de la IA: {error_msg}"]