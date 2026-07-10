"""
engines/phone_engine.py
Motor de investigación OSINT asíncrono para números telefónicos.
"""
import asyncio
import aiohttp
import json
import re
from datetime import datetime
from config import (
    NUMVERIFY_KEY, SERPAPI_KEY,
    SOCIAL_SEARCHER_KEY, get_user_agent
)

# Semáforo para limitar concurrencia
SEMAPHORE_LIMIT = 15
semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)

# Mapeo de códigos de país a dominios de búsqueda locales
COUNTRY_SEARCH_DOMAINS = {
    "ES": "paginasblancas.es",
    "US": "whitepages.com",
    "MX": "paginasblancas.com.mx",
    "AR": "paginasdoradas.com",
    "BR": "listaonline.com.br",
    "UK": "yell.com",
    "FR": "pagesjaunes.fr",
    "DE": "dastelefonbuch.de",
    "IT": "paginebianche.it",
    "PT": "paginasbrancas.pt",
    "CO": "paginasamarillas.com.co",
    "CL": "paginasblancas.cl",
    "PE": "paginasblancas.com.pe",
}


async def _fetch(session, url, method="GET", headers=None, data=None, params=None, timeout=10):
    """Función auxiliar para peticiones HTTP con semáforo."""
    async with semaphore:
        try:
            async with session.request(
                method, url, headers=headers, data=data, params=params,
                timeout=aiohttp.ClientTimeout(total=timeout),
                allow_redirects=True
            ) as response:
                return {
                    "status": response.status,
                    "headers": dict(response.headers),
                    "text": await response.text(errors='ignore'),
                    "url": str(response.url)
                }
        except asyncio.TimeoutError:
            return {"status": 408, "error": "Timeout"}
        except aiohttp.ClientError as e:
            return {"status": 0, "error": str(e)}
        except Exception as e:
            return {"status": 0, "error": str(e)}


async def validar_numverify(telefono: str, session: aiohttp.ClientSession):
    """
    Valida el número con NumVerify para obtener país, operador y tipo de línea.
    """
    if not NUMVERIFY_KEY:
        print("\n[!] API Key de NumVerify no encontrada, omitiendo módulo...")
        return None
    
    print(f"\n[*] Validando con NumVerify: {telefono}")
    
    url = "http://apilayer.net/api/validate"
    params = {
        "access_key": NUMVERIFY_KEY,
        "number": telefono,
        "country_code": "",
        "format": 1
    }
    headers = {"User-Agent": get_user_agent()}
    
    response = await _fetch(session, url, headers=headers, params=params)
    
    if response["status"] == 200:
        try:
            data = json.loads(response["text"])
            
            if data.get("valid"):
                print(f"  [+] Número VÁLIDO")
                print(f"      País: {data.get('country_name', 'N/A')} ({data.get('country_code', 'N/A')})")
                print(f"      Ubicación: {data.get('location', 'N/A')}")
                print(f"      Operador: {data.get('carrier', 'N/A')}")
                print(f"      Tipo de línea: {data.get('line_type', 'N/A')}")
                
                # Advertencia si es VoIP
                line_type = data.get("line_type", "").lower()
                if line_type in ["voip", "google_voice", "virtual"]:
                    print(f"\n  [!] ADVERTENCIA: El número es de tipo VOIP/Virtual.")
                    print(f"      Es probable que sea temporal, anónimo o vinculado a servicios como Google Voice.")
                
                return data
            else:
                print(f"  [-] NumVerify indica que el número NO es válido")
                return None
        except json.JSONDecodeError:
            print(f"  [-] Error al parsear JSON de NumVerify")
    elif response["status"] == 401:
        print(f"  [!] API Key de NumVerify inválida")
    elif response["status"] == 429:
        print(f"  [!] Rate Limit de NumVerify alcanzado")
    else:
        print(f"  [!] NumVerify: Status {response.get('status', 'N/A')}")
    
    return None


