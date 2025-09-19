import aiohttp
import asyncio
from typing import Dict, List, Any, Optional

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
        # Manejar caso donde la API devuelve datos vacíos
        if result and hasattr(result, 'get') and result.get('totalResults') == 0:
            return []
        return result
    
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
            
        return await self.make_request("/sports/odds", params)
    
    async def is_connected(self):
        """Verificar conexión con la API"""
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{self.base_url}/sports") as response:
                    return response.status == 200
        except:
            return False