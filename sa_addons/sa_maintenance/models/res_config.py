# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


from odoo import api, fields, models, tools


class MaintenanceConfiguration(models.TransientModel):
    """ Inherit the base settings to add a counter of failed email + configure
    the alias domain. """
    _name = 'sa.maintenance.settings'
    _inherit = 'res.config.settings'

    res_field = fields.Char('Result Related Field')

    @api.model
    def get_default_res_field(self, fields):
        res_field = self.env["ir.config_parameter"].get_param("maintenance.result.res_field", default=None)
        return {'res_field': res_field or False}

    @api.multi
    def set_res_field(self):
        for record in self:
            self.env['ir.config_parameter'].set_param("maintenance.result.res_field", record.res_field or '')
