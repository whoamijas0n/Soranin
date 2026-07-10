"""
utils/logger.py
Implementación del Dual Logger (Tee) que intercepta sys.stdout
para imprimir en consola y escribir en archivo simultáneamente.
"""
import sys
import os
from datetime import datetime


class TeeLogger:
    """
    Clase que duplica la salida: consola + archivo de log.
    Intercepta sys.stdout para capturar todos los print().
    """
    
    def __init__(self, filepath):
        """
        Inicializa el Dual Logger.
        
        Args:
            filepath: Ruta del archivo donde se guardarán los logs.
        """
        self.terminal = sys.__stdout__  # Terminal real
        self.filepath = filepath
        self.log_file = None
        self._open_file()
        
        # Parchear sys.stdout
        self._original_stdout = sys.stdout
        sys.stdout = self
    
    def _open_file(self):
        """Abre el archivo de log en modo append."""
        try:
            # Crear directorio si no existe
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            self.log_file = open(self.filepath, "a", encoding="utf-8")
        except (IOError, OSError) as e:
            self.terminal.write(f"[!] Error al abrir archivo de log: {e}\n")
            self.log_file = None
    
    def write(self, message):
        """
        Escribe el mensaje tanto en la terminal como en el archivo.
        Agrega timestamp al archivo pero no a la terminal.
        """
        if message and message.strip():  # Evita líneas vacías
            # Escribir en terminal (sin timestamp)
            try:
                self.terminal.write(message)
            except Exception:
                pass
            
            # Escribir en archivo (con timestamp)
            if self.log_file:
                try:
                    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S] ")
                    # Solo agregar timestamp si la línea no está vacía
                    if message.strip():
                        self.log_file.write(timestamp + message)
                    else:
                        self.log_file.write(message)
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
        """Restaura sys.stdout y cierra el archivo."""
        sys.stdout = self._original_stdout
        if self.log_file:
            self.log_file.close()
            self.log_file = None
    
    def __del__(self):
        """Destructor: cierra el archivo si está abierto."""
        if self.log_file:
            self.close()


def setup_dual_logger(target_name):
    """
    Configura el Dual Logger para una investigación específica.
    
    Args:
        target_name: Nombre del objetivo (email o teléfono)
        
    Returns:
        Instancia de TeeLogger configurada
    """
    from config import RESULTS_FOLDER
    from datetime import datetime
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"{target_name}_{timestamp}.txt"
    filepath = os.path.join(RESULTS_FOLDER, filename)
    
    # Mensaje de inicio
    sys.stdout.write(f"\n[+] Iniciando Dual Logger -> {filepath}\n")
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write(f"[+] Objetivo: {target_name}\n")
    sys.stdout.write(f"[+] Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    sys.stdout.write("=" * 60 + "\n\n")
    
    return TeeLogger(filepath)