async def buscar_social_searcher(telefono: str, session: aiohttp.ClientSession):
    """
    Busca menciones del número en redes sociales usando Social Searcher.
    """
    if not SOCIAL_SEARCHER_KEY:
        print("\n[!] API Key de Social Searcher no encontrada, omitiendo módulo...")
        return
    
    print(f"\n[*] Buscando menciones en redes con Social Searcher: {telefono}")
    
    url = "https://www.social-searcher.com/google-social-search/"
    params = {
        "q": telefono,
        "lang": "es"
    }
    headers = {
        "User-Agent": get_user_agent(),
        "Accept": "text/html,application/xhtml+xml"
    }
    
    response = await _fetch(session, url, headers=headers, params=params)
    
    if response["status"] == 200:
        # Social Searcher retorna HTML, extraemos menciones
        text = response["text"]
        
        # Buscar patrones de menciones (simple scraping)
        menciones = re.findall(r'<a[^>]+class="[^"]*result-link[^"]*"[^>]*>([^<]+)</a>', text)
        
        if menciones:
            print(f"  [+] Menciones encontradas: {len(menciones)}")
            for mencion in menciones[:10]:
                print(f"      - {mencion.strip()}")
        else:
            # Buscar texto plano
            if telefono in text:
                print(f"  [+] El número aparece en resultados de Social Searcher")
            else:
                print(f"  [-] No se encontraron menciones directas")
    else:
        print(f"  [!] Social Searcher: Status {response.get('status', 'N/A')}")


async def buscar_phoneinfoga_dorks(telefono: str, pais: str, session: aiohttp.ClientSession):
    """
    Genera dinámicamente Google Dorks basados en el país del número
    y los ejecuta mediante SerpApi.
    """
    if not SERPAPI_KEY:
        print("\n[!] API Key de SerpApi no encontrada, omitiendo módulo de Google Dorks...")
        return
    
    print(f"\n[*] Ejecutando Google Dorks estilo PhoneInfoga para: {telefono} (País: {pais})")
    
    # Obtener dominio de búsqueda del país
    search_domain = COUNTRY_SEARCH_DOMAINS.get(pais, "google.com")
    
    # Generar dorks dinámicos
    dorks = [
        f'"{telefono}"',
        f'site:{search_domain} "{telefono}"',
        f'site:facebook.com "{telefono}"',
        f'site:linkedin.com "{telefono}"',
        f'site:instagram.com "{telefono}"',
        f'site:twitter.com "{telefono}"',
        f'site:whatsapp.com "{telefono}"',
        f'site:t.me "{telefono}"',
        f'site:pagesjaunes.fr "{telefono}"' if pais == "FR" else f'site:paginasblancas.es "{telefono}"',
        f'inurl:contact "{telefono}"',
        f'"teléfono" "{telefono}"',
    ]
    
    base_url = "https://serpapi.com/search.json"
    
    for i, dork in enumerate(dorks[:5], 1):  # Limitar a 5 dorks
        print(f"\n  [+] Dork #{i}: {dork}")
        
        params = {
            "q": dork,
            "api_key": SERPAPI_KEY,
            "engine": "google",
            "num": 5
        }
        
        param_str = "&".join([f"{k}={v}" for k, v in params.items()])
        url = f"{base_url}?{param_str}"
        
        headers = {"User-Agent": get_user_agent()}
        response = await _fetch(session, url, headers=headers)
        
        if response["status"] == 200:
            try:
                data = json.loads(response["text"])
                results = data.get("organic_results", [])
                
                if results:
                    print(f"      Resultados encontrados: {len(results)}")
                    for result in results:
                        titulo = result.get("title", "Sin título")
                        link = result.get("link", "N/A")
                        snippet = result.get("snippet", "Sin descripción")[:100]
                        print(f"        - {titulo}")
                        print(f"          {link}")
                        print(f"          {snippet}...")
                else:
                    print(f"      Sin resultados")
            except json.JSONDecodeError:
                print(f"      [-] Error al parsear respuesta de SerpApi")
        else:
            print(f"      [!] SerpApi: Status {response.get('status', 'N/A')}")
        
        await asyncio.sleep(1)


