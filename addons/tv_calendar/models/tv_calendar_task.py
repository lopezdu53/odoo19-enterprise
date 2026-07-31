from odoo import api, fields, models
from odoo.exceptions import ValidationError

# Definicion central de los niveles de importancia.
# Se usa tanto en el backend como en la pantalla del TV para mantener
# los colores y etiquetas coherentes en todos lados.
#   - color: color HEX usado en la pantalla del TV (chips de tareas).
#   - kanban_color: indice de color de Odoo (0-11) para la vista calendario.
#   - rank: orden de prioridad (mayor = mas importante / se muestra primero).
IMPORTANCE_LEVELS = {
    'low': {'label': 'Baja', 'color': '#2e7d32', 'kanban_color': 10, 'rank': 1},
    'normal': {'label': 'Normal', 'color': '#1565c0', 'kanban_color': 4, 'rank': 2},
    'high': {'label': 'Alta', 'color': '#ef6c00', 'kanban_color': 2, 'rank': 3},
    'critical': {'label': 'Critica', 'color': '#c62828', 'kanban_color': 1, 'rank': 4},
}

IMPORTANCE_SELECTION = [
    ('low', 'Baja'),
    ('normal', 'Normal'),
    ('high', 'Alta'),
    ('critical', 'Critica'),
]

# Etapas de un proyecto por entregar (una pestana por etapa en el proyecto).
PROJECT_STAGES = [
    ('pedidos', '1. Pedidos Nacionales e Internacionales'),
    ('soldadura', '2. Soldadura'),
    ('torno', '3. Torno'),
    ('control', '4. Control y Automatizacion'),
    ('armado', '5. Armado'),
    ('fat', '6. Pruebas FAT'),
    ('logistica', '7. Logistica de Despacho'),
    ('instalacion', '8. Instalacion y Capacitacion'),
]


class TvCalendarTask(models.Model):
    _name = 'tv.calendar.task'
    _description = 'Tarea del calendario TV'
    _order = 'date, importance_rank desc, id'
    _inherit = ['mail.thread']

    name = fields.Char(string='Titulo', required=True, tracking=True)
    board_ids = fields.Many2many(
        'tv.calendar.board', 'tv_calendar_task_board_rel', 'task_id', 'board_id',
        string='Tableros', required=True, tracking=True,
        help="Uno o varios tableros (TV) donde se mostrara esta tarea.")
    date = fields.Date(
        string='Fecha', required=True, index=True,
        default=fields.Date.context_today, tracking=True)
    date_end = fields.Date(
        string='Fecha fin',
        help="Opcional. Si la tarea dura varios dias, se muestra en cada dia "
             "del rango.")
    importance = fields.Selection(
        IMPORTANCE_SELECTION, string='Importancia', required=True,
        default='normal', tracking=True)
    importance_rank = fields.Integer(
        compute='_compute_importance_meta', store=True)
    color = fields.Integer(
        string='Color', compute='_compute_importance_meta', store=True,
        help="Color usado por la vista calendario del backend.")
    project_id = fields.Many2one(
        'tv.calendar.project', string='Proyecto', ondelete='set null', index=True)
    stage = fields.Selection(PROJECT_STAGES, string='Etapa')
    user_id = fields.Many2one(
        'res.users', string='Responsable',
        default=lambda self: self.env.user, tracking=True)
    description = fields.Html(string='Descripcion', sanitize=True)
    reference_image = fields.Image(
        string='Imagen de referencia', max_width=1280, max_height=1280,
        help="Se muestra a la derecha de la tarea en la plantilla Mecanizado.")
    done = fields.Boolean(string='Completada', default=False, tracking=True)

    @api.depends('importance')
    def _compute_importance_meta(self):
        for task in self:
            level = IMPORTANCE_LEVELS.get(task.importance) or IMPORTANCE_LEVELS['normal']
            task.importance_rank = level['rank']
            task.color = level['kanban_color']

    @api.constrains('date', 'date_end')
    def _check_dates(self):
        for task in self:
            if task.date_end and task.date and task.date_end < task.date:
                raise ValidationError(
                    "La fecha fin no puede ser anterior a la fecha de inicio.")

    @api.constrains('board_ids')
    def _check_board(self):
        for task in self:
            if not task.board_ids:
                raise ValidationError(
                    "Asigna la tarea a al menos un tablero.")

    def importance_display(self):
        """Etiqueta legible del nivel de importancia."""
        self.ensure_one()
        return (IMPORTANCE_LEVELS.get(self.importance) or {}).get('label', '')

    def importance_hex(self):
        """Color HEX del nivel de importancia (para la pantalla del TV)."""
        self.ensure_one()
        return (IMPORTANCE_LEVELS.get(self.importance) or {}).get('color', '#455a64')
