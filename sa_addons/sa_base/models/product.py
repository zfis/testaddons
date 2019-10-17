# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    sa_type = fields.Selection([('screw', 'Screw'), ('vehicle', 'Vehicle')], default='vehicle', string='产品类型')


class ProductProduct(models.Model):
    _inherit = 'product.product'

    sa_type = fields.Selection(related='product_tmpl_id.sa_type', store=True)
    qcp_count = fields.Integer(string='Quality Point Count', compute='_compute_product_quality_point_count')
    active_bom_id = fields.Many2one('mrp.bom', string='Current Actived BOM', compute='_compute_active_bom_id')

    active_bom_line_ids = fields.One2many('mrp.bom.line', related='active_bom_id.bom_line_ids')
    description = fields.Text(string='Product Description')

    def _compute_product_quality_point_count(self):
        for product in self:
            product.qcp_count = self.env['sa.quality.point'].search_count([('product_id', '=', product.id)])

    @api.multi
    def copy(self, default=None):
        raise UserError(_('Product can not be copy by User!'))

    @api.multi
    def write(self, vals):
        if 'product_tmpl_id' in vals:
            for product in self:
                if product.product_tmpl_id.id == vals['product_tmpl_id']:
                    vals.pop('product_tmpl_id')
        super(ProductProduct, self).write(vals)
        return True

    @api.multi
    def toggle_active(self):
        ret = super(ProductProduct, self).toggle_active()
        if not ret:
            return ret
        bom_ids = self.mapped('bom_ids')
        if bom_ids:
            bom_ids.toggle_active()

    @api.multi
    @api.depends('bom_ids')
    def _compute_active_bom_id(self):
        for product in self:
            product.active_bom_id = product.bom_ids.filtered("active")[0] if product.bom_ids else False

    ###此方法打开相应的页面
    @api.multi
    def action_sa_view_bom(self):
        action = self.env.ref('sa_base.sa_product_open_bom').read()[0]
        template_ids = self.mapped('product_tmpl_id').ids
        # bom specific to this variant or global to template
        action['context'] = {
            'default_product_tmpl_id': template_ids[0],
            'default_product_id': self.ids[0],
        }
        action['domain'] = ['|', ('product_id', 'in', [self.ids]), '&', ('product_id', '=', False),
                            ('product_tmpl_id', 'in', template_ids)]
        return action

    @api.multi
    def button_create_qcp(self):
        self.ensure_one()
        # 首先删除所有的qcp
        self.env['sa.quality.point'].search([('product_id', '=', self.id)]).sudo().unlink()
        active_bom_line_ids = self.active_bom_line_ids
        # point_type_ids = self.env['sa.quality.point.type'].search([])
        for line in active_bom_line_ids:
            vals = {
                'product_id': self.id,
                'bom_line_id': line.id,
                'product_tmpl_id': self.product_tmpl_id.id,
                'operation_id': line.operation_id.id,
                'picking_type_id':
                    self.env['stock.picking.type'].search_read(domain=[('code', '=', 'mrp_operation')], fields=['id'],
                                                               limit=1)[0]['id'],
                'workcenter_id': line.operation_id.workcenter_id.id,
                'times': line.product_qty,
                'test_type': 'measure',
            }
            self.env['sa.quality.point'].create(vals)
