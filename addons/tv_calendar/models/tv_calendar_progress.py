from odoo import api, fields, models

from .tv_calendar_task import PROJECT_STAGES

PROGRESS_STATES = [
    ('draft', 'Borrador'),
    ('submitted', 'Enviado'),
    ('approved', 'Aprobado'),
    ('postponed', 'Pospuesto'),
    ('rejected', 'Rechazado'),
]


class TvCalendarProgress(models.Model):
    _name = 'tv.calendar.progress'
    _description = 'Reporte diario de avance'
    _order = 'date desc, id desc'
    _inherit = ['mail.thread']

    name = fields.Char(string='Resumen del avance', required=True, tracking=True)
    task_id = fields.Many2one(
        'tv.calendar.task', string='Tarea', required=True,
        ondelete='cascade', index=True)
    project_id = fields.Many2one(
        'tv.calendar.project', string='Proyecto',
        related='task_id.project_id', store=True, index=True)
    stage = fields.Selection(
        PROJECT_STAGES, string='Fase', related='task_id.stage', store=True)
    board_ids = fields.Many2many(
        'tv.calendar.board', string='Tableros', related='task_id.board_ids')
    date = fields.Date(
        string='Fecha', default=fields.Date.context_today,
        required=True, tracking=True)
    note = fields.Text(string='Avance del dia')
    image = fields.Image(string='Foto', max_width=1920, max_height=1920)
    state = fields.Selection(
        PROGRESS_STATES, string='Estado', default='draft',
        required=True, tracking=True)
    user_id = fields.Many2one(
        'res.users', string='Reportado por',
        default=lambda self: self.env.user, tracking=True)
    reviewer_id = fields.Many2one('res.users', string='Revisado por', readonly=True)
    review_date = fields.Datetime(string='Fecha de revision', readonly=True)
    review_note = fields.Char(string='Comentario de revision')

    def action_submit(self):
        self.write({'state': 'submitted'})
        for rep in self:
            rep.message_post(body="Avance enviado para revision.")
        return True

    def _review(self, state, label):
        now = fields.Datetime.now()
        for rep in self:
            rep.write({
                'state': state,
                'reviewer_id': self.env.user.id,
                'review_date': now,
            })
            body = "%s por %s" % (label, self.env.user.name)
            if rep.review_note:
                body += ": %s" % rep.review_note
            rep.message_post(body=body)
        return True

    def action_approve(self):
        return self._review('approved', 'Aprobado')

    def action_postpone(self):
        return self._review('postponed', 'Pospuesto')

    def action_reject(self):
        return self._review('rejected', 'Rechazado')

    def action_reset(self):
        self.write({'state': 'draft', 'reviewer_id': False, 'review_date': False})
        return True
