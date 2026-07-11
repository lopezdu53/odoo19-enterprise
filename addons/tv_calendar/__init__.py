import calendar
from datetime import date

from . import models
from . import controllers


def post_init_hook(env):
    """Crea unas tareas de ejemplo en el tablero por defecto (solo si esta
    vacio) para que la pantalla del TV muestre algo nada mas instalar."""
    board = env.ref('tv_calendar.board_default', raise_if_not_found=False)
    if not board or board.task_ids:
        return
    today = date.today()
    last_day = calendar.monthrange(today.year, today.month)[1]

    def day(number):
        return today.replace(day=min(number, last_day))

    env['tv.calendar.task'].create([
        {'name': 'Reunion de equipo', 'board_id': board.id,
         'importance': 'normal', 'date': day(3)},
        {'name': 'Entrega cliente', 'board_id': board.id,
         'importance': 'critical', 'date': day(12)},
        {'name': 'Mantenimiento servidores', 'board_id': board.id,
         'importance': 'high', 'date': day(18), 'date_end': day(19)},
        {'name': 'Revision inventario', 'board_id': board.id,
         'importance': 'low', 'date': day(25)},
    ])
