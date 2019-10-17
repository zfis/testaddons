# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    sa_type = fields.Selection(selection_add=[('carriage', 'Train Carriage')], default='carriage')
