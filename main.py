"""
main.py
Punto de entrada de OSINT-Framework.
Implementa la TUI basada en curses con tema Rojo Oscuro,
menú principal con 3 opciones y patrón Command.
"""
import curses
import subprocess
import os
import sys
from config import validate_environment
from engines.email_engine import investigar_email
from engines.phone_engine import investigar_telefono


# ============================================
# CLASES DEL PATRÓN COMMAND
# ============================================

class AccionBash:
    """Acción que ejecuta un comando de bash."""
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
    """Acción que ejecuta una función Python con argumentos."""
    def __init__(self, nombre, funcion, *args, **kwargs):
        self.nombre = nombre
        self.funcion = funcion
        self.args = args
        self.kwargs = kwargs

    def ejecutar(self):
        curses.endwin()
        os.system('clear')
        print(f"[*] Modo Interactivo: {self.nombre}")
        print("=" * 60)
        try:
            self.funcion(*self.args, **self.kwargs)
        except Exception as e:
            print(f"\n[!] Error crítico en la función: {e}")
        print("\n" + "=" * 60)
        print("\n[[-] Presiona ENTER para regresar al menú...]")
        input()


class Menu:
    """Representa un menú con opciones navegables."""
    def __init__(self, titulo):
        self.titulo = titulo
        self.opciones = []
        self.indice_actual = 0

    def agregar_opcion(self, nombre, destino):
        self.opciones.append((nombre, destino))


