import calendar
from datetime import date

from . import models
from . import controllers
from .models.tv_calendar_board import STANDARD_SCHEDULE


def post_init_hook(env):
    """Contenido de ejemplo para ver las plantillas nada mas instalar."""
    board = env.ref('tv_calendar.board_default', raise_if_not_found=False)
    if board and not board.task_ids:
        today = date.today()
        last_day = calendar.monthrange(today.year, today.month)[1]

        def day(number):
            return today.replace(day=min(number, last_day))

        env['tv.calendar.task'].create([
            {'name': 'Reunion de equipo', 'board_id': board.id,
             'importance': 'normal', 'date': day(3),
             'description': 'Sala de juntas, 9:00 am'},
            {'name': 'Entrega cliente', 'board_id': board.id,
             'importance': 'critical', 'date': day(12),
             'description': 'Pedido #1042'},
            {'name': 'Mantenimiento servidores', 'board_id': board.id,
             'importance': 'high', 'date': day(18), 'date_end': day(19)},
            {'name': 'Revision inventario', 'board_id': board.id,
             'importance': 'low', 'date': day(25)},
        ])

    # Tablero de Operario de ejemplo (con el horario estandar cargado).
    if not env['tv.calendar.board'].search_count([('template_type', '=', 'operator')]):
        env['tv.calendar.board'].create({
            'name': 'Puesto de Trabajo',
            'template_type': 'operator',
            'theme': 'dark',
            'operator_name': 'Juan Perez',
            'notice_message': 'Sin novedades para el turno de hoy.',
            'time_slot_ids': [
                (0, 0, {'sequence': i * 10, 'time_label': t, 'activity': a})
                for i, (t, a) in enumerate(STANDARD_SCHEDULE)
            ],
        })
