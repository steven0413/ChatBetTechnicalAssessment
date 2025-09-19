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
                        # Probar si la respuesta es JSON
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
            
        result = await self.make_request("/sports/fixtures", params)
        
        # Loggear la estructura de la respuesta para debugging
        if result:
            print(f"Estructura de fixtures: {json.dumps(result, indent=2)[:500]}...")
        
        # Manejar diferentes formatos de respuesta
        if result is None:
            return []
        
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
        
        return []
    
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
            
        result = await self.make_request("/sports/odds", params)
        
        # Loggear la estructura de la respuesta para debugging
        if result:
            print(f"Estructura de odds: {json.dumps(result, indent=2)[:500]}...")
        
        # Manejar diferentes formatos de respuesta
        if result is None:
            return []
        
        # Si la respuesta es una lista, devolverla directamente
        if isinstance(result, list):
            return result
        
        # Si la respuesta es un diccionario, buscar la clave que contiene las odds
        if isinstance(result, dict):
            # Buscar posibles claves que contengan las odds
            for key in ['odds', 'data', 'prices', 'quotes']:
                if key in result and isinstance(result[key], list):
                    return result[key]
            
            # Si no encuentra una clave específica, devolver todos los valores que sean listas
            for value in result.values():
                if isinstance(value, list):
                    return value
        
        return []
    
    async def is_connected(self):
        """Verificar conexión con la API"""
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{self.base_url}/sports") as response:
                    return response.status == 200
        except:
            return False