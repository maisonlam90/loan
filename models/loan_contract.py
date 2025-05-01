# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta, date
import re


class LoanContract(models.Model):
    _name = 'loan.contract'
    _description = 'Hợp đồng vay cầm đồ'
    # Theo dõi log và hoạt động
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Thêm các trường related từ customer
    cmnd = fields.Char(
        string="CMND/CCCD",
        related='customer_id.cmnd',
        readonly=True,
        tracking=True,
        store=True
    )
    phone = fields.Char(
        string="Số điện thoại",
        related='customer_id.phone',
        readonly=True,
        tracking=True,
        store=True
    )

    # ========== THÔNG TIN CƠ BẢN ==========
    name = fields.Char(
        string='Số hợp đồng',
        default=lambda self: _('New'),
        readonly=True,
        tracking=True,
        copy=False
    )

    company_id = fields.Many2one(
        'res.company',
        string='Cửa hàng',
        default=lambda self: self.env.company,
        required=True
    )

    customer_id = fields.Many2one(
        'res.partner',
        string='Khách hàng',
        required=True,
        tracking=True
    )

    date_start = fields.Date(
        string='Ngày giải ngân',
        default=fields.Date.today,
        tracking=True,
        required=True
    )

    date_end = fields.Date(
        string='Ngày đáo hạn',
        compute='_compute_date_end',
        store=True
    )

    current_principal = fields.Float(
        string='Số dư gốc hiện tại',
        compute='_compute_current_interest',
        store=True
    )

    storage_fee_rate = fields.Float(
        string='Chi phí lưu kho 1 ngày',
        default=0.0,
        tracking=True,
        help="Chi phí lưu giữ tài sản đảm bảo"
    )

    # Trường tính toán phí lưu kho
    storage_fee = fields.Float(
        string='Tổng phí lưu kho',
        compute='_compute_storage_fee',
        store=True,
        help="Tổng chi phí lưu kho từ ngày bắt đầu đến hiện tại"
    )


