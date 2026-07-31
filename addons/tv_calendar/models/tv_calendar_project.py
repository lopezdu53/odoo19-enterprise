from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .tv_calendar_task import IMPORTANCE_LEVELS, IMPORTANCE_SELECTION


class TvCalendarProject(models.Model):
    _name = 'tv.calendar.project'
    _description = 'Proyecto por entregar'
    _order = 'delivery_date, id'
    _inherit = ['mail.thread']
    _rec_name = 'client'

    client = fields.Char(string='Cliente', required=True, tracking=True)
    order_ref = fields.Char(string='# Cotizacion / OC', tracking=True)
    order_date = fields.Date(string='Fecha de orden', tracking=True)
    delivery_date = fields.Date(
        string='Fecha de entrega', required=True, index=True,
        default=fields.Date.context_today, tracking=True)
    machines = fields.Text(string='Maquinas a entregar')
    importance = fields.Selection(
        IMPORTANCE_SELECTION, string='Prioridad', required=True,
        default='normal', tracking=True)
    importance_rank = fields.Integer(compute='_compute_importance_meta', store=True)
    color = fields.Integer(compute='_compute_importance_meta', store=True)
    done = fields.Boolean(string='Entregado', default=False, tracking=True)
    board_ids = fields.Many2many(
        'tv.calendar.board', 'tv_calendar_project_board_rel', 'project_id', 'board_id',
        string='Tableros', required=True,
        help="Tableros (TV) de tipo Proyectos donde se muestra esta entrega.")

    @api.depends('importance')
    def _compute_importance_meta(self):
        for prj in self:
            level = IMPORTANCE_LEVELS.get(prj.importance) or IMPORTANCE_LEVELS['normal']
            prj.importance_rank = level['rank']
            prj.color = level['kanban_color']

    @api.constrains('order_date', 'delivery_date')
    def _check_dates(self):
        for prj in self:
            if prj.order_date and prj.delivery_date and prj.delivery_date < prj.order_date:
                raise ValidationError(
                    "La fecha de entrega no puede ser anterior a la fecha de orden.")

    @api.constrains('board_ids')
    def _check_board(self):
        for prj in self:
            if not prj.board_ids:
                raise ValidationError("Asigna el proyecto a al menos un tablero.")

    def importance_hex(self):
        self.ensure_one()
        return (IMPORTANCE_LEVELS.get(self.importance) or {}).get('color', '#455a64')
