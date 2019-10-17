# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class MailMail(models.Model):
    """ Model holding RFC2822 email messages to send. This model also provides
        facilities to queue and send new email messages.  """
    _inherit = 'mail.mail'

    @api.model
    def send_async_by_id(self, **kwargs):
        mail_id = kwargs.get('mail_id')
        mail = self.env['mail.mail'].browse(mail_id)
        return mail.send()
