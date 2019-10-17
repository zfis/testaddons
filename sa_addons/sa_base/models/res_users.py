# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    uuid = fields.Char(string='UUID')

    _sql_constraints = [
        ('unique_uuid', 'unique(uuid)', 'Every User unique UUID'),
    ]
