import asyncio
import aiohttp
import hashlib
import json
import re
import urllib.parse
import os
import csv
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from config import (
    HIBP_API_KEY, INTELX_API_KEY, SERPAPI_KEY,
    DEHASHED_KEY, DEHASHED_EMAIL, get_user_agent
)

SEMAPHORE_LIMIT = 15
semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)

SOCIAL_ENDPOINTS = [
    ("Instagram", "https://www.instagram.com/{email}/", "GET", None),
    ("Twitter/X", "https://twitter.com/search?q={email}&src=typed_query", "GET", None),
    ("LinkedIn", "https://www.linkedin.com/pub/dir/{email}", "GET", None),
    ("Facebook", "https://www.facebook.com/search/top/?q={email}", "GET", None),
    ("GitHub", "https://api.github.com/search/users?q={email}", "GET", lambda r: r.get("total_count", 0) > 0),
    ("Spotify", "https://spclient.wg.spotify.com/signup/public/v1/account/?validate=1&email={email}", "GET", lambda r: r.get("status") == 20),
    ("Adobe", "https://auth.services.adobe.com/signin/v2/users/accounts", "POST", lambda r: "account" in str(r)),
    ("Pinterest", "https://www.pinterest.com/resource/UserExistsResource/get/?source_url={email}", "GET", None),
    ("Duolingo", "https://www.duolingo.com/2017-06-30/users?email={email}", "GET", lambda r: r.get("users")),
    ("Strava", "https://www.strava.com/athletes/search?utf8=%E2%9C%93&search={email}", "GET", None),
    ("Amazon", "https://www.amazon.com/gp/signin/check-email-availability?email={email}", "GET", None),
    ("Microsoft", "https://login.microsoftonline.com/common/GetCredentialType", "POST", lambda r: r.get("IfExistsResult") == 0),
    ("Last.fm", "https://www.last.fm/user/{email}", "GET", None),
    ("Tumblr", "https://www.tumblr.com/api/v2/blog/{email}", "GET", None),
    ("Disqus", "https://disqus.com/api/3.0/users/details.json?user={email}", "GET", lambda r: r.get("response")),
    ("Keybase", "https://keybase.io/_/api/1.0/user/lookup.json?usernames={email}", "GET", lambda r: r.get("them") and len(r["them"]) > 0),
    ("Telegram", "https://t.me/{email}", "GET", None),
    ("Slack", "https://slack.com/account/lookup", "POST", lambda r: "account" in str(r)),
    ("PayPal", "https://www.paypal.com/auth/validateEmail?email={email}", "GET", None),
    ("Imgur", "https://imgur.com/signin?email={email}", "GET", None),
    ("StackOverflow", "https://stackoverflow.com/users/login?email={email}", "GET", None),
    ("Codecademy", "https://www.codecademy.com/pricing", "GET", None),
    ("Evernote", "https://www.evernote.com/CheckEmailAvailability.action?email={email}", "GET", None),
    ("Flickr", "https://www.flickr.com/people/{email}", "GET", None),
    ("Vimeo", "https://vimeo.com/{email}", "GET", None),
]


async def _fetch(session, url, method="GET", headers=None, data=None, timeout=10):
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
            
            accounts = entry.get("accounts", [])
            if accounts:
                print(f"      Cuentas vinculadas:")
                for acc in accounts:
                    print(f"        - {acc.get('shortname', 'N/A')}: {acc.get('url', 'N/A')}")
            return entry # Retorna la data obtenida
        except json.JSONDecodeError:
            print(f"  [-] Error al parsear JSON de Gravatar")
    elif response["status"] == 404:
        print(f"  [-] Gravatar no encontrado (404)")
    else:
        print(f"  [!] Gravatar: Status {response.get('status', 'N/A')}")
    
    return {}


