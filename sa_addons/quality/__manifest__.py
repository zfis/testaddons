# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Quality Control',
    'version': '1.0',
    'category': 'Manufacturing',
    'sequence': 50,
    'summary': 'Quality Alerts and Control Points',
    'depends': ['stock', 'decimal_precision'],
    'description': """
Quality Control
===============

* Define quality points that will generate quality checks on pickings,
  manufacturing orders or work orders (quality_mrp)
* Quality alerts can be created independently or related to quality checks
* Possibility to add a measure to the quality check with a min/max tolerance
* Define your stages for the quality alerts

""",
    'data': [
        'security/quality.xml',
        'security/ir.model.access.csv',
        'data/quality_data.xml',
        'views/quality_templates.xml',
        'views/quality_views.xml',
        'views/stock_picking_views.xml'
    ],
    'demo': [
        'data/quality_demo.xml'
    ],
    'application': True,
}
