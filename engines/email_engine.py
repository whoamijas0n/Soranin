"""
engines/email_engine.py
Motor de investigación OSINT asíncrono para correos electrónicos.
Usa aiohttp con semáforo para limitar concurrencia y rotación de User-Agents.
"""
import asyncio
import aiohttp
import hashlib
import json
import re
from datetime import datetime
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
    """
    if not INTELX_API_KEY:
        print("\n[!] API Key de IntelX no encontrada, omitiendo módulo...")
        return
    
    print(f"\n[*] Consultando IntelX para: {email}")
    
    # Paso 1: Iniciar búsqueda
    search_url = "https://2.intelx.io/phonebook/search"
    headers = {
        "User-Agent": get_user_agent(),
        "x-key": INTELX_API_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "term": email,
        "buckets": [],
        "lookuplevel": 0,
        "maxresults": 10,
        "timeout": 0,
        "datefrom": "",
        "dateto": "",
        "sort": 4,
        "media": 0,
        "terminate": []
    }
    
    response = await _fetch(session, search_url, method="POST", headers=headers, data=json.dumps(payload))
    
    if response["status"] in [200, 201]:
        try:
            data = json.loads(response["text"])
            search_id = data.get("id")
            
            if search_id:
                # Paso 2: Obtener resultados
                result_url = f"https://2.intelx.io/phonebook/search/result?id={search_id}&offset=0&limit=10"
                await asyncio.sleep(2)  # Dar tiempo al procesamiento
                
                result_response = await _fetch(session, result_url, headers=headers)
                
                if result_response["status"] == 200:
                    results = json.loads(result_response["text"])
                    records = results.get("records", [])
                    print(f"  [+] Registros encontrados en IntelX: {len(records)}")
                    for rec in records[:5]:
                        print(f"      - Nombre: {rec.get('name', 'N/A')}")
                        print(f"        Tipo: {rec.get('type', 'N/A')}")
                        print(f"        Tamaño: {rec.get('size', 'N/A')} bytes")
                else:
                    print(f"  [!] IntelX: No se pudieron obtener resultados")
        except json.JSONDecodeError:
            print(f"  [-] Error al parsear respuesta de IntelX")
    else:
        print(f"  [!] IntelX: Status {response.get('status', 'N/A')}")


async def buscar_serpapi_google_dorks(email: str, session: aiohttp.ClientSession):
    """
    Ejecuta Google Dorks predefinidos usando SerpApi.
    """
    if not SERPAPI_KEY:
        print("\n[!] API Key de SerpApi no encontrada, omitiendo módulo de Google Dorks...")
        return
    
    print(f"\n[*] Ejecutando Google Dorks via SerpApi para: {email}")
    
    dorks = [
        f'"{email}"',
        f'site:pastebin.com "{email}"',
        f'site:github.com "{email}"',
        f'site:linkedin.com "{email}"',
        f'site:instagram.com "{email}"',
        f'filetype:pdf "{email}"',
        f'inurl:profile "{email}"',
    ]
    
    base_url = "https://serpapi.com/search.json"
    
    for i, dork in enumerate(dorks[:3], 1):  # Limitar a 3 dorks por velocidad
        print(f"\n  [+] Dork #{i}: {dork}")
        
        params = {
            "q": dork,
            "api_key": SERPAPI_KEY,
            "engine": "google",
            "num": 5
        }
        
        # Construir URL con parámetros
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
        
        # Pausa entre peticiones
        await asyncio.sleep(1)


async def buscar_endpoints_sociales(email: str, session: aiohttp.ClientSession):
    """
    Técnica "Holehe": comprueba endpoints de registro y recuperación
    de contraseña en redes sociales para ver si el email está registrado.
    """
    print(f"\n[*] Técnica Holehe: Comprobando endpoints en redes sociales para: {email}")
    print(f"    (Puede tardar, usando Semaphore de {SEMAPHORE_LIMIT} concurrencia)")
    
    vinculadas = []
    
    for nombre, url_template, metodo, check_fn in SOCIAL_ENDPOINTS:
        url = url_template.format(email=email)
        headers = {
            "User-Agent": get_user_agent(),
            "Accept": "application/json, text/html, */*",
            "Accept-Language": "en-US,en;q=0.9"
        }
        
        try:
            response = await _fetch(session, url, method=metodo, headers=headers, timeout=8)
            
            # Determinar si el email está registrado
            registrado = False
            
            if check_fn and isinstance(response.get("text"), str):
                try:
                    json_data = json.loads(response["text"])
                    registrado = check_fn(json_data)
                except json.JSONDecodeError:
                    # Si no es JSON, buscar en el texto
                    pass
            
            if not registrado and response.get("text"):
                # Heurísticas comunes de que el email existe
                indicadores_existe = [
                    "already registered",
                    "ya registrado",
                    "already in use",
                    "email exists",
                    "account exists",
                    "user exists",
                    "already have an account",
                    "recover your account",
                    "reset your password",
                    "forgot password"
                ]
                texto_lower = response["text"].lower()
                if any(ind in texto_lower for ind in indicadores_existe):
                    registrado = True
            
            if response.get("status") == 200 and registrado:
                vinculadas.append(nombre)
                print(f"    [VINCULADA] {nombre} ({response['status']})")
            elif response.get("status") in [403, 429]:
                print(f"    [BLOQUEADO] {nombre} ({response['status']})")
            elif response.get("status") == 404:
                print(f"    [NO VINCULADA] {nombre} ({response['status']})")
            else:
                print(f"    [?] {nombre} (Status: {response.get('status', 'N/A')})")
        
        except Exception as e:
            print(f"    [!] Error con {nombre}: {e}")
        
        # Pequeña pausa para no saturar
        await asyncio.sleep(0.3)
    
    if vinculadas:
        print(f"\n  [+] REDES VINCULADAS: {', '.join(vinculadas)}")
    else:
        print(f"\n  [-] No se detectaron cuentas vinculadas claramente")
    
    return vinculadas


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
        await buscar_endpoints_sociales(email, session)
    
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
