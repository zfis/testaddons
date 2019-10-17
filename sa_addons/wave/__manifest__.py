# -*- coding: utf-8 -*-
{
    'name': "wave",

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
    'depends': ['web', 'web_widget_echarts', 'sa_base', 'web_notify'],

    "external_dependencies": {
        "python": ['minio'],
    },

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/wave_views.xml',
        'views/res_config_views.xml',
        'views/operation_result_views.xml',
        'views/wave_menu_views.xml',
        'views/wave_wizard_views.xml'
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
