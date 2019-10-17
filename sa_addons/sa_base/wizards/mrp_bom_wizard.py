# -*- coding: utf-8 -*-


from odoo import api, models, fields

import logging

_logger = logging.getLogger(__name__)


class MrpRoutingWorkCenterForm(models.TransientModel):
    _name = 'mrp.routing.wc.form'

    routing_id = fields.Many2one(
        'mrp.routing', 'Parent Routing',
        index=True, ondelete='cascade', required=True,
        help="The routing contains all the Work Centers used and for how long. This will create work orders afterwards"
             "which alters the execution of the manufacturing order. ")

    operation_ids = fields.Many2many('mrp.routing.workcenter', 'wc_form_operation_rel', 'routing_wc_id', 'operation_id',
                                     string="Operations", copy=False)

    @api.multi
    def submit(self):
        self.ensure_one()
        _logger.info("submit")

    @api.multi
    def create(self, vals):
        context = self.env.context
        _logger.info(context)
