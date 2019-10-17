# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.osv import expression
from validators import ip_address, ValidationFailure
from odoo.exceptions import UserError
from odoo.tools import html2text, ustr
import requests as Requests

import urllib
import json

HEALTHZ_URL = 'api/v1/healthz'

DEFAULT_TIMEOUT = 2  ### 2秒 timeout


class EquipmentConnection(models.Model):
    _name = 'maintenance.equipment.connection'
    _description = 'Equipment Connection'

    active = fields.Boolean(default=True)
    name = fields.Char(string='Connection', required=True, default='Connection')
    ip = fields.Char(string='IP')
    tty = fields.Char(string='Serial TTY')

    equipment_id = fields.Many2one('maintenance.equipment', string='Equipment')

    port = fields.Integer(string='port', default=0)
    unitid = fields.Integer(string='Unit ID', help='Modbus need this ID for identification', default=0)
    protocol = fields.Selection([('modbustcp', 'ModbusTCP'), ('modbusrtu', 'ModbusRTU'), ('http', "HTTP"),
                                 ('rawtcp', 'TCP'), ('rawudp', 'UDP')], string='Protocol')

    @api.multi
    def button_check_healthz(self):
        for connection in self:
            if connection.protocol != 'http':
                continue
            try:
                url = u'http://{0}:{1}/{2}'.format(connection.ip, connection.port, HEALTHZ_URL)
                ret = Requests.get(url, headers={'Content-Type': 'application/json'}, timeout=DEFAULT_TIMEOUT)
                if ret.status_code == 204:
                    raise UserError(_("Connection Test Succeeded! Everything seems properly set up!"))
                else:
                    raise UserError(_("Connection Test Failed! Here is what we got instead: %d!") % ret.status_code)
            except Exception as e:
                raise UserError(_("Connection Test Failed! Here is what we got instead:\n %s") % ustr(e))

    @api.one
    @api.constrains('ip', 'port')
    def _constraint_ip(self):
        if not self.ip:
            return
        ret = ip_address.ipv4(self.ip)
        if not ret:
            # 返回一个ValidationFailure对象： https://validators.readthedocs.io/en/latest/
            raise ValidationError(_('is NOT valid IP Address!'))
        if self.port <= 0:
            raise ValidationError(_('Port must be greater than ZERO!'))

    @api.multi
    def name_get(self):
        def get_names(cat):
            if cat.protocol == 'modbustcp':
                return u"modbustcp://{0}:{1}/{2}".format(cat.ip, cat.port, cat.unitid)
            if cat.protocol == 'modbusrtu':
                return u"modbusrtu://{0}/{1}".format(cat.tty, cat.unitid)
            if cat.protocol == 'rawtcp':
                return u"tcp://{0}:{1}".format(cat.ip, cat.port)
            if cat.protocol == 'modbustcp':
                return u"udp://{0}:{1}".format(cat.ip, cat.port)
            if cat.protocol == 'http':
                return u"http://{0}:{1}".format(cat.ip, cat.port)

        return [(cat.id, get_names(cat)) for cat in self]


class MaintenanceEquipmentCategory(models.Model):
    _inherit = 'maintenance.equipment.category'

    name = fields.Char('Category Name', required=True)

    technical_name = fields.Char('Technical name', required=True)


