# -*- coding: utf-8 -*-

from odoo import models, fields, api


class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'

    location_tag = fields.Char('Location Tag')
