"""
Module containing prompt templates and utilities for generating monologue podcasts.

This module provides a collection of prompt templates used to guide LLM responses
when generating podcast monologues from PDF documents. It includes templates for
summarization, synthesis, transcript generation, and dialogue formatting.
"""

import jinja2
from typing import Dict

# Template for summarizing individual PDF documents
MONOLOGUE_SUMMARY_PROMPT_STR = """
Eres un analista conocedor. Por favor proporciona un análisis dirigido del siguiente documento, enfocándote en: {{ focus }}

<document>
{{text}}
</document>

Requisitos para el análisis:
1. Información Esencial:
  - Métricas clave y puntos de datos
  - Tendencias importantes
  - Patrones notables
  - Proyecciones futuras
  - Perspectivas estratégicas

2. Contexto del Documento:
  - Tipo y propósito del documento
  - Entidades relevantes
  - Período de tiempo cubierto
  - Actores clave

3. Precisión de Datos:
  - Preserva valores numéricos exactos
  - Mantén fechas específicas
  - Conserva terminología precisa
  - Incluye revelaciones importantes textualmente cuando sea relevante

4. Requisitos de Conversión de Texto:
  - Escribe todos los números en forma de palabra (ej., "mil millones" no "1B")
  - Expresa moneda como "[cantidad] [unidad]" (ej., "cincuenta millones de dólares")
  - Escribe porcentajes en forma hablada (ej., "veinticinco por ciento")
  - Deletrea operaciones matemáticas (ej., "aumentó en" no "+")
  - Usa caracteres Unicode apropiados

Formatea el análisis usando markdown con encabezados claros y viñetas. Sé enfocado y específico,
Condensa la información en métricas fácilmente digeribles en formato de audiolibro sin hacerlo pesado en estadísticas/números, enfócate más en las áreas de crecimiento y tendencias de la empresa.
Estás presentando a la junta directiva. Habla de una manera que sea atractiva e informativa, pero no demasiado técnica y habla en primera persona.
"""

# Template for synthesizing multiple document summaries into an outline
MONOLOGUE_MULTI_DOC_SYNTHESIS_PROMPT_STR = """
Crea un esquema de monólogo estructurado sintetizando los siguientes resúmenes de documentos. El monólogo debe durar 30-45 segundos.

Áreas de Enfoque y Temas Clave:
{% if focus_instructions %}
{{focus_instructions}}
{% else %}
Usa tu juicio para identificar y priorizar los temas, métricas y perspectivas más importantes en todos los documentos.
{% endif %}

Documentos Fuente Disponibles:
{{documents}}

Requisitos:
1. Estrategia de Contenido
   - Enfócate en el contenido de los Documentos Objetivo, y usa los Documentos de Contexto como apoyo
   - Identifica métricas clave y tendencias
   - Analiza implicaciones potenciales
   - Establece conexiones entre documentos y áreas de enfoque

2. Requisitos de Estructura
   - Crea un flujo narrativo claro
   - Equilibra profundidad vs amplitud de cobertura
   - Asegura transiciones lógicas de temas
   - Mantén precisión y exactitud financiera

3. Gestión del Tiempo
   - Asigna tiempo basado en importancia del tema
   - Permite ritmo natural y énfasis
   - Incluye pausas breves para puntos clave
   - Mantente dentro de la duración total

4. Requisitos de Formato de Texto:
   - Escribe números en forma de palabra
   - Formatea moneda como "[cantidad] [unidad]"
   - Expresa porcentajes en forma hablada
   - Escribe operaciones matemáticas

Produce un esquema estructurado que sintetice perspectivas a través de todos los documentos, enfatizando Documentos Objetivo mientras usa Documentos de Contexto para apoyo."""

