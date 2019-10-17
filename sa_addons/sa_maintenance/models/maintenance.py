# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import odoo.addons.decimal_precision as dp
from odoo.exceptions import UserError
from urlparse import urljoin
import uuid

import requests as Requests
import json
from requests import ConnectionError, RequestException, exceptions
import logging

from datetime import date, datetime, timedelta

from dateutil.relativedelta import relativedelta

PUSH_MAINTENANCE_REQ_URL = '/rush/v1/maintenance'

logger = logging.getLogger(__name__)


class MaintenanceCheckPointCategory(models.Model):
    _name = 'maintenance.cp.category'

    name = fields.Char('Check Point Name')
    code = fields.Char('Check Point Code')

    test_type = fields.Selection([
        ('passfail', 'Pass - Fail'),
        ('measure', 'Measure')], string="Test Type",
        default='passfail', required=True)


class MaintenanceCheckPoint(models.Model):
    _name = 'maintenance.cp'
    _description = 'Equipment Checklist for each maintenance request '

    name = fields.Char('CP Name')
    equipment_id = fields.Many2one('maintenance.equipment', string='Equipment', index=True)

    category_id = fields.Many2one('maintenance.cp.category')
    description = fields.Char('Maintenance Check Point Description')

    test_type = fields.Selection(related='category_id.test_type', readonly=True)

    norm = fields.Float('Normal', digits=dp.get_precision('Maintenance Tests'))  # TDE RENAME ?
    tolerance_min = fields.Float('Min Tolerance', digits=dp.get_precision('Maintenance Tests'))
    tolerance_max = fields.Float('Max Tolerance', digits=dp.get_precision('Maintenance Tests'))

    @api.onchange('norm')
    def onchange_norm(self):
        if self.tolerance_max == 0.0:
            self.tolerance_max = self.norm


class MaintenanceCheckPointAction(models.Model):
    _name = 'maintenance.cp.action'

    request_id = fields.Many2one('maintenance.request', string='Request', index=True)

    test_type = fields.Selection([
        ('passfail', 'Pass - Fail'),
        ('measure', 'Measure')], string="Test Type",
        default='passfail', required=True)

    category_id = fields.Many2one('maintenance.cp.category')

    description = fields.Char('Maintenance Check Point Description')

    norm = fields.Float('Normal', digits=dp.get_precision('Maintenance Tests'))  # TDE RENAME ?
    tolerance_min = fields.Float('Min Tolerance', digits=dp.get_precision('Maintenance Tests'))
    tolerance_max = fields.Float('Max Tolerance', digits=dp.get_precision('Maintenance Tests'))

    measure = fields.Float(digits=dp.get_precision('Maintenance Tests'))

    measure_success = fields.Selection([
        ('none', 'No measure'),
        ('pass', 'Pass'),
        ('fail', 'Fail')], string="Measure Success", compute="_compute_measure_success", store=True)

    @api.one
    @api.depends('measure')
    def _compute_measure_success(self):
        if self.test_type == 'passfail':
            self.measure_success = 'none'
        else:
            if self.measure < self.tolerance_min or self.measure > self.tolerance_max:
                self.measure_success = 'fail'
            else:
                self.measure_success = 'pass'

    @api.model
    def bulk_create(self, all_vals):

        all_updates = []
        for vals in all_vals:
            tocreate = {
                parent_model: {'id': vals.pop(parent_field, None)}
                for parent_model, parent_field in self._inherits.iteritems()
            }

            # list of column assignments defined as tuples like:
            #   (column_name, format_string, column_value)
            #   (column_name, sql_formula)
            # Those tuples will be used by the string formatting for the INSERT
            # statement below.
            updates = [
                ('id', "%s", "nextval('%s')" % self._sequence),
            ]

            upd_todo = []
            unknown_fields = []
            protected_fields = []
            for name, val in vals.items():
                field = self._fields.get(name)
                if not field:
                    unknown_fields.append(name)
                    del vals[name]
                elif field.inherited:
                    tocreate[field.related_field.model_name][name] = val
                    del vals[name]
                elif not field.store:
                    del vals[name]
                elif field.inverse:
                    protected_fields.append(field)

            # set boolean fields to False by default (to make search more powerful)
            for name, field in self._fields.iteritems():
                if field.type == 'boolean' and field.store and name not in vals:
                    vals[name] = False

            # determine SQL values
            for name, val in vals.iteritems():
                field = self._fields[name]
                if field.store and field.column_type:
                    updates.append((name, field.column_format, field.convert_to_column(val, self)))
                else:
                    upd_todo.append(name)

                if hasattr(field, 'selection') and val:
                    self._check_selection_field_value(name, val)

            if self._log_access:
                updates.append(('create_uid', '%s', self._uid))
                updates.append(('write_uid', '%s', self._uid))
                # updates.append(('create_date', '%s', '(now() at time zone \'UTC\')'))
                # updates.append(('write_date', '%s', '(now() at time zone \'UTC\')'))
            all_updates.append(updates)
        cr = self._cr
        t = [tuple(u[2] for u in update if len(u) > 2) for update in all_updates]
        query = """INSERT INTO "%s" (%s) VALUES %s RETURNING id""" % (
            self._table,
            ', '.join('"%s"' % u[0] for u in all_updates[0]),
            ','.join("(nextval('%s')," % self._sequence + str(_t[1:])[1:] for _t in t),
        )

        cr.execute(query)

        # from now on, self is the new record
        ids_news = cr.fetchall()
        return [ids[0] for ids in ids_news]


