# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Mrp Workorder',
    'version': '1.0',
    'category': 'Manufacturing',
    'sequence': 51,
    'summary': """Work Orders, Planing, Stock Reports.""",
    'depends': ['mrp'],
    'description': """Enterprise extension for MRP

* Work order planning.  Check planning by Gantt views grouped by production order / work center
* Traceability report
* Cost Structure report (mrp_account)""",
    'data': [
        'data/stock_traceability_report_data.xml',
        'views/mrp_workorder_views.xml',
        'views/mrp_workcenter_views.xml',
        'views/mrp_workorder_template.xml',
        'views/mrp_production_views.xml',
        'views/mrp_routing_views.xml',
        'views/report_stock_traceability.xml',
        'views/stock_traceability_report_views.xml',
    ],
    'demo': [
        'data/mrp_production_demo.xml'
    ],
    'qweb': [
        'static/src/xml/stock_traceability_report_backend.xml',
    ],
    'auto_install': True,
}
