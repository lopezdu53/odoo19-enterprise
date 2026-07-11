from odoo import fields, models

# Colores por palabra clave de la actividad (plantilla Operario).
# Las franjas sin actividad son bloques de trabajo normales (sin color).
SLOT_COLORS = {
    'INGRESO': '#2e7d32',
    'OPERARIO EN EL PUESTO DE TRABAJO': '#00838f',
    'PAUSA ACTIVA': '#ef6c00',
    'ALMUERZO': '#1565c0',
    'LIMPIEZA PUESTO DE TRABAJO': '#6a1b9a',
    'SALIDA': '#c62828',
}
DEFAULT_SLOT_COLOR = '#37474f'


class TvCalendarTimeSlot(models.Model):
    _name = 'tv.calendar.time.slot'
    _description = 'Franja horaria del turno (plantilla Operario)'
    _order = 'sequence, id'

    board_id = fields.Many2one(
        'tv.calendar.board', string='Tablero', required=True,
        ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    time_label = fields.Char(string='Hora', required=True)
    activity = fields.Char(string='Actividad')

    def slot_color(self):
        self.ensure_one()
        key = (self.activity or '').strip().upper()
        if not key:
            return None
        return SLOT_COLORS.get(key, DEFAULT_SLOT_COLOR)
