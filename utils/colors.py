# utils/colors.py
"""
utils/colors.py
Códigos de escape ANSI para dar formato y color a la salida en terminal.
"""

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Prefijos estandarizados y coloreados
INFO = f"{CYAN}[*]{RESET} "
SUCCESS = f"{GREEN}[+]{RESET} "
FAILURE = f"{RED}[-]{RESET} "
WARNING = f"{YELLOW}[!]{RESET} "
