# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

from dateutil.relativedelta import relativedelta


class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'

    @api.multi
    def _compute_maintenance_request(self):
        for equipment in self:
            maintenance_requests = equipment.maintenance_ids.filtered(
                lambda x: x.maintenance_type == 'corrective' and x.stage_id.done)
            mttr_days = 0
            for maintenance in maintenance_requests:
                if maintenance.stage_id.done and maintenance.close_date:
                    mttr_days += (fields.Datetime.from_string(maintenance.close_date) - fields.Datetime.from_string(
                        maintenance.request_date)).total_seconds()
            equipment.mttr = len(maintenance_requests) and (mttr_days / len(maintenance_requests)) or 0

            maintenance = maintenance_requests.sorted(lambda x: x.request_date)
            if len(maintenance) > 1:
                time_delta = fields.Datetime.from_string(maintenance[-1].request_date) - fields.Datetime.from_string(
                    maintenance[0].request_date)
                equipment.mtbf = time_delta.total_seconds() / (len(maintenance_requests) - 1)
            else:
                equipment.mtbf = 0
            equipment.latest_failure_date = maintenance and maintenance[-1].request_date or False
            if equipment.mtbf:
                equipment.estimated_next_failure = fields.Datetime.from_string(
                    equipment.latest_failure_date) + relativedelta(seconds=equipment.mtbf)
            else:
                equipment.estimated_next_failure = False
