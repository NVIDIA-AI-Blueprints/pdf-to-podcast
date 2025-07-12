"""
Module containing prompt templates and utilities for generating podcast dialogues.

This module provides a collection of prompt templates used to guide LLM responses
when generating podcast dialogues from PDF documents. It includes templates for
summarization, outline generation, transcript creation, and dialogue formatting.
"""

import jinja2
from typing import Dict

# Template for summarizing individual PDF documents
PODCAST_SUMMARY_PROMPT_STR = """
Por favor, proporciona un resumen comprehensivo del siguiente documento. Nota que este documento puede contener artefactos de conversión OCR/PDF, así que por favor interpreta el contenido, especialmente datos numéricos y tablas, con el contexto apropiado.

<document>
{{text}}
</document>

Requisitos para el resumen:
1. Preserva metadatos clave del documento:
   - Título/tipo del documento
   - Nombre de la empresa/organización
   - Proveedor/autor del reporte
   - Fecha/período de tiempo cubierto
   - Cualquier identificador relevante del documento

2. Incluye toda la información crítica:
   - Hallazgos principales y conclusiones
   - Estadísticas y métricas clave
   - Recomendaciones importantes
   - Tendencias o cambios significativos
   - Riesgos o preocupaciones notables
   - Datos financieros materiales

3. Mantén precisión factual:
   - Mantén todos los valores numéricos precisos
   - Preserva fechas específicas y marcos temporales
   - Retén nombres y títulos exactos
   - Cita declaraciones críticas textualmente cuando sea necesario

Por favor, formatea el resumen usando markdown, con encabezados apropiados, listas y énfasis para mejor legibilidad.

Nota: Enfócate en extraer y organizar la información más esencial mientras aseguras que no se omitan detalles críticos. Mantén el tono y contexto originales del documento en tu resumen.
"""

# Template for synthesizing multiple document summaries into an outline
PODCAST_MULTI_PDF_OUTLINE_PROMPT_STR = """
Crea un esquema de podcast estructurado sintetizando los siguientes resúmenes de documentos. El podcast debe durar {{total_duration}} minutos.

Áreas de Enfoque y Temas Clave:
{% if focus_instructions %}
{{focus_instructions}}
{% else %}
Usa tu juicio para identificar y priorizar los temas, hallazgos y perspectivas más importantes en todos los documentos.
{% endif %}

Documentos Fuente Disponibles:
{{documents}}

Requisitos:
1. Estrategia de Contenido
  - Enfócate en el contenido de los Documentos Objetivo, y usa los Documentos de Contexto como apoyo y contexto
  - Identifica debates clave y puntos de vista divergentes
  - Analiza preguntas/preocupaciones potenciales de la audiencia
  - Establece conexiones entre documentos y áreas de enfoque

2. Estructura
  - Crea jerarquía clara de temas
  - Asigna asignaciones de tiempo por sección (basado en prioridades)
  - Referencia documentos fuente usando rutas de archivo
  - Construye flujo narrativo natural entre temas

3. Cobertura
  - Tratamiento comprehensivo de Documentos Objetivo
  - Integración estratégica de Documentos de Contexto para apoyo
  - Evidencia de apoyo de todos los documentos relevantes
  - Equilibra precisión técnica con entrega atractiva

Asegura que el esquema cree una narrativa cohesiva que enfatice los Documentos Objetivo mientras usa los Documentos de Contexto para proporcionar profundidad y información de fondo adicional.
"""

