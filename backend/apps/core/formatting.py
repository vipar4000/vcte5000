from django.utils.formats import number_format


def format_euros(value, decimales=2):
    """
    Formatea un importe en notación española: punto para miles, coma para
    decimales (ej. 8.294,00 EUR). Usa la localización activa (es-es).
    """
    return f"{number_format(value, decimales)} EUR"