class MaintenanceRequest(models.Model):
    _inherit = 'maintenance.request'

    def _default_access_token(self):
        return uuid.uuid4().hex

    access_token = fields.Char('Invitation Token', default=_default_access_token)

    check_point_action_ids = fields.One2many('maintenance.cp.action', 'request_id')

    maintenance_type = fields.Selection(selection_add=[("calibration", "Equipment Calibration")])

    action_times = fields.Integer('Times to Actions Maintenance')

    close_date = fields.Datetime('Close Date', help="Date the maintenance was finished. ")

    request_date = fields.Datetime('Request Date', track_visibility='onchange', default=fields.Datetime.now,
                                   help="Date requested for the maintenance to happen")

    @api.multi
    def write(self, vals):
        res = super(MaintenanceRequest, self).write(vals)
        if self.stage_id.done and 'stage_id' in vals:
            self.write({'close_date': fields.Datetime.now()})
        return res

    @api.multi
    def assign_ticket_to_self(self):
        for r in self:
            r.technician_user_id = self.env.uid

    @api.multi
    def post_maintenance_req(self):
        self.ensure_one()
        ret = self.equipment_id
        if not ret:
            return
        if ret.category_name == 'Gun':
            master = ret._get_parent_masterpc()[0]
            if not master:
                return
            connections = master.connection_ids.filtered(
                lambda r: r.protocol == 'http') if master.connection_ids else None
            if not connections:
                return
            url = ['http://{0}:{1}{2}'.format(connect.ip, connect.port, PUSH_MAINTENANCE_REQ_URL) for connect in
                   connections][0]
            val = {
                "type": ret.category_name,
                "name": ret.display_name,
                "expire_time": fields.Date.today()
            }
            try:
                # logger.debug("try to push maintenance request to masterpc:{0}".format(url))
                Requests.post(urljoin(url, PUSH_MAINTENANCE_REQ_URL), data=json.dumps(val),
                              headers={'Content-Type': 'application/json'}, timeout=3)
            except ConnectionError as e:
                logger.debug(u'发送维护请求失败, 错误原因:{0}'.format(e.message))
            except RequestException as e:
                logger.debug(u'发送维护请求失败, 错误原因:{0}'.format(e.message))
            finally:
                return

    @api.model
    def create(self, vals):
        ret = super(MaintenanceRequest, self).create(vals)
        if 'equipment_id' in vals and vals.get('maintenance_type', 'corrective') == 'preventive':
            equipment_id = vals.get('equipment_id')
            check_point_ids = self.env['maintenance.cp'].sudo().search([('equipment_id', '=', equipment_id)])
            actions = []
            for check_point in check_point_ids:
                actions.append({
                    'point_id': check_point.id,
                    'category_id': check_point.category_id.id,
                    'request_id': ret.id,
                    'description': check_point.description if check_point.description else "",
                    'test_type': check_point.category_id.test_type,
                    'norm': check_point.norm,
                    'tolerance_min': check_point.tolerance_min,
                    'tolerance_max': check_point.tolerance_max,
                })
            if len(actions) > 0:
                self.env['maintenance.cp.action'].sudo().bulk_create(actions)

            ret.post_maintenance_req()  # 主动发送维护请求到HMI
            # template_id = self.env.ref('sa_maintenance.new_maintenance_request_email_template', False)
            # if template_id:
            #     rendering_context = dict(self._context)
            #     rendering_context.update({
            #         'dbname': self._cr.dbname,
            #         'base_url': self.env['ir.config_parameter'].sudo().get_param('web.base.url',
            #                                                                      default='http://localhost:8069')
            #     })
            #     template_id = template_id.with_context(rendering_context)
            #     mail_id = template_id.send_mail(ret.id)  # 先不要发送,之后调用send方法发送邮件
            #     current_mail = self.env['mail.mail'].browse(mail_id)
            #     # self.env["celery.task"].call_task("mail.mail", "send_async_by_id", mail_id=mail_id)
            #     current_mail.send()  # 发送邮件
        return ret