# Template for converting outline into structured JSON format
PODCAST_MULTI_PDF_STRUCUTRED_OUTLINE_PROMPT_STR = """
Convierte el siguiente esquema en un formato JSON estructurado. La sección final debe marcarse como el segmento de conclusión.

<outline>
{{outline}}
</outline>

Requisitos de Salida:
1. Cada segmento debe incluir:
   - nombre de sección
   - duración (en minutos) representando la longitud del segmento
   - lista de referencias (rutas de archivo)
   - lista de temas, donde cada tema tiene:
     - título
     - lista de puntos detallados

2. La estructura general debe incluir:
   - título del podcast
   - lista completa de segmentos

3. Notas importantes:
   - Las referencias deben elegirse de esta lista de nombres de archivo válidos: {{ valid_filenames }}
   - Las referencias solo deben aparecer en el array "references" del segmento, no como un tema
   - La duración representa la longitud de cada segmento, no su marca de tiempo de inicio
   - La duración de cada segmento debe ser un número positivo

El resultado debe conformarse al siguiente esquema JSON:
{{ schema }}
"""

# Template for generating transcript with source references
PODCAST_PROMPT_WITH_REFERENCES_STR = """
Crea una transcripción incorporando detalles del material fuente proporcionado:

Texto Fuente:
{{ text }}

Parámetros:
- Duración: {{ duration }} minutos (~{{ (duration * 180) | int }} palabras)
- Tema: {{ topic }}
- Áreas de Enfoque: {{ angles }}

Requisitos:
1. Integración de Contenido
  - Haz referencia a citas clave con nombre del hablante e institución
  - Explica la información citada en términos accesibles
  - Identifica consensos y desacuerdos entre las fuentes
  - Analiza el razonamiento detrás de diferentes puntos de vista

2. Presentación
  - Desglosa conceptos complejos para audiencia general
  - Usa analogías y ejemplos relevantes
  - Aborda preguntas anticipadas
  - Proporciona contexto necesario a lo largo del contenido
  - Mantén precisión factual, especialmente con números
  - Cubre todas las áreas de enfoque comprehensivamente dentro del límite de tiempo

Asegura cobertura exhaustiva de cada tema mientras preservas la precisión y matices del material fuente.
"""

# Template for generating transcript without source references
PODCAST_PROMPT_NO_REFERENCES_STR = """
Crea una transcripción basada en conocimiento siguiendo este esquema:

Parámetros:
- Duración: {{ duration }} minutos (~{{ (duration * 180) | int }} palabras)
- Tema: {{ topic }}
- Áreas de Enfoque: {{ angles }}

1. Lluvia de Ideas de Conocimiento
   - Mapea el panorama del conocimiento disponible
   - Identifica principios y marcos clave
   - Nota debates importantes y perspectivas
   - Lista ejemplos y aplicaciones relevantes
   - Considera contexto histórico y desarrollo

2. Desarrollo de Contenido
   - Extrae de una base de conocimiento comprehensiva
   - Presenta puntos de vista equilibrados
   - Apoya afirmaciones con razonamiento claro
   - Conecta temas lógicamente
   - Construye entendimiento progresivamente

3. Presentación
   - Desglosa conceptos complejos para audiencia general
   - Usa analogías y ejemplos relevantes
   - Aborda preguntas anticipadas
   - Proporciona contexto necesario a lo largo del contenido
   - Mantén precisión factual, especialmente con números
   - Cubre todas las áreas de enfoque comprehensivamente dentro del límite de tiempo

Desarrolla una exploración exhaustiva de cada tema usando el conocimiento disponible. Comienza con una lluvia de ideas cuidadosa para mapear conexiones entre ideas, luego construye una narrativa clara que haga conceptos complejos accesibles mientras mantiene precisión y completitud.
"""

