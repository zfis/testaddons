# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class QualityPoint(models.Model):
    _inherit = "sa.quality.point"

    workcenter_id = fields.Many2one('mrp.workcenter', 'Workcenter')
    code = fields.Selection(related='picking_type_id.code')  # TDE FIXME: necessary ?


class QualityAlert(models.Model):
    _inherit = "sa.quality.alert"

    operation_id = fields.Many2one('mrp.workorder', 'Operation')
    workcenter_id = fields.Many2one('mrp.workcenter', 'Work Center')
    production_id = fields.Many2one('mrp.production', "Production Order")

    @api.multi
    def action_create_message(self):
        self.ensure_one()
        return {
            'name': _('Workorder Messages'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mrp.message',
            'view_id': self.env.ref('mrp.mrp_message_view_form_embedded_product').id,
            'type': 'ir.actions.act_window',
            'context': {
                'default_workcenter_id': self.workcenter_id.id,
                'default_product_tmpl_id': self.product_tmpl_id.id,
                'default_product_id': self.product_id.id,
                'default_message': 'Quality Alert For Product: %s' % self.product_id.name
            },
            'target': 'new',
        }


class QualityCheck(models.Model):
    _inherit = "sa.quality.check"

    workorder_id = fields.Many2one('mrp.workorder', 'Operation')
    workcenter_id = fields.Many2one('mrp.workcenter', related='workorder_id.workcenter_id', store=True,
                                    readonly=True)  # TDE: necessary ?
    production_id = fields.Many2one('mrp.production', 'Production Order')

    @api.multi
    def redirect_after_pass_fail(self):
        self.ensure_one()
        checks = False
        if self.production_id and not self.workorder_id:
            checks = self.production_id.check_ids.filtered(lambda x: x.quality_state == 'none')
        elif self.workorder_id:
            checks = self.workorder_id.check_ids.filtered(lambda x: x.quality_state == 'none')
        elif self.picking_id:
            checks = self.picking_id.check_ids.filtered(lambda x: x.quality_state == 'none')
        if checks:
            action = self.env.ref('quality.quality_check_action_small').read()[0]
            action['res_id'] = checks.ids[0]
            return action
        else:
            return {'type': 'ir.actions.act_window_close'}
