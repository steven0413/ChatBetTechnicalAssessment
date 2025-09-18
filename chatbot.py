import os
import json
import aiohttp
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import google.generativeai as genai
from collections import defaultdict

# Configuración de Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('models/gemini-1.5-flash')
else:
    model = None

class SportsAPIClient:
    def __init__(self, base_url):
        self.base_url = base_url
        
    async def make_request(self, endpoint, params=None):
        timeout = aiohttp.ClientTimeout(total=30)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    f"{self.base_url}{endpoint}",
                    params=params or {}
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        print(f"Error en API request: {response.status}")
                        return None
        except asyncio.TimeoutError:
            print(f"Timeout al conectar con {endpoint}")
            return None
        except Exception as e:
            print(f"Error en API request: {e}")
            return None
    
    async def get_sports(self):
        return await self.make_request("/sports")
    
    async def get_fixtures(self):
        return await self.make_request("/sports/fixtures")
    
    async def get_odds(self):
        return await self.make_request("/sports/odds")
    
    async def is_connected(self):
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{self.base_url}/sports") as response:
                    return response.status == 200
        except:
            return False

class ConversationContextManager:
    def __init__(self):
        self.contexts = defaultdict(dict)
        
    def get_context(self, session_id):
        return self.contexts.get(session_id, {})
    
    def update_context(self, session_id, key, value):
        if session_id not in self.contexts:
            self.contexts[session_id] = {}
        self.contexts[session_id][key] = value
        
    def clear_context(self, session_id):
        if session_id in self.contexts:
            del self.contexts[session_id]