# Template for converting transcript to dialogue format
PODCAST_TRANSCRIPT_TO_DIALOGUE_PROMPT_STR = """
Tu tarea es transformar la transcripción proporcionada en un diálogo de podcast atractivo e informativo.

Hay dos hablantes:

- **Anfitrión**: {{ speaker_1_name }}, el presentador del podcast.
- **Invitado**: {{ speaker_2_name }}, un experto en el tema.

**Instrucciones:**

- **Pautas de Contenido:**
    - Presenta la información de manera clara y precisa.
    - Explica términos complejos o conceptos en lenguaje simple.
    - Discute puntos clave, perspectivas y ideas de la transcripción.
    - Incluye el análisis experto y las perspectivas del invitado sobre el tema.
    - Incorpora citas relevantes, anécdotas y ejemplos de la transcripción.
    - Aborda preguntas comunes o preocupaciones relacionadas con el tema, si es aplicable.
    - Trae conflicto y desacuerdo a la discusión, pero converge hacia una conclusión.

- **Tono y Estilo:**
    - Mantén un tono profesional pero conversacional.
    - Usa lenguaje claro y conciso.
    - Incorpora patrones de habla naturales, incluyendo muletillas ocasionales (ej., "bueno," "sabes")—usadas con moderación y apropiadamente.
    - Asegura que el diálogo fluya suavemente, reflejando una conversación de la vida real.
    - Mantén un ritmo animado con una mezcla de discusión seria y momentos más ligeros.
    - Usa preguntas retóricas o hipotéticas para involucrar al oyente.
    - Crea momentos naturales de reflexión o énfasis.
    - Permite interrupciones naturales e intercambios entre anfitrión e invitado.

- **Pautas Adicionales:**
    - Menciona los nombres de los hablantes ocasionalmente para hacer la conversación más natural.
    - Asegura que las respuestas del invitado estén respaldadas por el texto de entrada, evitando afirmaciones no sustentadas.
    - Evita monólogos largos; divide la información en intercambios interactivos.
    - Usa etiquetas de diálogo para expresar emociones (ej., "dijo emocionado", "respondió pensativamente") para guiar la síntesis de voz.
    - Busca autenticidad. Incluye:
        - Momentos de curiosidad genuina o sorpresa del anfitrión.
        - Instancias donde el invitado puede pausar para articular ideas complejas.
        - Momentos ligeros apropiados o humor.
        - Anécdotas personales breves que se relacionen con el tema (dentro de los límites de la transcripción).
    - No agregues nueva información que no esté presente en la transcripción.
    - No pierdas ninguna información o detalles de la transcripción.

**Detalles del Segmento:**

- Duración: Aproximadamente {{ duration }} minutos (~{{ (duration * 180) | int }} palabras).
- Tema: {{ descriptions }}

Debes mantener todas las analogías, historias, ejemplos y citas de la transcripción.

**Aquí está la transcripción:**

{{ text }}

**Por favor, transfórmala en un diálogo de podcast siguiendo las pautas anteriores.**

*Solo devuelve la transcripción completa del diálogo; no incluyas ninguna otra información como presupuesto de tiempo o nombres de segmentos.*
"""

# Template for combining multiple dialogue sections
PODCAST_COMBINE_DIALOGUES_PROMPT_STR = """Estás revisando una transcripción de podcast para hacerla más atractiva mientras preservas su contenido y estructura. Tienes acceso a tres elementos clave:

1. El esquema del podcast
<outline>
{{ outline }}
</outline>

2. La transcripción actual del diálogo
<dialogue>
{{ dialogue_transcript }}
</dialogue>

3. La siguiente sección a integrar
<next_section>
{{ next_section }}
</next_section>

Sección actual siendo integrada: {{ current_section }}

Tu tarea es:
- Integrar sin problemas la siguiente sección con el diálogo existente
- Mantener toda la información clave de ambas secciones
- Reducir cualquier redundancia mientras mantienes alta densidad de información
- Dividir monólogos largos en diálogo natural de ida y vuelta
- Limitar el turno de cada hablante a máximo 3 oraciones
- Mantener la conversación fluyendo naturalmente entre temas

Pautas clave:
- Evita frases de transición explícitas como "Bienvenidos de vuelta" o "Ahora discutamos"
- No agregues introducciones o conclusiones a mitad de conversación
- No señales cambios de sección en el diálogo
- Fusiona temas relacionados según el esquema
- Mantén el tono conversacional natural a lo largo del contenido

Por favor, produce la transcripción completa revisada del diálogo desde el principio, con la siguiente sección integrada sin problemas."""

