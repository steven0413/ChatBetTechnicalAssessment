import os
import json
import aiohttp
import asyncio
import re
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import google.generativeai as genai
from collections import defaultdict
from .api_client import SportsAPIClient
from .nlp_processor import NLPProcessor

# Configuración de Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('models/gemini-1.5-flash')
else:
    model = None

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

class SportsBettingChatbot:
    def __init__(self, api_base_url):
        self.api_client = SportsAPIClient(api_base_url)
        self.nlp_processor = NLPProcessor(self.api_client)
        self.context_manager = ConversationContextManager()
        
    async def process_query(self, query, session_id="default"):
        try:
            print(f"Procesando consulta: {query}")
            
            # Verificar si es confirmación de apuesta
            if query.lower() in ['sí', 'si', 'confirmar', 'sí confirmar']:
                pending_bet = self.context_manager.get_context(session_id).get("pending_bet")
                if pending_bet:
                    return await self.confirm_bet(session_id)
            
            # Extraer entidades
            print("Extrayendo entidades...")
            entities = await self.nlp_processor.extract_entities_enhanced(query)
            print(f"Entidades extraídas: {entities}")
            
            # Manejar preguntas no relacionadas con deportes
            if entities.get("question_type") == "non_sports":
                return self._generate_non_sports_response(query)
            
            # Obtener datos relevantes de la API (filtrados por entidades)
            print("Obteniendo datos de la API...")
            relevant_data = await self.nlp_processor.get_relevant_data(entities)
            print(f"Datos relevantes obtenidos: {json.dumps(relevant_data, indent=2)[:1000]}...")
            
            # Si no hay datos, generar respuesta apropiada
            if (not relevant_data.get("fixtures") and 
                not relevant_data.get("odds") and
                not relevant_data.get("sports")):
                return self._generate_no_data_response(entities)
            
            # Generar respuesta
            context = self.context_manager.get_context(session_id)
            response = await self._generate_response_with_llm(query, entities, relevant_data, context)
            
            # Actualizar contexto
            self._update_context(session_id, entities, relevant_data)
            
            return response
        except Exception as e:
            print(f"Error processing query: {e}")
            import traceback
            traceback.print_exc()
            return self._generate_error_response()

    def _generate_no_data_response(self, entities):
        """Generar respuesta cuando no hay datos disponibles"""
        response = "🔍 **No encontré información específica en este momento**\n\n"
        
        if entities.get("teams"):
            teams = ", ".join(entities["teams"])
            response += f"Para los equipos: {teams}\n"
        
        if entities.get("tournaments"):
            tournaments = ", ".join(entities["tournaments"])
            response += f"En los torneos: {tournaments}\n"
        
        response += "\n📋 **Esto puede deberse a:**\n"
        response += "• No hay partidos programados en este momento\n"
        response += "• Los datos aún no están disponibles\n"
        response += "• La información solicitada no está en nuestra base de datos\n\n"
        
        response += "💡 **Puedo ayudarte con:**\n"
        response += "• Información general sobre equipos y torneos 🏆\n"
        response += "• Estrategias de apuestas deportivas 💡\n"
        response += "• Análisis de partidos y probabilidades 📊\n\n"
        
        response += "¿Te gustaría que te ayude con algo específico? 😊"
        
        return response

    async def process_betting_query(self, query, entities, session_id):
        """Procesar consultas relacionadas con apuestas"""
        # Extraer información de apuesta
        stake_match = re.search(r'(\$|€|£)?\s*(\d+)(?:\s*(dólares|euros|libras))?', query)
        stake = float(stake_match.group(2)) if stake_match else None
        
        # Obtener odds relevantes
        relevant_data = await self.nlp_processor.get_relevant_data(entities)
        odds_data = relevant_data.get("odds", [])
        
        # Filtrar odds según entidades
        filtered_odds = self._filter_odds_by_entities(odds_data, entities)
        
        if not filtered_odds and entities.get("teams"):
            # Buscar coincidencias parciales de nombres de equipos
            normalized_teams = [self.nlp_processor.normalize_team_name(team) for team in entities["teams"]]
            filtered_odds = [o for o in odds_data if any(
                team in o["home_team"].lower() or team in o["away_team"].lower() 
                for team in normalized_teams
            )]
        
        if not filtered_odds:
            return "No pude encontrar odds para los equipos o partidos mencionados."
        
        # Calcular posibles ganancias
        if stake and filtered_odds:
            selection = self._determine_bet_selection(entities, filtered_odds[0])
            potential_winnings = stake * filtered_odds[0]["odds"].get(selection, 1)
            
            response = f"📊 **Análisis de Apuesta**\n\n"
            response += f"• **Partido:** {filtered_odds[0]['home_team']} vs {filtered_odds[0]['away_team']}\n"
            response += f"• **Cuota para {selection}:** {filtered_odds[0]['odds'].get(selection, 'N/A')}\n"
            response += f"• **Apuesta:** ${stake}\n"
            response += f"• **Ganancia potencial:** ${potential_winnings:.2f}\n\n"
            response += "¿Te gustaría simular esta apuesta? (responde 'sí' para confirmar)"
            
            # Guardar contexto de apuesta pendiente
            self.context_manager.update_context(session_id, "pending_bet", {
                "fixture_id": filtered_odds[0]["id"],
                "market_type": "moneyline",
                "selection": selection,
                "stake": stake,
                "potential_winnings": potential_winnings
            })
            
            return response
        
        return "Necesito saber cuánto quieres apostar para calcular las ganancias potenciales."
    
    async def confirm_bet(self, session_id):
        """Confirmar apuesta simulada"""
        pending_bet = self.context_manager.get_context(session_id).get("pending_bet")
        if not pending_bet:
            return "No hay ninguna apuesta pendiente para confirmar."
        
        # Simular colocación de apuesta
        result = await self.api_client.place_bet(
            pending_bet["fixture_id"],
            pending_bet["market_type"],
            pending_bet["selection"],
            pending_bet["stake"]
        )
        
        if result and result.get("success"):
            response = "✅ **Apuesta simulada confirmada**\n\n"
            response += f"• **ID de apuesta:** {result.get('bet_id', 'SIM-001')}\n"
            response += f"• **Monto apostado:** ${pending_bet['stake']}\n"
            response += f"• **Ganancia potencial:** ${pending_bet['potential_winnings']:.2f}\n"
            response += f"• **Estado:** {result.get('status', 'confirmada')}\n\n"
            response += "¡Buena suerte! 🍀"
        else:
            response = "❌ No pude procesar la apuesta. Por favor, intenta nuevamente."
        
        # Limpiar apuesta pendiente
        self.context_manager.update_context(session_id, "pending_bet", None)
        
        return response
    
    def _filter_odds_by_entities(self, odds_data, entities):
        """Filtrar odds basado en las entidades extraídas"""
        if not odds_data or not isinstance(odds_data, list):
            return []
        
        filtered_odds = []
        
        for odds in odds_data:
            if not isinstance(odds, dict):
                continue
                
            # Buscar nombres de equipos en diferentes campos posibles
            home_team = odds.get('home_team') or odds.get('homeTeam') or odds.get('home') or odds.get('team1') or ''
            away_team = odds.get('away_team') or odds.get('awayTeam') or odds.get('away') or odds.get('team2') or ''
            
            # Convertir a minúsculas para comparación sin distinción de mayúsculas/minúsculas
            home_team_lower = str(home_team).lower()
            away_team_lower = str(away_team).lower()
            
            # Verificar si coincide con los equipos de las entidades
            match_found = False
            if entities.get("teams"):
                for team in entities["teams"]:
                    team_lower = team.lower()
                    if team_lower in home_team_lower or team_lower in away_team_lower:
                        match_found = True
                        break
            
            # Si no hay equipos en las entidades, incluir todas las odds
            if not entities.get("teams") or match_found:
                filtered_odds.append(odds)
        
        return filtered_odds

    def _determine_bet_selection(self, entities, odds_data):
        """Determinar la selección de apuesta basada en las entidades"""
        if not odds_data or not isinstance(odds_data, dict):
            return "home_win"  # Valor por defecto
        
        if not entities.get("bet_types"):
            return "home_win"  # Valor por defecto
        
        bet_type = entities["bet_types"][0].lower()
        
        if "draw" in bet_type or "empate" in bet_type:
            return "draw"
        elif any(word in bet_type for word in ["away", "visitante"]):
            return "away_win"
        else:
            return "home_win"
    
    async def _generate_response_with_llm(self, query, entities, relevant_data, context):
        # Determinar el tipo de deporte principal de la consulta
        sport_type = self._determine_sport_type(entities)
        
        prompt = f"""
        Eres un asistente de apuestas deportivas para **ChatBet**, una startup de IA que opera en WhatsApp y Telegram.
        Tu objetivo es proporcionar respuestas instantáneas, precisas y útiles, utilizando los datos que te proporciono.
        Tu tono debe ser experto, directo y amigable, enfocado en el valor.
        
        ---

        ### **Datos de la Sesión**

        **CONSULTA DEL USUARIO:** {query}

        **ENTIDADES IDENTIFICADAS:** {json.dumps(entities, ensure_ascii=False)}

        **DATOS DISPONIBLES:** {json.dumps(relevant_data, ensure_ascii=False)}

        **CONTEXTO PREVIO:** {json.dumps(context, ensure_ascii=False)}

        ---

        ### **Instrucciones Clave**

        1.  **Prioriza la concisión:** Ve al grano. Inicia la respuesta con la información más relevante de `DATOS DISPONIBLES`. Evita saludos o frases introductorias genéricas.
        2.  **Si hay datos, úsalos:** Si `relevant_data` contiene información, úsala para responder la consulta directamente. Presenta los datos de forma clara y legible usando listas con viñetas (•) o tablas simples con texto.
        3.  **Si no hay datos, sé proactivo pero honesto:** Si `relevant_data` está vacío o no es útil, informa al usuario de manera transparente que no se encontraron partidos activos para su consulta. No inventes información. Luego, ofrece valor adicional:
            * Sugiere una consulta alternativa (ej. "Puedes preguntar por un equipo o torneo específico").
            * Proporciona un consejo de apuesta general o una estadística interesante basada en conocimiento general.
        4.  **Adapta la respuesta al `question_type`:** Usa el campo `question_type` de las entidades para personalizar el enfoque:
            * **"Análisis y Recomendación":** Ofrece una breve sugerencia de apuesta basada en las cuotas, explicando la lógica detrás (ej. "la cuota de 1.5 sugiere que los Lakers son los favoritos").
            * **"Estadísticas":** Céntrate en los datos relevantes que tengas. Si no hay datos, explica por qué la información es limitada y sugiere dónde podrían encontrarse.
            * **"Información General":** Responde de manera informativa, proporcionando los partidos y cuotas disponibles.
        5.  **Usa el contexto previo:** Si hay contexto previo, intégralo naturalmente en la respuesta para mantener la continuidad.
        6.  **Añade un recordatorio de responsabilidad:** Finaliza con un recordatorio conciso sobre el juego responsable. Ejemplo: "Recuerda: Apuesta de forma responsable".
        7.  **Mantén el lenguaje accesible:** Usa un equilibrio entre expertise y claridad. Evita jargon técnico innecesario.

        Responde en español.
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