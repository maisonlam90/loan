from odoo import models, fields, api
from odoo.exceptions import ValidationError


class LoanTransaction(models.Model):
    _name = 'loan.transaction'
    _description = 'Giao dịch hợp đồng vay'
    _order = 'date asc, id asc'  # Sắp xếp mặc định theo ngày
    
    name = fields.Char(string='Mã giao dịch', readonly=1, default='New')

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
        string='Số tiền',  help="Dương = vay thêm, Âm = thanh toán", tracking="True",)
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
    

# Không cho user xoá giao dịch   
    @api.model
    def unlink(self):
        if not self.env.user.has_group('base.group_system'):
            raise ValidationError("Bạn chỉ được sửa chứ không được xóa giao dịch, để đảm bảo lịch sử các giao dịch vay được lưu trữ và theo dõi chính xác.")
        return super().unlink()
# Gửi lịch sử thay đổi vào chatter hợp đồng vay    
    

    @api.model
    def create(self, vals):
        contract = self.env['loan.contract'].browse(vals['contract_id'])

        # Sinh mã giao dịch: LOAN-...-5-1
        existing = self.search([
            ('contract_id', '=', contract.id),
            ('name', '!=', 'New')
        ], order='id desc', limit=1)
        if existing and existing[0].name and existing[0].name.count('-') >= 4:
            try:
                last_seq = int(existing[0].name.split('-')[-1])
            except ValueError:
                last_seq = 0
        else:
            last_seq = 0

        seq = last_seq + 1
        vals['name'] = f"{contract.name}-{seq}"

        # Tạo bản ghi
        record = super().create(vals)

        # Ghi vào chatter
        if not self.env.context.get('suppress_log'):
            message = (
                f"Giao dịch mới: {record.name} - loại {record.transaction_type}, "
                f"số tiền {record.amount}, ngày {record.date}"
            )
            record.contract_id.message_post(body=message)

        return record
    
    def write(self, vals):
        significant_fields = {'amount', 'transaction_type', 'date'}
        log_needed = bool(significant_fields.intersection(vals.keys()))

        for rec in self:
            old_amount = rec.amount
            old_type = rec.transaction_type
            old_date = rec.date

            res = super(LoanTransaction, rec).write(vals)

            if log_needed and not self.env.context.get('suppress_log'):
                new_amount = rec.amount
                new_type = rec.transaction_type
                new_date = rec.date

                msg_parts = [f"{rec.name}"]

                if 'amount' in vals and old_amount != new_amount:
                    msg_parts.append(f"Số tiền: {format(old_amount, ',.0f')} → {format(new_amount, ',.0f')}")
                if 'transaction_type' in vals and old_type != new_type:
                    msg_parts.append(f"Loại: {old_type} → {new_type}")
                if 'date' in vals and old_date != new_date:
                    msg_parts.append(f"Ngày: {old_date} → {new_date}")

                message = "\n".join(msg_parts)
                rec.contract_id.message_post(body=message)

        return res








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