class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'
    _parent_name = "parent_id"
    _parent_store = True
    _order = 'parent_left'
    _parent_order = 'name'

    parent_id = fields.Many2one('maintenance.equipment', 'Parent Equipment', index=True, ondelete='cascade')
    child_ids = fields.One2many('maintenance.equipment', 'parent_id', 'Child Equipments')

    external_url = fields.Text('External URL', compute='_compute_external_url')

    healthz_url = fields.Char('Healthz Check URL')

    parent_left = fields.Integer('Left Parent', index=1)
    parent_right = fields.Integer('Right Parent', index=1)
    #
    child_equipments_count = fields.Integer(compute='_compute_child_equipments_count')

    connections_count = fields.Integer(compute='_compute_connections_count')

    category_name = fields.Char(related='category_id.name')

    connection_ids = fields.One2many('maintenance.equipment.connection', 'equipment_id', 'Connection Information')

    image_medium = fields.Binary("Medium-sized image", attachment=True)

    parent_id_domain = fields.Char(
        compute="_compute_parent_id_domain",
        readonly=True,
        default=json.dumps([]),
        store=False,
    )

    @api.multi
    @api.depends('category_id')
    def _compute_parent_id_domain(self):
        for rec in self:
            rec.parent_id_domain = json.dumps([])
            if rec.category_id.id == self.env.ref('sa_base.equipment_Gun').id:
                child_ids = self.env['maintenance.equipment'].sudo().search(
                    [('category_id', '=', self.env.ref('sa_base.equipment_screw_controller').id)])
                rec.parent_id_domain = json.dumps([('id', 'in', child_ids.ids)])
            elif rec.category_id.id == self.env.ref('sa_base.equipment_screw_controller').id:
                child_ids = self.env['maintenance.equipment'].sudo().search(
                    [('category_id', '=', self.env.ref('sa_base.equipment_MasterPC').id)])
                rec.parent_id_domain = json.dumps([('id', 'in', child_ids.ids)])
            else:
                rec.parent_id_domain = json.dumps([])

    @api.multi
    def button_check_healthz(self):
        for e in self:
            url = e.healthz_url
            if not url:
                continue
            try:
                ret = Requests.get(url, headers={'Content-Type': 'application/json'}, timeout=DEFAULT_TIMEOUT)
                if ret.status_code == 204:
                    raise UserError(_("Connection Test Succeeded! Everything seems properly set up!"))
                else:
                    raise UserError(_("Connection Test Failed! Here is what we got instead: %d!") % ret.status_code)
            except Exception as e:
                raise UserError(_("Connection Test Failed! Here is what we got instead:\n %s") % ustr(e))

    @api.multi
    def _compute_external_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for rec in self:
            rec.external_url = urllib.quote(
                u'{0}/web#id={1}&view_type=form&model=maintenance.equipment'.format(base_url, rec.id))

    @api.multi
    def _compute_child_equipments_count(self):
        for equipment in self:
            equipment.child_equipments_count = len(equipment.child_ids)

    @api.multi
    def _compute_connections_count(self):
        for equipment in self:
            equipment.connections_count = len(equipment.connection_ids)

    # @api.multi
    # @api.depends('category_id')
    # def _compute_category_name(self):
    #     for equipment in self:
    #         equipment.category_name = equipment.category_id.name or ''

    @api.constrains('parent_id')
    def _check_category_recursion(self):
        if not self._check_recursion():
            raise ValidationError(_('Error ! You cannot create recursive Equipments.'))
        return True

    @api.multi
    def name_get(self):
        def get_names(cat):
            """ Return the list [cat.name, cat.parent_id.name, ...] """
            res = []
            while cat:
                if cat.name and cat.serial_no:
                    res.append(u"[{0}]{1}".format(cat.serial_no, cat.name))
                if cat.name and not cat.serial_no:
                    res.append(cat.name)
                cat = cat.parent_id
            return res

        return [(cat.id, " / ".join(reversed(get_names(cat)))) for cat in self]

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        if not args:
            args = []
        if name:
            # Be sure name_search is symetric to name_get
            equipment_names = name.split(' / ')
            parents = list(equipment_names)
            child = parents.pop()
            domain = ['|', ('name', operator, child), ('serial_no', operator, child)]
            if parents:
                names_ids = super(MaintenanceEquipment, self).name_search(' / '.join(parents), args=args,
                                                                          operator='ilike', limit=limit)
                equipment_ids = [name_id[0] for name_id in names_ids]
                if operator in expression.NEGATIVE_TERM_OPERATORS:
                    equipments = self.search([('id', 'not in', equipment_ids)])
                    domain = expression.OR([[('parent_id', 'in', equipments.ids)], domain])
                else:
                    domain = expression.AND([[('parent_id', 'in', equipment_ids)], domain])
                for i in range(1, len(equipment_names)):
                    domain = [[('name', operator, ' / '.join(equipment_names[-1 - i:]))], domain]
                    if operator in expression.NEGATIVE_TERM_OPERATORS:
                        domain = expression.AND(domain)
                    else:
                        domain = expression.OR(domain)
            equipments = self.search(expression.AND([domain, args]), limit=limit)
        else:
            equipments = self.search(args, limit=limit)
        return equipments.name_get()
