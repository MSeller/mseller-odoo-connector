{
    'name': 'MSeller DGII e-CF Connector',
    'summary': 'Foundation connector for the MSeller DGII electronic invoice (e-CF) API',
    'description': """
MSeller DGII e-CF Connector (Foundation)
=========================================
Configures and validates a connection to the MSeller e-CF API
(https://ecf.api.mseller.app). Targets Odoo 17.0+ (17, 18, 19).

This foundation module exposes the configuration UI (email,
password, API key, environment) on res.company and ships a
reusable Python client (`MSellerClient`) covering the full public
e-CF API surface: authentication, document submission, validation,
single status query and batch status query.

Future phases will wire account.move (invoices, vendor bills) to
the client, manage eNCF sequences, and add cron-driven token
refresh.
""",
    'author': 'MSeller Community',
    'website': 'https://github.com/MSeller/mseller-odoo-connector',
    'license': 'LGPL-3',
    'category': 'Accounting/Localizations/EDI',
    'version': '1.0.0',
    'depends': ['base', 'base_setup'],
    'data': [
        'views/res_config_settings_views.xml',
        'views/res_company_views.xml',
    ],
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
