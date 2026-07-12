import asyncio
import aiohttp
import hashlib
import json
import re
import urllib.parse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from config import (
    HIBP_API_KEY, INTELX_API_KEY, SERPAPI_KEY,
    DEHASHED_KEY, DEHASHED_EMAIL, get_user_agent
)

# Límite de concurrencia para evitar bloqueos por WAF
SEMAPHORE_LIMIT = 15
semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)

# Lista de endpoints de redes sociales para la técnica Holehe
# Cada entrada: (nombre, url, método, indicador_de_existencia)
SOCIAL_ENDPOINTS = [
    # Instagram
    ("Instagram", "https://www.instagram.com/{email}/", "GET", None),
    # Twitter/X - búsqueda en perfiles
    ("Twitter/X", "https://twitter.com/search?q={email}&src=typed_query", "GET", None),
    # LinkedIn
    ("LinkedIn", "https://www.linkedin.com/pub/dir/{email}", "GET", None),
    # Facebook
    ("Facebook", "https://www.facebook.com/search/top/?q={email}", "GET", None),
    # GitHub (API pública)
    ("GitHub", "https://api.github.com/search/users?q={email}", "GET", lambda r: r.get("total_count", 0) > 0),
    # Spotify
    ("Spotify", "https://spclient.wg.spotify.com/signup/public/v1/account/?validate=1&email={email}", "GET", lambda r: r.get("status") == 20),
    # Adobe
    ("Adobe", "https://auth.services.adobe.com/signin/v2/users/accounts", "POST", lambda r: "account" in str(r)),
    # Pinterest
    ("Pinterest", "https://www.pinterest.com/resource/UserExistsResource/get/?source_url={email}", "GET", None),
    # Duolingo
    ("Duolingo", "https://www.duolingo.com/2017-06-30/users?email={email}", "GET", lambda r: r.get("users")),
    # Strava
    ("Strava", "https://www.strava.com/athletes/search?utf8=%E2%9C%93&search={email}", "GET", None),
    # Amazon
    ("Amazon", "https://www.amazon.com/gp/signin/check-email-availability?email={email}", "GET", None),
    # Microsoft
    ("Microsoft", "https://login.microsoftonline.com/common/GetCredentialType", "POST", lambda r: r.get("IfExistsResult") == 0),
    # Gravatar ya se consulta aparte
    # Last.fm
    ("Last.fm", "https://www.last.fm/user/{email}", "GET", None),
    # Tumblr
    ("Tumblr", "https://www.tumblr.com/api/v2/blog/{email}", "GET", None),
    # Disqus
    ("Disqus", "https://disqus.com/api/3.0/users/details.json?user={email}", "GET", lambda r: r.get("response")),
    # Keybase
    ("Keybase", "https://keybase.io/_/api/1.0/user/lookup.json?usernames={email}", "GET", lambda r: r.get("them") and len(r["them"]) > 0),
    # Telegram
    ("Telegram", "https://t.me/{email}", "GET", None),
    # Slack
    ("Slack", "https://slack.com/account/lookup", "POST", lambda r: "account" in str(r)),
    # PayPal
    ("PayPal", "https://www.paypal.com/auth/validateEmail?email={email}", "GET", None),
    # Imgur
    ("Imgur", "https://imgur.com/signin?email={email}", "GET", None),
    # StackOverflow
    ("StackOverflow", "https://stackoverflow.com/users/login?email={email}", "GET", None),
    # Codecademy
    ("Codecademy", "https://www.codecademy.com/pricing", "GET", None),
    # Evernote
    ("Evernote", "https://www.evernote.com/CheckEmailAvailability.action?email={email}", "GET", None),
    # Flickr
    ("Flickr", "https://www.flickr.com/people/{email}", "GET", None),
    # Vimeo
    ("Vimeo", "https://vimeo.com/{email}", "GET", None),
]


