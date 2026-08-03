from odoo import fields, models

COMPONENT_STATES = [
    ('new', 'Pendiente'),
    ('requested', 'Solicitado al proveedor'),
    ('delivered', 'Entregado al operario'),
]


class TvCalendarComponentRequest(models.Model):
    _name = 'tv.calendar.component.request'
    _description = 'Solicitud de componente (TV)'
    _order = 'create_date desc, id desc'

    name = fields.Char(string='Titulo', required=True)
    board_id = fields.Many2one(
        'tv.calendar.board', string='Tablero', ondelete='cascade', index=True)
    task_id = fields.Many2one(
        'tv.calendar.task', string='Tarea', ondelete='set null')
    product_id = fields.Many2one('product.product', string='Producto')
    category_id = fields.Many2one('product.category', string='Categoria')
    description = fields.Text(string='Descripcion')
    value = fields.Float(string='Valor')
    operator = fields.Char(string='Operario')
    state = fields.Selection(
        COMPONENT_STATES, string='Estado', default='new', required=True, index=True)
    requested_datetime = fields.Datetime(string='Solicitado al proveedor')
    delivered_datetime = fields.Datetime(string='Entregado al operario')
