# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    result_ids = fields.One2many('operation.result', 'production_id', string='Operation Results')

    @api.multi
    def action_see_spc_control(self):
        action = self.env.ref('spc.quality_check_action_spc').read()[0]
        action.update({
            'context': {
                'search_default_name': self.knr if self.knr else self.vin
            }
        })
        return action
