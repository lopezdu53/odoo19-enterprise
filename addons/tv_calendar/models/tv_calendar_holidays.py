from datetime import date, timedelta


def _easter(year):
    """Domingo de Pascua (algoritmo de Meeus/Jones/Butcher, calendario gregoriano)."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _next_monday(d):
    """Ley Emiliani: si no cae lunes, se traslada al lunes siguiente."""
    if d.weekday() == 0:
        return d
    return d + timedelta(days=(7 - d.weekday()))


def colombian_holidays(year):
    """Devuelve {fecha: nombre} con los festivos de Colombia de un anio."""
    easter = _easter(year)
    holidays = {}

    # Fechas fijas (no se trasladan)
    for d, name in [
        (date(year, 1, 1), 'Ano Nuevo'),
        (date(year, 5, 1), 'Dia del Trabajo'),
        (date(year, 7, 20), 'Independencia'),
        (date(year, 8, 7), 'Batalla de Boyaca'),
        (date(year, 12, 8), 'Inmaculada Concepcion'),
        (date(year, 12, 25), 'Navidad'),
    ]:
        holidays[d] = name

    # Ley Emiliani (se trasladan al lunes siguiente)
    for d, name in [
        (date(year, 1, 6), 'Reyes Magos'),
        (date(year, 3, 19), 'San Jose'),
        (date(year, 6, 29), 'San Pedro y San Pablo'),
        (date(year, 8, 15), 'Asuncion de la Virgen'),
        (date(year, 10, 12), 'Dia de la Raza'),
        (date(year, 11, 1), 'Todos los Santos'),
        (date(year, 11, 11), 'Independencia de Cartagena'),
    ]:
        holidays[_next_monday(d)] = name

    # Fechas moviles basadas en la Pascua
    holidays[easter - timedelta(days=3)] = 'Jueves Santo'
    holidays[easter - timedelta(days=2)] = 'Viernes Santo'
    holidays[_next_monday(easter + timedelta(days=39))] = 'Ascension del Senor'
    holidays[_next_monday(easter + timedelta(days=60))] = 'Corpus Christi'
    holidays[_next_monday(easter + timedelta(days=68))] = 'Sagrado Corazon'

    return holidays


def holidays_for_years(years):
    """Combina los festivos de varios anios en un solo dict."""
    result = {}
    for y in set(years):
        result.update(colombian_holidays(y))
    return result
