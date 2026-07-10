import secrets

from odoo import api, fields, models


class TvCalendarBoard(models.Model):
    _name = 'tv.calendar.board'
    _description = 'Tablero de calendario TV'
    _order = 'name'

    name = fields.Char(string='Nombre', required=True)
    active = fields.Boolean(default=True)
    access_token = fields.Char(
        string='Token de acceso', copy=False, index=True, readonly=True,
        help="Token secreto que forma parte de la URL publica del TV.")
    task_ids = fields.One2many('tv.calendar.task', 'board_id', string='Tareas')
    task_count = fields.Integer(compute='_compute_task_count')

    refresh_interval = fields.Integer(
        string='Auto-refresco (segundos)', default=300,
        help="Cada cuantos segundos la pantalla del TV se recarga sola para "
             "mostrar los cambios. 0 = sin recarga automatica.")
    week_start = fields.Selection(
        [('0', 'Lunes'), ('6', 'Domingo')],
        string='La semana empieza en', default='0', required=True)
    show_weekends = fields.Boolean(
        string='Mostrar fines de semana', default=True)
    theme = fields.Selection(
        [('light', 'Claro'), ('dark', 'Oscuro')],
        string='Tema', default='light', required=True)

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

    def action_view_tasks(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Tareas',
            'res_model': 'tv.calendar.task',
            'view_mode': 'calendar,list,form',
            'domain': [('board_id', '=', self.id)],
            'context': {'default_board_id': self.id},
        }