async def validar_whatsapp_telegram(telefono: str, session: aiohttp.ClientSession):
    """
    Consulta endpoints públicos de WhatsApp y Telegram para verificar
    si el número tiene cuenta activa.
    """
    print(f"\n[*] Validando cuentas en WhatsApp y Telegram para: {telefono}")
    
    resultados = {}
    
    # WhatsApp: usar la API web (limitada, solo verifica existencia)
    print(f"\n  [+] WhatsApp:")
    try:
        # Eliminar el + y cualquier otro caracter no numérico
        numero_limpio = re.sub(r'\D', '', telefono)
        
        # Endpoint para verificar contacto (sin autenticación)
        wa_url = f"https://wa.me/{numero_limpio}"
        headers = {"User-Agent": get_user_agent()}
        
        response = await _fetch(session, wa_url, headers=headers, timeout=8)
        
        if response["status"] == 200:
            text = response["text"].lower()
            if "chat" in text or "whatsapp" in text:
                print(f"      [VINCULADA] WhatsApp tiene cuenta para este número")
                resultados["whatsapp"] = True
            else:
                print(f"      [?] Respuesta ambigua de WhatsApp")
                resultados["whatsapp"] = "maybe"
        elif response["status"] == 404:
            print(f"      [NO VINCULADA] No existe cuenta de WhatsApp")
            resultados["whatsapp"] = False
        else:
            print(f"      [!] Status: {response.get('status', 'N/A')}")
            resultados["whatsapp"] = "unknown"
    except Exception as e:
        print(f"      [!] Error: {e}")
    
    # Telegram: verificar username/numero
    print(f"\n  [+] Telegram:")
    try:
        # Telegram usa el número como @username en algunos casos
        # Intentamos con el número limpio
        numero_limpio = re.sub(r'\D', '', telefono)
        
        # Endpoint: t.me/<numero>
        tg_url = f"https://t.me/{numero_limpio}"
        headers = {"User-Agent": get_user_agent()}
        
        response = await _fetch(session, tg_url, headers=headers, timeout=8)
        
        if response["status"] == 200:
            text = response["text"].lower()
            if "if you have" in text or "telegram" in text and "not found" not in text:
                print(f"      [VINCULADA] Posible cuenta de Telegram vinculada")
                resultados["telegram"] = True
            elif "not found" in text or "404" in text:
                print(f"      [NO VINCULADA] No se encontró cuenta")
                resultados["telegram"] = False
            else:
                print(f"      [?] Respuesta ambigua")
                resultados["telegram"] = "maybe"
        elif response["status"] == 404:
            print(f"      [NO VINCULADA] No existe cuenta pública de Telegram")
            resultados["telegram"] = False
        else:
            print(f"      [!] Status: {response.get('status', 'N/A')}")
    except Exception as e:
        print(f"      [!] Error: {e}")
    
    return resultados


async def investigar_telefono_async(telefono: str):
    """
    Función asíncrona principal que coordina todas las investigaciones del teléfono.
    """
    print(f"\n{'='*60}")
    print(f"[+] INICIANDO INVESTIGACIÓN OSINT DE TELÉFONO: {telefono}")
    print(f"[+] Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    connector = aiohttp.TCPConnector(limit=SEMAPHORE_LIMIT, limit_per_host=5)
    timeout = aiohttp.ClientTimeout(total=120)
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        # 1. Validar con NumVerify
        datos_numverify = await validar_numverify(telefono, session)
        
        # 2. Extraer país para dorks dinámicos
        pais = "UNKNOWN"
        if datos_numverify and datos_numverify.get("country_code"):
            pais = datos_numverify["country_code"]
        
        # 3. Social Searcher
        await buscar_social_searcher(telefono, session)
        
        # 4. Google Dorks estilo PhoneInfoga
        await buscar_phoneinfoga_dorks(telefono, pais, session)
        
        # 5. Validar WhatsApp/Telegram
        await validar_whatsapp_telegram(telefono, session)
    
    print(f"\n{'='*60}")
    print(f"[+] INVESTIGACIÓN DE TELÉFONO COMPLETADA")
    print(f"{'='*60}")


def investigar_telefono(telefono: str):
    """
    Punto de entrada síncrono para el motor de teléfonos.
    Llamado desde la TUI a través de AccionPython.
    """
    from utils.validators import validar_telefono_e164, normalizar_telefono
    from utils.logger import setup_dual_logger
    
    # 1. Normalizar y validar
    print(f"[*] Validando teléfono: {telefono}")
    telefono_normalizado = normalizar_telefono(telefono)
    
    if not telefono_normalizado:
        print(f"[!] El teléfono NO tiene formato E.164 válido. Abortando.")
        return
    
    if not validar_telefono_e164(telefono_normalizado):
        print(f"[!] El teléfono normalizado {telefono_normalizado} NO es válido E.164. Abortando.")
        return
    
    print(f"[+] Teléfono validado en formato E.164: {telefono_normalizado}")
    
    # 2. Configurar Dual Logger (nombre limpio para archivo)
    nombre_archivo = telefono_normalizado.replace("+", "plus")
    logger = setup_dual_logger(nombre_archivo)
    
    try:
        # 3. Ejecutar motor asíncrono
        asyncio.run(investigar_telefono_async(telefono_normalizado))
    except KeyboardInterrupt:
        print("\n[!] Investigación interrumpida por el usuario")
    except Exception as e:
        print(f"\n[!] Error crítico en la investigación: {e}")
    finally:
        # 4. Cerrar logger
        logger.close()
        print(f"\n[+] Resultados guardados en archivo de log.")