class NLPProcessor:
    def __init__(self, api_client):
        self.api_client = api_client
        
    async def extract_entities(self, query):
        # Usar Gemini 1.5 Flash para análisis avanzado de entidades
        if model:
            try:
                return await self._extract_entities_with_gemini(query)
            except Exception as e:
                print(f"Error con Gemini: {e}")
                return self._extract_entities_fallback(query)
        else:
            return self._extract_entities_fallback(query)
    
    async def _extract_entities_with_gemini(self, query):
        prompt = """
        Eres un analista deportivo y de apuestas experto para ChatBet, una startup de apuestas impulsada por IA que opera a través de aplicaciones de mensajería como WhatsApp y Telegram. Tu función es procesar la solicitud del usuario para identificar y categorizar los componentes clave de su consulta. Debes extraer los datos relevantes (equipos, torneos, fechas, tipos de apuesta y el propósito de la pregunta) y devolverlos estrictamente en el formato JSON especificado a continuación. Tu respuesta debe ser solo el objeto JSON, sin texto explicativo adicional.
        
        ADVERTENCIA DE RESPONSABILIDAD
        La información proporcionada es para fines de análisis y entretenimiento. Las apuestas deportivas conllevan un riesgo financiero. No hay garantía de ganancias. Los usuarios deben apostar de forma responsable y solo con dinero que puedan permitirse perder.

        Proceso de Extracción y Clasificación:
        Análisis de la Solicitud: Lee la solicitud del usuario e identifica los siguientes elementos:
        - Equipos/Jugadores: Nombres de los equipos o jugadores mencionados.
        - Torneos: Nombres de las ligas, copas o torneos.
        - Fechas: Cualquier fecha o rango de fechas relevante.
        - Tipos de Apuesta: Términos de apuestas como "Moneyline", "Spread", "Over/Under", etc.
        - Tipo de Pregunta: Clasifica el propósito de la pregunta en categorías como:
          * "Análisis y Recomendación" (si pide análisis de un partido y una sugerencia de apuesta).
          * "Estadísticas" (si pide datos específicos como "goles de [jugador]" o "récord de [equipo]").
          * "Información General" (para consultas no relacionadas con un evento o análisis específico).

        Manejo de la Ausencia de Datos: Si un elemento no se menciona en la solicitud del usuario, su array correspondiente debe quedar vacío ([]) y el campo question_type debe reflejar la naturaleza de la pregunta.

        Formato de Salida JSON:
        Genera la respuesta únicamente en formato JSON, adhiriéndote estrictamente a la siguiente estructura. La salida debe ser solo el objeto JSON, sin ningún otro texto.

        Devuelve SOLO un objeto JSON con esta estructura:
        {
            "teams": [],
            "tournaments": [],
            "dates": [],
            "bet_types": [],
            "question_type": ""
        }
        """
        
        full_prompt = f"{prompt}\n\nConsulta del usuario: {query}"
        
        response = model.generate_content(full_prompt)
        response_text = response.text.strip()
        
        # Limpiar la respuesta para obtener solo el JSON
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        return json.loads(response_text)
    
    def _extract_entities_fallback(self, query):
        query_lower = query.lower()
        entities = {
            "teams": [],
            "tournaments": [],
            "dates": [],
            "bet_types": [],
            "question_type": "general"
        }
        
        # Detectar si es una pregunta no relacionada con deportes
        non_sports_keywords = ["tiempo", "clima", "noticias", "noticia", "política", "entretenimiento", 
                              "música", "película", "series", "tecnología", "ciencia", "historia"]
        
        if any(keyword in query_lower for keyword in non_sports_keywords):
            entities["question_type"] = "non_sports"
            return entities
        
        # Detectar equipos
        team_aliases = {
            "atletico madrid": ["atlético de madrid", "atletico", "atm", "atlético madrid", "atleti"],
            "barcelona": ["barça", "barca", "fc barcelona"],
            "real madrid": ["real", "rm", "realmadrid", "madrid"],
            "lakers": ["los angeles lakers", "la lakers", "lakers"],
            "celtics": ["boston celtics", "celtics"],
            "bayern munich": ["bayern", "bayern múnich", "bayern munich"],
            "psg": ["paris saint germain", "paris sg", "psg"],
            "manchester city": ["man city", "mancity"],
            "liverpool": ["liverpool fc", "the reds"],
            "river plate": ["river", "riverplate"],
            "boca juniors": ["boca", "bocajuniors", "xeneizes"],
        }
        
        for team, aliases in team_aliases.items():
            if any(alias in query_lower for alias in aliases):
                entities["teams"].append(team)
        
        # Detectar torneos
        tournament_aliases = {
            "champions league": ["uefa champions league", "champions", "ucl"],
            "premier league": ["premier", "epl"],
            "liga española": ["la liga", "primera división", "laliga"],
            "nba": ["nba", "national basketball association"],
            "bundesliga": ["bundesliga", "liga alemana"],
            "serie a": ["serie a", "liga italiana"],
            "copa libertadores": ["libertadores", "copa libertadores"],
        }
        
        for tournament, aliases in tournament_aliases.items():
            if any(alias in query_lower for alias in aliases):
                entities["tournaments"].append(tournament)
        
        # Detectar fechas
        date_patterns = {
            "hoy": datetime.now().strftime("%Y-%m-%d"),
            "mañana": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
            "fin de semana": self._get_next_weekend(),
            "próxima semana": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        }
        
        for pattern, date_value in date_patterns.items():
            if pattern in query_lower:
                entities["dates"].append(date_value)
        
        # Detectar tipos de apuesta
        bet_type_aliases = {
            "moneyline": ["moneyline", "ganador", "winner", "victoria"],
            "spread": ["spread", "handicap", "handicap asiático", "ventaja"],
            "over/under": ["over/under", "total goles", "total puntos", "ambos marcan", "gg"],
            "parlay": ["parlay", "combinada", "múltiple"],
            "prop bet": ["prop bet", "apuesta de propuesta", "jugador específico"],
        }
        
        for bet_type, aliases in bet_type_aliases.items():
            if any(alias in query_lower for alias in aliases):
                entities["bet_types"].append(bet_type)
        
        # Detectar tipo de pregunta
        question_patterns = {
            "análisis y recomendación": ["analiza", "recomienda", "recomendación", "predice", "pronóstico", "qué apuesta"],
            "estadísticas": ["estadísticas", "estadisticas", "datos", "números", "récord", "record", "historial"],
            "información general": ["quién", "qué", "cuándo", "dónde", "cómo", "información", "details"]
        }
        
        for q_type, patterns in question_patterns.items():
            if any(pattern in query_lower for pattern in patterns):
                entities["question_type"] = q_type
                break
        
        # Si no se detectó un tipo específico, usar "información general"
        if entities["question_type"] == "general":
            entities["question_type"] = "información general"
        
        return entities
    
    def _get_next_weekend(self):
        today = datetime.now()
        days_until_saturday = (5 - today.weekday()) % 7
        return (today + timedelta(days=days_until_saturday)).strftime("%Y-%m-%d")
    
    async def get_relevant_data(self, entities):
        data = {}
        data["fixtures"] = await self.api_client.get_fixtures()
        data["odds"] = await self.api_client.get_odds()
        return data

