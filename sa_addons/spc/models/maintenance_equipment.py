# -*- coding: utf-8 -*-

from odoo import models, fields, api


class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'

    @api.multi
    def action_see_spc_control(self):
        action = self.env.ref('spc.quality_check_action_spc').read()[0]
        action.update({
            'context': {
                'search_default_gun_id': self.id
            }
        })
        return action