# Tính tổng số tiền lưu kho


    @api.depends('date_start', 'storage_fee_rate')
    def _compute_storage_fee(self):
        for record in self:
            if not record.date_start:
                record.storage_fee = 0
                continue

            # Tính số ngày từ ngày bắt đầu đến hiện tại
            today = date.today()
            days = (today - record.date_start).days
            days = max(days, 0)  # Đảm bảo không âm

            # Tính phí lưu kho: Số ngày * Đơn giá/ngày
            record.storage_fee = days * record.storage_fee_rate

    duration_months = fields.Integer(
        string='Thời hạn (tháng)',
        default=6,
        tracking=True,
        required=True
    )

    # ========== THÔNG TIN TÀI SẢN CẦM ==========
    
    
    collateral_type = fields.Selection(
        [('home', 'Nhà'),
         ('xe', 'Xe cộ'),
         ('other', 'Khác')],
        string='Loại tài sản',
        required=True
    )

    collateral_description = fields.Text(
        string='Mô tả tài sản',
        tracking=True,
    )

    collateral_value = fields.Float(
        string='Giá trị tài sản',
        tracking=True,
        digits=(16, 0),  # Làm tròn đến đơn vị VND
        required=True
    )

    # ========== THÔNG TIN KHOẢN VAY ==========
    loan_amount = fields.Float(
        string='Số tiền vay',
        digits=(16, 0),
        tracking=True,
        required=True
    )
    

    # Trường lưu lịch sử biến động
    transaction_ids = fields.One2many(
        'loan.transaction',
        'contract_id',
        string='Lịch sử giao dịch'
    )

    current_interest = fields.Float(
        string="Lãi hiện tại",
        compute='_compute_current_interest',
        store=True,
        help="Lãi tính đến hiện tại dựa trên số dư còn lại"
    )

    interest_rate = fields.Float(
        string='Lãi suất (%/năm)',
        default=3.0,
        tracking=True,
        required=True
    )

    state = fields.Selection(
        [('draft', 'Nháp'),
         ('active', 'Đang vay'),
         ('paid', 'Đã tất toán'),
         ('default', 'Quá hạn')],
        string='Trạng thái',
        default='draft',
        tracking=True
    )

    total_settlement_amount = fields.Monetary(
        string='Tổng tất toán',
        compute='_compute_total_settlement_amount',
        currency_field='currency_id',
        store=True,
        help="Tổng số tiền cần thanh toán để tất toán hợp đồng (gốc + lãi + phí)"
    )

    accumulated_interest = fields.Float(
        string='Lãi tích lũy',
        compute='_compute_interest_totals',  # PHẢI TRÙNG VỚI TÊN PHƯƠNG THỨC
        store=True
    )

    total_paid_interest = fields.Float(
        string='Tổng lãi đã trả',
        compute='_compute_interest_totals',
        store=True,
        help="Tổng số tiền lãi đã thanh toán"
    )

    # Tạo trường Kiểm Tra Lãi
    interest_check = fields.Monetary(
        string="Kiểm Tra Lãi",
        compute='_compute_interest_check',
        store=True,
        currency_field='currency_id'
    )

    @api.depends('accumulated_interest', 'total_paid_interest', 'current_interest')
    def _compute_interest_check(self):
        for contract in self:
            contract.interest_check = (contract.accumulated_interest or 0) - \
                                      (contract.total_paid_interest or 0) - \
                                      (contract.current_interest or 0)

    currency_id = fields.Many2one('res.currency', string='Tiền tệ',
                                  required=True, default=lambda self: self.env.company.currency_id)

    # ========== COMPUTE METHODS ==========
    @api.depends('date_start', 'duration_months')
    def _compute_date_end(self):
        for record in self:
            if record.date_start and record.duration_months:
                record.date_end = record.date_start + \
                    timedelta(days=30*record.duration_months)
            else:
                record.date_end = False

    # ========== CONSTRAINTS ==========
    @api.constrains('loan_amount', 'collateral_value')
    def _check_loan_ratio(self):
        """Kiểm tra tỷ lệ cho vay/tài sản"""
        for record in self:
            if record.loan_amount > record.collateral_value * 0.7:  # Chỉ cho vay tối đa 70% giá trị tài sản
                raise ValidationError(_(
                    "Số tiền vay không vượt quá 70%% giá trị tài sản!\n"
                    "- Giá trị tài sản: %s\n"
                    "- Số tiền tối đa có thể vay: %s"
                ) % (
                    format(record.collateral_value, ',.0f'),
                    format(record.collateral_value * 0.7, ',.0f')
                ))

# Hợp đồng phải thuộc về 1 công ty không được bỏ trống
    @api.constrains('company_id')
    def _check_company(self):
        for contract in self:
            if not contract.company_id:
                raise ValidationError("Hợp đồng phải thuộc về một công ty!")
# Tự động sinh số hợp đồng

    @api.model_create_multi
    def create(self, vals_list):
        today = fields.Date.today().strftime('%d%m%Y')  # Ngày hiện tại định dạng DDMMYYYY

        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                type_code = {
                    'home': 'NH',
                    'xe': 'XE',
                    'other': 'TS'
                }.get(vals.get('collateral_type', 'other'), 'TS')

                # Tìm hợp đồng cuối cùng trong NGÀY HÔM NAY và theo loại tài sản
                last_contract = self.search([
                    ('name', 'like', f"{type_code}-{today}-%")
                ], order='name desc', limit=1)

                if last_contract:
                    # Lấy số thứ tự từ mã hợp đồng cuối cùng
                    last_seq = int(last_contract.name.split('-')[-1])
                    seq = last_seq + 1
                else:
                    seq = 1

                # Không cần zfill, dùng số tự nhiên
                vals['name'] = f"{type_code}-{today}-{seq}"

        records = super(LoanContract, self).create(vals_list)
        return records


