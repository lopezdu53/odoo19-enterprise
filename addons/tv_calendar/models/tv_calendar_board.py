import secrets

from odoo import api, fields, models

# Horario de turno por defecto para la plantilla Operario.
STANDARD_SCHEDULE = [
    ('7:30 am', 'TAREAS DE HOY'),
    ('10:00-10:20 am', 'PAUSA ACTIVA'),
    ('10:20 am', 'TAREAS DE HOY'),
    ('1:00-2:00 pm', 'ALMUERZO'),
    ('2:00 pm', 'TAREAS DE HOY'),
    ('4:30 pm', 'LIMPIEZA PUESTO DE TRABAJO'),
    ('4:45 pm', 'SALIDA'),
]


class TvCalendarBoard(models.Model):
    _name = 'tv.calendar.board'
    _description = 'Tablero de calendario TV'
    _order = 'name'

    name = fields.Char(string='Nombre', required=True)
    active = fields.Boolean(default=True)
    access_token = fields.Char(
        string='Token de acceso', copy=False, index=True, readonly=True,
        help="Token secreto que forma parte de la URL publica del TV.")
    task_ids = fields.Many2many(
        'tv.calendar.task', 'tv_calendar_task_board_rel', 'board_id', 'task_id',
        string='Tareas')
    task_count = fields.Integer(compute='_compute_task_count')

    template_type = fields.Selection(
        [
            ('schedule', 'Cronograma principal'),
            ('operator', 'Operario'),
            ('ad', 'Publicidad'),
        ],
        string='Tipo de plantilla', default='schedule', required=True,
        help="Que se muestra en el TV:\n"
             "- Cronograma principal: calendario mensual de tareas.\n"
             "- Operario: horario del turno + EPP y avisos.\n"
             "- Publicidad: una lista de reproduccion de YouTube.")

    refresh_interval = fields.Integer(
        string='Auto-refresco (segundos)', default=300,
        help="Cada cuantos segundos la pantalla del TV se recarga sola para "
             "mostrar los cambios. 0 = sin recarga automatica.")
    schedule_range = fields.Selection(
        [
            ('5_days', '5 dias'),
            ('10_days', '10 dias'),
            ('two_weeks', '2 semanas (14 dias)'),
            ('month', 'Mes completo'),
        ],
        string='Rango del cronograma', default='10_days', required=True,
        help="Los rangos por dias empiezan el dia anterior al actual "
             "(ventana rodante). 'Mes completo' muestra el mes en curso.")
    week_start = fields.Selection(
        [('0', 'Lunes'), ('6', 'Domingo')],
        string='La semana empieza en', default='0', required=True)
    show_weekends = fields.Boolean(
        string='Mostrar fines de semana', default=True)
    theme = fields.Selection(
        [('light', 'Claro'), ('dark', 'Oscuro')],
        string='Tema', default='light', required=True)

    # --- Plantilla Operario ---
    employee_id = fields.Many2one(
        'hr.employee', string='Operario (empleado)',
        help="Selecciona el operario desde el modulo de Empleados.")
    operator_name = fields.Char(
        string='Nombre del operario (manual)',
        help="Se usa solo si no seleccionas un empleado.")
    operator_display = fields.Char(
        string='Operario', compute='_compute_operator_display')
    epp_message = fields.Char(
        string='Mensaje EPP',
        default='USAR EPP · ELEMENTOS DE PROTECCION PERSONAL')
    epp_message2 = fields.Char(
        string='Mensaje EPP 2',
        default='PROHIBIDO el uso de celular, accesorios o joyas')
    notice_message = fields.Text(
        string='Avisos',
        help="Horas extra, cambios de horario de almuerzo o pausa activa, etc.")
    time_slot_ids = fields.One2many(
        'tv.calendar.time.slot', 'board_id', string='Horario del turno')
    task_board_id = fields.Many2one(
        'tv.calendar.board', string='Tareas del tablero',
        help="De que tablero tomar las tareas del dia. Vacio = este mismo tablero.")

    # --- Plantilla Publicidad ---
    youtube_url = fields.Char(
        string='URL de la playlist de YouTube',
        help="Pega el enlace de la lista de reproduccion (contiene 'list=...').")

    kiosk_url = fields.Char(string='URL del TV', compute='_compute_kiosk_url')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('access_token'):
                vals['access_token'] = secrets.token_urlsafe(24)
        return super().create(vals_list)

    @api.depends('task_ids')
    def _compute_task_count(self):
        for board in self:
            board.task_count = len(board.task_ids)

    @api.depends('employee_id', 'operator_name')
    def _compute_operator_display(self):
        for board in self:
            board.operator_display = (
                board.employee_id.name or board.operator_name or '')

    @api.depends('access_token')
    def _compute_kiosk_url(self):
        base = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for board in self:
            if board.access_token:
                board.kiosk_url = '%s/tv/calendar/%s' % (base, board.access_token)
            else:
                board.kiosk_url = False

    def action_open_kiosk(self):
        """Abre la pantalla del TV en una pestana nueva."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/tv/calendar/%s' % self.access_token,
            'target': 'new',
        }

    def action_regenerate_token(self):
        """Genera un token nuevo (invalida la URL anterior)."""
        for board in self:
            board.access_token = secrets.token_urlsafe(24)
        return True

    def action_load_standard_schedule(self):
        """Carga el horario de turno estandar en la plantilla Operario."""
        self.ensure_one()
        self.time_slot_ids.unlink()
        self.time_slot_ids = [
            (0, 0, {'sequence': i * 10, 'time_label': t, 'activity': a})
            for i, (t, a) in enumerate(STANDARD_SCHEDULE)
        ]
        return True

    def action_view_tasks(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Tareas',
            'res_model': 'tv.calendar.task',
            'view_mode': 'calendar,list,form',
            'domain': [('board_ids', 'in', self.id)],
            'context': {'default_board_ids': [(6, 0, [self.id])]},
        }
