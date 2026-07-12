# 

<div align="center">

<img src="img/logo.png" alt="logo" width="800" height="auto" />

<h1>Soranin</h1>

**OSINT-Framework** — Rastreo de Identidades, Data Breach Hunting & OSINT

<br/>

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)


</div>
<br/>

Soranin es un framework de Inteligencia de Fuentes Abiertas (OSINT) avanzado, diseñado para automatizar y centralizar investigaciones digitales sobre correos electrónicos y números de teléfono.

La herramienta ejecuta de forma asíncrona múltiples módulos que consultan diversas bases de datos y plataformas web para descubrir presencia en redes sociales, información de operadores telefónicos, menciones públicas en la web y posibles filtraciones de datos (brechas de seguridad). Además, incluye un sistema automático de guardado que exporta de manera limpia los resultados de cada investigación a una carpeta local llamada Resultados.

<div align="center">

## Instalación

</div>

Para utilizar Soranin, es requisito indispensable tener Python instalado en tu sistema.

Abre tu terminal y ejecuta el siguiente comando exacto para instalar todas las dependencias necesarias:

```bash
pip install python-dotenv aiohttp trio httpx holehe git+https://github.com/megadose/ignorant.git

```
<div align="center">


## Configuración del Archivo `.env` (APIs)

</div>

Soranin potencia sus búsquedas utilizando diversas APIs externas que recolectan información estructurada de diferentes fuentes. Para que estas integraciones funcionen, el usuario debe crear un archivo llamado `.env` en el directorio raíz del proyecto.

Copia y pega exactamente la siguiente plantilla en tu archivo `.env`:

```text
# ============================================
# OSINT-Framework - Configuración de APIs
# ============================================
# Obtén tus API Keys en los servicios correspondientes

# Have I Been Pwned (https://haveibeenpwned.com/API/Key)
HIBP_API_KEY=tu_hibp_api_key_aqui

# IntelX (https://intelx.io/signup)
INTELX_API_KEY=529ca4ba-4318-410a-930a-a3dff07d5f85

# SerpApi - Google Dorks (https://serpapi.com/)
SERPAPI_KEY=28e4c7445825d72793d2b57592a4126c6e0bcd3a0a5d97a18dc72ea770a4dcfe

# NumVerify - Validación de teléfonos (https://numverify.com/)
NUMVERIFY_KEY=b004a709d55508c51d071bb838ea6997

# Social Searcher (https://www.social-searcher.com/)
SOCIAL_SEARCHER_KEY=tu_social_searcher_key_aqui

# Dehashed (https://www.dehashed.com/) - Opcional
DEHASHED_KEY=
DEHASHED_EMAIL=

```

<div align="center">

## Explicación de las APIs (Costos y Utilidad)

</div>

A continuación, se detalla el uso de cada API dentro del entorno de Soranin, su propósito y su modelo de costos:

- Have I Been Pwned: Busca el correo electrónico analizado en un amplio catálogo de filtraciones y brechas de bases de datos. (De pago).

- IntelX: Realiza búsquedas de menciones del correo electrónico en la Dark Web y en Pastebins. (Tiene una capa gratuita que la herramienta detecta y usa automáticamente como respaldo si la API Key no es premium, además de la capa de pago).

- SerpApi: Automatiza ejecuciones de búsquedas avanzadas en Google (conocidas como Google Dorks) tanto para correos electrónicos como para números de teléfono, limitando y analizando los resultados orgánicos de manera eficiente. (Tiene capa gratuita mensual).

- NumVerify: Encargada de validar números de teléfono para obtener datos esenciales como el país, el operador de red y detectar si se trata de un número de línea virtual (VoIP) o temporal. (Tiene capa gratuita).

- Social Searcher: Realiza un rastreo en redes sociales y la web pública para localizar menciones específicas del número de teléfono ingresado. (Tiene capa gratuita).

- Dehashed: Motor alternativo y de respaldo para localizar los correos electrónicos dentro de bases de datos hackeadas. (De pago / Opcional).

> Nota importante: Soranin utiliza de manera integral otros potentes módulos gratuitos que no requieren API Key. 
> - Entre ellos están Gravatar, consultas públicas de contactos a WhatsApp y Telegram, y las librerías Holehe e Ignorant.
> - Holehe verifica la existencia de cuentas vinculadas a un email en más de 120 sitios web, mientras que Ignorant hace lo propio en redes sociales (como Instagram, Amazon, etc.) utilizando el número telefónico. 

<div align="center">

## Configuración de Proxies (Archivo `config.py`)

</div>

Para maximizar la efectividad en la recolección de datos, Soranin permite el uso de Proxies. Esto ayuda a prevenir el bloqueo por límite de peticiones (Rate Limiting) en las plataformas consultadas. Es una característica especialmente útil y recomendada al utilizar los exhaustivos módulos de Holehe (para emails) e Ignorant (para teléfonos).

Para configurarlos:

- Abre el archivo `config.py` en tu editor de texto.

- Localiza la lista denominada `PROXIES_LIST`.

- Añade tus proxies, uno por línea, siguiendo obligatoriamente este formato de cadena: `"protocolo://usuario:password@host:puerto"`.

Ejemplos de configuración válidos:

- `"http://proxy1.example.com:8080"`

- `"socks5://user:pass@proxy2.example.com:1080"`

> Si la lista de proxies está vacía, Soranin utilizará su conexión directa predeterminada.

<div align="center">

## Uso de la Herramienta

</div>

Para iniciar el programa, sitúate en la raíz del proyecto y ejecuta en tu terminal:

```bash
python main.py
```

Al iniciarse, serás recibido por la interfaz de usuario interactiva del menú principal. Para navegar entre las opciones (OSINT a Correos Electrónicos u OSINT a Números Telefónicos), utiliza las flechas de dirección (arriba/abajo), presiona la tecla ESPACIO para seleccionar una opción, o presiona Q para salir de la aplicación.

Reglas de formato para las búsquedas:

- Emails: Deben poseer una sintaxis de correo electrónico válida. El sistema cuenta con validación estricta y, además, te advertirá si detecta que estás investigando un dominio de correo desechable o temporal (como tempmail o yopmail).

- Teléfonos: Deben ser ingresados utilizando el estándar internacional E.164. Esto significa que el número debe incluir su respectivo código de país precedido por un signo más (`+`). Por ejemplo: `+34666777888` o `+15551234567`. Si omites el código de país y el signo `+`, Soranin intentará deducirlo y normalizarlo de forma automática.

<div align="center">

## Resultados

</div>

Durante el proceso, Soranin te mostrará el avance y los descubrimientos de la investigación en tiempo real directamente en la pantalla de la terminal.

Para preservar la información recolectada de forma cómoda, la herramienta utiliza un sistema interno (Dual Logger). Esto significa que, paralelamente a la visualización, se generará y guardará de manera automática un informe de texto completo en formato `.txt` dentro de la carpeta `Resultados`. Este archivo es procesado y limpiado para asegurar que no posea códigos extraños de colores de la terminal (códigos ANSI), dejando un registro organizado, legible y con marcas de tiempo exactas para un posterior análisis.