# Template for generating the actual monologue transcript
MONOLOGUE_TRANSCRIPT_PROMPT_STR = """
Crea una actualización enfocada basada en este esquema y documentos fuente.

Esquema:
{{ raw_outline }}

Documentos Fuente Disponibles:
{% for doc in documents %}
<document>
<type>{"Documento Objetivo" if doc.type == "target" else "Documento de Contexto"}</type>
<path>{{doc.filename}}</path>
<summary>
{{doc.summary}}
</summary>
</document>
{% endfor %}

Áreas de Enfoque: {{ focus }}

Parámetros:
- Duración: 30 segundos (~90 palabras)
- Locutor: {{ speaker_1_name }}
- Estructura: Sigue el esquema mientras mantienes:
  * Apertura (5-7 palabras)
  * Puntos clave del esquema (60-70 palabras)
  * Evidencia de apoyo (15-20 palabras)
  * Conclusión (10-15 palabras)

Requisitos:
1. Patrón de Habla
   - Usa entrega estilo transmisión
   - Pausas naturales y énfasis
   - Tono profesional pero conversacional
   - Atribución clara de fuentes

2. Estructura de Contenido
   - Prioriza insights de Documentos Objetivo
   - Apoya con Documentos de Contexto donde sea relevante
   - Mantén flujo lógico entre puntos
   - Termina con una conclusión clara

3. Formato de Texto:
   - Todos los números en forma de palabra
   - Moneda como "[cantidad] [unidad]"
   - Porcentajes en forma hablada
   - Operaciones matemáticas escritas

Crea un monólogo conciso y atractivo que siga el esquema mientras entrega información financiera esencial."""

# Template for converting monologue to structured dialogue format
MONOLOGUE_DIALOGUE_PROMPT_STR = """Se te ha asignado convertir un monólogo financiero en un formato JSON estructurado. Tienes:

1. Información del hablante:
   - Hablante: {{ speaker_1_name }} (mapeado a "speaker-1")

2. El monólogo original:
{{ text }}

3. Esquema de salida requerido:
{{ schema }}

Tu tarea es:
- Convertir el monólogo exactamente al formato JSON especificado
- Preservar todo el contenido sin omisiones
- Mapear todo el contenido a "speaker-1"
- Mantener toda la precisión de datos financieros

Debes absolutamente, sin excepción:
- Usar caracteres Unicode apropiados directamente (ej., usar ' en lugar de \\u2019)
- Asegurar que todas las apostrofes, comillas y caracteres especiales estén formateados apropiadamente
- No escapar caracteres Unicode en la salida

Debes absolutamente, sin excepción:
- Convertir todos los números y símbolos a forma hablada:
  * Los números deben escribirse con palabras (ej., "mil millones" en lugar de "1B")
  * La moneda debe expresarse como "[cantidad] [unidad de moneda]" (ej., "cincuenta millones de dólares" en lugar de "$50M")
  * Los símbolos matemáticos deben hablarse (ej., "aumentó en" en lugar de "+")
  * Los porcentajes deben hablarse como "por ciento" (ej., "veinticinco por ciento" en lugar de "25%")

Por favor, produce el JSON siguiendo el esquema proporcionado, manteniendo todos los detalles financieros y formato apropiado. La salida debe usar caracteres Unicode apropiados directamente, no secuencias escapadas. No produzcas nada más que el JSON."""

# Dictionary mapping template names to their content
PROMPT_TEMPLATES = {
    "monologue_summary_prompt": MONOLOGUE_SUMMARY_PROMPT_STR,
    "monologue_multi_doc_synthesis_prompt": MONOLOGUE_MULTI_DOC_SYNTHESIS_PROMPT_STR,
    "monologue_transcript_prompt": MONOLOGUE_TRANSCRIPT_PROMPT_STR,
    "monologue_dialogue_prompt": MONOLOGUE_DIALOGUE_PROMPT_STR,
}

# Create Jinja templates once
TEMPLATES: Dict[str, jinja2.Template] = {
    name: jinja2.Template(template) for name, template in PROMPT_TEMPLATES.items()
}


class FinancialSummaryPrompts:
    """
    A class providing access to financial summary prompt templates.
    
    This class serves as an interface to access and render various prompt templates
    used in the monologue generation process. Templates are accessed either through
    attribute access or the get_template class method.

    Attributes:
        None

    Methods:
        __getattr__(name: str) -> str: Dynamically retrieves prompt template strings by name
        get_template(name: str) -> jinja2.Template: Retrieves compiled Jinja templates by name
    """

    def __getattr__(self, name: str) -> str:
        """
        Get the Jinja template by name

        Args:
            name (str): Name of the prompt template to retrieve

        Returns:
            str: The prompt template string

        Raises:
            AttributeError: If the requested template name doesn't exist
        """
        if name in PROMPT_TEMPLATES:
            return PROMPT_TEMPLATES[name]
        raise AttributeError(f"'{self.__class__.__name__}' has no attribute '{name}'")

    @classmethod
    def get_template(cls, name: str) -> jinja2.Template:
        """
        Get the compiled Jinja template by name.

        Args:
            name (str): Name of the template to retrieve

        Returns:
            jinja2.Template: The compiled Jinja template object

        Raises:
            KeyError: If the requested template name doesn't exist
        """
        return TEMPLATES[name]
