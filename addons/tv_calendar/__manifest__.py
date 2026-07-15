{
    'name': 'TV Calendar Board',
    'version': '19.0.1.1.0',
    'category': 'Productivity',
    'summary': 'Calendario mensual a pantalla completa para proyectar en un TV (modo kiosco).',
    'description': """
TV Calendar Board
=================

Convierte una TV en un cronograma visual. Muestra el mes de trabajo en una
sola pantalla, a pantalla completa, con letras grandes y tareas coloreadas
segun su importancia. Pensado para proyectarse sin raton ni teclado: se
actualiza solo cada cierto tiempo.

Caracteristicas
---------------
* Vista de mes completo, pantalla completa, alto contraste.
* Tareas creadas por los usuarios de Odoo desde el backend.
* Color por importancia: Baja, Normal, Alta, Critica.
* Varios tableros (boards), cada uno con su URL/token publico para el TV.
* Auto-refresco configurable (no requiere interaccion).
* Vista calendario en el backend para gestionar las tareas comodamente.
""",
    'author': 'Odoo TV Calendar',
    'website': 'https://github.com/lopezdu53/odoo19-enterprise',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'hr'],
    'data': [
        'security/tv_calendar_security.xml',
        'security/ir.model.access.csv',
        'views/tv_calendar_task_views.xml',
        'views/tv_calendar_board_views.xml',
        'views/tv_calendar_menus.xml',
        'templates/kiosk_templates.xml',
        'data/demo_data.xml',
    ],
    'application': True,
    'installable': True,
    'post_init_hook': 'post_init_hook',
}
