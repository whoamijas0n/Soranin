import asyncio
import aiohttp
import json
import re
import os
import csv
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from config import (
    NUMVERIFY_KEY, SERPAPI_KEY,
    SOCIAL_SEARCHER_KEY, get_user_agent
)

SEMAPHORE_LIMIT = 15
semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)

COUNTRY_SEARCH_DOMAINS = {
    "ES": "paginasblancas.es", "US": "whitepages.com", "MX": "paginasblancas.com.mx",
    "AR": "paginasdoradas.com", "BR": "listaonline.com.br", "UK": "yell.com",
    "FR": "pagesjaunes.fr", "DE": "dastelefonbuch.de", "IT": "paginebianche.it",
    "PT": "paginasbrancas.pt", "CO": "paginasamarillas.com.co", "CL": "paginasblancas.cl",
    "PE": "paginasblancas.com.pe",
}


async def _fetch(session, url, method="GET", headers=None, data=None, params=None, timeout=10):
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
        except Exception as e:
            return {"status": 0, "error": str(e)}


async def validar_numverify(telefono: str, session: aiohttp.ClientSession):
    if not NUMVERIFY_KEY:
        print("\n[!] API Key de NumVerify no encontrada, omitiendo módulo...")
        return {}
    
    print(f"\n[*] Validando con NumVerify: {telefono}")
    url = "http://apilayer.net/api/validate"
    params = {"access_key": NUMVERIFY_KEY, "number": telefono, "country_code": "", "format": 1}
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
                return data
            else:
                print(f"  [-] NumVerify indica que el número NO es válido")
        except json.JSONDecodeError:
            print(f"  [-] Error al parsear JSON de NumVerify")
    return {}


async def buscar_social_searcher(telefono: str, session: aiohttp.ClientSession):
    if not SOCIAL_SEARCHER_KEY:
        print("\n[!] API Key de Social Searcher no encontrada, omitiendo módulo...")
        return []
    
    print(f"\n[*] Buscando menciones en redes con Social Searcher: {telefono}")
    url = "https://www.social-searcher.com/google-social-search/"
    params = {"q": telefono, "lang": "es"}
    headers = {"User-Agent": get_user_agent(), "Accept": "text/html"}
    
    response = await _fetch(session, url, headers=headers, params=params)
    resultados_ss = []
    
    if response["status"] == 200:
        text = response["text"]
        menciones = re.findall(r'<a[^>]+class="[^"]*result-link[^"]*"[^>]*>([^<]+)</a>', text)
        
        if menciones:
            print(f"  [+] Menciones encontradas: {len(menciones)}")
            for mencion in menciones[:10]:
                print(f"      - {mencion.strip()}")
                resultados_ss.append(mencion.strip())
        else:
            if telefono in text:
                print(f"  [+] El número aparece en resultados de Social Searcher")
                resultados_ss.append("Aparece en Social Searcher Raw Text")
    
    return resultados_ss


async def buscar_phoneinfoga_dorks(telefono: str, pais: str, session: aiohttp.ClientSession):
    if not SERPAPI_KEY:
        print("\n[!] API Key de SerpApi no encontrada, omitiendo módulo de Google Dorks...")
        return []
    
    print(f"\n[*] Ejecutando Google Dorks estilo PhoneInfoga para: {telefono} (País: {pais})")
    search_domain = COUNTRY_SEARCH_DOMAINS.get(pais, "google.com")
    dorks = [
        f'"{telefono}"', f'site:{search_domain} "{telefono}"',
        f'site:facebook.com "{telefono}"', f'site:instagram.com "{telefono}"'
    ]
    base_url = "https://serpapi.com/search.json"
    resultados_dorks = []
    
    for i, dork in enumerate(dorks[:4], 1):
        print(f"\n  [+] Dork #{i}: {dork}")
        params = {"q": dork, "api_key": SERPAPI_KEY, "engine": "google", "num": 5}
        param_str = "&".join([f"{k}={v}" for k, v in params.items()])
        url = f"{base_url}?{param_str}"
        
        response = await _fetch(session, url, headers={"User-Agent": get_user_agent()})
        
        if response["status"] == 200:
            try:
                data = json.loads(response["text"])
                results = data.get("organic_results", [])
                if results:
                    print(f"      Resultados encontrados: {len(results)}")
                    for result in results:
                        resultados_dorks.append(result)
                        print(f"        - {result.get('title', 'Sin título')} | {result.get('link', 'N/A')}")
            except json.JSONDecodeError:
                pass
        await asyncio.sleep(1)
        
    return resultados_dorks


