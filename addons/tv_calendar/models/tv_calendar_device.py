from odoo import api, fields, models

# Segundos sin recibir latido tras los cuales se considera desconectado.
# El kiosco envia un latido cada 60 s, asi que 180 s tolera 2 fallos.
OFFLINE_AFTER = 180


class TvCalendarDevice(models.Model):
    _name = 'tv.calendar.device'
    _description = 'Pantalla / dispositivo del TV'
    _order = 'name'

    name = fields.Char(string='Nombre del dispositivo', required=True)
    board_id = fields.Many2one(
        'tv.calendar.board', string='Tablero', ondelete='cascade', index=True)
    last_seen = fields.Datetime(string='Ultima conexion')
    last_ip = fields.Char(string='Ultima IP')
    status = fields.Selection(
        [('online', 'En linea'), ('offline', 'Desconectado')],
        string='Estado', compute='_compute_status', search='_search_status')
    seconds_since = fields.Integer(
        string='Hace (s)', compute='_compute_status')

    _sql_constraints = [
        ('name_board_uniq', 'unique(name, board_id)',
         'Ya existe un dispositivo con ese nombre en este tablero.'),
    ]

    @api.depends('last_seen')
    def _compute_status(self):
        now = fields.Datetime.now()
        for dev in self:
            if dev.last_seen:
                secs = int((now - dev.last_seen).total_seconds())
            else:
                secs = -1
            dev.seconds_since = secs
            dev.status = 'online' if 0 <= secs <= OFFLINE_AFTER else 'offline'

    def _search_status(self, operator, value):
        from datetime import timedelta
        threshold = fields.Datetime.now() - timedelta(seconds=OFFLINE_AFTER)
        online_ids = self.search([('last_seen', '>=', threshold)]).ids
        if (operator == '=' and value == 'online') or (operator == '!=' and value == 'offline'):
            return [('id', 'in', online_ids)]
        return [('id', 'not in', online_ids)]

    @api.model
    def register_ping(self, board, name, ip=None):
        """Crea o actualiza el dispositivo y marca su ultima conexion."""
        name = (name or 'Sin nombre').strip()[:120]
        device = self.search(
            [('board_id', '=', board.id), ('name', '=', name)], limit=1)
        vals = {'last_seen': fields.Datetime.now()}
        if ip:
            vals['last_ip'] = ip
        if device:
            device.write(vals)
        else:
            vals.update({'name': name, 'board_id': board.id})
            device = self.create(vals)
        return device