# Template for converting dialogue to JSON format
PODCAST_DIALOGUE_PROMPT_STR = """Se te ha asignado convertir una transcripción de podcast en un formato JSON estructurado. Tienes:

1. Dos hablantes:
   - Hablante 1: {{ speaker_1_name }}
   - Hablante 2: {{ speaker_2_name }}

2. La transcripción original:
{{ text }}

3. Esquema de salida requerido:
{{ schema }}

Tu tarea es:
- Convertir la transcripción exactamente al formato JSON especificado
- Preservar todo el contenido del diálogo sin omisiones
- Mapear las líneas de {{ speaker_1_name }} a "speaker-1"
- Mapear las líneas de {{ speaker_2_name }} a "speaker-2"

Debes absolutamente, sin excepción:
- Usar caracteres Unicode apropiados directamente (ej., usar ' en lugar de \\u2019)
- Asegurar que todas las apostrofes, comillas y caracteres especiales estén formateados apropiadamente
- No escapar caracteres Unicode en la salida

Debes absolutamente, sin excepción:
- Convertir todos los números y símbolos a forma hablada:
  * Los números deben escribirse con palabras (ej., "mil" en lugar de "1000")
  * La moneda debe expresarse como "[cantidad] [unidad de moneda]" (ej., "mil dólares" en lugar de "$1000")
  * Los símbolos matemáticos deben hablarse (ej., "igual a" en lugar de "=", "más" en lugar de "+")
  * Los porcentajes deben hablarse como "por ciento" (ej., "cincuenta por ciento" en lugar de "50%")

Por favor, produce el JSON siguiendo el esquema proporcionado, manteniendo todos los detalles conversacionales y atribuciones de hablantes. La salida debe usar caracteres Unicode apropiados directamente, no secuencias escapadas. No produzcas nada más que el JSON."""

# Dictionary mapping prompt names to their template strings
PROMPT_TEMPLATES = {
    "podcast_summary_prompt": PODCAST_SUMMARY_PROMPT_STR,
    "podcast_multi_pdf_outline_prompt": PODCAST_MULTI_PDF_OUTLINE_PROMPT_STR,
    "podcast_multi_pdf_structured_outline_prompt": PODCAST_MULTI_PDF_STRUCUTRED_OUTLINE_PROMPT_STR,
    "podcast_prompt_with_references": PODCAST_PROMPT_WITH_REFERENCES_STR,
    "podcast_prompt_no_references": PODCAST_PROMPT_NO_REFERENCES_STR,
    "podcast_transcript_to_dialogue_prompt": PODCAST_TRANSCRIPT_TO_DIALOGUE_PROMPT_STR,
    "podcast_combine_dialogues_prompt": PODCAST_COMBINE_DIALOGUES_PROMPT_STR,
    "podcast_dialogue_prompt": PODCAST_DIALOGUE_PROMPT_STR,
}

# Create Jinja templates once
TEMPLATES: Dict[str, jinja2.Template] = {
    name: jinja2.Template(template) for name, template in PROMPT_TEMPLATES.items()
}


class PodcastPrompts:
    """
    A class providing access to podcast-related prompt templates.
    
    This class manages a collection of Jinja2 templates used for generating
    various prompts in the podcast creation process, from PDF summarization
    to dialogue generation.

    The templates are pre-compiled for efficiency and can be accessed either
    through attribute access or the get_template class method.

    Attributes:
        None - Templates are stored in module-level constants

    Methods:
        __getattr__(name: str) -> str:
            Dynamically retrieves prompt template strings by name
        get_template(name: str) -> jinja2.Template:
            Retrieves pre-compiled Jinja2 templates by name
    """
    
    def __getattr__(self, name: str) -> str:
        """
        Dynamically retrieve prompt templates by name.

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
        Get a pre-compiled Jinja2 template by name.

        Args:
            name (str): Name of the template to retrieve

        Returns:
            jinja2.Template: The pre-compiled Jinja2 template object

        Raises:
            KeyError: If the requested template name doesn't exist
        """
        return TEMPLATES[name]
