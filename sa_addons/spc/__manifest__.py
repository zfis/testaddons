# -*- coding: utf-8 -*-
{
    'name': "spc",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Long description of module's purpose
    """,

    'author': "My Company",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['sa_base', 'web_widget_echarts', 'web_notify'],

    # always loaded
    'data': [
        'data/result_data.xml',
        'security/spc_security.xml',
        'security/ir.model.access.csv',
        'views/mrp_workorder_views.xml',
        'views/spc_menu_views.xml',
        'views/spc_wizard.xml',
        'views/operation_result_views.xml',
        'views/res_config_views.xml',
        'report/spc_report_main.xml',
        'report/report_result_views.xml'
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
