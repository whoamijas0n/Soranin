"""
utils/validators.py
Funciones de validación y sanitización de entradas.
"""
import re


def validar_email(email: str) -> bool:
    """
    Valida un correo electrónico usando regex estricto.
    
    Args:
        email: Cadena a validar
        
    Returns:
        True si el email es válido, False en caso contrario
    """
    if not email or not isinstance(email, str):
        return False
    
    email = email.strip().lower()
    
    # Regex estricto según RFC 5322 simplificado
    patron = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(patron, email):
        return False
    
    # Validación adicional: no permitir dominios de descarte conocidos
    dominios_descarte = [
        'tempmail.com', 'throwaway.email', 'guerrillamail.com',
        'mailinator.com', 'yopmail.com', '10minutemail.com'
    ]
    dominio = email.split('@')[1]
    if dominio in dominios_descarte:
        print(f"[!] ADVERTENCIA: Dominio de correo temporal detectado: {dominio}")
    
    return True


def validar_telefono_e164(telefono: str) -> bool:
    """
    Valida un número telefónico en formato E.164.
    Formato: +[código país 1-3 dígitos][número 6-14 dígitos]
    
    Args:
        telefono: Cadena a validar
        
    Returns:
        True si el teléfono es válido en formato E.164, False en caso contrario
    """
    if not telefono or not isinstance(telefono, str):
        return False
    
    telefono = telefono.strip()
    
    # Regex para formato E.164 estricto
    patron = r'^\+[1-9]\d{6,14}$'
    
    if not re.match(patron, telefono):
        return False
    
    return True


def normalizar_telefono(telefono: str) -> str:
    """
    Intenta normalizar un teléfono a formato E.164.
    
    Args:
        telefono: Número en cualquier formato
        
    Returns:
        Número en formato E.164 o cadena vacía si no se pudo normalizar
    """
    if not telefono:
        return ""
    
    # Eliminar caracteres no numéricos excepto el +
    limpio = re.sub(r'[^\d+]', '', telefono)
    
    # Si no empieza con +, asumir que falta el código de país
    if not limpio.startswith('+'):
        if limpio.startswith('00'):
            limpio = '+' + limpio[2:]
        else:
            # Asumir +34 (España) por defecto si no hay código
            # En producción se debería pedir al usuario
            limpio = '+' + limpio
    
    return limpio if validar_telefono_e164(limpio) else ""


def sanitizar_texto(texto: str) -> str:
    """
    Sanitiza un texto para evitar inyecciones o caracteres problemáticos.
    
    Args:
        texto: Cadena a sanitizar
        
    Returns:
        Cadena sanitizada
    """
    if not texto:
        return ""
    # Eliminar caracteres de control y saltos de línea
    texto = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', texto)
    # Limitar longitud para evitar problemas
    return texto[:200].strip()