async def buscar_hibp(email: str, session: aiohttp.ClientSession):
    if not HIBP_API_KEY:
        print("\n[!] API Key de HIBP no encontrada, omitiendo módulo...")
        return []
    
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
            for breach in breaches[:10]:
                print(f"      - {breach.get('Name', 'N/A')} ({breach.get('BreachDate', 'N/A')})")
                print(f"        Dominio: {breach.get('Domain', 'N/A')}")
                print(f"        Datos filtrados: {', '.join(breach.get('DataClasses', []))}")
            if len(breaches) > 10:
                print(f"      ... y {len(breaches) - 10} brechas más")
            return breaches # Retorna la lista de brechas
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
    
    return []


async def buscar_intelx(email: str, session: aiohttp.ClientSession):
    if not INTELX_API_KEY:
        print("\n[!] API Key de IntelX no encontrada, omitiendo módulo...")
        return []

    print(f"\n[*] Consultando IntelX para: {email}")
    headers = {
        "User-Agent": "OSINT-Framework/1.0",
        "x-key": INTELX_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload = {
        "term": email, "buckets": [], "lookuplevel": 0,
        "maxresults": 100, "timeout": 5, "datefrom": "",
        "dateto": "", "sort": 4, "media": 0, "terminate": [], "target": 2
    }

    search_url_paid = "https://2.intelx.io/phonebook/search"
    result_url_paid_tpl = "https://2.intelx.io/phonebook/search/result?id={}&offset=0&limit=20"
    search_url_free = "https://free.intelx.io/intelligent/search"
    result_url_free_tpl = "https://free.intelx.io/intelligent/search/result?id={}&limit=20"

    response = await _fetch(session, search_url_paid, method="POST", headers=headers, data=json.dumps(payload))
    is_paid_api = True

    if response["status"] in [401, 402, 403]:
        print(f"  [*] API Key sin acceso a phonebook (Status: {response['status']}).")
        print(f"  [*] Cambiando al endpoint gratuito (free.intelx.io)...")
        is_paid_api = False
        response = await _fetch(session, search_url_free, method="POST", headers=headers, data=json.dumps(payload))

    records_encontrados = []
    if response["status"] in [200, 201]:
        try:
            data = json.loads(response["text"])
            search_id = data.get("id")
            if search_id:
                print(f"  [+] Búsqueda iniciada con ID: {search_id}")
                result_url = result_url_paid_tpl.format(search_id) if is_paid_api else result_url_free_tpl.format(search_id)
                await asyncio.sleep(3)
                
                result_response = await _fetch(session, result_url, method="GET", headers=headers)
                if result_response["status"] == 200:
                    results = json.loads(result_response["text"])
                    records = results.get("records", [])
                    if records:
                        records_encontrados = records
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
        print(f"  [!] IntelX: No autorizado (401). Verifica API Key.")
    elif response["status"] == 429:
        print(f"  [!] IntelX: Rate limit alcanzado (429).")
    
    return records_encontrados

async def buscar_serpapi_google_dorks(email: str, session: aiohttp.ClientSession):
    if not SERPAPI_KEY:
        print("\n[!] API Key de SerpApi no encontrada, omitiendo módulo de Google Dorks...")
        return []
    
    print(f"\n[*] Ejecutando Google Dorks via SerpApi para: {email}")
    dorks = [
        f'"{email}"',
        f'"{email.split("@")[0]}" site:pastebin.com',
        f'"{email.split("@")[0]}" site:github.com',
        f'"{email}" OR "{email.split("@")[0]}"',
        f'inurl:profile "{email}"',
    ]
    
    base_url = "https://serpapi.com/search.json"
    resultados_totales = 0
    resultados_recolectados = []
    
    for i, dork in enumerate(dorks[:5], 1):
        print(f"\n  [+] Dork #{i}: {dork}")
        params = {
            "q": dork, "api_key": SERPAPI_KEY, "engine": "google",
            "num": 10, "hl": "es", "gl": "es"
        }
        encoded_params = urllib.parse.urlencode(params)
        url = f"{base_url}?{encoded_params}"
        headers = {"User-Agent": get_user_agent(), "Accept": "application/json"}
        
        response = await _fetch(session, url, headers=headers, timeout=15)
        
        if response["status"] == 200:
            try:
                data = json.loads(response["text"])
                if "error" in data:
                    error_msg = data.get("error", "Desconocido")
                    if "hasn't returned any results" in error_msg:
                        print(f"      [-] Sin resultados en Google")
                    else:
                        print(f"      [!] Error: {error_msg}")
                    continue
                
                organic_results = data.get("organic_results", [])
                if organic_results:
                    print(f"      [+] Resultados encontrados: {len(organic_results)}")
                    resultados_totales += len(organic_results)
                    for result in organic_results[:5]:
                        resultados_recolectados.append(result)
                        titulo = result.get("title", "Sin título")
                        link = result.get("link", "N/A")
                        snippet = result.get("snippet", "Sin descripción")[:150]
                        print(f"        - {titulo}")
                        print(f"          {link}")
                        print(f"          {snippet}...")
                else:
                    print(f"      [-] Sin resultados orgánicos directos")
                        
            except json.JSONDecodeError:
                print(f"      [-] Error al parsear respuesta de SerpApi")
        elif response["status"] == 429:
            print(f"      [!] SerpApi: Rate limit alcanzado")
            break
        
        await asyncio.sleep(2.5)
    
    if resultados_totales > 0:
        print(f"\n  [+] TOTAL: {resultados_totales} resultados encontrados en Google Dorks")
    return resultados_recolectados

async def buscar_holehe(email: str, session: aiohttp.ClientSession):
    print(f"\n[*] Ejecutando Holehe (librería oficial) para: {email}")
    from config import PROXIES_LIST, USE_PROXIES
    
    if USE_PROXIES:
        print(f"    [✓] Rotación de proxies ACTIVADA ({len(PROXIES_LIST)} proxies disponibles)")
    else:
        print(f"    [!] Sin proxies configurados - usando conexión directa")
    
    def _ejecutar_holehe_en_hilo(target_email: str, proxies: list) -> list:
        import trio
        import httpx
        from holehe.core import import_submodules, get_functions, launch_module
        
        async def _holehe_runner():
            modules = import_submodules("holehe.modules")
            websites = get_functions(modules)
            clients = []
            if proxies:
                for proxy_url in proxies:
                    try:
                        clients.append(httpx.AsyncClient(timeout=15, proxy=proxy_url, follow_redirects=True))
                    except Exception: pass
                if not clients: clients.append(httpx.AsyncClient(timeout=15, follow_redirects=True))
            else:
                clients.append(httpx.AsyncClient(timeout=15, follow_redirects=True))
            
            out = []
            async def ejecutar_con_proxy(website, email, client, output_list):
                try: await launch_module(website, email, client, output_list)
                except Exception: pass
            
            async with trio.open_nursery() as nursery:
                for i, website in enumerate(websites):
                    client = clients[i % len(clients)]
                    nursery.start_soon(ejecutar_con_proxy, website, target_email, client, out)
            
            for client in clients: await client.aclose()
            return sorted(out, key=lambda i: i['name'])
        
        return trio.run(_holehe_runner)
    
    try:
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="holehe") as executor:
            resultados = await loop.run_in_executor(executor, _ejecutar_holehe_en_hilo, email, PROXIES_LIST if USE_PROXIES else [])
        
        vinculadas = []
        for resultado in resultados:
            if resultado.get("exists"):
                nombre = resultado.get("name", "Desconocido")
                dominio = resultado.get("domain", "N/A")
                print(f"    [✓ VINCULADA] {nombre} ({dominio})")
                vinculadas.append(resultado)
        return vinculadas
    except Exception as e:
        print(f"  [!] Error crítico ejecutando Holehe: {e}")
        return []

