# -*- coding: utf-8 -*-
{
    'name': "sa_maintenance",

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
    'depends': ['mrp_maintenance', 'sa_base'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'data/data.xml',
        'views/maintenance_views.xml',
        'views/mrp_maintenance_template.xml',
        'views/equipment_view.xml',
        'views/res_config_views.xml',
        'report/maintenance_report_main.xml',
        'report/report_maintenance_views.xml',
        'report/sheet_maintenance_views.xml'
    ],
    # 'qweb': [
    #     "static/src/xml/mrp_maintenance_template.xml",
    # ],
    # only loaded in demonstration mode
    # 'demo': [
    #     'demo/demo.xml',
    # ],
}
