import os
import json
import re
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dateutil.parser import parse
import google.generativeai as genai

# Configuración de Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('models/gemini-1.5-flash')
else:
    model = None

class NLPProcessor:
    def __init__(self, api_client):
        self.api_client = api_client
        self.team_synonyms = self._load_team_synonyms()
        self.tournament_synonyms = self._load_tournament_synonyms()
        self.bet_type_synonyms = self._load_bet_type_synonyms()
        
    def _load_team_synonyms(self):
        """Cargar sinónimos de equipos"""
        return {
            "barcelona": ["barça", "barca", "fc barcelona", "blaugrana"],
            "real madrid": ["real", "rm", "realmadrid", "madrid", "merengues"],
            "atletico madrid": ["atlético de madrid", "atletico", "atm", "atlético madrid", "atleti"],
            "lakers": ["los angeles lakers", "la lakers"],
            "celtics": ["boston celtics"],
            "bayern munich": ["bayern", "bayern múnich", "bayern munich"],
            "psg": ["paris saint germain", "paris sg"],
            "manchester city": ["man city", "mancity"],
            "liverpool": ["liverpool fc", "the reds"],
            "river plate": ["river", "riverplate"],
            "boca juniors": ["boca", "bocajuniors", "xeneizes"],
        }
    
    def _load_tournament_synonyms(self):
        """Cargar sinónimos de torneos"""
        return {
            "champions league": ["uefa champions league", "champions", "ucl"],
            "premier league": ["premier", "epl", "english premier league"],
            "liga española": ["la liga", "primera división", "laliga"],
            "nba": ["nba", "national basketball association"],
            "bundesliga": ["bundesliga", "liga alemana"],
            "serie a": ["serie a", "liga italiana"],
            "copa libertadores": ["libertadores", "copa libertadores"],
        }
    
    def _load_bet_type_synonyms(self):
        """Cargar sinónimos de tipos de apuesta"""
        return {
            "moneyline": ["moneyline", "ganador", "winner", "victoria", "vencedor"],
            "spread": ["spread", "handicap", "handicap asiático", "ventaja", "hándicap"],
            "over/under": ["over/under", "total goles", "total puntos", "ambos marcan", "gg", "goles"],
            "parlay": ["parlay", "combinada", "múltiple", "combinado"],
            "prop bet": ["prop bet", "apuesta de propuesta", "jugador específico", "propuesta"],
        }
    
    def normalize_team_name(self, team_name):
        """Normalizar nombre de equipo usando sinónimos"""
        team_name_lower = team_name.lower()
        for canonical_name, synonyms in self.team_synonyms.items():
            if team_name_lower in synonyms or team_name_lower == canonical_name:
                return canonical_name
        return team_name
    
    def normalize_tournament_name(self, tournament_name):
        """Normalizar nombre de torneo usando sinónimos"""
        tournament_name_lower = tournament_name.lower()
        for canonical_name, synonyms in self.tournament_synonyms.items():
            if tournament_name_lower in synonyms or tournament_name_lower == canonical_name:
                return canonical_name
        return tournament_name
    
    def normalize_bet_type(self, bet_type):
        """Normalizar tipo de apuesta usando sinónimos"""
        bet_type_lower = bet_type.lower()
        for canonical_name, synonyms in self.bet_type_synonyms.items():
            if bet_type_lower in synonyms or bet_type_lower == canonical_name:
                return canonical_name
        return bet_type
    
    async def extract_entities(self, query):
        """Extraer entidades usando Gemini 1.5 Flash"""
        if model:
            try:
                return await self._extract_entities_with_gemini(query)
            except Exception as e:
                print(f"Error con Gemini: {e}")
                return self._extract_entities_fallback(query)
        else:
            return self._extract_entities_fallback(query)
    
    async def extract_entities_enhanced(self, query):
        """Extracción de entidades mejorada con validación contra API"""
        # Primero, extraer entidades básicas
        basic_entities = await self.extract_entities(query)
        
        # Validar y normalizar equipos
        if basic_entities.get("teams"):
            validated_teams = []
            for team in basic_entities["teams"]:
                normalized_team = self.normalize_team_name(team)
                validated_teams.append(normalized_team)
            
            basic_entities["teams"] = validated_teams
        
        # Validar y normalizar torneos
        if basic_entities.get("tournaments"):
            validated_tournaments = []
            for tournament in basic_entities["tournaments"]:
                normalized_tournament = self.normalize_tournament_name(tournament)
                validated_tournaments.append(normalized_tournament)
            
            basic_entities["tournaments"] = validated_tournaments
        
        # Validar y normalizar tipos de apuesta
        if basic_entities.get("bet_types"):
            validated_bet_types = []
            for bet_type in basic_entities["bet_types"]:
                normalized_bet_type = self.normalize_bet_type(bet_type)
                validated_bet_types.append(normalized_bet_type)
            
            basic_entities["bet_types"] = validated_bet_types
        
        return basic_entities
    
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
        for team, aliases in self.team_synonyms.items():
            if any(alias in query_lower for alias in aliases):
                entities["teams"].append(team)
        
        # Detectar torneos
        for tournament, aliases in self.tournament_synonyms.items():
            if any(alias in query_lower for alias in aliases):
                entities["tournaments"].append(tournament)
        
        # Detectar fechas
        entities["dates"] = self._extract_dates_with_regex(query)
        
        # Detectar tipos de apuesta
        for bet_type, aliases in self.bet_type_synonyms.items():
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
    
    def _extract_dates_with_regex(self, query):
        """Extracción de fechas usando expresiones regulares avanzadas"""
        date_patterns = [
            r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b',  # DD/MM/YYYY
            r'\b(\d{1,2}\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+\d{4})\b',  # 15 octubre 2023
            r'\b(?:este|pr[oó]ximo)\s+(lunes|martes|mi[ée]rcoles|jueves|viernes|s[áa]bado|domingo)\b',
            r'\b(hoy|mañana|pasado\s+mañana)\b'
        ]
        
        dates = []
        for pattern in date_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            for match in matches:
                try:
                    if isinstance(match, tuple):
                        match = match[0]
                    parsed_date = parse(match, fuzzy=True)
                    dates.append(parsed_date.strftime("%Y-%m-%d"))
                except:
                    continue
        
        # Añadir fechas relativas comunes
        if "hoy" in query.lower():
            dates.append(datetime.now().strftime("%Y-%m-%d"))
        if "mañana" in query.lower():
            dates.append((datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"))
        if "fin de semana" in query.lower():
            dates.append(self._get_next_weekend())
        
        return list(set(dates))  # Eliminar duplicados
    
    def _get_next_weekend(self):
        today = datetime.now()
        days_until_saturday = (5 - today.weekday()) % 7
        return (today + timedelta(days=days_until_saturday)).strftime("%Y-%m-%d")
    
    async def get_relevant_data(self, entities):
        """Obtener datos relevantes de la API basados en las entidades"""
        data = {}
        
        # Obtener fixtures con filtros
        sport = None  # Podemos intentar determinar el deporte basado en las entidades
        tournament = entities.get("tournaments")[0] if entities.get("tournaments") else None
        date = entities.get("dates")[0] if entities.get("dates") else None
        
        data["fixtures"] = await self.api_client.get_fixtures(sport, tournament, date)
        
        # Si no hay fixtures, intentar obtener odds directamente
        if not data["fixtures"]:
            print("No se encontraron fixtures, obteniendo odds directamente...")
            data["odds"] = await self.api_client.get_odds(sport, tournament, None)
        else:
            # Filtrar fixtures por equipos si hay entidades de equipos
            if entities.get("teams"):
                filtered_fixtures = []
                for fixture in data["fixtures"]:
                    # Verificar si el fixture tiene campos de equipos
                    if isinstance(fixture, dict):
                        # Buscar nombres de equipos en diferentes campos posibles
                        home_team = fixture.get("home_team") or fixture.get("homeTeam") or fixture.get("home") or ""
                        away_team = fixture.get("away_team") or fixture.get("awayTeam") or fixture.get("away") or ""
                        
                        # Convertir a minúsculas para comparación
                        home_team_lower = home_team.lower()
                        away_team_lower = away_team.lower()
                        
                        # Verificar si algún equipo de la entidad está en los nombres de los equipos
                        for team in entities["teams"]:
                            team_lower = team.lower()
                            if team_lower in home_team_lower or team_lower in away_team_lower:
                                filtered_fixtures.append(fixture)
                                break
                
                data["fixtures"] = filtered_fixtures
            
            # Obtener odds con filtros
            fixture_id = None
            if data["fixtures"]:
                # Intentar obtener el ID del primer fixture
                fixture = data["fixtures"][0]
                fixture_id = fixture.get("id") or fixture.get("fixture_id") or fixture.get("_id")
            
            data["odds"] = await self.api_client.get_odds(sport, tournament, fixture_id)
        
        return data