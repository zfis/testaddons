# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
from dateutil.relativedelta import relativedelta
import random

from odoo import api, fields, models, _, SUPERUSER_ID
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import odoo.addons.decimal_precision as dp


class TestType(models.Model):
    _name = "sa.quality.point.test_type"
    _description = "Quality Control Test Type"

    # Used instead of selection field in order to hide a choice depending on the view.
    name = fields.Char('Name', required=True)
    technical_name = fields.Char('Technical name', required=True)


class QualityPoint(models.Model):
    _name = "sa.quality.point"
    _description = "Quality Point"
    _inherit = ['mail.thread']

    def __get_default_team_id(self):
        return self.env['sa.quality.alert.team'].search([], limit=1).id

    def _get_type_default_domain(self):
        return []

    def _get_default_test_type_id(self):
        domain = self._get_type_default_domain()
        return self.env['sa.quality.point.test_type'].search(domain, limit=1).id

    name = fields.Char(
        'Reference', copy=False, default=lambda self: _('New'),
        readonly=True, required=True)
    title = fields.Char('Title')
    team_id = fields.Many2one(
        'sa.quality.alert.team', 'Team',
        default=__get_default_team_id, required=True)
    product_id = fields.Many2one(
        'product.product', 'Product Variant',
        domain="[('product_tmpl_id', '=', product_tmpl_id)]")
    product_tmpl_id = fields.Many2one(
        'product.template', 'Product', required=True,
        domain="[('type', 'in', ['consu', 'product'])]")
    picking_type_id = fields.Many2one('stock.picking.type', "Picking Type", required=True)
    measure_frequency_type = fields.Selection([
        ('all', 'All Operations'),
        ('random', 'Randomly'),
        ('periodical', 'Periodically')], string="Frequency",
        default='all', required=True)
    measure_frequency_value = fields.Float('Percentage')  # TDE RENAME ?
    measure_frequency_unit_value = fields.Integer('Frequency')  # TDE RENAME ?
    measure_frequency_unit = fields.Selection([
        ('day', 'Day(s)'),
        ('week', 'Week(s)'),
        ('month', 'Month(s)')], default="day")  # TDE RENAME ?
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id)
    user_id = fields.Many2one('res.users', 'Responsible')
    active = fields.Boolean(default=True)
    check_count = fields.Integer(compute="_compute_check_count")
    test_type_id = fields.Many2one('sa.quality.point.test_type', 'Test Type',
                                   help="Defines the type of the quality control point.",
                                   required=True, default=_get_default_test_type_id)
    test_type = fields.Char(related='test_type_id.technical_name', readonly=True)

    norm = fields.Float('Norm', digits=dp.get_precision('Quality Tests'))  # TDE RENAME ?
    tolerance_min = fields.Float('Min Tolerance', digits=dp.get_precision('Quality Tests'))
    tolerance_max = fields.Float('Max Tolerance', digits=dp.get_precision('Quality Tests'))
    norm_unit = fields.Char('Unit of Measure', default=lambda self: 'mm')  # TDE RENAME ?
    note = fields.Html('Note')
    reason = fields.Html('Note')

    def _compute_check_count(self):
        check_data = self.env['sa.quality.check'].read_group([('point_id', 'in', self.ids)], ['point_id'], ['point_id'])
        result = dict((data['point_id'][0], data['point_id_count']) for data in check_data)
        for point in self:
            point.check_count = result.get(point.id, 0)

    @api.onchange('product_tmpl_id')
    def onchange_product_tmpl_id(self):
        self.product_id = self.product_tmpl_id.product_variant_ids.ids and self.product_tmpl_id.product_variant_ids[0]

    @api.onchange('norm')
    def onchange_norm(self):
        if self.tolerance_max == 0.0:
            self.tolerance_max = self.norm

    @api.model
    def create(self, vals):
        if 'name' not in vals or vals['name'] == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('sa.quality.point') or _('New')
        return super(QualityPoint, self).create(vals)

    @api.multi
    def action_see_quality_checks(self):
        action = self.env.ref('quality.quality_check_action_main').read()[0]
        action['domain'] = [('point_id', '=', self.ids[0])]
        action['context'] = {'default_point_id': self.ids[0]}
        return action

    @api.multi
    def action_see_spc_control(self):
        action = self.env.ref('quality.quality_check_action_spc').read()[0]
        action['domain'] = [('point_id', '=', self.ids[0])]
        return action

    @api.multi
    def check_execute_now(self):
        # TDE FIXME: make true multi
        self.ensure_one()
        if self.measure_frequency_type == 'all':
            return True
        elif self.measure_frequency_type == 'random':
            return (random.random() < self.measure_frequency_value / 100.0)
        elif self.measure_frequency_type == 'periodical':
            delta = False
            if self.measure_frequency_unit == 'day':
                delta = relativedelta(days=self.measure_frequency_unit_value)
            elif self.measure_frequency_unit == 'week':
                delta = relativedelta(weeks=self.measure_frequency_unit_value)
            elif self.measure_frequency_unit == 'month':
                delta = relativedelta(months=self.measure_frequency_unit_value)
            date_previous = datetime.today() - delta
            checks = self.env['sa.quality.check'].search([
                ('point_id', '=', self.id),
                ('create_date', '>=', date_previous.strftime(DEFAULT_SERVER_DATETIME_FORMAT))], limit=1)
            return not (bool(checks))
        return False


