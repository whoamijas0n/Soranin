import sys
import os
import re
from datetime import datetime

class TeeLogger:
    """
    Clase que duplica la salida: consola (con colores) + archivo de log (limpio y ordenado).
    Intercepta sys.stdout para capturar de forma segura la salida de los hilos/tareas asíncronas.
    """
    
    def __init__(self, filepath):
        """Inicializa el Dual Logger."""
        self.terminal = sys.__stdout__  # Terminal nativa
        self.filepath = filepath
        self.log_file = None
        self.at_start_of_line = True  # Flag para rastrear saltos de línea reales
        
        # Regex para remover códigos de escape ANSI
        self.ansi_cleaner = re.compile(r'\x1b\[[0-9;]*[mK]')
        
        self._open_file()
        
        # Parchear sys.stdout
        self._original_stdout = sys.stdout
        sys.stdout = self
    
    def _open_file(self):
        """Abre el archivo de log en modo append."""
        try:
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            self.log_file = open(self.filepath, "a", encoding="utf-8")
        except (IOError, OSError) as e:
            self.terminal.write(f"\033[91m[!] Error al abrir archivo de log: {e}\033[0m\n")
            self.log_file = None
    
    def write(self, message):
        """Escribe en terminal (con colores) y en archivo (sanitizado y con timestamps correctos)."""
        if not message:
            return

        # 1. Escribir siempre el mensaje crudo (con colores ANSI) a la terminal
        try:
            self.terminal.write(message)
        except Exception:
            pass
        
        # 2. Procesar y escribir el mensaje sanitizado al archivo de texto
        if self.log_file:
            try:
                # Quitar los códigos de color ANSI
                clean_message = self.ansi_cleaner.sub('', message)
                
                # Procesar carácter por carácter o fragmento para ubicar los timestamps correctamente
                lines = clean_message.split('\n')
                for i, line in enumerate(lines):
                    # Si es un fragmento intermedio debido a un split por '\n'
                    if i > 0:
                        self.log_file.write('\n')
                        self.at_start_of_line = True
                    
                    if line:
                        if self.at_start_of_line:
                            timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S] ")
                            self.log_file.write(timestamp)
                            self.at_start_of_line = False
                        self.log_file.write(line)
                        
                self.log_file.flush()
            except Exception:
                pass
    
    def flush(self):
        """Sincroniza los buffers de salida."""
        try:
            self.terminal.flush()
        except Exception:
            pass
        if self.log_file:
            try:
                self.log_file.flush()
            except Exception:
                pass
    
    def close(self):
        """Restaura sys.stdout y cierra el archivo de forma segura."""
        sys.stdout = self._original_stdout
        if self.log_file:
            self.log_file.close()
            self.log_file = None
    
    def __del__(self):
        """Asegura el cierre del archivo al destruir el objeto."""
        if hasattr(self, 'log_file') and self.log_file:
            self.close()


def setup_dual_logger(target_name):
    """
    Configura el Dual Logger aplicando los estilos ANSI iniciales.
    MODIFICACIÓN: Crea una subcarpeta única por objetivo y tiempo, 
    retornando la instancia del logger y la ruta del directorio base.
    """
    from config import RESULTS_FOLDER
    from utils.colors import CYAN, BOLD, RESET
    
    # Formato de carpeta solicitado: YYYY-MM-DD_HH-MM-SS
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # Sanitizar target_name para nombres de carpeta seguros
    safe_target = target_name.replace("+", "plus").replace("@", "_at_")
    
    # Construir ruta de carpeta única
    folder_name = f"{safe_target}_{timestamp}"
    folder_path = os.path.join(RESULTS_FOLDER, folder_name)
    
    # Crear directorio maestro para esta auditoría
    os.makedirs(folder_path, exist_ok=True)
    
    # El archivo de log de texto base
    filepath = os.path.join(folder_path, "report.txt")
    
    sys.stdout.write(f"\n{CYAN}{BOLD}[+] Iniciando Dual Logger -> Directorio: {folder_path}{RESET}\n")
    sys.stdout.write(f"{CYAN}" + "=" * 60 + f"{RESET}\n")
    sys.stdout.write(f"{CYAN}{BOLD}[+] Objetivo:{RESET} {target_name}\n")
    sys.stdout.write(f"{CYAN}{BOLD}[+] Fecha:{RESET} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    sys.stdout.write(f"{CYAN}" + "=" * 60 + f"{RESET}\n\n")
    
    # Retornar tupla para posibilitar el guardado de CSV y JSON post-análisis
    return TeeLogger(filepath), folder_path