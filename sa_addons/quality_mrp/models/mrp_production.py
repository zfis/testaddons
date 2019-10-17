# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    check_ids = fields.One2many('sa.quality.check', 'production_id', string="Checks")
    check_todo = fields.Boolean(compute='_compute_check_todo')
    alert_ids = fields.One2many('sa.quality.alert', "production_id", string="Alerts")
    # TODO : No need alert ids field
    alert_count = fields.Integer(compute='_compute_alert_count')

    @api.multi
    def _compute_check_todo(self):
        for production in self:
            if any([(x.quality_state == 'none') for x in production.check_ids]):
                production.check_todo = True

    @api.multi
    def _compute_alert_count(self):
        # TODO: Check if we include those in the work orders
        alert_data = self.env['sa.quality.alert'].read_group([('production_id', 'in', self.ids)], ['production_id'],
                                                             ['production_id'])
        result = dict((data['production_id'][0], data['production_id_count']) for data in alert_data)
        for order in self:
            order.alert_count = result.get(order.id, 0)

    @api.multi
    def open_quality_alert_mo(self):
        self.ensure_one()
        if self.alert_count == 1:
            view = self.env.ref('quality.quality_alert_view_form')
            res_id = self.env['sa.quality.alert'].search([('production_id', '=', self.id)])
            return {
                'name': _('Quality Alerts'),
                'type': 'ir.actions.act_window',
                'res_model': 'sa.quality.alert',
                'views': [(view.id, 'form')],
                'res_id': res_id.id,
                'context': {'production_id': self.ids},
            }
        else:
            action_rec = self.env.ref('quality.quality_alert_action_check')
            if action_rec:
                action = action_rec.read([])[0]
                action['context'] = {'default_production_id': self.id}
                action['domain'] = [('production_id', '=', self.id)]
                return action

    @api.multi
    def button_quality_alert(self):
        self.ensure_one()
        action_rec = self.env.ref('quality.quality_alert_action_check')
        if action_rec:
            action = action_rec.read([])[0]
            action['views'] = [(view_id, mode) for (view_id, mode) in action['views'] if mode == 'form'] or action[
                'views']
            action['context'] = {
                'default_product_tmpl_id': self.product_id.product_tmpl_id.id,
                'default_product_id': self.product_id.id,
                'company_id': self.company_id.id
            }
            return action

    @api.multi
    def button_plan(self):
        super(MrpProduction, self).button_plan()
        for production in self:
            if not production.workorder_ids.mapped('check_ids'):
                production.workorder_ids._create_checks()

    @api.multi
    def _generate_moves(self):
        for production in self:
            points = self.env['sa.quality.point'].search([('workcenter_id', '=', False),
                                                          ('picking_type_id', '=', production.picking_type_id.id),
                                                          '|', ('product_id', '=', production.product_id.id),
                                                          '&', ('product_id', '=', False), ('product_tmpl_id', '=',
                                                                                            production.product_id.product_tmpl_id.id)])
            for point in points:
                if point.check_execute_now():
                    self.env['sa.quality.check'].create({'workorder_id': False,
                                                         'production_id': production.id,
                                                         'point_id': point.id,
                                                         'team_id': point.team_id.id,
                                                         'product_id': production.product_id.id,
                                                         })
        return super(MrpProduction, self)._generate_moves()

    @api.multi
    def button_mark_done(self):
        for order in self:
            if any([(x.quality_state == 'none') for x in order.check_ids]):
                raise UserError(_('You still need to do the quality checks!'))
        return super(MrpProduction, self).button_mark_done()

    @api.multi
    def check_quality(self):
        self.ensure_one()
        checks = self.check_ids.filtered(lambda x: x.quality_state == 'none')
        if checks:
            action_rec = self.env.ref('quality.quality_check_action_small')
            if action_rec:
                action = action_rec.read([])[0]
                action['context'] = self.env.context
                action['res_id'] = checks[0].id
                return action

    @api.multi
    def action_cancel(self):
        res = super(MrpProduction, self).action_cancel()
        self.sudo().mapped('check_ids').filtered(lambda x: x.quality_state == 'none').unlink()
        return res
