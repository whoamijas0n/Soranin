from abc import ABC, abstractmethod
import asyncio
import aiohttp
import json
import os
from typing import Dict, Any

from utils.logger import setup_dual_logger

class BasePlugin(ABC):
    
    @property
    @abstractmethod
    def menu_name(self) -> str:
        """Nombre del plugin que aparecerá en el menú dinámico de curses."""
        pass

    @property
    @abstractmethod
    def input_prompt(self) -> str:
        """El texto que se le mostrará al usuario para pedirle el dato objetivo."""
        pass

    def normalize_input(self, target: str) -> str:
        """Permite a los plugins sanitizar o normalizar el input (ej. añadir + al teléfono)."""
        return target.strip()

    @abstractmethod
    def validate_input(self, target: str) -> bool:
        """Función estricta de validación del objetivo."""
        pass

    @abstractmethod
    async def run_async(self, target: str, session: aiohttp.ClientSession) -> Dict[str, Any]:
        """Lógica principal asíncrona que el plugin debe ejecutar. Retorna el diccionario de resultados."""
        pass

    @abstractmethod
    def export_to_csv(self, data: Dict[str, Any], folder_path: str) -> None:
        """Lógica para aplanar el diccionario y guardarlo como report.csv"""
        pass

    def pedir_input(self) -> str:
        """Pide input al usuario en la terminal estándar."""
        print("\n" + "=" * 60)
        print(f"  {self.input_prompt}")
        print("=" * 60)
        return input(">> ").strip()

    def ejecutar(self) -> None:
        """
        Template Method: Orquesta todo el flujo de auditoría sin duplicar código en los hijos.
        Se ejecuta desde main.py con curses suspendido.
        """
        raw_target = self.pedir_input()
        if not raw_target:
            print("[!] No se introdujo ningún dato. Volviendo al menú.")
            return
            
        target = self.normalize_input(raw_target)
        if not self.validate_input(target):
            print(f"[!] Entrada inválida o no soportada. Abortando investigación.")
            return

        # 1. Crear carpeta dinámica e iniciar el Logger
        logger, folder_path = setup_dual_logger(target)
        
        try:
            # 2. Ejecutar la recolección de datos asíncrona
            report_data = asyncio.run(self._runner(target))
            
            # 3. Guardado en JSON estandarizado
            json_path = os.path.join(folder_path, 'report.json')
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=4, ensure_ascii=False)
                
            # 4. Guardado en CSV (Delegado al hijo)
            self.export_to_csv(report_data, folder_path)
            
        except KeyboardInterrupt:
            print("\n[!] Investigación interrumpida por el usuario")
        except Exception as e:
            print(f"\n[!] Error crítico en la investigación: {e}")
        finally:
            logger.close()
            print(f"\n[+] Resultados guardados exitosamente en: {folder_path}")
            print(f"    Archivos generados: report.txt, report.json, report.csv")

    async def _runner(self, target: str) -> Dict[str, Any]:
        """Inicia la sesión aiohttp compartida y llama a run_async del hijo."""
        # Se puede centralizar el límite de semáforos aquí
        connector = aiohttp.TCPConnector(limit=15, limit_per_host=5)
        timeout = aiohttp.ClientTimeout(total=120)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            return await self.run_async(target, session)