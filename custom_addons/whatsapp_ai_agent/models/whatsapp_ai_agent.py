import logging
import threading
import time
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class WhatsappAiAgent(models.Model):
    _name = 'whatsapp.ai.agent'
    _description = 'Agente AI para WhatsApp'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name asc'

    # ── Identificación ─────────────────────────────────────────────────────────
    name = fields.Char(string='Nombre', required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        'res.company', string='Empresa',
        default=lambda self: self.env.company,
    )

    # ── Cuenta WhatsApp ─────────────────────────────────────────────────────────
    whatsapp_account_id = fields.Many2one(
        'whatsapp.account',
        string='Cuenta WhatsApp',
        required=True,
        tracking=True,
        help='Cuenta de WhatsApp Business API que este agente va a monitorear.',
    )

    # ── Proveedor de AI ─────────────────────────────────────────────────────────
    ai_provider = fields.Selection([
        ('openai', 'OpenAI / ChatGPT'),
        ('anthropic', 'Anthropic / Claude'),
        ('openai_compatible', 'API Compatible con OpenAI'),
        ('odoo_native', 'Agente AI Nativo de Odoo'),
    ], string='Proveedor de AI', default='openai', required=True, tracking=True)

    api_key = fields.Char(
        string='API Key',
        help='Clave de API del proveedor de AI (OpenAI, Anthropic, etc.).',
    )
    api_base_url = fields.Char(
        string='URL Base de la API',
        help='Solo para APIs compatibles con OpenAI. '
             'Ejemplo: https://api.openai.com/v1 o http://localhost:11434/v1 (Ollama).',
    )
    ai_model = fields.Char(
        string='Modelo AI',
        help='Nombre del modelo a usar.\n'
             'OpenAI: gpt-4o, gpt-4o-mini, gpt-3.5-turbo\n'
             'Anthropic: claude-3-5-sonnet-20241022, claude-3-haiku-20240307\n'
             'Ollama: llama3.2, mistral, etc.',
    )
    ai_temperature = fields.Float(
        string='Temperatura',
        default=0.7,
        help='Controla la creatividad del AI (0.0 = determinístico, 1.0 = creativo).',
    )
    ai_max_tokens = fields.Integer(
        string='Máx. Tokens Respuesta',
        default=500,
        help='Longitud máxima de la respuesta del AI.',
    )

    # ── Integración con Agente Nativo de Odoo 19 ────────────────────────────────
    odoo_ai_model_name = fields.Char(
        string='Modelo del Agente Odoo',
        help='Nombre técnico del modelo del agente AI nativo de Odoo '
             '(ej: discuss.ai.agent, mail.ai.agent).',
    )
    odoo_ai_agent_res_id = fields.Integer(
        string='ID del Agente Odoo',
        help='ID del registro del agente AI nativo de Odoo.',
    )

    # ── Entrenamiento (System Prompt) ────────────────────────────────────────────
    system_prompt = fields.Text(
        string='Prompt de Sistema (Entrenamiento)',
        help='Define la personalidad, rol y conocimientos del agente.\n\n'
             'Ejemplo:\n'
             'Eres un asistente de ventas de [Tu Empresa]. '
             'Ayudas a los clientes con información sobre nuestros productos y servicios. '
             'Siempre responde en español de forma amigable y profesional. '
             'Si el cliente quiere comprar algo, pide sus datos de contacto.',
    )
    max_history_messages = fields.Integer(
        string='Mensajes de Historial',
        default=10,
        help='Número de mensajes anteriores que se envían al AI como contexto.',
    )

    # ── Auto-respuesta ──────────────────────────────────────────────────────────
    auto_respond = fields.Boolean(
        string='Respuesta Automática',
        default=True,
        tracking=True,
        help='Si está activo, el agente responde automáticamente a los mensajes entrantes.',
    )
    response_delay_seconds = fields.Integer(
        string='Retardo de Respuesta (segundos)',
        default=2,
        help='Simula tiempo de escritura humana antes de enviar la respuesta.',
    )
    fallback_message = fields.Text(
        string='Mensaje de Error',
        default='Disculpa, estoy teniendo problemas técnicos en este momento. '
                'Un representante te contactará pronto.',
        help='Mensaje que se envía si el AI no puede responder.',
    )

    # ── Creación de Contactos ────────────────────────────────────────────────────
    create_partner = fields.Boolean(
        string='Crear Contacto Automáticamente',
        default=True,
        tracking=True,
        help='Crea un contacto (res.partner) para números de WhatsApp desconocidos.',
    )
    partner_name_prefix = fields.Char(
        string='Prefijo para Nombres de Contacto',
        default='Contacto WhatsApp',
        help='Prefijo usado al crear contactos automáticos.',
    )

    # ── Creación de Leads CRM ────────────────────────────────────────────────────
    create_lead = fields.Boolean(
        string='Crear Lead Automáticamente',
        default=True,
        tracking=True,
        help='Crea un lead en CRM para cada nueva conversación de WhatsApp.',
    )
    lead_team_id = fields.Many2one(
        'crm.team',
        string='Equipo de Ventas',
        help='Equipo de ventas al que se asignarán los leads creados.',
    )
    lead_user_id = fields.Many2one(
        'res.users',
        string='Asignar a',
        help='Usuario responsable de los leads creados.',
    )
    lead_tag_ids = fields.Many2many(
        'crm.tag',
        'whatsapp_ai_agent_crm_tag_rel',
        'agent_id', 'tag_id',
        string='Etiquetas del Lead',
        help='Etiquetas que se aplican automáticamente a los leads creados.',
    )
    lead_priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Baja'),
        ('2', 'Alta'),
        ('3', 'Muy Alta'),
    ], string='Prioridad del Lead', default='0')

    # ── Estadísticas (compute) ──────────────────────────────────────────────────
    session_ids = fields.One2many(
        'whatsapp.ai.session', 'agent_id', string='Sesiones',
    )
    total_sessions = fields.Integer(
        string='Total Sesiones', compute='_compute_stats',
    )
    active_sessions = fields.Integer(
        string='Sesiones Activas', compute='_compute_stats',
    )
    total_messages_sent = fields.Integer(
        string='Mensajes Enviados', compute='_compute_stats',
    )

    @api.depends('session_ids', 'session_ids.state', 'session_ids.message_ids')
    def _compute_stats(self):
        for agent in self:
            sessions = agent.session_ids
            agent.total_sessions = len(sessions)
            agent.active_sessions = len(sessions.filtered(lambda s: s.state == 'active'))
            agent.total_messages_sent = len(
                sessions.mapped('message_ids').filtered(
                    lambda m: m.direction == 'outbound'
                )
            )

    # ── Validaciones ────────────────────────────────────────────────────────────
    @api.constrains('ai_temperature')
    def _check_temperature(self):
        for rec in self:
            if not 0.0 <= rec.ai_temperature <= 2.0:
                raise ValidationError(_('La temperatura debe estar entre 0.0 y 2.0.'))

    @api.constrains('max_history_messages')
    def _check_history(self):
        for rec in self:
            if rec.max_history_messages < 0:
                raise ValidationError(_('El historial de mensajes no puede ser negativo.'))

    # ── Acciones UI ─────────────────────────────────────────────────────────────
    def action_view_sessions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sesiones de %s') % self.name,
            'res_model': 'whatsapp.ai.session',
            'view_mode': 'list,form',
            'domain': [('agent_id', '=', self.id)],
            'context': {'default_agent_id': self.id},
        }

    def action_test_ai_connection(self):
        """Prueba la conexión con el proveedor de AI."""
        self.ensure_one()
        test_messages = [{'role': 'user', 'content': 'Responde solo "OK" si recibes este mensaje.'}]
        response = self._get_ai_response(
            'Eres un asistente de prueba. Responde solo "OK".',
            test_messages,
        )
        if response:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Conexión exitosa'),
                    'message': _('Respuesta del AI: %s') % response,
                    'type': 'success',
                    'sticky': False,
                },
            }
        raise UserError(_('No se pudo conectar con el proveedor de AI. Verifica tu API Key y configuración.'))

    # ── Lógica de AI ────────────────────────────────────────────────────────────

    def _get_ai_response(self, system_prompt, messages):
        """Obtiene respuesta del AI según el proveedor configurado."""
        self.ensure_one()

        if self.ai_provider == 'odoo_native':
            response = self._get_odoo_native_response(messages)
            if response:
                return response
            _logger.warning('[WhatsApp AI] Agente nativo falló, no hay fallback configurado.')
            return None

        if self.ai_provider in ('openai', 'openai_compatible'):
            return self._get_openai_response(system_prompt, messages)

        if self.ai_provider == 'anthropic':
            return self._get_anthropic_response(system_prompt, messages)

        _logger.error('[WhatsApp AI] Proveedor no soportado: %s', self.ai_provider)
        return None

    def _get_openai_response(self, system_prompt, messages):
        """Llama a la API de OpenAI o compatible."""
        try:
            import requests

            base_url = (self.api_base_url or 'https://api.openai.com/v1').rstrip('/')
            url = f"{base_url}/chat/completions"

            api_messages = []
            if system_prompt:
                api_messages.append({'role': 'system', 'content': system_prompt})
            api_messages.extend(messages)

            headers = {'Content-Type': 'application/json'}
            if self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'

            payload = {
                'model': self.ai_model or 'gpt-4o',
                'messages': api_messages,
                'max_tokens': self.ai_max_tokens or 500,
                'temperature': self.ai_temperature,
            }

            resp = requests.post(url, headers=headers, json=payload, timeout=45)
            resp.raise_for_status()
            data = resp.json()

            return data['choices'][0]['message']['content'].strip()

        except Exception as e:
            _logger.error('[WhatsApp AI] Error OpenAI: %s', str(e))
            return None

    def _get_anthropic_response(self, system_prompt, messages):
        """Llama a la API de Anthropic."""
        try:
            import requests

            # Anthropic no acepta 'system' dentro de messages, va aparte
            anthropic_messages = [
                m for m in messages if m.get('role') in ('user', 'assistant')
            ]

            payload = {
                'model': self.ai_model or 'claude-3-5-sonnet-20241022',
                'max_tokens': self.ai_max_tokens or 500,
                'messages': anthropic_messages,
            }
            if system_prompt:
                payload['system'] = system_prompt

            resp = requests.post(
                'https://api.anthropic.com/v1/messages',
                headers={
                    'x-api-key': self.api_key or '',
                    'anthropic-version': '2023-06-01',
                    'Content-Type': 'application/json',
                },
                json=payload,
                timeout=45,
            )
            resp.raise_for_status()
            data = resp.json()

            return data['content'][0]['text'].strip()

        except Exception as e:
            _logger.error('[WhatsApp AI] Error Anthropic: %s', str(e))
            return None

    def _get_odoo_native_response(self, messages):
        """Intenta usar el agente AI nativo de Odoo 19."""
        if not self.odoo_ai_model_name or not self.odoo_ai_agent_res_id:
            return None
        try:
            model_obj = self.env.get(self.odoo_ai_model_name)
            if model_obj is None:
                _logger.warning(
                    '[WhatsApp AI] Modelo Odoo AI no encontrado: %s',
                    self.odoo_ai_model_name,
                )
                return None

            agent_record = model_obj.browse(self.odoo_ai_agent_res_id)
            if not agent_record.exists():
                return None

            last_user_msg = messages[-1]['content'] if messages else ''

            # Intentamos varios métodos posibles según la versión/nombre del módulo
            for method_name in ('process_message', 'get_response', 'respond', 'chat', 'answer'):
                if hasattr(agent_record, method_name):
                    return getattr(agent_record, method_name)(last_user_msg)

        except Exception as e:
            _logger.error('[WhatsApp AI] Error agente nativo Odoo: %s', str(e))
        return None

    # ── Lógica de Contacto / Partner ────────────────────────────────────────────

    def _find_or_create_partner(self, mobile_number, display_name=None):
        """Busca o crea un contacto a partir del número de teléfono."""
        self.ensure_one()

        normalized = self._normalize_phone(mobile_number)
        candidates = [mobile_number]
        if normalized and normalized != mobile_number:
            candidates.append(normalized)

        partner_fields = self.env['res.partner']._fields
        phone_field = 'mobile' if 'mobile' in partner_fields else 'phone'

        domain = ['|'] * (len(candidates) - 1)
        for num in candidates:
            domain += [(phone_field, '=', num)]
        domain += [('active', '=', True)]

        partner = self.env['res.partner'].search(domain, limit=1)

        if not partner and self.create_partner:
            name = display_name or f"{self.partner_name_prefix} {mobile_number}"
            partner = self.env['res.partner'].create({
                'name': name,
                phone_field: mobile_number,
                'customer_rank': 1,
                'comment': _('Contacto creado automáticamente por WhatsApp AI Agent.'),
            })
            _logger.info('[WhatsApp AI] Contacto creado: %s (%s)', name, mobile_number)

        return partner

    def _normalize_phone(self, phone):
        """Normalización básica de número telefónico."""
        if not phone:
            return phone
        return ''.join(c for c in phone if c.isdigit() or c == '+')

    # ── Lógica de Sesión ────────────────────────────────────────────────────────

    def _find_or_create_session(self, mobile_number, partner=None):
        """Busca sesión activa en las últimas 24 h o crea una nueva."""
        self.ensure_one()

        cutoff = fields.Datetime.now() - timedelta(hours=24)
        session = self.env['whatsapp.ai.session'].search([
            ('agent_id', '=', self.id),
            ('mobile_number', '=', mobile_number),
            ('state', '=', 'active'),
            ('last_message_date', '>=', cutoff),
        ], limit=1, order='last_message_date desc')

        if not session:
            session = self.env['whatsapp.ai.session'].create({
                'agent_id': self.id,
                'mobile_number': mobile_number,
                'partner_id': partner.id if partner else False,
                'state': 'active',
                'last_message_date': fields.Datetime.now(),
            })
            _logger.info(
                '[WhatsApp AI] Nueva sesión creada para %s (agente: %s)',
                mobile_number, self.name,
            )
        else:
            if partner and not session.partner_id:
                session.partner_id = partner

        return session

    # ── Lógica de CRM Lead ──────────────────────────────────────────────────────

    def _ensure_crm_lead(self, session):
        """Crea un lead CRM si está configurado y no existe ya."""
        self.ensure_one()

        if not self.create_lead or session.lead_id:
            return session.lead_id

        partner = session.partner_id
        lead_name = (
            f"WhatsApp - {partner.name}" if partner
            else f"WhatsApp - {session.mobile_number}"
        )

        crm_fields = self.env['crm.lead']._fields
        lead_phone_field = 'mobile' if 'mobile' in crm_fields else 'phone'
        lead_vals = {
            'name': lead_name,
            lead_phone_field: session.mobile_number,
            'partner_id': partner.id if partner else False,
            'partner_name': partner.name if partner else session.mobile_number,
            'team_id': self.lead_team_id.id if self.lead_team_id else False,
            'user_id': self.lead_user_id.id if self.lead_user_id else False,
            'tag_ids': [(6, 0, self.lead_tag_ids.ids)],
            'priority': self.lead_priority,
            'description': _(
                'Lead generado automáticamente por el Agente AI de WhatsApp.\n'
                'Agente: %s\nTeléfono: %s'
            ) % (self.name, session.mobile_number),
        }

        lead = self.env['crm.lead'].create(lead_vals)
        session.lead_id = lead
        _logger.info(
            '[WhatsApp AI] Lead creado: %s (ID: %d)',
            lead_name, lead.id,
        )
        return lead

    # ── Construcción del historial ──────────────────────────────────────────────

    def _build_conversation_history(self, session):
        """Construye el historial de conversación para el AI."""
        self.ensure_one()

        limit = self.max_history_messages or 10
        recent_messages = session.message_ids.sorted('date')[-limit:]

        messages = []
        for msg in recent_messages:
            role = 'user' if msg.direction == 'inbound' else 'assistant'
            messages.append({'role': role, 'content': msg.body or ''})

        return messages

    # ── Envío de respuesta via WhatsApp ─────────────────────────────────────────

    def _send_whatsapp_response(self, mobile_number, response_text, partner=None):
        """Envía la respuesta del AI por WhatsApp (múltiples métodos de fallback)."""
        self.ensure_one()
        account = self.whatsapp_account_id

        # Método 1: método del account de Odoo
        for method_name in ('_send_message', 'send_message', '_send_whatsapp_message'):
            if hasattr(account, method_name):
                try:
                    kwargs = {'mobile_number': mobile_number, 'body': response_text}
                    if partner:
                        kwargs['partner_id'] = partner.id
                    getattr(account, method_name)(**kwargs)
                    _logger.info(
                        '[WhatsApp AI] Respuesta enviada via account.%s a %s',
                        method_name, mobile_number,
                    )
                    return True
                except Exception as e:
                    _logger.debug('[WhatsApp AI] account.%s falló: %s', method_name, e)

        # Método 2: crear whatsapp.message outbound
        try:
            msg_vals = {
                'mobile_number': mobile_number,
                'body': response_text,
                'whatsapp_account_id': account.id,
                'state': 'outgoing',
                'message_type': 'text',
            }
            if partner:
                msg_vals['partner_id'] = partner.id

            outbound = self.env['whatsapp.message'].with_context(
                whatsapp_ai_response=True
            ).create(msg_vals)

            # Intentar activar el envío
            for send_method in ('_send', 'action_send', '_process_send', 'send'):
                if hasattr(outbound, send_method):
                    try:
                        getattr(outbound, send_method)()
                        _logger.info(
                            '[WhatsApp AI] Respuesta enviada via whatsapp.message.%s',
                            send_method,
                        )
                        return True
                    except Exception:
                        pass
        except Exception as e:
            _logger.debug('[WhatsApp AI] Creación de whatsapp.message falló: %s', e)

        # Método 3: llamada directa a Meta Graph API
        return self._send_via_meta_api(mobile_number, response_text)

    def _send_via_meta_api(self, mobile_number, body):
        """Envía mensaje directamente a la Meta WhatsApp Business API."""
        try:
            import requests

            account = self.whatsapp_account_id

            phone_number_id = (
                getattr(account, 'phone_uid', None)
                or getattr(account, 'phone_number_id', None)
                or getattr(account, 'wa_phone_number_id', None)
            )
            token = (
                getattr(account, 'token', None)
                or getattr(account, 'access_token', None)
                or getattr(account, 'app_access_token', None)
            )

            if not phone_number_id or not token:
                _logger.error(
                    '[WhatsApp AI] No se encontraron credenciales de Meta API en la cuenta %s',
                    account.name,
                )
                return False

            url = f"https://graph.facebook.com/v19.0/{phone_number_id}/messages"
            resp = requests.post(
                url,
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json',
                },
                json={
                    'messaging_product': 'whatsapp',
                    'to': mobile_number,
                    'type': 'text',
                    'text': {'body': body, 'preview_url': False},
                },
                timeout=30,
            )

            if resp.status_code == 200:
                _logger.info(
                    '[WhatsApp AI] Respuesta enviada via Meta API directa a %s',
                    mobile_number,
                )
                return True

            _logger.error(
                '[WhatsApp AI] Meta API error %d: %s',
                resp.status_code, resp.text,
            )
            return False

        except Exception as e:
            _logger.error('[WhatsApp AI] Error al llamar Meta API: %s', str(e))
            return False

    # ── Procesamiento principal del mensaje entrante ─────────────────────────────

    def process_inbound_message(self, whatsapp_message):
        """
        Método principal: recibe un whatsapp.message entrante,
        procesa con AI y envía respuesta.
        """
        self.ensure_one()

        if not self.auto_respond:
            return

        mobile_number = getattr(whatsapp_message, 'mobile_number', None)
        message_body = getattr(whatsapp_message, 'body', None)

        if not mobile_number:
            _logger.debug('[WhatsApp AI] Mensaje sin número de teléfono, ignorado.')
            return

        # Ignorar mensajes sin texto (imágenes, audio, etc. sin caption)
        if not message_body or not message_body.strip():
            if self.fallback_message:
                self._send_whatsapp_response(mobile_number, self.fallback_message)
            return

        # 1. Encontrar o crear contacto
        partner = self._find_or_create_partner(mobile_number)

        # Actualizar partner en el mensaje si no tiene
        if partner and not getattr(whatsapp_message, 'partner_id', None):
            try:
                whatsapp_message.partner_id = partner
            except Exception:
                pass

        # 2. Encontrar o crear sesión
        session = self._find_or_create_session(mobile_number, partner)
        session.last_message_date = fields.Datetime.now()

        # 3. Registrar mensaje entrante en la sesión
        self.env['whatsapp.ai.message'].create({
            'session_id': session.id,
            'direction': 'inbound',
            'body': message_body,
            'whatsapp_message_id': whatsapp_message.id,
        })

        # 4. Crear lead CRM si está configurado
        if self.create_lead:
            lead = self._ensure_crm_lead(session)
            # Agregar mensaje al chatter del lead
            if lead:
                try:
                    lead.message_post(
                        body=_('WhatsApp (entrada): %s') % message_body,
                        message_type='comment',
                        subtype_xmlid='mail.mt_note',
                    )
                except Exception:
                    pass

        # 5. Retardo de respuesta (simula escritura)
        if self.response_delay_seconds > 0:
            time.sleep(self.response_delay_seconds)

        # 6. Construir historial y obtener respuesta del AI
        conversation = self._build_conversation_history(session)
        ai_response = self._get_ai_response(self.system_prompt, conversation)

        if ai_response:
            # Eliminar bloques <think>...</think> del modelo
            import re
            ai_response = re.sub(r'<think>.*?</think>', '', ai_response, flags=re.DOTALL).strip()

        if not ai_response:
            _logger.warning(
                '[WhatsApp AI] Sin respuesta del AI para mensaje de %s. '
                'Usando mensaje de error.',
                mobile_number,
            )
            if self.fallback_message:
                ai_response = self.fallback_message
            else:
                return

        # 7. Enviar respuesta por WhatsApp
        success = self._send_whatsapp_response(mobile_number, ai_response, partner)

        if success:
            # 8. Registrar respuesta en la sesión
            self.env['whatsapp.ai.message'].create({
                'session_id': session.id,
                'direction': 'outbound',
                'body': ai_response,
            })

            # 9. Publicar respuesta en el canal de Odoo para que agentes humanos la vean
            try:
                mail_msg = getattr(whatsapp_message, 'mail_message_id', None)
                if mail_msg and mail_msg.model == 'discuss.channel':
                    channel = self.env['discuss.channel'].browse(mail_msg.res_id)
                    if channel.exists():
                        channel.with_context(whatsapp_ai_response=True).message_post(
                            body=ai_response,
                            message_type='comment',
                            author_id=self.env.ref('base.user_root').partner_id.id,
                        )
            except Exception as e:
                _logger.debug('[WhatsApp AI] No se pudo postear en canal Odoo: %s', e)

            # Registrar en el lead también
            if self.create_lead and session.lead_id:
                try:
                    session.lead_id.message_post(
                        body=_('WhatsApp AI (salida): %s') % ai_response,
                        message_type='comment',
                        subtype_xmlid='mail.mt_note',
                    )
                except Exception:
                    pass
        else:
            _logger.error(
                '[WhatsApp AI] Falló el envío de respuesta a %s',
                mobile_number,
            )

    # ── Cron: Cerrar sesiones inactivas ─────────────────────────────────────────

    @api.model
    def _cron_close_inactive_sessions(self):
        """Cierra sesiones sin actividad en las últimas 48 h."""
        cutoff = fields.Datetime.now() - timedelta(hours=48)
        stale = self.env['whatsapp.ai.session'].search([
            ('state', '=', 'active'),
            ('last_message_date', '<', cutoff),
        ])
        if stale:
            stale.write({'state': 'closed'})
            _logger.info(
                '[WhatsApp AI] %d sesiones inactivas cerradas.', len(stale),
            )
