import curses
import subprocess
import os
import sys
import pkgutil
import importlib
import inspect
from config import validate_environment

# Importamos la clase base y el paquete engines para la carga dinámica
import engines
from engines.base_plugin import BasePlugin
import random

# ============================================
# ARTE ASCII GLOBAL 
# ============================================
ARTE_SORANIN = r"""

                        ░░░░░░░░░░░░░░░░░░░░░░░░     
                  ░░░░░░░░░░▒▒░░░░░░░░░░░░░░░░░░░░          
              ░░░░░░░░▒▒▒▒▒▒▓▓▒▒▒▒░░▒▒▒▒▒▒▒▒░░░░░░░░        
            ░░░░░░▒▒▒▒▓▓▒▒▒▒░░░░░░░░░░░░░░░░░░▒▒▒▒░░░░      
          ░░░░▒▒▓▓▓▓▒▒░░▒▒░░▒▒▒▒▒▒▒▒▒▒▒▒░░░░░░░░░░▒▒▒▒░░    
        ░░░░▒▒▓▓▒▒▒▒▒▒▓▓▓▓▓▓▓▓▓▓████▓▓▓▓▓▓▒▒░░░░░░░░▒▒▒▒░░  
      ░░░░▓▓██▒▒░░▒▒▓▓▓▓▓▓▒▒▓▓████▓▓░░  ▓▓██▓▓▒▒░░░░  ▒▒▒▒  
    ░░░░▒▒▓▓▒▒▒▒▓▓██▓▓▒▒░░░░████████▒▒▒▒▒▒▓▓▓▓░░▒▒░░░░  ░░░░
    ░░▒▒▓▓▒▒▓▓▓▓▓▓▓▓▒▒░░░░░░▓▓▒▒▓▓██████▒▒▒▒▓▓  ░░▒▒▒▒░░  ░░
  ░░▒▒▓▓▓▓▓▓▓▓▓▓▓▓▒▒░░      ▓▓▒▒▒▒██████░░▒▒▒▒      ░░▒▒▒▒  
░░░░▓▓▓▓▓▓▓▓▓▓▒▒▒▒▒▒░░      ▓▓▒▒▒▒░░▒▒░░▒▒▒▒▒▒      ░░░░░░▒▒
  ░░▒▒▒▒▒▒▒▒▒▒▒▒░░▒▒░░░░    ░░▓▓░░░░░░▒▒▒▒▒▒░░      ░░░░░░░░
    ░░  ░░░░░░▒▒▒▒▒▒░░░░░░░░  ░░▒▒▒▒▒▒▒▒░░░░░░░░            
          ░░░░░░░░░░▒▒▒▒▒▒░░░░░░  ░░░░░░░░░░░░░░            
              ░░░░░░░░░░░░░░▒▒▒▒▒▒▒▒▒▒░░░░    
                ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░                   

   [ SORANIN - OSINT FRAMEWORK ] 
"""

class AccionBash:
    def __init__(self, nombre, comando):
        self.nombre = nombre
        self.comando = comando

    def ejecutar(self):
        curses.endwin()
        os.system('clear')
        print(f"[*] Ejecutando: {self.nombre}")
        print("=" * 60 + "\n")
        try:
            subprocess.run(self.comando, shell=True)
        except Exception as e:
            print(f"[!] Error crítico al ejecutar: {e}")
        print("\n" + "=" * 60)
        print("\n[[-] Presiona ENTER para regresar al menú...]")
        input()

class AccionPython:
    def __init__(self, nombre, funcion, *args, **kwargs):
        self.nombre = nombre
        self.funcion = funcion
        self.args = args
        self.kwargs = kwargs

    def ejecutar(self):
        curses.endwin()
        os.system('clear')
        try:
            self.funcion(*self.args, **self.kwargs)
        except Exception as e:
            print(f"\n[!] Error crítico en la función: {e}")
        print("\n[[-] Presiona ENTER para regresar al menú...]")
        input()

