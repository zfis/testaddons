# -*- coding: utf-8 -*-
{
    'name': "svw_enhanced",

    'summary': """
        TS003, 上海大众(延锋)公用模块""",

    'description': """
        TS003, 上海大众(延锋)公用模块
    """,

    'author': "Frank Gu",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Manufacturing',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['sa_base', 'spc'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/mrp_production_views.xml',
        'views/mrp_bom_views.xml',
        'views/hide_menu.xml',
        'views/mrp_routing_view.xml',
        'views/mrp_workcenter_views.xml',
        'views/operation_result_views.xml',
        'views/spc_wizard.xml',
        'report/svw_mrp_report_main.xml',
        'report/mrp_production_pin_template.xml',
    ],
    # only loaded in demonstration mode
}
