# -*- coding: utf-8 -*-

from odoo import models, fields, exceptions, _


class MinioSettings(models.TransientModel):
    _name = 'minio.config.settings'
    _inherit = 'res.config.settings'

    minio_url = fields.Char('Minio URL', default='http://127.0.0.1:9000')
    minio_bucket = fields.Char(string='Minio bucket name', help="i.e. 'cunrong'")
    minio_access_key = fields.Char(string='Minio access key')
    minio_secret_key = fields.Char(string='Minio secret key')

    def get_default_all(self, fields):
        minio_url = self.env["ir.config_parameter"].get_param("minio.url", default='http://127.0.0.1:9000')
        minio_bucket = self.env["ir.config_parameter"].get_param("minio.bucket", default='cunrong')
        minio_access_key = self.env["ir.config_parameter"].get_param("minio.access_key", default='cunrong')
        minio_secret_key = self.env["ir.config_parameter"].get_param("minio.secret_key", default='cunrong123')

        return dict(
            minio_url=minio_url,
            minio_bucket=minio_bucket,
            minio_access_key=minio_access_key,
            minio_secret_key=minio_secret_key,
        )

    # minio_url
    def set_minio_url(self):
        self.env['ir.config_parameter'].set_param("minio.url",
                                                  self.minio_url or 'http://127.0.0.1:9000',
                                                  groups=['base.group_system'])

    # s3_bucket
    def set_minio_bucket(self):
        self.env['ir.config_parameter'].set_param("minio.bucket",
                                                  self.minio_bucket or '',
                                                  groups=['base.group_system'])

    # s3_access_key
    def set_minio_access_key(self):
        self.env['ir.config_parameter'].set_param("minio.access_key",
                                                  self.minio_access_key or '',
                                                  groups=['base.group_system'])

    # s3_secret_key
    def set_minio_secret_key(self):
        self.env['ir.config_parameter'].set_param("minio.secret_key",
                                                  self.minio_secret_key or '',
                                                  groups=['base.group_system'])

    def read_weave(self):
        pass
