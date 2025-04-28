
# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re

# Khai báo trường khách hàng


class loan(models.Model):
    _inherit = 'res.partner'
    _description = 'loan.customer'

    # Thông tin CCCD
    cmnd = fields.Char(string='CMND/CCCD')
    cmnd_issue_date = fields.Date(string='Ngày cấp CCCD')
    cmnd_issue_place = fields.Char(string='Nơi cấp CCCD')

    # Thông tin ngân hàng
    bank_account = fields.Char(string='Số tài khoản ngân hàng')
    bank_name = fields.Char(string='Tên ngân hàng')
    bank_branch = fields.Char(string='Chi nhánh')

# Định dạng số điện thoại

    @api.constrains('phone')
    def _check_phone_format(self):
        """Validate phone number format"""
        for record in self:
            if record.phone:
                # Kiểm tra chỉ chứa số
                if not re.match(r'^\d+$', record.phone):
                    raise ValidationError(
                        _("Số điện thoại chỉ được chứa chữ số (0-9)!"))
                # Kiểm tra độ dài tối thiểu
                if len(record.phone) < 10:
                    raise ValidationError(
                        _("Số điện thoại phải có ít nhất 10 chữ số!"))
                # Kiểm tra số VN (tuỳ chọn)
                if not record.phone.startswith('0'):
                    raise ValidationError(
                        _("Số điện thoại Việt Nam phải bắt đầu bằng 0!"))

# Không cho trùng số điện thoại khi tạo liên hệ mới
    @api.constrains('phone')
    def _check_phone_unique(self):
        for record in self:
            if record.phone:
                # Tìm liên hệ khác có cùng số điện thoại
                existing_partner = self.env['res.partner'].search([
                    ('phone', '=', record.phone),
                    ('id', '!=', record.id)  # Không tính chính mình khi update
                ], limit=1)

                if existing_partner:
                    raise ValidationError(
                        _("Số điện thoại này đã tồn tại cho khách hàng khác (%s)!") % (
                            existing_partner.name)
                    )
                    
# Bắt buộc nhập sđt khi tạo liên hệ
    @api.constrains('phone')
    def _check_phone_not_empty(self):
        for record in self:
            if not record.phone:
                raise ValidationError(_("Số điện thoại là bắt buộc. Vui lòng nhập số điện thoại!"))