async def validar_whatsapp_telegram(telefono: str, session: aiohttp.ClientSession):
    print(f"\n[*] Validando cuentas en WhatsApp y Telegram para: {telefono}")
    resultados = {"whatsapp": False, "telegram": False}
    
    # WhatsApp
    print(f"\n  [+] WhatsApp:")
    try:
        numero_limpio = re.sub(r'\D', '', telefono)
        wa_url = f"https://wa.me/{numero_limpio}"
        response = await _fetch(session, wa_url, headers={"User-Agent": get_user_agent()}, timeout=8)
        if response["status"] == 200 and ("chat" in response["text"].lower() or "whatsapp" in response["text"].lower()):
            print(f"      [VINCULADA] WhatsApp tiene cuenta para este número")
            resultados["whatsapp"] = True
    except Exception: pass
    
    # Telegram
    print(f"\n  [+] Telegram:")
    try:
        tg_url = f"https://t.me/{numero_limpio}"
        response = await _fetch(session, tg_url, headers={"User-Agent": get_user_agent()}, timeout=8)
        if response["status"] == 200 and "if you have" in response["text"].lower() and "not found" not in response["text"].lower():
            print(f"      [VINCULADA] Posible cuenta de Telegram vinculada")
            resultados["telegram"] = True
    except Exception: pass
    
    return resultados

async def buscar_ignorant(telefono: str, pais: str, session: aiohttp.ClientSession):
    if not pais or pais.upper() == "UNKNOWN":
        return []

    print(f"\n[*] Ejecutando Ignorant (librería oficial) para: {telefono} (País: {pais.upper()})")
    from config import PROXIES_LIST, USE_PROXIES
    
    def _ejecutar_ignorant_en_hilo(target_phone: str, country_code: str, proxies: list) -> list:
        import trio
        import httpx
        from ignorant.core import import_submodules, get_functions, launch_module
        
        async def _ignorant_runner():
            modules = import_submodules("ignorant.modules")
            websites = get_functions(modules)
            clients = [httpx.AsyncClient(timeout=15, follow_redirects=True)]
            out = []
            
            async def ejecutar_con_proxy(website, phone, c_code, client, output_list):
                try: await launch_module(website, phone, c_code, client, output_list)
                except Exception: pass
            
            async with trio.open_nursery() as nursery:
                for i, website in enumerate(websites):
                    nursery.start_soon(ejecutar_con_proxy, website, target_phone, country_code, clients[0], out)
            
            for client in clients: await client.aclose()
            return sorted(out, key=lambda i: i['name'])
        
        return trio.run(_ignorant_runner)
    
    try:
        telefono_limpio = telefono.replace("+", "")
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="ignorant") as executor:
            resultados = await loop.run_in_executor(
                executor, _ejecutar_ignorant_en_hilo, telefono_limpio, pais.lower(), []
            )
        
        vinculadas = []
        for resultado in resultados:
            if resultado.get("exists"):
                print(f"    [✓ VINCULADA] {resultado.get('name', 'Desconocido')}")
                vinculadas.append(resultado)
        return vinculadas
    except Exception as e:
        print(f"  [!] Error crítico ejecutando Ignorant: {e}")
        return []


