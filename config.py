"""
config.py
Carga centralizada de variables de entorno desde .env
"""
import os
from dotenv import load_dotenv

# Cargar variables desde .env
load_dotenv()

# API Keys
HIBP_API_KEY = os.getenv("HIBP_API_KEY")
INTELX_API_KEY = os.getenv("INTELX_API_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
NUMVERIFY_KEY = os.getenv("NUMVERIFY_KEY")
SOCIAL_SEARCHER_KEY = os.getenv("SOCIAL_SEARCHER_KEY")
DEHASHED_KEY = os.getenv("DEHASHED_KEY")
DEHASHED_EMAIL = os.getenv("DEHASHED_EMAIL")

# Configuración General
RESULTS_FOLDER = "Resultados"
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; SM-S908B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# ============================================
# CONFIGURACIÓN DE PROXIES
# ============================================
# Lista de proxies en formato: protocolo://usuario:password@host:puerto
# Ejemplos:
#   - "http://proxy1.example.com:8080"
#   - "http://user:pass@proxy2.example.com:3128"
#   - "socks5://user:pass@proxy3.example.com:1080"

PROXIES_LIST = [
    # Agrega tus proxies aquí (uno por línea)
    # "http://user:pass@proxy1.example.com:8080",
    # "http://user:pass@proxy2.example.com:8080",
    # "socks5://user:pass@proxy3.example.com:1080",
]

# Si no hay proxies configurados, usar conexión directa
USE_PROXIES = len(PROXIES_LIST) > 0

def get_user_agent():
    """Retorna un User-Agent aleatorio de la lista."""
    import random
    return random.choice(USER_AGENTS)

def validate_environment():
    """Valida que al menos las APIs críticas estén configuradas."""
    warnings = []
    if not HIBP_API_KEY:
        warnings.append("HIBP_API_KEY no configurada")
    if not SERPAPI_KEY:
        warnings.append("SERPAPI_KEY no configurada (los Google Dorks no funcionarán)")
    return warnings

