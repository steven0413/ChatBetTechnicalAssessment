import aiohttp
import asyncio
from typing import Dict, List, Any, Optional
import json

class SportsAPIClient:
    def __init__(self, base_url):
        self.base_url = base_url
        
    async def make_request(self, endpoint, params=None):
        """Realizar solicitud a la API pública"""
        timeout = aiohttp.ClientTimeout(total=30)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    f"{self.base_url}{endpoint}",
                    params=params or {}
                ) as response:
                    if response.status == 200:
                        # Intentar parsear como JSON
                        try:
                            return await response.json()
                        except:
                            # Si falla el JSON, devolver el texto
                            text = await response.text()
                            print(f"Respuesta no JSON de {endpoint}: {text[:200]}...")
                            return None
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
        """Obtener deportes disponibles"""
        return await self.make_request("/sports")
    
    async def get_fixtures(self, sport=None, tournament=None, date=None):
        """Obtener partidos con filtros opcionales"""
        params = {}
        if sport:
            params["sport"] = sport
        if tournament:
            params["tournament"] = tournament
        if date:
            params["date"] = date
            
        # Inicializar result con un valor por defecto
        result = None
        
        try:
            result = await self.make_request("/sports/fixtures", params)
        except Exception as e:
            print(f"Error al obtener fixtures: {e}")
            result = None
        
        # Si no hay resultado o la respuesta está vacía, usar datos de demostración
        if result is None or (isinstance(result, dict) and result.get('totalResults') == 0):
            print("API devolvió respuesta vacía, usando datos de demostración...")
            return await self.get_demo_data("/sports/fixtures")
        
        # Loggear la estructura de la respuesta para debugging
        print(f"Estructura de fixtures: {json.dumps(result, indent=2)[:500]}...")
        
        # Manejar diferentes formatos de respuesta
        if result is None:
            return await self.get_demo_data("/sports/fixtures")
        
        # Si la respuesta es una lista, devolverla directamente
        if isinstance(result, list):
            return result
        
        # Si la respuesta es un diccionario, buscar la clave que contiene los fixtures
        if isinstance(result, dict):
            # Buscar posibles claves que contengan los fixtures
            for key in ['fixtures', 'data', 'matches', 'events', 'games']:
                if key in result and isinstance(result[key], list):
                    return result[key]
            
            # Si no encuentra una clave específica, devolver todos los valores que sean listas
            for value in result.values():
                if isinstance(value, list):
                    return value
        
        # Si no se pudo procesar, usar datos de demostración
        return await self.get_demo_data("/sports/fixtures")
    
    async def get_tournaments(self, sport=None):
        """Obtener torneos"""
        params = {}
        if sport:
            params["sport"] = sport
            
        return await self.make_request("/sports/tournaments", params)
    
    async def get_odds(self, sport=None, tournament=None, fixture_id=None):
        """Obtener odds con filtros"""
        params = {}
        if sport:
            params["sport"] = sport
        if tournament:
            params["tournament"] = tournament
        if fixture_id:
            params["fixture_id"] = fixture_id
            
        # Inicializar result con un valor por defecto
        result = None
        
        try:
            result = await self.make_request("/sports/odds", params)
        except Exception as e:
            print(f"Error al obtener odds: {e}")
            result = None
        
        # Si no hay resultado o la respuesta está vacía/inactiva, usar datos de demostración
        if result is None or (isinstance(result, dict) and result.get('status') == 'Inactive'):
            print("API devolvió odds inactivas o vacías, usando datos de demostración...")
            return await self.get_demo_data("/sports/odds")
        
        # Loggear la estructura de la respuesta para debugging
        print(f"Estructura de odds: {json.dumps(result, indent=2)[:500]}...")
        
        # Manejar diferentes formatos de respuesta
        if result is None:
            return await self.get_demo_data("/sports/odds")
        
        # Si la respuesta es una lista, devolverla directamente
        if isinstance(result, list):
            return result
        
        # Si la respuesta es un diccionario, convertirlo en una lista con un elemento
        if isinstance(result, dict):
            return [result]
        
        # Si no se pudo procesar, usar datos de demostración
        return await self.get_demo_data("/sports/odds")
    
    async def is_connected(self):
        """Verificar conexión con la API"""
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{self.base_url}/sports") as response:
                    return response.status == 200
        except:
            return False

    async def get_demo_data(self, endpoint):
        """Datos de demostración para desarrollo cuando la API no devuelve datos"""
        demo_data = {
            "/sports/fixtures": [
                {
                    "id": 1,
                    "home_team": "Barcelona",
                    "away_team": "Real Madrid",
                    "date": "2024-03-20",
                    "time": "20:00",
                    "tournament": "La Liga",
                    "status": "Scheduled"
                },
                {
                    "id": 2,
                    "home_team": "Liverpool",
                    "away_team": "Manchester City",
                    "date": "2024-03-21",
                    "time": "19:45",
                    "tournament": "Premier League",
                    "status": "Scheduled"
                },
                {
                    "id": 3,
                    "home_team": "New York Yankees",
                    "away_team": "Boston Red Sox",
                    "date": "2024-03-22",
                    "time": "18:05",
                    "tournament": "MLB",
                    "status": "Scheduled"
                },
                {
                    "id": 4,
                    "home_team": "LA Lakers",
                    "away_team": "Chicago Bulls",
                    "date": "2024-03-23",
                    "time": "20:30",
                    "tournament": "NBA",
                    "status": "Scheduled"
                }
            ],
            "/sports/odds": [
                {
                    "fixture_id": 1,
                    "home_team": "Barcelona",
                    "away_team": "Real Madrid",
                    "status": "Active",
                    "odds": {
                        "home_win": 2.1,
                        "draw": 3.2,
                        "away_win": 3.5
                    }
                },
                {
                    "fixture_id": 3,
                    "home_team": "New York Yankees",
                    "away_team": "Boston Red Sox",
                    "status": "Active",
                    "odds": {
                        "home_win": 1.8,
                        "away_win": 2.0
                    }
                },
                {
                    "fixture_id": 4,
                    "home_team": "LA Lakers",
                    "away_team": "Chicago Bulls",
                    "status": "Active",
                    "odds": {
                        "home_win": 1.5,
                        "away_win": 2.5
                    }
                }
            ]
        }
        
        return demo_data.get(endpoint, [])