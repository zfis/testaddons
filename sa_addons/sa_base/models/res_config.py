# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class SAConfiguration(models.TransientModel):
    _name = 'sa.config.settings'
    _inherit = 'res.config.settings'

    generate_result_sequence = fields.Selection([
        (0, "Set Sequence by Operation(default)"),
        (1, "Set Sequence by Per Vehicle")
    ], string="Result Sequences")

    auto_operation_inherit = fields.Selection([
        (0, "un auto operation inherit(default)"),
        (1, "auto operation inherit")
    ], string="Auto Operation Inherit")

    auto_operation_point_inherit = fields.Selection([
        (0, "un auto operation point inherit(default)"),
        (1, "auto operation point inherit")
    ], string="Auto Operation Point Inherit")

    @api.multi
    def set_default_generate_result_sequence(self):
        check = self.env.user.has_group('base.group_system')
        Values = check and self.env['ir.values'].sudo() or self.env['ir.values']
        for config in self:
            Values.set_default('sa.config.settings', 'generate_result_sequence', config.generate_result_sequence)

    @api.multi
    def set_default_auto_operation_inherit(self):
        check = self.env.user.has_group('base.group_system')
        Values = check and self.env['ir.values'].sudo() or self.env['ir.values']
        for config in self:
            Values.set_default('sa.config.settings', 'auto_operation_inherit', config.auto_operation_inherit)

    @api.multi
    def set_default_auto_operation_point_inherit(self):
        check = self.env.user.has_group('base.group_system')
        Values = check and self.env['ir.values'].sudo() or self.env['ir.values']
        for config in self:
            Values.set_default('sa.config.settings', 'auto_operation_point_inherit',
                               config.auto_operation_point_inherit)
