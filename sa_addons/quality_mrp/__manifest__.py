# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'MRP features for Quality Control',
    'version': '1.0',
    'category': 'Manufacturing',
    'sequence': 50,
    'summary': 'Quality Management with MRP',
    'depends': ['quality', 'mrp_workorder'],
    'description': """
    Adds workcenters to Quality Control
""",
    "data": [
        'security/quality_mrp.xml',
        'views/quality_views.xml',
        'views/mrp_production_views.xml',
        'views/mrp_workorder_views.xml',
        'views/mrp_workcenter_views.xml',
    ],
    "demo": ['data/quality_mrp_demo.xml'],
    'auto_install': True,
}