class AplicacionTUI:
    """Aplicación principal de TUI con curses."""
    def __init__(self, stdscr, menu_raiz):
        self.stdscr = stdscr
        self.pila_menus = [menu_raiz]
        curses.curs_set(0)
        self.stdscr.keypad(True)
        curses.start_color()
        curses.use_default_colors()
        
        # PALETA DE COLORES: Rojo Oscuro
        curses.init_pair(1, curses.COLOR_RED, -1)
        
        # Intentar un rojo más oscuro si la terminal lo soporta
        try:
            curses.init_color(9, 500, 0, 0)  # Rojo oscuro personalizado
            curses.init_pair(2, 9, -1)
            self.color_principal = curses.color_pair(2)
        except curses.error:
            # Si no se puede cambiar colores, usar rojo estándar
            self.color_principal = curses.color_pair(1)

    def dibujar_interfaz(self):
        """Dibuja la interfaz TUI completa en cada frame."""
        self.stdscr.clear()
        alto, ancho = self.stdscr.getmaxyx()
        color_rojo = self.color_principal
        
        if alto < 25 or ancho < 75:
            mensaje = "Terminal muy pequeña. Mínimo 75x25"
            try:
                self.stdscr.addstr(alto // 2, max(0, (ancho // 2) - (len(mensaje) // 2)),
                                   mensaje, color_rojo)
            except curses.error:
                pass
            self.stdscr.refresh()
            return False

        # Borde con color
        self.stdscr.attron(color_rojo)
        self.stdscr.border(0, 0, 0, 0, 0, 0, 0, 0)
        self.stdscr.attroff(color_rojo)

        menu_actual = self.pila_menus[-1]

        # Arte ASCII OSINT: Ojo vigilante (Eye of Sauron / Big Brother)
        arte_ascii = [
            r"      .-''''''-.       ",
            r"    .'          '.     ",
            r"   /   O      O   \    ",
            r"  :   .--------.   :   ",
            r"  |  /          \  |   ",
            r"  :  \__________/  :   ",
            r"   \              /    ",
            r"    '.          .'     ",
            r"      '-......-'       ",
            r"   [ SORANIN - OSINT FRAMEWORK ] ",
        ]

        titulo = f"=== {menu_actual.titulo} ==="
        
        if len(self.pila_menus) > 1:
            subtitulo = "[ ↑/↓: Navegar | ESPACIO: Seleccionar | ←: Volver | Q: Salir ]"
        else:
            subtitulo = "[ ↑/↓: Navegar | ESPACIO: Seleccionar | Q: Salir ]"

        elementos_totales = len(arte_ascii) + 5 + len(menu_actual.opciones)
        y_inicial = (alto // 2) - (elementos_totales // 2)

        # Dibujar arte ASCII
        self.stdscr.attron(color_rojo)
        for i, linea in enumerate(arte_ascii):
            x = (ancho // 2) - (len(linea) // 2)
            try:
                self.stdscr.addstr(y_inicial + i, x, linea)
            except curses.error:
                pass
        self.stdscr.attroff(color_rojo)

        # Dibujar título y subtítulo
        y_titulo = y_inicial + len(arte_ascii) + 2
        try:
            self.stdscr.addstr(y_titulo, (ancho // 2) - (len(titulo) // 2),
                               titulo, curses.A_BOLD | curses.A_UNDERLINE | color_rojo)
            self.stdscr.addstr(y_titulo + 1, (ancho // 2) - (len(subtitulo) // 2),
                               subtitulo, color_rojo)
        except curses.error:
            pass

        # Dibujar opciones del menú
        y_opciones = y_titulo + 3
        for i, (nombre, _) in enumerate(menu_actual.opciones):
            texto = f" {i + 1}. {nombre} "
            x = (ancho // 2) - (len(texto) // 2)
            
            try:
                if i == menu_actual.indice_actual:
                    self.stdscr.addstr(y_opciones + i, x, f">>{texto}<<",
                                       curses.A_REVERSE | curses.A_BOLD | color_rojo)
                else:
                    self.stdscr.addstr(y_opciones + i, x, f"  {texto}  ", color_rojo)
            except curses.error:
                pass

        self.stdscr.refresh()
        return True

    def ejecutar(self):
        """Bucle principal de la aplicación."""
        while True:
            espacio_suficiente = self.dibujar_interfaz()
            tecla = self.stdscr.getch()
            
            if not espacio_suficiente:
                if tecla in [ord('q'), ord('Q')]:
                    break
                continue
            
            menu_actual = self.pila_menus[-1]
            
            # Navegación vertical
            if tecla == curses.KEY_UP and menu_actual.indice_actual > 0:
                menu_actual.indice_actual -= 1
            elif tecla == curses.KEY_DOWN and menu_actual.indice_actual < len(menu_actual.opciones) - 1:
                menu_actual.indice_actual += 1
            # Selección
            elif tecla == ord(' ') or tecla == curses.KEY_ENTER or tecla in [10, 13]:
                destino_seleccionado = menu_actual.opciones[menu_actual.indice_actual][1]
                
                if isinstance(destino_seleccionado, Menu):
                    self.pila_menus.append(destino_seleccionado)
                elif isinstance(destino_seleccionado, (AccionBash, AccionPython)):
                    destino_seleccionado.ejecutar()
                elif destino_seleccionado == "SALIR":
                    break
            # Volver
            elif tecla == curses.KEY_LEFT or tecla == ord('b') or tecla == curses.KEY_BACKSPACE:
                if len(self.pila_menus) > 1:
                    self.pila_menus.pop()
            # Salir
            elif tecla in [ord('q'), ord('Q')]:
                break


def pedir_input(prompt_text: str):
    """
    Pide input al usuario con curses desactivado temporalmente.
    """
    curses.endwin()
    print()
    print("=" * 60)
    print(f"  {prompt_text}")
    print("=" * 60)
    valor = input(">> ").strip()
    print()
    return valor


def iniciar_investigacion_email():
    """Flujo para iniciar una investigación de email."""
    email = pedir_input("Introduce el correo electrónico a investigar (Ctrl+C para cancelar)")
    if email:
        investigar_email(email)
    else:
        print("[!] No se introdujo ningún email. Volviendo al menú.")
        input("\n[[-] Presiona ENTER para continuar...]")


def iniciar_investigacion_telefono():
    """Flujo para iniciar una investigación de teléfono."""
    telefono = pedir_input(
        "Introduce el número telefónico en formato E.164\n"
        "   (Ej: +34666777888, +15551234567) (Ctrl+C para cancelar)"
    )
    if telefono:
        investigar_telefono(telefono)
    else:
        print("[!] No se introdujo ningún teléfono. Volviendo al menú.")
        input("\n[[-] Presiona ENTER para continuar...]")


def main(stdscr):
    """Función principal que configura la TUI."""
    # Validar entorno al inicio
    warnings = validate_environment()
    if warnings:
        curses.endwin()
        print("\n[!] ADVERTENCIAS DE CONFIGURACIÓN:")
        for w in warnings:
            print(f"    - {w}")
        print("\n    Algunas funcionalidades pueden estar limitadas.\n")
        input("[[-] Presiona ENTER para continuar...]")

    # Crear árbol de menús
    menu_principal = Menu("OSINT-FRAMEWORK | Menú Principal")
    menu_principal.agregar_opcion("OSINT a Correos Electrónicos",
                                   AccionPython("Investigación de Email",
                                                iniciar_investigacion_email))
    menu_principal.agregar_opcion("OSINT a Números Telefónicos",
                                   AccionPython("Investigación de Teléfono",
                                                iniciar_investigacion_telefono))
    menu_principal.agregar_opcion("Salir", "SALIR")

    # Iniciar aplicación
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