async def _fetch(session, url, method="GET", headers=None, data=None, timeout=10):
    """
    Función auxiliar para hacer peticiones HTTP con semáforo y manejo de errores.
    """
    async with semaphore:
        try:
            async with session.request(
                method, url, headers=headers, data=data,
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


async def buscar_gravatar(email: str, session: aiohttp.ClientSession):
    """
    Busca información en Gravatar usando el hash MD5 del correo.
    """
    print(f"\n[*] Consultando Gravatar para: {email}")
    
    email_hash = hashlib.md5(email.strip().lower().encode()).hexdigest()
    url = f"https://en.gravatar.com/{email_hash}.json"
    
    headers = {"User-Agent": get_user_agent()}
    response = await _fetch(session, url, headers=headers)
    
    if response["status"] == 200:
        try:
            data = json.loads(response["text"])
            entry = data.get("entry", [{}])[0]
            print(f"  [+] Gravatar ENCONTRADO:")
            print(f"      Nombre: {entry.get('displayName', 'N/A')}")
            print(f"      Foto: {entry.get('thumbnailUrl', 'N/A')}")
            print(f"      Ubicación: {entry.get('currentLocation', 'N/A')}")
            print(f"      Bio: {entry.get('aboutMe', 'N/A')}")
            
            # Enlaces sociales
            accounts = entry.get("accounts", [])
            if accounts:
                print(f"      Cuentas vinculadas:")
                for acc in accounts:
                    print(f"        - {acc.get('shortname', 'N/A')}: {acc.get('url', 'N/A')}")
            return entry
        except json.JSONDecodeError:
            print(f"  [-] Error al parsear JSON de Gravatar")
    elif response["status"] == 404:
        print(f"  [-] Gravatar no encontrado (404)")
    else:
        print(f"  [!] Gravatar: Status {response.get('status', 'N/A')}")
    
    return None


async def buscar_hibp(email: str, session: aiohttp.ClientSession):
    """
    Consulta Have I Been Pwned para ver en qué brechas aparece el email.
    """
    if not HIBP_API_KEY:
        print("\n[!] API Key de HIBP no encontrada, omitiendo módulo...")
        return
    
    print(f"\n[*] Consultando Have I Been Pwned para: {email}")
    url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}?truncateResponse=false"
    
    headers = {
        "User-Agent": "OSINT-Framework/1.0",
        "hibp-api-key": HIBP_API_KEY
    }
    
    response = await _fetch(session, url, headers=headers)
    
    if response["status"] == 200:
        try:
            breaches = json.loads(response["text"])
            print(f"  [+] Brechas encontradas: {len(breaches)}")
            for breach in breaches[:10]:  # Limitar a 10 para no saturar
                print(f"      - {breach.get('Name', 'N/A')} ({breach.get('BreachDate', 'N/A')})")
                print(f"        Dominio: {breach.get('Domain', 'N/A')}")
                print(f"        Datos filtrados: {', '.join(breach.get('DataClasses', []))}")
            if len(breaches) > 10:
                print(f"      ... y {len(breaches) - 10} brechas más")
        except json.JSONDecodeError:
            print(f"  [-] Error al parsear JSON de HIBP")
    elif response["status"] == 404:
        print(f"  [-] Email NO encontrado en brechas conocidas (HIBP)")
    elif response["status"] == 429:
        print(f"  [!] Rate Limit de HIBP alcanzado (429). Espera unos minutos.")
    elif response["status"] == 401:
        print(f"  [!] API Key de HIBP inválida")
    elif response["status"] == 403:
        print(f"  [!] HIBP bloqueó la petición (403). Falta User-Agent válido o API key.")
    else:
        print(f"  [!] HIBP: Status {response.get('status', 'N/A')}")


