from odoo import models, fields

class LoanAsset(models.Model):
    _name = 'loan.asset'
    _description = 'Tài Sản Cầm'

    name = fields.Char(string='Tên tài sản', required=True)
    asset_type = fields.Selection([
        ('gold', 'Vàng'),
        ('vehicle', 'Xe cộ'),
        ('electronics', 'Điện tử'),
        ('other', 'Khác')
    ], string='Loại tài sản', required=True)
    description = fields.Text(string='Mô tả')
    estimated_value = fields.Float(string='Giá trị ước tính')
    loan_id = fields.Many2one('loan.contract', string='Khoản vay liên quan')
    customer_id = fields.Many2one('res.partner', string='Khách hàng')