class QualityAlertTeam(models.Model):
    _name = "sa.quality.alert.team"
    _description = "Quality Alert Team"
    _inherit = ['mail.alias.mixin', 'mail.thread']
    _order = "sequence, id"

    name = fields.Char('Name', required=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id)
    sequence = fields.Integer('Sequence')
    check_count = fields.Integer('# Quality Checks', compute='_compute_check_count')
    alert_count = fields.Integer('# Quality Alerts', compute='_compute_alert_count')
    color = fields.Integer('Color')
    alias_id = fields.Many2one('mail.alias', 'Alias', ondelete="restrict", required=True)

    @api.multi
    def _compute_check_count(self):
        check_data = self.env['sa.quality.check'].read_group(
            [('team_id', 'in', self.ids), ('quality_state', '=', 'none')], ['team_id'], ['team_id'])
        check_result = dict((data['team_id'][0], data['team_id_count']) for data in check_data)
        for team in self:
            team.check_count = check_result.get(team.id, 0)

    @api.multi
    def _compute_alert_count(self):
        alert_data = self.env['sa.quality.alert'].read_group(
            [('team_id', 'in', self.ids), ('stage_id.done', '=', False)], ['team_id'], ['team_id'])
        alert_result = dict((data['team_id'][0], data['team_id_count']) for data in alert_data)
        for team in self:
            team.alert_count = alert_result.get(team.id, 0)

    def get_alias_model_name(self, vals):
        return vals.get('alias_model', 'sa.quality.alert')

    def get_alias_values(self):
        values = super(QualityAlertTeam, self).get_alias_values()
        values['alias_defaults'] = {'team_id': self.id}
        return values


class QualityReason(models.Model):
    _name = "sa.quality.reason"
    _description = "Quality Reason"

    name = fields.Char('Name', required=True)


class QualityTag(models.Model):
    _name = "sa.quality.tag"
    _description = "Quality Tag"

    name = fields.Char('Name', required=True)
    color = fields.Integer('Color Index', help='Used in the kanban view')  # TDE: should be default value


class QualityAlertStage(models.Model):
    _name = "sa.quality.alert.stage"
    _description = "Quality Alert Stage"
    _order = "sequence, id"
    _fold_name = 'folded'

    name = fields.Char('Name', required=True)
    sequence = fields.Integer('Sequence')
    folded = fields.Boolean('Folded')
    done = fields.Boolean('Alert Processed')