async def buscar_intelx(email: str, session: aiohttp.ClientSession):
    """
    Consulta IntelX para buscar información en dark web, pastes y filtraciones.
    Intenta primero con la API de pago (phonebook/search). Si la API key es gratuita
    (devuelve 401/402/403), hace fallback automático al endpoint gratuito (intelligent/search).
    """
    if not INTELX_API_KEY:
        print("\n[!] API Key de IntelX no encontrada, omitiendo módulo...")
        return

    print(f"\n[*] Consultando IntelX para: {email}")
    
    headers = {
        "User-Agent": "OSINT-Framework/1.0",
        "x-key": INTELX_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # Payload común para ambos endpoints
    payload = {
        "term": email,
        "buckets": [],
        "lookuplevel": 0,
        "maxresults": 100,
        "timeout": 5,
        "datefrom": "",
        "dateto": "",
        "sort": 4,
        "media": 0,
        "terminate": [],
        "target": 2  # 2 = Email
    }

    # URLs para API de Pago
    search_url_paid = "https://2.intelx.io/phonebook/search"
    result_url_paid_tpl = "https://2.intelx.io/phonebook/search/result?id={}&offset=0&limit=20"
    
    # URLs para API Gratuita
    search_url_free = "https://free.intelx.io/intelligent/search"
    result_url_free_tpl = "https://free.intelx.io/intelligent/search/result?id={}&limit=20"

    # Paso 1: Iniciar búsqueda (Intento con API de pago primero)
    response = await _fetch(session, search_url_paid, method="POST", headers=headers, data=json.dumps(payload))
    is_paid_api = True

    # Si la API key no tiene permisos para phonebook (es gratuita), hacemos fallback
    if response["status"] in [401, 402, 403]:
        print(f"  [*] API Key sin acceso a phonebook (Status: {response['status']}).")
        print(f"  [*] Cambiando al endpoint gratuito (free.intelx.io)...")
        is_paid_api = False
        response = await _fetch(session, search_url_free, method="POST", headers=headers, data=json.dumps(payload))

    if response["status"] in [200, 201]:
        try:
            data = json.loads(response["text"])
            search_id = data.get("id")
            if search_id:
                print(f"  [+] Búsqueda iniciada con ID: {search_id}")
                
                # Paso 2: Obtener resultados usando la URL correspondiente
                if is_paid_api:
                    result_url = result_url_paid_tpl.format(search_id)
                else:
                    result_url = result_url_free_tpl.format(search_id)
                    
                await asyncio.sleep(3)  # Dar tiempo al procesamiento en los servidores de IntelX
                
                # Los resultados se obtienen por GET
                result_response = await _fetch(session, result_url, method="GET", headers=headers)
                
                if result_response["status"] == 200:
                    results = json.loads(result_response["text"])
                    records = results.get("records", [])
                    if records:
                        print(f"  [+] Registros encontrados en IntelX: {len(records)}")
                        for rec in records[:10]:
                            print(f"      - Nombre: {rec.get('name', 'N/A')}")
                            print(f"        Tipo: {rec.get('type', 'N/A')}")
                            print(f"        Tamaño: {rec.get('size', 'N/A')} bytes")
                            if rec.get('bucket'):
                                print(f"        Bucket: {rec.get('bucket', 'N/A')}")
                    else:
                        print(f"  [-] No se encontraron registros para este email")
                elif result_response["status"] == 204:
                    print(f"  [-] Búsqueda aún en proceso o sin resultados (Status 204)")
                else:
                    print(f"  [!] IntelX: Error al obtener resultados (Status: {result_response['status']})")
            else:
                print(f"  [!] IntelX: No se recibió ID de búsqueda")
        except json.JSONDecodeError:
            print(f"  [-] Error al parsear respuesta de IntelX")
            
    elif response["status"] == 401:
        print(f"  [!] IntelX: No autorizado (401). Posibles causas:")
        print(f"      - API Key inválida o caducada")
        print(f"      - Verifica tu API key en: https://intelx.io/account?tab=developer")
    elif response["status"] == 402:
        print(f"  [!] IntelX: Sin créditos disponibles (402). Recarga tu cuenta.")
    elif response["status"] == 429:
        print(f"  [!] IntelX: Rate limit alcanzado (429). Espera unos minutos.")
    else:
        print(f"  [!] IntelX: Status {response.get('status', 'N/A')}")

async def buscar_serpapi_google_dorks(email: str, session: aiohttp.ClientSession):
    """
    Ejecuta Google Dorks predefinidos usando SerpApi con mejor manejo de resultados.
    """
    if not SERPAPI_KEY:
        print("\n[!] API Key de SerpApi no encontrada, omitiendo módulo de Google Dorks...")
        return
    
    print(f"\n[*] Ejecutando Google Dorks via SerpApi para: {email}")
    
    # Dorks optimizados - menos restrictivos para obtener más resultados
    dorks = [
        f'"{email}"',  # Búsqueda exacta del email
        f'"{email.split("@")[0]}" site:pastebin.com',  # Solo username en pastebin
        f'"{email.split("@")[0]}" site:github.com',  # Solo username en github
        f'"{email}" OR "{email.split("@")[0]}"',  # Email O username
        f'inurl:profile "{email}"',  # Perfiles que contengan el email
        f'"{email}" filetype:pdf',  # PDFs que contengan el email
        f'"{email}" (site:linkedin.com OR site:facebook.com OR site:twitter.com)',  # Redes sociales
    ]
    
    base_url = "https://serpapi.com/search.json"
    resultados_totales = 0
    
    for i, dork in enumerate(dorks[:5], 1):  # Limitar a 5 dorks
        print(f"\n  [+] Dork #{i}: {dork}")
        
        # Usar urllib.parse para codificación correcta
        params = {
            "q": dork,
            "api_key": SERPAPI_KEY,
            "engine": "google",
            "num": 10,
            "hl": "es",  # Español
            "gl": "es"   # España/Latinoamérica
        }
        
        encoded_params = urllib.parse.urlencode(params)
        url = f"{base_url}?{encoded_params}"
        
        headers = {
            "User-Agent": get_user_agent(),
            "Accept": "application/json"
        }
        
        response = await _fetch(session, url, headers=headers, timeout=15)
        
        if response["status"] == 200:
            try:
                data = json.loads(response["text"])
                
                # Verificar si hay error en la respuesta
                if "error" in data:
                    error_msg = data.get("error", "Desconocido")
                    if "hasn't returned any results" in error_msg:
                        print(f"      [-] Sin resultados en Google")
                    else:
                        print(f"      [!] Error: {error_msg}")
                    continue
                
                # Resultados orgánicos
                organic_results = data.get("organic_results", [])
                
                # Otros tipos de resultados
                knowledge_graph = data.get("knowledge_graph", {})
                answer_box = data.get("answer_box", {})
                
                if organic_results:
                    print(f"      [+] Resultados encontrados: {len(organic_results)}")
                    resultados_totales += len(organic_results)
                    for result in organic_results[:5]:
                        titulo = result.get("title", "Sin título")
                        link = result.get("link", "N/A")
                        snippet = result.get("snippet", "Sin descripción")[:150]
                        print(f"        - {titulo}")
                        print(f"          {link}")
                        print(f"          {snippet}...")
                else:
                    # Verificar si hay otros tipos de resultados
                    if knowledge_graph:
                        print(f"      [+] Resultado en Knowledge Graph")
                    elif answer_box:
                        print(f"      [+] Resultado en Answer Box")
                    else:
                        print(f"      [-] Sin resultados en Google")
                        
            except json.JSONDecodeError:
                print(f"      [-] Error al parsear respuesta de SerpApi")
                
        elif response["status"] == 429:
            print(f"      [!] SerpApi: Rate limit alcanzado")
            break
            
        elif response["status"] == 401:
            print(f"      [!] SerpApi: API Key inválida")
            break
            
        else:
            print(f"      [!] SerpApi: Status {response.get('status', 'N/A')}")
        
        # Pausa aumentada para evitar bloqueos
        await asyncio.sleep(2.5)
    
    if resultados_totales > 0:
        print(f"\n  [+] TOTAL: {resultados_totales} resultados encontrados en Google Dorks")
    else:
        print(f"\n  [-] No se encontraron resultados en los Google Dorks")
        print(f"      Esto puede significar que el email no tiene presencia pública significativa")

async def buscar_holehe(email: str, session: aiohttp.ClientSession):
    """
    Usa la librería oficial Holehe para verificar en qué servicios
    está registrado el correo electrónico.
    
    Soporta rotación de proxies para evitar rate limiting.
    
    Args:
        email: Correo electrónico a investigar
        session: Sesión aiohttp (no usada directamente, pero mantenida por consistencia)
    
    Returns:
        Lista de diccionarios con los servicios donde el email está registrado
    """
    print(f"\n[*] Ejecutando Holehe (librería oficial) para: {email}")
    print(f"    (Analizando +120 servicios con técnicas optimizadas)")
    
    # Importar configuración de proxies
    from config import PROXIES_LIST, USE_PROXIES
    
    if USE_PROXIES:
        print(f"    [✓] Rotación de proxies ACTIVADA ({len(PROXIES_LIST)} proxies disponibles)")
    else:
        print(f"    [!] Sin proxies configurados - usando conexión directa")
        print(f"        (Puede causar rate limiting en algunos servicios)")
    
    def _ejecutar_holehe_en_hilo(target_email: str, proxies: list) -> list:
        """
        Función síncrona que ejecuta trio.run() dentro de un hilo separado.
        Implementa rotación de proxies para evitar rate limiting.
        """
        import trio
        import httpx
        import random
        
        # Importar componentes internos de holehe
        from holehe.core import import_submodules, get_functions, launch_module
        
        async def _holehe_runner():
            # Importar todos los módulos de sitios web
            modules = import_submodules("holehe.modules")
            websites = get_functions(modules)
            
            # Crear múltiples clientes HTTP con diferentes proxies
            clients = []
            
            if proxies:
                # Modo con proxies: crear un cliente por cada proxy
                for proxy_url in proxies:
                    try:
                        client = httpx.AsyncClient(
                            timeout=15,
                            proxy=proxy_url,
                            follow_redirects=True
                        )
                        clients.append(client)
                    except Exception as e:
                        print(f"    [!] Error creando cliente con proxy {proxy_url}: {e}")
                
                # Si no se pudo crear ningún cliente válido, usar conexión directa
                if not clients:
                    print(f"    [!] No se pudieron crear clientes con proxies, usando conexión directa")
                    clients.append(httpx.AsyncClient(timeout=15, follow_redirects=True))
            else:
                # Modo sin proxies: un solo cliente
                clients.append(httpx.AsyncClient(timeout=15, follow_redirects=True))
            
            out = []
            proxy_index = 0
            
            # Función para ejecutar un módulo con un cliente específico
            async def ejecutar_con_proxy(website, email, client, output_list):
                try:
                    await launch_module(website, email, client, output_list)
                except Exception as e:
                    # Si falla, intentar con el siguiente proxy
                    pass
            
            # Ejecutar todos los módulos con rotación de proxies
            async with trio.open_nursery() as nursery:
                for i, website in enumerate(websites):
                    # Rotar entre los clientes disponibles
                    client = clients[i % len(clients)]
                    nursery.start_soon(ejecutar_con_proxy, website, target_email, client, out)
            
            # Cerrar todos los clientes
            for client in clients:
                await client.aclose()
            
            # Ordenar resultados alfabéticamente
            return sorted(out, key=lambda i: i['name'])
        
        return trio.run(_holehe_runner)
    
    try:
        # Ejecutar holehe en un hilo separado para no bloquear asyncio
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="holehe") as executor:
            resultados = await loop.run_in_executor(
                executor, 
                _ejecutar_holehe_en_hilo, 
                email,
                PROXIES_LIST if USE_PROXIES else []
            )
        
        # Clasificar resultados
        vinculadas = []
        rate_limited = []
        errores = []
        no_registradas = 0
        
        for resultado in resultados:
            nombre = resultado.get("name", "Desconocido")
            dominio = resultado.get("domain", "N/A")
            
            if resultado.get("exists"):
                # Cuenta encontrada - extraer información adicional
                info_extra = []
                if resultado.get("emailrecovery"):
                    info_extra.append(f"Email recuperación: {resultado['emailrecovery']}")
                if resultado.get("phoneNumber"):
                    info_extra.append(f"Tel: {resultado['phoneNumber']}")
                if resultado.get("others"):
                    if "FullName" in str(resultado.get("others", {})):
                        info_extra.append(f"Nombre: {resultado['others']['FullName']}")
                
                info_str = f" | {' | '.join(info_extra)}" if info_extra else ""
                print(f"    [✓ VINCULADA] {nombre} ({dominio}){info_str}")
                vinculadas.append(resultado)
                
            elif resultado.get("rateLimit"):
                print(f"    [✗ RATE LIMIT] {nombre} ({dominio})")
                rate_limited.append(resultado)
                
            elif resultado.get("error"):
                errores.append(resultado)
                
            else:
                no_registradas += 1
        
        # Resumen final
        print(f"\n  {'='*50}")
        print(f"  [+] RESUMEN HOLEHE:")
        print(f"      ✓ Cuentas vinculadas: {len(vinculadas)}")
        print(f"      ✗ Rate limited: {len(rate_limited)}")
        print(f"      ! Errores de conexión: {len(errores)}")
        print(f"      - No registradas: {no_registradas}")
        print(f"      Total servicios analizados: {len(resultados)}")
        print(f"  {'='*50}")
        
        if vinculadas:
            nombres_vinculadas = [r['name'] for r in vinculadas]
            print(f"\n  [+] CUENTAS VINCULADAS: {', '.join(nombres_vinculadas)}")
        else:
            print(f"\n  [-] No se detectaron cuentas vinculadas en los servicios analizados")
        
        if rate_limited:
            print(f"\n  [!] NOTA: {len(rate_limited)} servicios aplicaron rate-limiting.")
            if USE_PROXIES:
                print(f"      Considera agregar más proxies o usar proxies de mayor calidad.")
            else:
                print(f"      Configura proxies en config.py para evitar este problema.")
        
        return vinculadas
        
    except ImportError as e:
        print(f"  [!] ERROR: Dependencia faltante - {e}")
        print(f"      Instala con: pip install holehe trio httpx")
        return []
    except Exception as e:
        print(f"  [!] Error crítico ejecutando Holehe: {e}")
        import traceback
        traceback.print_exc()
        return []

