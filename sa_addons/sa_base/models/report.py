# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from reportlab.graphics.barcode import createBarcodeDrawing
import qrcode


class Report(models.Model):
    _inherit = "report"

    def barcode(self, barcode_type, value, width=600, height=100, humanreadable=0):
        if barcode_type == 'UPCA' and len(value) in (11, 12, 13):
            barcode_type = 'EAN13'
            if len(value) in (11, 12):
                value = '0%s' % value
        try:
            if barcode_type != 'QR':
                width, height, humanreadable = int(width), int(height), bool(int(humanreadable))
                barcode = createBarcodeDrawing(
                    barcode_type, value=value, format='png', width=width, height=height,
                    humanReadable=humanreadable
                )
                return barcode.asString('png')
            else:
                qr = qrcode.QRCode(
                    version=2,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=10,
                    border=4,
                )
                qr.add_data(value)
                qr.make(fit=True)

                img = qr.make_image(fill_color="black", back_color="white")
                return img
        except (ValueError, AttributeError):
            raise ValueError("Cannot convert into barcode.")
