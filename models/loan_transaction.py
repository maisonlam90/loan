from odoo import models, fields, api
from odoo.exceptions import ValidationError


class LoanTransaction(models.Model):
    _name = 'loan.transaction'
    _description = 'Giao dịch hợp đồng vay'
    _order = 'date asc, id asc'  # Sắp xếp mặc định theo ngày

    contract_id = fields.Many2one(
        'loan.contract',
        string='Hợp đồng',
        required=True,
        ondelete='cascade'  # Xóa giao dịch nếu xóa hợp đồng
    )
    transaction_type = fields.Selection([
        ('principal', 'Trả gốc'),
        ('interest', 'Trả lãi'),
        ('additional', 'Vay thêm')
    ], string='Loại giao dịch',  default='principal')
    date = fields.Date(string='Ngày giao dịch',
                        default=fields.Date.today)
    amount = fields.Float(
        string='Số tiền',  help="Dương = vay thêm, Âm = thanh toán")
    note = fields.Char(string='Ghi chú', )

    days_from_prev = fields.Integer(
        string='Số ngày tính lãi',
        compute='_compute_interest_details',
        store=True
    )

    interest_for_period = fields.Float(
        string='Lãi phát sinh',
        compute='_compute_interest_details',
        digits=(16, 0),
        store=True
    )

    accumulated_interest = fields.Float(
        string='Lãi tích lũy',
        compute='_compute_interest_details',
        digits=(16, 0),
        store=True
    )

    principal_balance = fields.Float(
        string='Dư nợ gốc',
        compute='_compute_interest_details',
        digits=(16, 0),
        store=True
    )
# Tính lãi trong noteboook

    @api.depends('date', 'amount', 'transaction_type', 'contract_id')
    def _compute_interest_details(self):
        for tx in self:
            contract = tx.contract_id
            prev_tx = self.search([
                ('contract_id', '=', contract.id),
                ('date', '<', tx.date)
            ], order='date desc', limit=1)

            # Tính số ngày từ giao dịch trước
            if prev_tx:
                tx.days_from_prev = (tx.date - prev_tx.date).days
                prev_date = prev_tx.date
                principal = prev_tx.principal_balance
            else:
                tx.days_from_prev = (
                    tx.date - contract.date_start).days if contract.date_start else 0
                prev_date = contract.date_start
                principal = contract.loan_amount

            # Tính lãi phát sinh
            daily_rate = contract.interest_rate / 100 / 365
            tx.interest_for_period = principal * daily_rate * tx.days_from_prev

            # Tính lãi tích lũy
            if prev_tx:
                tx.accumulated_interest = prev_tx.accumulated_interest + tx.interest_for_period
            else:
                tx.accumulated_interest = tx.interest_for_period

            # Cập nhật dư nợ gốc
            if tx.transaction_type == 'principal':
                tx.principal_balance = principal + tx.amount  # amount âm khi trả gốc
            elif tx.transaction_type == 'additional':
                tx.principal_balance = principal + tx.amount  # amount dương khi vay thêm
            else:
                tx.principal_balance = principal