class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'

    check_point_ids = fields.One2many('maintenance.cp', 'equipment_id')

    maintenance_lead_time = fields.Integer('Lead Days', default=5)

    times_margin = fields.Integer('Margin Times between each maintenance', default=1000)

    next_calibration_action_times = fields.Integer(compute='_compute_next_action_times',
                                                   string='Times of the next calibration maintenance', store=True)

    next_action_times = fields.Integer(compute='_compute_next_action_times',
                                       string='Times of the next preventive maintenance', store=True)

    times = fields.Integer('Times between each preventive maintenance')

    calibration_times = fields.Integer('Times between each calibration maintenance')

    calibration_period = fields.Integer('Days between each calibration maintenance')

    next_calibration_action_date = fields.Date(compute='_compute_next_calibration_maintenance',
                                               string='Date of the next calibration maintenance', store=True)

    effective_date = fields.Date('Effective Date', default=fields.Date.context_today, required=True,
                                 help="Date at which the equipment became effective. This date will be used to compute the Mean Time Between Failure.")

    mttf = fields.Integer(compute='_compute_maintenance_request', string='MTTF',
                          help='Mean Time TO Failure, computed based on done corrective maintenances.')

    @api.depends('times', 'calibration_times', 'maintenance_ids.action_times')
    def _compute_next_action_times(self):
        for equipment in self.filtered(lambda x: x.times > 0 or x.calibration_times > 0):
            need_calib_calc = False
            need_pre_calc = False
            if equipment.calibration_times > 0:
                need_calib_calc = True
            if equipment.times > 0:
                need_pre_calc = True
            next_maintenance_todo = self.env['maintenance.request'].search([
                ('equipment_id', '=', equipment.id),
                ('maintenance_type', 'in', ['preventive']),
                ('stage_id.done', '!=', True),
                ('action_times', '!=', False)], order="action_times asc", limit=1)
            last_maintenance_done = self.env['maintenance.request'].search([
                ('equipment_id', '=', equipment.id),
                ('maintenance_type', 'in', ['preventive']),
                ('stage_id.done', '=', True),
                ('action_times', '!=', False)], order="action_times desc", limit=1)
            if next_maintenance_todo and last_maintenance_done:
                equipment.next_calibration_action_times = next_maintenance_todo.action_times + equipment.calibration_times
                equipment.next_action_times = next_maintenance_todo.action_times + equipment.times  # 设置一个预先数值
                times_gap = next_maintenance_todo.action_times - last_maintenance_done.action_times
                if times_gap > 0:
                    if need_calib_calc:
                        if times_gap > 2 * equipment.calibration_times or times_gap < equipment.calibration_times:
                            equipment.next_calibration_action_times = last_maintenance_done.action_times + equipment.calibration_times
                    if need_pre_calc:
                        if times_gap > 2 * equipment.times or times_gap < equipment.times:
                            equipment.next_action_times = last_maintenance_done.action_times + equipment.times
            elif next_maintenance_todo:
                if need_calib_calc:
                    equipment.next_calibration_action_times = next_maintenance_todo.action_times + equipment.calibration_times
                if need_pre_calc:
                    equipment.next_action_times = next_maintenance_todo.action_times + equipment.times
            elif last_maintenance_done:
                if need_calib_calc:
                    equipment.next_calibration_action_times = last_maintenance_done.action_times + equipment.calibration_times
                if need_pre_calc:
                    equipment.next_action_times = last_maintenance_done.action_times + equipment.times
            else:
                if need_calib_calc:
                    equipment.next_calibration_action_times = equipment.calibration_times
                if need_pre_calc:
                    equipment.next_action_times = equipment.times

    @api.depends('calibration_period', 'maintenance_ids.request_date', 'maintenance_ids.close_date')
    def _compute_next_calibration_maintenance(self):
        date_now = fields.Date.context_today(self)
        for equipment in self.filtered(lambda x: x.calibration_period > 0):
            next_maintenance_todo = self.env['maintenance.request'].search([
                ('equipment_id', '=', equipment.id),
                ('maintenance_type', 'in', ['preventive', 'calibration']),
                ('stage_id.done', '!=', True),
                ('close_date', '=', False)], order="request_date asc", limit=1)
            last_maintenance_done = self.env['maintenance.request'].search([
                ('equipment_id', '=', equipment.id),
                ('maintenance_type', 'in', ['preventive', 'calibration']),
                ('stage_id.done', '=', True),
                ('close_date', '!=', False)], order="close_date desc", limit=1)
            if next_maintenance_todo and last_maintenance_done:
                next_date = next_maintenance_todo.request_date
                date_gap = fields.Date.from_string(next_maintenance_todo.request_date) - fields.Date.from_string(
                    last_maintenance_done.close_date)
                # If the gap between the last_maintenance_done and the next_maintenance_todo one is bigger than 2 times the period and next request is in the future
                # We use 2 times the period to avoid creation too closed request from a manually one created
                if date_gap > timedelta(0) and date_gap > timedelta(
                        days=equipment.calibration_period) * 2 and fields.Date.from_string(
                    next_maintenance_todo.request_date) > fields.Date.from_string(date_now):
                    # If the new date still in the past, we set it for today
                    if fields.Date.from_string(last_maintenance_done.close_date) + timedelta(
                            days=equipment.calibration_period) < fields.Date.from_string(date_now):
                        next_date = date_now
                    else:
                        next_date = fields.Date.to_string(
                            fields.Date.from_string(last_maintenance_done.close_date) + timedelta(
                                days=equipment.calibration_period))
            elif next_maintenance_todo:
                next_date = next_maintenance_todo.request_date
                date_gap = fields.Date.from_string(next_maintenance_todo.request_date) - fields.Date.from_string(
                    date_now)
                # If next maintenance to do is in the future, and in more than 2 times the period, we insert an new request
                # We use 2 times the period to avoid creation too closed request from a manually one created
                if date_gap > timedelta(0) and date_gap > timedelta(days=equipment.calibration_period) * 2:
                    next_date = fields.Date.to_string(
                        fields.Date.from_string(date_now) + timedelta(days=equipment.calibration_period))
            elif last_maintenance_done:
                next_date = fields.Date.from_string(last_maintenance_done.close_date) + timedelta(
                    days=equipment.calibration_period)
                # If when we add the period to the last maintenance done and we still in past, we plan it for today
                if next_date < fields.Date.from_string(date_now):
                    next_date = date_now
            else:
                next_date = fields.Date.to_string(
                    fields.Date.from_string(date_now) + timedelta(days=equipment.calibration_period))

            equipment.next_calibration_action_date = next_date

    def _create_new_calibration_request(self, date):
        self.ensure_one()
        self.env['maintenance.request'].create({
            'name': _('Calibration Maintenance - %s') % self.name,
            'request_date': date,
            'schedule_date': date,
            'category_id': self.category_id.id,
            'equipment_id': self.id,
            'maintenance_type': 'calibration',
            'owner_user_id': self.owner_user_id.id,
            'technician_user_id': self.technician_user_id.id,
            'maintenance_team_id': self.maintenance_team_id.id,
            'duration': self.maintenance_duration,
        })

    @api.model
    def _cron_generate_requests(self):
        """
            Generates maintenance request on the next_action_date or today if none exists
        """
        for equipment in self.search(['|', ('calibration_period', '>', 0), ('period', '>', 0)]):
            if equipment.period:
                next_requests = self.env['maintenance.request'].search([('stage_id.done', '=', False),
                                                                        ('equipment_id', '=', equipment.id),
                                                                        ('maintenance_type', '=', 'preventive'),
                                                                        ('request_date', '=',
                                                                         equipment.next_action_date)])
                need_action = (fields.Date.from_string(equipment.next_action_date) - fields.Date.from_string(
                    fields.Date.context_today(self))).days <= equipment.maintenance_lead_time
                if not next_requests and need_action:
                    equipment._create_new_request(equipment.next_action_date)
                    return  # 创建了维护请求就无需创建标定请求
            if equipment.calibration_period:
                next_requests = self.env['maintenance.request'].search([('stage_id.done', '=', False),
                                                                        ('equipment_id', '=', equipment.id),
                                                                        ('maintenance_type', 'in',
                                                                         ['calibration', 'preventive']),
                                                                        ('request_date', 'in',
                                                                         [equipment.next_calibration_action_date,
                                                                          equipment.next_action_date])])
                if not next_requests:
                    equipment._create_new_calibration_request(equipment.next_calibration_action_date)

    @api.one
    def _get_parent_masterpc(self):
        cat = self
        while cat:
            if cat.category_id.id == self.env.ref('sa_base.equipment_MasterPC').id:
                return cat
            cat = cat.parent_id
        return None

    @api.multi
    def _compute_maintenance_request(self):
        for equipment in self:
            maintenance_requests = equipment.maintenance_ids.filtered(
                lambda x: x.maintenance_type == 'corrective' and x.stage_id.done)
            mttr_days = 0
            for maintenance in maintenance_requests:
                if maintenance.stage_id.done and maintenance.close_date:
                    mttr_days += (fields.Date.from_string(maintenance.close_date) - fields.Date.from_string(
                        maintenance.request_date)).days
            equipment.mttr = len(maintenance_requests) and (mttr_days / len(maintenance_requests)) or 0

            maintenance = maintenance_requests.sorted(lambda x: x.request_date)
            if len(maintenance) > 1:
                equipment.mtbf = (fields.Date.from_string(maintenance[-1].request_date) - fields.Date.from_string(
                    maintenance[0].request_date)).days / (len(maintenance) - 1)
            else:
                equipment.mtbf = 0
            equipment.latest_failure_date = maintenance and maintenance[-1].request_date or False
            if equipment.mtbf:
                equipment.estimated_next_failure = fields.Datetime.from_string(
                    equipment.latest_failure_date) + relativedelta(days=equipment.mtbf)
            else:
                equipment.estimated_next_failure = False
            # equipment.mttf = equipment.mtbf - equipment.mttr