async def investigar_email_async(email: str):
    """
    Función asíncrona principal que coordina todas las investigaciones.
    """
    print(f"\n{'='*60}")
    print(f"[+] INICIANDO INVESTIGACIÓN OSINT DE EMAIL: {email}")
    print(f"[+] Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    # Configurar sesión aiohttp con timeouts
    connector = aiohttp.TCPConnector(limit=SEMAPHORE_LIMIT, limit_per_host=5)
    timeout = aiohttp.ClientTimeout(total=120)
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        # 1. Gravatar
        await buscar_gravatar(email, session)
        
        # 2. Have I Been Pwned
        await buscar_hibp(email, session)
        
        # 3. IntelX
        await buscar_intelx(email, session)
        
        # 4. Google Dorks via SerpApi
        await buscar_serpapi_google_dorks(email, session)
        
        # 5. Técnica Holehe (endpoints sociales)
        await buscar_holehe(email, session)
    
    print(f"\n{'='*60}")
    print(f"[+] INVESTIGACIÓN DE EMAIL COMPLETADA")
    print(f"{'='*60}")


def investigar_email(email: str):
    """
    Punto de entrada síncrono que ejecuta el motor asíncrono.
    Llamado desde la TUI a través de AccionPython.
    """
    from utils.validators import validar_email
    from utils.logger import setup_dual_logger
    
    # 1. Validación
    print(f"[*] Validando correo: {email}")
    if not validar_email(email):
        print(f"[!] El correo NO es válido. Abortando investigación.")
        return
    
    # 2. Configurar Dual Logger
    logger = setup_dual_logger(email)
    
    try:
        # 3. Ejecutar motor asíncrono
        asyncio.run(investigar_email_async(email))
    except KeyboardInterrupt:
        print("\n[!] Investigación interrumpida por el usuario")
    except Exception as e:
        print(f"\n[!] Error crítico en la investigación: {e}")
    finally:
        # 4. Cerrar logger
        logger.close()
        print(f"\n[+] Resultados guardados en archivo de log.")
