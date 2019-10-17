from odoo import api, fields, models,_

class MrpWorkcenterGroup(models.Model):
    _name = 'mrp.workcenter.group'
    _description = 'Work Center Group'
    _order = "id"

    sequence = fields.Integer('sequence', default=1)
    code = fields.Char('Reference', copy=False, required=True)
    name = fields.Char('Work Center Group')
    sa_workcenter_ids = fields.Many2many('mrp.workcenter', 'mrp_workcenter_rel', 'group_id', 'workcenter_id',
                                     string="Workcenters", copy=False)

    active = fields.Boolean(
        'Active', default=True,
        help="If the active field is set to False, it will allow you to hide the bills of material without removing it.")

    @api.multi
    def name_get(self):
        res = []
        for point in self:
            res.append((point.id, _('[%s] %s') % (point.code, point.name)))
        return res