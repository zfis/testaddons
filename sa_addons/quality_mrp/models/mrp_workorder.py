# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MrpProductionWorkcenterLine(models.Model):
    _inherit = "mrp.workorder"

    check_ids = fields.One2many('sa.quality.check', 'workorder_id')
    check_todo = fields.Boolean(compute='_compute_check_todo')
    alert_count = fields.Integer(compute="_compute_alert_count")

    @api.multi
    @api.depends('check_ids.quality_state')
    def _compute_check_todo(self):
        for workorder in self:
            if any([(x.quality_state == 'none') for x in workorder.check_ids]):
                workorder.check_todo = True

    @api.multi
    def _compute_alert_count(self):
        alert_data = self.env['sa.quality.alert'].read_group([('operation_id', 'in', self.ids)], ['operation_id'],
                                                             ['operation_id'])
        result = dict((data['operation_id'][0], data['operation_id_count']) for data in alert_data)
        for order in self:
            order.alert_count = result.get(order.id, 0)

    @api.multi
    def open_quality_alert_wo(self):
        self.ensure_one()
        if self.alert_count == 1:
            res_id = self.env['sa.quality.alert'].search([('operation_id', '=', self.id)])
            view = self.env.ref('quality.quality_alert_view_form')
            return {
                'name': _('Quality Alerts'),
                'type': 'ir.actions.act_window',
                'res_model': 'sa.quality.alert',
                'views': [(view.id, 'form')],
                'res_id': res_id.id,
                'context': {'operation_id': self.ids},
            }
        else:
            action_rec = self.env.ref('quality.quality_alert_action_check')
            if action_rec:
                action = action_rec.read([])[0]
                action['context'] = {'default_operation_id': self.id}
                action['domain'] = [('operation_id', '=', self.id)]
                return action

    @api.multi
    def button_quality_alert(self):
        self.ensure_one()
        action_rec = self.env.ref('quality.quality_alert_action_team')
        if action_rec:
            action = action_rec.read([])[0]
            action['views'] = [(view_id, mode) for (view_id, mode) in action['views'] if mode == 'form'] or action[
                'views']
            action['context'] = {
                'default_product_id': self.product_id.id,
                'default_product_tmpl_id': self.product_id.product_tmpl_id.id,
                'default_operation_id': self.id,
                'company_id': self.production_id.company_id.id
            }
            return action

    @api.multi
    def _create_checks(self):
        for wo in self:
            production = wo.production_id
            points = self.env['sa.quality.point'].search([('workcenter_id', '=', wo.workcenter_id.id),
                                                          ('picking_type_id', '=', production.picking_type_id.id),
                                                          '|', ('product_id', '=', production.product_id.id),
                                                          '&', ('product_id', '=', False), ('product_tmpl_id', '=',
                                                                                            production.product_id.product_tmpl_id.id)])
            for point in points:
                if point.check_execute_now():
                    self.env['sa.quality.check'].create({'workorder_id': wo.id,
                                                         'point_id': point.id,
                                                         'team_id': point.team_id.id,
                                                         'product_id': production.product_id.id,
                                                         })

    @api.multi
    def record_production(self):
        self.ensure_one()
        if any([(x.quality_state == 'none') for x in self.check_ids]):
            raise UserError(_('You still need to do the quality checks!'))
        if self.check_ids:
            # Check if you can attribute the lot to the checks
            if (self.production_id.product_id.tracking != 'none') and self.final_lot_id:
                checks_to_assign = self.check_ids.filtered(lambda x: not x.lot_id)
                if checks_to_assign:
                    checks_to_assign.write({'lot_id': self.final_lot_id.id})
        res = super(MrpProductionWorkcenterLine, self).record_production()
        if self.qty_producing > 0:
            self._create_checks()
        return res

    @api.multi
    def check_quality(self):
        self.ensure_one()
        checks = self.check_ids.filtered(lambda x: x.quality_state == 'none')
        if checks:
            action_rec = self.env.ref('quality.quality_check_action_small')
            if action_rec:
                action = action_rec.read([])[0]
                action['context'] = dict(self.env.context, active_model='mrp.workorder')
                action['res_id'] = checks[0].id
                return action
