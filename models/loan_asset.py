from odoo import models, fields

class LoanAsset(models.Model):
    _name = 'loan.asset'
    _description = 'Tài sản thế chấp'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Tên tài sản', required=True ,tracking=True)
    contract_id = fields.Many2one('loan.contract', string='Hợp đồng vay', ondelete='cascade')
    asset_type = fields.Selection([
        ('gold', 'Vàng'),
        ('vehicle', 'Xe'),
        ('real_estate', 'Bất động sản'),
        ('other', 'Khác')
    ], string='Loại tài sản', required=True)
    value = fields.Monetary(string='Giá trị định giá', currency_field='currency_id',tracking=True)
    currency_id = fields.Many2one('res.currency', string='Đơn vị tiền tệ', required=True, default=lambda self: self.env.company.currency_id)
    description = fields.Text(string='Mô tả chi tiết',tracking=True)
    image = fields.Image(string='Ảnh tài sản', max_width=512, max_height=512)
    customer_id = fields.Many2one(
        'res.partner',
        string='Khách hàng',
        related='contract_id.customer_id',
        store=True,
        readonly=True
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Công ty',
        related='contract_id.company_id',
        store=True,
        readonly=True
    )