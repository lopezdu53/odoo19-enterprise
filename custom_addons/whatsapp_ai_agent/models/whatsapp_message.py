import logging
import threading

from odoo import api, models

_logger = logging.getLogger(__name__)


class WhatsappMessage(models.Model):
    """
    Extiende whatsapp.message para interceptar mensajes entrantes
    y enrutarlos al agente AI configurado para esa cuenta.
    """
    _inherit = 'whatsapp.message'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        # Evitar loop infinito cuando el AI crea mensajes de respuesta
        if self.env.context.get('whatsapp_ai_response'):
            return records

        # Filtrar mensajes entrantes
        inbound = records.filtered(self._is_inbound)
        if inbound:
            inbound._schedule_ai_processing()

        return records

    def write(self, vals):
        result = super().write(vals)

        # Detectar cuando el estado cambia a "recibido"
        if self.env.context.get('whatsapp_ai_response'):
            return result

        new_state = vals.get('state')
        if new_state and self._state_is_received(new_state):
            self.filtered(self._is_inbound)._schedule_ai_processing()

        return result

    # ── Helpers para detectar mensajes entrantes ────────────────────────────────

    def _is_inbound(self):
        """
        Determina si este mensaje es entrante (del cliente).

        El módulo whatsapp de Odoo 19 puede usar diferentes campos
        para indicar la dirección. Soportamos múltiples variantes.
        """
        # Variante 1: campo 'state' con valor 'received'
        state = getattr(self, 'state', None)
        if state is not None:
            if self._state_is_received(state):
                return True
            if state in ('outgoing', 'sent', 'delivered', 'read', 'cancel', 'error', 'failed'):
                return False

        # Variante 2: campo 'direction'
        direction = getattr(self, 'direction', None)
        if direction is not None:
            return direction == 'inbound'

        # Variante 3: tipo de mensaje indica dirección
        msg_type = getattr(self, 'message_type', None)
        if msg_type == 'inbound':
            return True
        if msg_type == 'outbound':
            return False

        # Variante 4: sin usuario creador (viene del webhook, no de un usuario Odoo)
        create_uid = getattr(self, 'create_uid', None)
        if create_uid:
            # Si fue creado por el usuario público o administrador del sistema = entrante
            if create_uid.id in (1,) and not getattr(self, 'author_id', None):
                return True

        # No podemos determinar la dirección con certeza: no procesar
        return False

    @staticmethod
    def _state_is_received(state):
        """Verifica si el estado corresponde a un mensaje recibido."""
        return state in ('received', 'inbound', 'incoming')

    # ── Procesamiento asíncrono ─────────────────────────────────────────────────

    def _schedule_ai_processing(self):
        """
        Lanza el procesamiento del AI en un hilo en segundo plano
        para no bloquear la respuesta del webhook de WhatsApp.
        """
        if not self:
            return

        db_name = self.env.cr.dbname
        message_ids = self.ids

        def _process_in_background():
            # Pequeño retardo para asegurar que la transacción del webhook esté committed
            import time
            time.sleep(1.5)

            try:
                from odoo import registry as odoo_registry

                with odoo_registry(db_name).cursor() as new_cr:
                    new_env = self.env(cr=new_cr)
                    messages = new_env['whatsapp.message'].browse(message_ids).exists()

                    for message in messages:
                        # Saltar si no tiene cuenta WhatsApp
                        account_id = getattr(message, 'whatsapp_account_id', None)
                        if not account_id:
                            continue

                        # Buscar agentes activos configurados para esta cuenta
                        agents = new_env['whatsapp.ai.agent'].search([
                            ('whatsapp_account_id', '=', account_id.id),
                            ('active', '=', True),
                            ('auto_respond', '=', True),
                        ])

                        for agent in agents:
                            try:
                                agent.process_inbound_message(message)
                            except Exception as exc:
                                _logger.error(
                                    '[WhatsApp AI] Error procesando mensaje %d con agente %s: %s',
                                    message.id, agent.name, str(exc),
                                    exc_info=True,
                                )

                    # Commit explícito al finalizar todo el procesamiento
                    new_cr.commit()

            except Exception as exc:
                _logger.error(
                    '[WhatsApp AI] Error general en procesamiento en segundo plano: %s',
                    str(exc),
                    exc_info=True,
                )

        thread = threading.Thread(
            target=_process_in_background,
            name=f'whatsapp_ai_agent_{self.env.cr.dbname}',
            daemon=True,
        )
        thread.start()
        _logger.debug(
            '[WhatsApp AI] Hilo de procesamiento lanzado para mensajes: %s',
            message_ids,
        )
