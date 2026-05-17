{
    'name': 'WhatsApp AI Agent',
    'version': '19.0.1.0.0',
    'category': 'Discuss/WhatsApp',
    'summary': 'Integra Agentes AI con WhatsApp: respuestas automáticas, creación de leads y contactos',
    'description': """
        Módulo de integración entre WhatsApp Business API y los Agentes AI de Odoo 19.

        Funcionalidades:
        - Configura agentes AI para responder automáticamente mensajes de WhatsApp
        - Soporta OpenAI (ChatGPT), Anthropic (Claude) y APIs compatibles con OpenAI
        - Integración opcional con el módulo nativo AI Agent de Odoo 19
        - Creación automática de contactos (res.partner) desde números de WhatsApp
        - Creación automática de leads en CRM con datos de la conversación
        - Historial de conversación para contexto del AI
        - Configuración de prompt de sistema (entrenamiento del agente)
        - Sesiones de conversación con seguimiento de estado
        - Compatible con múltiples cuentas WhatsApp Business
    """,
    'author': 'Custom Development',
    'website': '',
    'depends': [
        'whatsapp',
        'crm',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/whatsapp_ai_agent_views.xml',
        'views/whatsapp_ai_session_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
    'images': ['static/description/banner.png'],
}
