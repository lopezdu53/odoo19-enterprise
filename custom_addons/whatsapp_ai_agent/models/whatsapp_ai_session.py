import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class WhatsappAiSession(models.Model):
    """
    Sesión de conversación entre un contacto y el agente AI de WhatsApp.
    Una sesión agrupa todos los mensajes de la misma conversación
    (ventana de 24 horas según política de WhatsApp Business).
    """
    _name = 'whatsapp.ai.session'
    _description = 'Sesión de Conversación WhatsApp AI'
    _order = 'last_message_date desc'
    _rec_name = 'display_name'

    # ── Relaciones ───────────────────────────────────────────────────────────────
    agent_id = fields.Many2one(
        'whatsapp.ai.agent',
        string='Agente AI',
        required=True,
        ondelete='cascade',
        index=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Contacto',
        index=True,
    )
    lead_id = fields.Many2one(
        'crm.lead',
        string='Lead CRM',
        index=True,
    )

    # ── Datos de contacto ────────────────────────────────────────────────────────
    mobile_number = fields.Char(
        string='Número de WhatsApp',
        required=True,
        index=True,
    )

    # ── Estado y fechas ──────────────────────────────────────────────────────────
    state = fields.Selection([
        ('active', 'Activa'),
        ('closed', 'Cerrada'),
    ], string='Estado', default='active', index=True, required=True)

    last_message_date = fields.Datetime(
        string='Último Mensaje',
        index=True,
    )

    # ── Control humano ───────────────────────────────────────────────────────────
    human_takeover = fields.Boolean(
        string='En control humano',
        default=False,
        index=True,
        help='El agente humano tomó el control. El AI no responderá hasta que expire el tiempo configurado.',
    )
    human_takeover_date = fields.Datetime(
        string='Fecha de intervención humana',
        help='Cuando el agente humano tomó el control.',
    )

    # ── Mensajes ─────────────────────────────────────────────────────────────────
    message_ids = fields.One2many(
        'whatsapp.ai.message',
        'session_id',
        string='Mensajes',
    )
    message_count = fields.Integer(
        string='Mensajes',
        compute='_compute_message_count',
        store=True,
    )
    inbound_count = fields.Integer(
        string='Mensajes Recibidos',
        compute='_compute_message_count',
        store=True,
    )
    outbound_count = fields.Integer(
        string='Mensajes Enviados',
        compute='_compute_message_count',
        store=True,
    )

    # ── Computed ─────────────────────────────────────────────────────────────────
    display_name = fields.Char(
        string='Identificador',
        compute='_compute_display_name',
        store=True,
    )

    @api.depends('partner_id', 'mobile_number', 'agent_id')
    def _compute_display_name(self):
        for session in self:
            contact = session.partner_id.name if session.partner_id else session.mobile_number
            session.display_name = f"{contact} — {session.agent_id.name or ''}"

    @api.depends('message_ids', 'message_ids.direction')
    def _compute_message_count(self):
        for session in self:
            msgs = session.message_ids
            session.message_count = len(msgs)
            session.inbound_count = len(msgs.filtered(lambda m: m.direction == 'inbound'))
            session.outbound_count = len(msgs.filtered(lambda m: m.direction == 'outbound'))

    # ── Acciones ─────────────────────────────────────────────────────────────────
    def action_close_session(self):
        self.write({'state': 'closed'})

    def action_resume_ai(self):
        self.write({'human_takeover': False, 'human_takeover_date': False})

    def action_reopen_session(self):
        self.write({'state': 'active'})

    def action_view_lead(self):
        self.ensure_one()
        if not self.lead_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'crm.lead',
            'res_id': self.lead_id.id,
            'view_mode': 'form',
        }

    def action_view_partner(self):
        self.ensure_one()
        if not self.partner_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'res_id': self.partner_id.id,
            'view_mode': 'form',
        }


class WhatsappAiMessage(models.Model):
    """
    Mensaje individual dentro de una sesión de conversación.
    Almacena cada mensaje entrante y saliente para mantener contexto
    y permitir análisis de las conversaciones.
    """
    _name = 'whatsapp.ai.message'
    _description = 'Mensaje de Sesión WhatsApp AI'
    _order = 'date asc'

    session_id = fields.Many2one(
        'whatsapp.ai.session',
        string='Sesión',
        required=True,
        ondelete='cascade',
        index=True,
    )
    direction = fields.Selection([
        ('inbound', 'Entrante (Cliente)'),
        ('outbound', 'Saliente (AI)'),
        ('human', 'Agente Humano'),
    ], string='Dirección', required=True, index=True)

    body = fields.Text(string='Mensaje')
    date = fields.Datetime(
        string='Fecha',
        default=fields.Datetime.now,
        index=True,
    )

    # Referencia al mensaje original de WhatsApp (si existe)
    whatsapp_message_id = fields.Many2one(
        'whatsapp.message',
        string='Mensaje WhatsApp',
        ondelete='set null',
    )

    # Datos desnormalizados para rendimiento
    agent_id = fields.Many2one(
        'whatsapp.ai.agent',
        related='session_id.agent_id',
        store=True,
        index=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        related='session_id.partner_id',
        store=True,
    )
    mobile_number = fields.Char(
        related='session_id.mobile_number',
        store=True,
    )
