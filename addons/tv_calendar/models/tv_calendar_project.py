from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .tv_calendar_task import IMPORTANCE_LEVELS, IMPORTANCE_SELECTION, PROJECT_STAGES


DELIVERY_TYPES = [
    ('project', 'Proyecto'),
    ('installation', 'Instalacion y Capacitacion'),
    ('fat', 'Pruebas FAT'),
    ('sat', 'Pruebas SAT'),
    ('service', 'Servicio Tecnico'),
    ('warranty', 'Garantia'),
]


def _bar(pct, color):
    return Markup(
        '<div style="background:#e2e6ee;border-radius:5px;height:12px;overflow:hidden;">'
        '<div style="width:%d%%;background:%s;height:12px;"></div></div>'
    ) % (pct, color)


def _stage_o2m(stage):
    """One2many de tareas del proyecto filtrado por etapa (y que fija la etapa
    en las tareas nuevas creadas desde esa pestana)."""
    return fields.One2many(
        'tv.calendar.task', 'project_id',
        domain=[('stage', '=', stage)],
        context={'default_stage': stage})


class TvCalendarProject(models.Model):
    _name = 'tv.calendar.project'
    _description = 'Proyecto por entregar'
    _order = 'delivery_date, id'
    _inherit = ['mail.thread']
    _rec_name = 'client'

    client = fields.Char(string='Cliente', required=True, tracking=True)
    delivery_type = fields.Selection(
        DELIVERY_TYPES, string='Tipo de entrega', default='project', required=True,
        help="'Proyecto' muestra todo (cliente, fechas, maquinas, avance). "
             "Los demas tipos muestran solo el cliente en el TV.")
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

    # Tareas del proyecto, agrupadas por etapa (una pestana por etapa).
    task_ids = fields.One2many('tv.calendar.task', 'project_id', string='Tareas')
    task_count = fields.Integer(compute='_compute_task_count')
    tasks_pedidos = _stage_o2m('pedidos')
    tasks_soldadura = _stage_o2m('soldadura')
    tasks_torno = _stage_o2m('torno')
    tasks_control = _stage_o2m('control')
    tasks_armado = _stage_o2m('armado')
    tasks_fat = _stage_o2m('fat')
    tasks_logistica = _stage_o2m('logistica')
    tasks_instalacion = _stage_o2m('instalacion')

    task_done_count = fields.Integer(compute='_compute_dashboard')
    progress = fields.Integer(string='Avance (%)', compute='_compute_dashboard')
    progress_html = fields.Html(
        string='Avance por etapa', compute='_compute_dashboard', sanitize=False)

    @api.depends('task_ids')
    def _compute_task_count(self):
        for prj in self:
            prj.task_count = len(prj.task_ids)

    @api.depends('task_ids.done', 'task_ids.stage')
    def _compute_dashboard(self):
        for prj in self:
            tasks = prj.task_ids
            total = len(tasks)
            done = len(tasks.filtered('done'))
            prj.task_done_count = done
            prj.progress = int(round(done * 100.0 / total)) if total else 0

            parts = [Markup(
                '<div style="display:flex;justify-content:space-between;'
                'font-weight:800;margin-bottom:3px;">'
                '<span>Avance total</span><span>%d/%d (%d%%)</span></div>'
            ) % (done, total, prj.progress)]
            parts.append(_bar(prj.progress, '#0b57d0'))
            parts.append(Markup('<div style="height:10px;"></div>'))
            for key, label in PROJECT_STAGES:
                st = tasks.filtered(lambda t, k=key: t.stage == k)
                st_total = len(st)
                st_done = len(st.filtered('done'))
                pct = int(round(st_done * 100.0 / st_total)) if st_total else 0
                color = '#2e7d32' if (st_total and pct == 100) else (
                    '#ef6c00' if st_total else '#9aa4b2')
                parts.append(Markup(
                    '<div style="display:flex;justify-content:space-between;'
                    'font-size:13px;margin:5px 0 2px;">'
                    '<span>%s</span><span>%d/%d</span></div>'
                ) % (label, st_done, st_total))
                parts.append(_bar(pct, color))
            prj.progress_html = Markup('').join(parts)

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