async def investigar_telefono_async(telefono: str):
    """
    Función asíncrona principal que coordina todas las investigaciones del teléfono.
    MODIFICADA para recopilar datos de todas las funciones asíncronas y estructurarlas.
    """
    print(f"\n{'='*60}")
    print(f"[+] INICIANDO INVESTIGACIÓN OSINT DE TELÉFONO: {telefono}")
    print(f"[+] Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    connector = aiohttp.TCPConnector(limit=SEMAPHORE_LIMIT, limit_per_host=5)
    timeout = aiohttp.ClientTimeout(total=120)
    
    report_data = {
        "objetivo": telefono,
        "tipo": "telefono",
        "fecha": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "resultados": {}
    }
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        datos_numverify = await validar_numverify(telefono, session)
        report_data["resultados"]["numverify"] = datos_numverify or {}
        
        pais = datos_numverify.get("country_code", "UNKNOWN") if datos_numverify else "UNKNOWN"
        
        report_data["resultados"]["social_searcher"] = await buscar_social_searcher(telefono, session) or []
        report_data["resultados"]["google_dorks"] = await buscar_phoneinfoga_dorks(telefono, pais, session) or []
        report_data["resultados"]["whatsapp_telegram"] = await validar_whatsapp_telegram(telefono, session) or {}
        report_data["resultados"]["ignorant"] = await buscar_ignorant(telefono, pais, session) or []

    print(f"\n{'='*60}")
    print(f"[+] INVESTIGACIÓN DE TELÉFONO COMPLETADA")
    print(f"{'='*60}")
    
    return report_data


def guardar_csv_telefono(data: dict, folder_path: str):
    """Aplana el diccionario de resultados del teléfono para exportarlo como CSV."""
    csv_path = os.path.join(folder_path, 'report.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Módulo", "Dato Principal", "Detalles Extras"])
        
        resultados = data.get("resultados", {})
        
        # NumVerify
        num = resultados.get("numverify", {})
        if num:
            writer.writerow(["NumVerify", "País", num.get("country_name", "N/A")])
            writer.writerow(["NumVerify", "Operador", num.get("carrier", "N/A")])
            writer.writerow(["NumVerify", "Tipo de Línea", num.get("line_type", "N/A")])
            
        # Redes Mensajería
        wa_tg = resultados.get("whatsapp_telegram", {})
        if wa_tg:
            writer.writerow(["Mensajería", "WhatsApp Vinculado", str(wa_tg.get("whatsapp", False))])
            writer.writerow(["Mensajería", "Telegram Vinculado", str(wa_tg.get("telegram", False))])
            
        # Ignorant
        for i in resultados.get("ignorant", []):
            writer.writerow(["Cuenta Vinculada", i.get("name", "N/A"), i.get("domain", "N/A")])
            
        # Dorks
        for d in resultados.get("google_dorks", []):
            writer.writerow(["Google Search", d.get("title", "N/A"), d.get("link", "N/A")])


def investigar_telefono(telefono: str):
    from utils.validators import validar_telefono_e164, normalizar_telefono
    from utils.logger import setup_dual_logger
    
    print(f"[*] Validando teléfono: {telefono}")
    telefono_normalizado = normalizar_telefono(telefono)
    
    if not telefono_normalizado or not validar_telefono_e164(telefono_normalizado):
        print(f"[!] El teléfono NO tiene formato E.164 válido. Abortando.")
        return
    
    # MODIFICACIÓN: Desempaquetar instancia del logger y la ruta de la carpeta
    logger, folder_path = setup_dual_logger(telefono_normalizado)
    
    try:
        report_data = asyncio.run(investigar_telefono_async(telefono_normalizado))
        
        # Guardado en JSON
        json_path = os.path.join(folder_path, 'report.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=4, ensure_ascii=False)
            
        # Guardado en CSV (Flattening)
        guardar_csv_telefono(report_data, folder_path)
            
    except KeyboardInterrupt:
        print("\n[!] Investigación interrumpida por el usuario")
    except Exception as e:
        print(f"\n[!] Error crítico en la investigación: {e}")
    finally:
        logger.close()
        print(f"\n[+] Resultados guardados exitosamente en: {folder_path}")
        print(f"    Archivos generados: report.txt, report.json, report.csv")