async def investigar_email_async(email: str):
    """
    Función asíncrona principal que coordina y centraliza la información en un diccionario.
    """
    print(f"\n{'='*60}")
    print(f"[+] INICIANDO INVESTIGACIÓN OSINT DE EMAIL: {email}")
    print(f"[+] Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    connector = aiohttp.TCPConnector(limit=SEMAPHORE_LIMIT, limit_per_host=5)
    timeout = aiohttp.ClientTimeout(total=120)
    
    report_data = {
        "objetivo": email,
        "tipo": "email",
        "fecha": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "resultados": {}
    }

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        report_data["resultados"]["gravatar"] = await buscar_gravatar(email, session) or {}
        report_data["resultados"]["hibp"] = await buscar_hibp(email, session) or []
        report_data["resultados"]["intelx"] = await buscar_intelx(email, session) or []
        report_data["resultados"]["google_dorks"] = await buscar_serpapi_google_dorks(email, session) or []
        report_data["resultados"]["holehe"] = await buscar_holehe(email, session) or []
    
    print(f"\n{'='*60}")
    print(f"[+] INVESTIGACIÓN DE EMAIL COMPLETADA")
    print(f"{'='*60}")
    
    return report_data

def guardar_csv_email(data: dict, folder_path: str):
    """
    Aplana el diccionario de resultados del email para exportarlo como CSV.
    """
    csv_path = os.path.join(folder_path, 'report.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Módulo", "Dato Principal", "Detalles Extras"])
        
        resultados = data.get("resultados", {})
        
        # Gravatar
        grav = resultados.get("gravatar", {})
        if grav:
            writer.writerow(["Gravatar", "Display Name", grav.get("displayName", "N/A")])
            writer.writerow(["Gravatar", "Profile URL", grav.get("profileUrl", "N/A")])
        
        # HIBP
        for b in resultados.get("hibp", []):
            writer.writerow(["Brecha (HIBP)", b.get("Name", "N/A"), b.get("BreachDate", "N/A")])
            
        # IntelX
        for r in resultados.get("intelx", []):
            writer.writerow(["IntelX Leak", r.get("name", "N/A"), f"Bucket: {r.get('bucket', 'N/A')}"])
            
        # Google Dorks
        # for d in resultados.get("google_dorks", []):
        #     writer.writerow(["Google Search", d.get("title", "N/A"), d.get("link", "N/A")])
        # Google Dorks
        for d in resultados.get("google_dorks", []):
            enlace = d.get("link", "N/A")
            fragmento = d.get("snippet", "Sin descripción").replace('\n', ' ')[:100]
            writer.writerow(["Google Search", d.get("title", "N/A"), f"{enlace} | Extracto: {fragmento}..."])


        # Holehe
        for h in resultados.get("holehe", []):
            writer.writerow(["Cuenta Vinculada", h.get("name", "N/A"), h.get("domain", "N/A")])


def investigar_email(email: str):
    from utils.validators import validar_email
    from utils.logger import setup_dual_logger
    
    print(f"[*] Validando correo: {email}")
    if not validar_email(email):
        print(f"[!] El correo NO es válido. Abortando investigación.")
        return
    
    # MODIFICACIÓN: Desempaquetar instancia del logger y la ruta de la carpeta
    logger, folder_path = setup_dual_logger(email)
    
    try:
        report_data = asyncio.run(investigar_email_async(email))
        
        # Guardado en JSON
        json_path = os.path.join(folder_path, 'report.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=4, ensure_ascii=False)
            
        # Guardado en CSV (Flattening)
        guardar_csv_email(report_data, folder_path)
            
    except KeyboardInterrupt:
        print("\n[!] Investigación interrumpida por el usuario")
    except Exception as e:
        print(f"\n[!] Error crítico en la investigación: {e}")
    finally:
        logger.close()
        print(f"\n[+] Resultados guardados exitosamente en: {folder_path}")
        print(f"    Archivos generados: report.txt, report.json, report.csv")