# Tính tổng lãi tất toán


    @api.depends('current_principal', 'current_interest', 'storage_fee', 'state')
    def _compute_total_settlement_amount(self):
        for record in self:
            if record.state == 'paid':
                record.total_settlement_amount = 0
            else:
                record.total_settlement_amount = (
                    record.current_principal +
                    record.current_interest +
                    record.storage_fee
                )

 # Tính lãi theo phương pháp dồn tích

    @api.depends('transaction_ids', 'transaction_ids.amount', 'transaction_ids.date', 'transaction_ids.transaction_type', 'loan_amount', 'interest_rate')
    def _compute_current_interest(self):
        for contract in self:
            total_interest = 0.0
            balance = contract.loan_amount  # Số dư gốc ban đầu
            interest_balance = 0.0  # Lãi tích lũy chưa trả
            prev_date = contract.date_start or fields.Date.today()

            # Sắp xếp giao dịch theo ngày
            transactions = contract.transaction_ids.sorted('date')

            for tx in transactions:
                # Tính lãi từ ngày trước đến ngày giao dịch hiện tại
                if tx.date > prev_date:
                    days = (tx.date - prev_date).days
                    daily_rate = contract.interest_rate / 100 / 365
                    period_interest = balance * daily_rate * days
                    total_interest += period_interest
                    interest_balance += period_interest

                # Xử lý từng loại giao dịch
                if tx.transaction_type == 'principal':
                    balance += tx.amount  # Trả gốc (số âm)
                elif tx.transaction_type == 'interest':
                    interest_balance += tx.amount  # Trả lãi (số âm)
                elif tx.transaction_type == 'additional':
                    balance += tx.amount  # Vay thêm (số dương)

                prev_date = tx.date

            # Tính lãi từ giao dịch cuối đến hiện tại
            today = fields.Date.today()
            if prev_date < today:
                days = (today - prev_date).days
                daily_rate = contract.interest_rate / 100 / 365
                period_interest = balance * daily_rate * days
                total_interest += period_interest
                interest_balance += period_interest

            contract.current_interest = max(interest_balance, 0)  # Không âm
            contract.current_principal = balance  # Số dư gốc hiện tại
# Tính lãi tích luỹ và tổng lãi đã trả phần tổng hợp dưới notebook

    @api.depends('transaction_ids.accumulated_interest', 'transaction_ids.date',
                 'transaction_ids.principal_balance', 'date_start', 'interest_rate', 'loan_amount')
    def _compute_interest_totals(self):
        """Tính Lãi tích lũy đến ngày hiện tại (bao gồm cả lãi từ giao dịch cuối đến hôm nay)"""
        for contract in self:
            today = fields.Date.today()
            daily_rate = contract.interest_rate / 100 / 365
            total_paid = 0.0

            # Trường hợp KHÔNG có giao dịch
            if not contract.transaction_ids:
                days = (
                    today - contract.date_start).days if contract.date_start else 0
                contract.accumulated_interest = contract.loan_amount * daily_rate * days
                contract.total_paid_interest = 0.0
                continue

            # Lấy giao dịch cuối cùng trước hoặc bằng hôm nay
            last_tx = contract.transaction_ids.filtered(
                lambda tx: tx.date <= today
            ).sorted('date', reverse=True)[:1]

            if last_tx:
                # Tính lãi từ giao dịch cuối đến hôm nay
                days_since_last_tx = (today - last_tx.date).days
                interest_since_last_tx = last_tx.principal_balance * daily_rate * days_since_last_tx

                # Lãi tích lũy = Lãi đến giao dịch cuối + Lãi từ giao dịch cuối đến hôm nay
                contract.accumulated_interest = last_tx.accumulated_interest + interest_since_last_tx

                # Tổng lãi đã trả
                contract.total_paid_interest = sum(
                    abs(tx.amount)
                    for tx in contract.transaction_ids
                    if tx.transaction_type == 'interest' and tx.amount < 0 and tx.date <= today
                )
            else:
                # Nếu tất cả giao dịch đều trong tương lai
                days = (
                    today - contract.date_start).days if contract.date_start else 0
                contract.accumulated_interest = contract.loan_amount * daily_rate * days
                contract.total_paid_interest = 0.0

# Hàm cập nhật số liệu tính lãi trong notebook
    def write(self, vals):
        res = super(LoanContract, self).write(vals)
        if not self.env.context.get('no_recompute'):
            self.with_context(no_recompute=True)._update_financial_data()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super(LoanContract, self).create(vals_list)
        records.with_context(no_recompute=True)._update_financial_data()
        return records

    def _update_financial_data(self):
        for contract in self:
            sorted_txs = contract.transaction_ids.sorted(lambda tx: (tx.date, tx.id))

            for tx in sorted_txs:
                tx._compute_interest_details()

            contract._compute_interest_totals()
            contract._compute_current_interest()
            contract._compute_total_settlement_amount()