class Menu:
    def __init__(self, titulo):
        self.titulo = titulo
        self.opciones = []
        self.indice_actual = 0

    def agregar_opcion(self, nombre, destino):
        self.opciones.append((nombre, destino))

class AplicacionTUI:
    # (El código de AplicacionTUI y animar_splash_screen se mantiene EXACTAMENTE igual al original)
    def __init__(self, stdscr, menu_raiz):
        self.stdscr = stdscr
        self.pila_menus = [menu_raiz]
        curses.curs_set(0)
        self.stdscr.keypad(True)
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_RED, -1)
        try:
            curses.init_color(9, 500, 0, 0)
            curses.init_pair(2, 9, -1)
            self.color_principal = curses.color_pair(2)
        except curses.error:
            self.color_principal = curses.color_pair(1)

    def dibujar_interfaz(self):
        self.stdscr.clear()
        alto, ancho = self.stdscr.getmaxyx()
        color_rojo = self.color_principal
        
        if alto < 25 or ancho < 75:
            mensaje = "Terminal muy pequeña. Mínimo 75x25"
            try:
                self.stdscr.addstr(alto // 2, max(0, (ancho // 2) - (len(mensaje) // 2)), mensaje, color_rojo)
            except curses.error:
                pass
            self.stdscr.refresh()
            return False

        self.stdscr.attron(color_rojo)
        self.stdscr.border(0, 0, 0, 0, 0, 0, 0, 0)
        self.stdscr.attroff(color_rojo)

        menu_actual = self.pila_menus[-1]
        arte_ascii = ARTE_SORANIN.strip('\n').split('\n')
        titulo = f"=== {menu_actual.titulo} ==="
        
        subtitulo = "[ ↑/↓: Navegar | ESPACIO: Seleccionar | ←: Volver | Q: Salir ]" if len(self.pila_menus) > 1 else "[ ↑/↓: Navegar | ESPACIO: Seleccionar | Q: Salir ]"
        elementos_totales = len(arte_ascii) + 5 + len(menu_actual.opciones)
        y_inicial = (alto // 2) - (elementos_totales // 2)

        self.stdscr.attron(color_rojo)
        for i, linea in enumerate(arte_ascii):
            x = (ancho // 2) - (len(linea) // 2)
            try:
                self.stdscr.addstr(y_inicial + i, max(0, x), linea)
            except curses.error:
                pass
        self.stdscr.attroff(color_rojo)

        y_titulo = y_inicial + len(arte_ascii) + 2
        try:
            self.stdscr.addstr(y_titulo, (ancho // 2) - (len(titulo) // 2), titulo, curses.A_BOLD | curses.A_UNDERLINE | color_rojo)
            self.stdscr.addstr(y_titulo + 1, (ancho // 2) - (len(subtitulo) // 2), subtitulo, color_rojo)
        except curses.error:
            pass

        y_opciones = y_titulo + 3
        for i, (nombre, _) in enumerate(menu_actual.opciones):
            texto = f" {i + 1}. {nombre} "
            x = (ancho // 2) - (len(texto) // 2)
            try:
                if i == menu_actual.indice_actual:
                    self.stdscr.addstr(y_opciones + i, x, f">>{texto}<<", curses.A_REVERSE | curses.A_BOLD | color_rojo)
                else:
                    self.stdscr.addstr(y_opciones + i, x, f"  {texto}  ", color_rojo)
            except curses.error:
                pass

        self.stdscr.refresh()
        return True

    def animar_splash_screen(self):
        arte_ascii = ARTE_SORANIN.strip('\n').split('\n')
        ruido_chars = ["░", "▒", "▓", "█", "#", "@", "%", "*"]
        frames_totales = 18
        
        for frame in range(frames_totales + 1):
            self.stdscr.clear()
            alto, ancho = self.stdscr.getmaxyx()
            if alto < 25 or ancho < 75: break
            self.stdscr.attron(self.color_principal)
            self.stdscr.border(0, 0, 0, 0, 0, 0, 0, 0)
            nivel_ruido = 1.0 - (frame / frames_totales)
            y_inicial = (alto // 2) - (len(arte_ascii) // 2)
            for i, linea in enumerate(arte_ascii):
                linea_borrosa = "".join([random.choice(ruido_chars) if char not in (" ", "\n") and random.random() < nivel_ruido else char for char in linea])
                x = (ancho // 2) - (len(linea_borrosa) // 2)
                try: self.stdscr.addstr(y_inicial + i, max(0, x), linea_borrosa)
                except curses.error: pass
            self.stdscr.attroff(self.color_principal)
            self.stdscr.refresh()
            curses.napms(80)
        curses.napms(500)

    def ejecutar(self):
        self.animar_splash_screen()
        while True:
            espacio_suficiente = self.dibujar_interfaz()
            tecla = self.stdscr.getch()
            
            if not espacio_suficiente:
                if tecla in [ord('q'), ord('Q')]: break
                continue
            
            menu_actual = self.pila_menus[-1]
            if tecla == curses.KEY_UP and menu_actual.indice_actual > 0:
                menu_actual.indice_actual -= 1
            elif tecla == curses.KEY_DOWN and menu_actual.indice_actual < len(menu_actual.opciones) - 1:
                menu_actual.indice_actual += 1
            elif tecla == ord(' ') or tecla == curses.KEY_ENTER or tecla in [10, 13]:
                destino = menu_actual.opciones[menu_actual.indice_actual][1]
                if isinstance(destino, Menu): self.pila_menus.append(destino)
                elif isinstance(destino, (AccionBash, AccionPython)): destino.ejecutar()
                elif destino == "SALIR": break
            elif tecla == curses.KEY_LEFT or tecla == ord('b') or tecla == curses.KEY_BACKSPACE:
                if len(self.pila_menus) > 1: self.pila_menus.pop()
            elif tecla in [ord('q'), ord('Q')]: break

# ============================================
# GESTOR DINÁMICO DE PLUGINS
# ============================================
def cargar_plugins_dinamicos(menu: Menu):
    """
    Escanea la carpeta 'engines', importa los módulos dinámicamente y
    registra en el menú todas las clases que hereden de BasePlugin.
    """
    paquete = engines
    prefix = paquete.__name__ + "."
    
    for _, modname, _ in pkgutil.iter_modules(paquete.__path__, prefix):
        # Evitar importar la propia clase base
        if modname == "engines.base_plugin":
            continue
            
        try:
            modulo = importlib.import_module(modname)
            for nombre_clase, obj_clase in inspect.getmembers(modulo, inspect.isclass):
                if issubclass(obj_clase, BasePlugin) and obj_clase is not BasePlugin:
                    # Instanciar el plugin
                    plugin = obj_clase()
                    # Vincular la acción al método 'ejecutar()' del plugin (Template Method)
                    menu.agregar_opcion(
                        plugin.menu_name,
                        AccionPython(plugin.menu_name, plugin.ejecutar)
                    )
        except Exception as e:
            # Puedes registrar si falla la importación de un plugin (ej. dependencias faltantes)
            pass


def main(stdscr):
    warnings = validate_environment()
    if warnings:
        curses.endwin()
        print("\n[!] ADVERTENCIAS DE CONFIGURACIÓN:")
        for w in warnings:
            print(f"    - {w}")
        print("\n    Algunas funcionalidades pueden estar limitadas.\n")
        input("[[-] Presiona ENTER para continuar...]")

    menu_principal = Menu("OBSERVA EL MUNDO DE UNA MANERA DISTINTA")
    
    # 1. Cargar Plugins Automáticamente en lugar de hardcodear
    cargar_plugins_dinamicos(menu_principal)
    
    # 2. Añadir la opción de salida
    menu_principal.agregar_opcion("Salir", "SALIR")

    app = AplicacionTUI(stdscr, menu_principal)
    app.ejecutar()

if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        print("\n[!] OSINT-Framework terminado por el usuario.")
        sys.exit(0)
    except Exception as e:
        print(f"\n[!] Error fatal: {e}")
        sys.exit(1)
    finally:
        print("\n[+] Hasta luego.\n")