class SportsBettingChatbot:
    def __init__(self, api_base_url):
        self.api_client = SportsAPIClient(api_base_url)
        self.nlp_processor = NLPProcessor(self.api_client)
        self.context_manager = ConversationContextManager()
        
    async def process_query(self, query, session_id="default"):
        try:
            # Extraer entidades
            entities = await self.nlp_processor.extract_entities(query)
            
            # Manejar preguntas no relacionadas con deportes
            if entities.get("question_type") == "non_sports":
                return self._generate_non_sports_response(query)
            
            # Obtener datos relevantes de la API
            relevant_data = await self.nlp_processor.get_relevant_data(entities)
            
            # Generar respuesta
            response = await self._generate_response_with_llm(query, entities, relevant_data, {})
            
            # Actualizar contexto
            self._update_context(session_id, entities, relevant_data)
            
            return response
        except Exception as e:
            print(f"Error processing query: {e}")
            return self._generate_error_response()
    
    async def _generate_response_with_llm(self, query, entities, relevant_data, context):
        # Determinar el tipo de deporte principal de la consulta
        sport_type = self._determine_sport_type(entities)
        
        prompt = f"""
        Eres un asistente de apuestas deportivas experto, resolutivo, pedagógico y profesional. Tu objetivo es proporcionar respuestas completas, 
        útiles y accionables para cualquier consulta relacionada con deportes y apuestas, incluso cuando la información 
        específica no esté disponible en tu base de datos actual.

        CONSULTA DEL USUARIO: {query}

        DEPORTE PRINCIPAL: {sport_type}

        ENTIDADES IDENTIFICADAS: {json.dumps(entities, ensure_ascii=False)}

        DATOS DISPONIBLES: {json.dumps(relevant_data, ensure_ascii=False)}

        CONTEXTO PREVIO: {json.dumps(context, ensure_ascii=False)}

        DIRECTRICES ESTRICTAS:
        1. **SÉ 100% RESOLUTIVO**: Nunca digas "no tengo información" o "no puedo ayudarte". Siempre proporciona valor.
        2. **USA INFORMACIÓN CONTEXTUAL**: Si no tienes datos específicos, usa conocimiento general del deporte.
        3. **PROPORCIONA RECOMENDACIONES ACCIONABLES**: Ofrece consejos concretos que el usuario pueda seguir.
        4. **MANTÉN CONVERSACIÓN FLUIDA**: Sé natural, amigable y conversacional.
        5. **EDUCA AL USUARIO**: Explica conceptos de apuestas cuando sea relevante.
        6. **GENERA CONFIANZA**: Usa lenguaje experto pero accesible.

        ESTRUCTURA DE RESPUESTA IDEAL:
        - Saludo amigable y reconocimiento de la consulta
        - Análisis/respuesta principal con información valiosa
        - Recomendaciones específicas y accionables
        - Explicación educativa cuando sea necesario
        - Próximos pasos o preguntas de seguimiento
        - Recordatorio de apuestas responsables

        Responde en español con un estilo conversacional pero informativo.
        """
        
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"Error con Gemini: {e}")
            return self._generate_resolutive_fallback(query, entities, relevant_data)
    
    def _determine_sport_type(self, entities):
        """Determina el tipo de deporte principal basado en las entidades"""
        if "nba" in [t.lower() for t in entities.get("tournaments", [])]:
            return "NBA/Baloncesto"
        elif any(t in ["champions league", "premier league", "liga española"] for t in entities.get("tournaments", [])):
            return "Fútbol"
        elif entities.get("teams"):
            # Determinar por nombres de equipos
            nba_teams = ["lakers", "celtics", "warriors", "bulls"]
            if any(team in nba_teams for team in entities["teams"]):
                return "NBA/Baloncesto"
            else:
                return "Fútbol"
        else:
            return "Deportes Generales"
    
    def _generate_resolutive_fallback(self, query, entities, relevant_data):
        """Genera una respuesta resolutiva cuando Gemini no está disponible"""
        query_lower = query.lower()
        
        # Respuesta para análisis y recomendación
        if entities.get("question_type") == "análisis y recomendación":
            return self._generate_resolutive_analysis_response(entities)
        
        # Respuesta para estadísticas
        elif entities.get("question_type") == "estadísticas":
            return self._generate_resolutive_stats_response(entities)
        
        # Respuesta para información general
        else:
            return self._generate_resolutive_general_response(entities, query)
    
    def _generate_resolutive_analysis_response(self, entities):
        """Genera una respuesta resolutiva para análisis y recomendaciones"""
        response = "🎯 **ANÁLISIS Y RECOMENDACIÓN EXPERTA**\n\n"
        
        if entities.get("teams"):
            teams = " vs ".join(entities["teams"])
            response += f"**Partido Analizado:** {teams}\n\n"
        
        response += "📊 **Factores Clave Considerados:**\n"
        response += "• Forma reciente de ambos equipos/jugadores\n"
        response += "• Historial de enfrentamientos directos\n"
        response += "• Lesiones y ausencias importantes\n"
        response += "• Contexto de la competición/torneo\n"
        response += "• Factor localía/visitante\n"
        response += "• Motivación y estado mental\n\n"
        
        response += "💡 **Recomendación de Apuesta Principal:**\n"
        if entities.get("bet_types"):
            main_bet = entities["bet_types"][0]
            response += f"**{main_bet.upper()}** - Esta opción ofrece el mejor valor según el análisis actual.\n\n"
        else:
            response += "**Moneyline (Ganador del Partido)** - Recomiendo analizar las cuotas del ganador directo.\n\n"
        
        response += "🎲 **Estrategias Recomendadas:**\n"
        response += "• Considera apuestas en vivo para aprovechar momentum changes\n"
        response += "• Diversifica con apuestas a mercados alternativos\n"
        response += "• Establece límites claros antes de apostar\n\n"
        
        response += "📈 **Pronóstico Experto:**\n"
        response += "Basado en el análisis integral, espero un encuentro competitivo donde [equipo/jugador] "\
                   "podría tener una ligera ventaja debido a [razón específica].\n\n"
        
        response += "⚠️ **Gestión de Riesgos:**\n"
        response += "• Solo arriesga el 1-2% de tu bankroll por apuesta\n"
        response += "• Considera esperar hasta cerca del inicio para mejores cuotas\n"
        response += "• Monitorea noticias de última hora sobre alineaciones\n\n"
        
        response += "¿Te gustaría que profundice en algún aspecto específico o prefieres que analice otras opciones de apuesta? 🏆"

        return response
    
    def _generate_resolutive_stats_response(self, entities):
        """Genera una respuesta resolutiva para consultas estadísticas"""
        response = "📊 **ANÁLISIS ESTADÍSTICO COMPLETO**\n\n"
        
        if entities.get("teams"):
            teams = ", ".join(entities["teams"])
            response += f"**Estadísticas Solicitadas:** {teams}\n\n"
        
        response += "📈 **Métricas Clave Analizadas:**\n"
        response += "• Rendimiento en los últimos 10 partidos\n"
        response += "• Eficiencia ofensiva y defensiva\n"
        response += "• Estadísticas en casa vs fuera\n"
        response += "• Tendencia de resultados recientes\n"
        response += "• Comparativa con promedio de la liga\n\n"
        
        response += "🔢 **Datos Estadísticos Relevantes:**\n"
        response += "• **Victorias/Derrotas:** [X]% de efectividad\n"
        response += "• **Puntos/Goles Anotados:** [X] por partido (avg)\n"
        response += "• **Puntos/Goles Recibidos:** [X] por partido (avg)\n"
        response += "• **Diferencial:** [+X] a favor del equipo\n"
        response += "• **Rendimiento en Crucial Moments:** [X]% de efectividad\n\n"
        
        response += "📋 **Tendencias Identificadas:**\n"
        response += "• Tendencia [alcista/bajista/estable] en rendimiento\n"
        response += "• Fortaleza particular en [aspecto específico]\n"
        response += "• Oportunidad de mejora en [área específica]\n"
        response += "• Correlación interesante entre [métrica A] y [métrica B]\n\n"
        
        response += "💡 **Aplicación Práctica:**\n"
        response += "Estas estadísticas sugieren que [conclusión accionable] para "\
                   "tus decisiones de apuestas. Recomiendo considerar [estrategia específica].\n\n"
        
        response += "¿Necesitas que profundice en alguna métrica específica o prefieres el análisis de otro aspecto? 📝"

        return response
    
    def _generate_resolutive_general_response(self, entities, query):
        """Genera una respuesta resolutiva para consultas generales"""
        response = "🏆 **INFORMACIÓN DEPORTIVA COMPLETA**\n\n"
        
        response += f"**Consulta:** {query}\n\n"
        
        response += "📋 **Contexto General:**\n"
        response += "Basándome en tu consulta, aquí tienes información completa y relevante:\n\n"
        
        if entities.get("teams"):
            teams = ", ".join(entities["teams"])
            response += f"**Equipos/Jugadores:** {teams}\n"
            response += "• Historial y logros relevantes\n"
            response += "• Situación actual en competiciones\n"
            response += "• Próximos desafíos y partidos\n\n"
        
        if entities.get("tournaments"):
            tournaments = ", ".join(entities["tournaments"])
            response += f"**Torneos/Competiciones:** {tournaments}\n"
            response += "• Formato y estructura de la competición\n"
            response += "• Equipos participantes y favoritos\n"
            response += "• Fechas clave y calendario\n\n"
        
        response += "💎 **Valor Añadido:**\n"
        response += "• **Factores Clave a Considerar:** [Aspectos importantes]\n"
        response += "• **Oportunidades Destacadas:** [Áreas de interés]\n"
        response += "• **Perspectiva Experta:** [Análisis profesional]\n\n"
        
        response += "🎯 **Recomendación Accionable:**\n"
        response += "Basado en esta información, te recomiendo [acción específica] "\
                   "para maximizar tus oportunidades en apuestas relacionadas.\n\n"
        
        response += "⚠️ **Recordatorio Importante:**\n"
        response += "• Las apuestas deben ser siempre responsables\n"
        response += "• Investiga múltiples fuentes antes de decidir\n"
        response += "• Establece límites claros de bankroll\n\n"
        
        response += "¿En qué otro aspecto te puedo ayudar o necesitas más detalles sobre algo específico? 🤔"

        return response
    
    def _generate_non_sports_response(self, query):
        """Genera una respuesta educada para consultas no deportivas"""
        return "¡Hola! 👋 Soy un asistente especializado exclusivamente en deportes y apuestas deportivas. 🏆\n\n" \
               "Puedo ayudarte con:\n" \
               "• Análisis de partidos y equipos 🏀⚽\n" \
               "• Recomendaciones de apuestas informadas 💰\n" \
               "• Estadísticas deportivas 📊\n" \
               "• Información sobre torneos y competiciones 🏅\n\n" \
               "¿En qué puedo ayudarte respecto a deportes o apuestas deportivas? 😊"
    
    def _generate_error_response(self):
        """Genera una respuesta para errores del sistema"""
        return "¡Vaya! 🔧 Estoy teniendo dificultades técnicas momentáneas, pero quiero ayudarte. \n\n" \
               "Mientras resuelvo esto, te puedo orientar sobre:\n" \
               "• Estrategias generales de apuestas deportivas 🎯\n" \
               "• Análisis de equipos y torneos populares 📈\n" \
               "• Conceptos clave de apuestas deportivas 💡\n\n" \
               "¿Sobre qué deporte o tipo de apuesta te gustaría conversar? 😊"
    
    def _update_context(self, session_id, entities, relevant_data):
        if "teams" in entities and entities["teams"]:
            self.context_manager.update_context(session_id, "last_mentioned_teams", entities["teams"])
        
        if "tournaments" in entities and entities["tournaments"]:
            self.context_manager.update_context(session_id, "last_mentioned_tournament", entities["tournaments"][0])
        
        if "bet_types" in entities and entities["bet_types"]:
            self.context_manager.update_context(session_id, "preferred_bet_types", entities["bet_types"])
    
    async def is_connected(self):
        return await self.api_client.is_connected()