class QualityCheck(models.Model):
    _name = "sa.quality.check"
    _description = "Quality Check"
    _inherit = ['mail.thread']

    name = fields.Char('Name', default=lambda self: _('New'))
    point_id = fields.Many2one('sa.quality.point', 'Control Point')
    quality_state = fields.Selection([
        ('none', 'To do'),
        ('pass', 'Passed'),
        ('fail', 'Failed')], string='Status', track_visibility='onchange',
        default='none', copy=False)
    control_date = fields.Datetime('Control Date', track_visibility='onchange')
    product_id = fields.Many2one(
        'product.product', 'Product',
        domain="[('type', 'in', ['consu', 'product'])]", required=True)
    picking_id = fields.Many2one('stock.picking', 'Operation')
    lot_id = fields.Many2one('stock.production.lot', 'Lot', domain="[('product_id', '=', product_id)]")
    user_id = fields.Many2one('res.users', 'Responsible', track_visibility='onchange')
    team_id = fields.Many2one('sa.quality.alert.team', 'Team', required=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.user.company_id)
    alert_ids = fields.One2many('sa.quality.alert', 'check_id', string='Alerts')
    alert_count = fields.Integer('# Quality Alerts', compute="_compute_alert_count")
    note = fields.Html(related='point_id.note', readonly=True)
    test_type = fields.Char(related="point_id.test_type", readonly=True)
    norm_unit = fields.Char(related='point_id.norm_unit', readonly=True)
    measure = fields.Float('Measure', default=0.0, digits=dp.get_precision('Quality Tests'),
                           track_visibility='onchange')
    measure_success = fields.Selection([
        ('none', 'No measure'),
        ('pass', 'Pass'),
        ('fail', 'Fail')], string="Measure Success", compute="_compute_measure_success",
        readonly=True, store=True)

    @api.multi
    def _compute_alert_count(self):
        alert_data = self.env['sa.quality.alert'].read_group([('check_id', 'in', self.ids)], ['check_id'], ['check_id'])
        alert_result = dict((data['check_id'][0], data['check_id_count']) for data in alert_data)
        for check in self:
            check.alert_count = alert_result.get(check.id, 0)

    @api.one
    @api.depends('measure')
    def _compute_measure_success(self):
        if self.point_id.test_type == 'passfail':
            self.measure_success = 'none'
        else:
            if self.measure < self.point_id.tolerance_min or self.measure > self.point_id.tolerance_max:
                self.measure_success = 'fail'
            else:
                self.measure_success = 'pass'

    @api.onchange('point_id')
    def _onchange_point_id(self):
        if self.point_id:
            self.product_id = self.point_id.product_id
            self.team_id = self.point_id.team_id.id

    @api.model
    def create(self, vals):
        if 'name' not in vals or vals['name'] == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('sa.quality.check') or _('New')
        return super(QualityCheck, self).create(vals)

    @api.multi
    def do_fail(self):
        self.write({
            'quality_state': 'fail',
            'user_id': self.env.user.id,
            'control_date': datetime.now()})
        return self.redirect_after_pass_fail()

    @api.multi
    def do_pass(self):
        self.write({'quality_state': 'pass',
                    'user_id': self.env.user.id,
                    'control_date': datetime.now()})
        return self.redirect_after_pass_fail()

    @api.multi
    def do_measure(self):
        if self.measure < self.point_id.tolerance_min or self.measure > self.point_id.tolerance_max:
            return self.do_fail()
        else:
            return self.do_pass()

    @api.multi
    def do_alert(self):
        self.ensure_one()
        alert = self.env['sa.quality.alert'].create({
            'check_id': self.id,
            'product_id': self.product_id.id,
            'product_tmpl_id': self.product_id.product_tmpl_id.id,
            'lot_id': self.lot_id.id,
            'user_id': self.user_id.id,
            'team_id': self.team_id.id,
            'company_id': self.company_id.id
        })
        return {
            'name': _('Quality Alert'),
            'type': 'ir.actions.act_window',
            'res_model': 'sa.quality.alert',
            'views': [(self.env.ref('quality.quality_alert_view_form').id, 'form')],
            'res_id': alert.id,
            'context': {'default_check_id': self.id},
        }

    @api.multi
    def action_see_alerts(self):
        self.ensure_one()
        if len(self.alert_ids) == 1:
            return {
                'name': _('Quality Alert'),
                'type': 'ir.actions.act_window',
                'res_model': 'sa.quality.alert',
                'views': [(self.env.ref('quality.quality_alert_view_form').id, 'form')],
                'res_id': self.alert_ids.ids[0],
                'context': {'default_check_id': self.id},
            }
        else:
            action = self.env.ref('quality.quality_alert_action_check').read()[0]
            action['domain'] = [('id', 'in', self.alert_ids.ids)]
            return action

    @api.multi
    def redirect_after_pass_fail(self):
        check = self[0]
        if check.picking_id:
            checks = self.picking_id.check_ids.filtered(lambda x: x.quality_state == 'none')
            if checks:
                action = self.env.ref('quality.quality_check_action_small').read()[0]
                action['res_id'] = checks.ids[0]
                return action
        return {'type': 'ir.actions.act_window_close'}


class QualityAlert(models.Model):
    _name = "sa.quality.alert"
    _description = "Quality Alert"
    _inherit = ['mail.thread']

    name = fields.Char('Name', default=lambda self: _('New'))
    description = fields.Text('Description')
    stage_id = fields.Many2one('sa.quality.alert.stage', 'Stage',
                               group_expand='_read_group_stage_ids',
                               default=lambda self: self.env['sa.quality.alert.stage'].search([], limit=1).id)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.user.company_id)
    reason_id = fields.Many2one('sa.quality.reason', 'Root Cause')
    tag_ids = fields.Many2many('sa.quality.tag', string="Tags")
    date_assign = fields.Datetime('Date Assigned')
    date_close = fields.Datetime('Date Closed')
    action_corrective = fields.Text('Corrective Action')
    action_preventive = fields.Text('Preventive Action')
    user_id = fields.Many2one('res.users', 'Responsible', default=lambda self: self.env.user)
    team_id = fields.Many2one(
        'sa.quality.alert.team', 'Team', required=True,
        default=lambda x: x.env['sa.quality.alert.team'].search([], limit=1))
    partner_id = fields.Many2one('res.partner', 'Vendor')
    check_id = fields.Many2one('sa.quality.check', 'Check')
    product_tmpl_id = fields.Many2one('product.template', 'Product', required=True)
    product_id = fields.Many2one(
        'product.product', 'Product Variant',
        domain="[('product_tmpl_id', '=', product_tmpl_id)]")
    lot_id = fields.Many2one(
        'stock.production.lot', 'Lot',
        domain="['|', ('product_id', '=', product_id), ('product_id.product_tmpl_id.id', '=', product_tmpl_id)]")
    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Low'),
        ('2', 'High'),
        ('3', 'Very High')], string='Priority',
        index=True)

    @api.model
    def create(self, vals):
        if 'name' not in vals or vals['name'] == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('sa.quality.alert') or _('New')
        return super(QualityAlert, self).create(vals)

    @api.onchange('product_tmpl_id')
    def onchange_product_tmpl_id(self):
        self.product_id = self.product_tmpl_id.product_variant_ids.ids and self.product_tmpl_id.product_variant_ids.ids[
            0]

    @api.multi
    def action_see_check(self):
        return {
            'name': _('Quality Check'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'sa.quality.check',
            'target': 'current',
            'res_id': self.check_id.id,
        }

    @api.model
    def _read_group_stage_ids(self, stages, domain, order):
        """ Read group customization in order to display all the stages of the ECO type
        in the Kanban view, even if there is no ECO in that stage
        """
        stage_ids = stages._search([], order=order, access_rights_uid=SUPERUSER_ID)
        return stages.browse(stage_ids)
