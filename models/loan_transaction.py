from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta, date as dt_date


class LoanTransaction(models.Model):
    _name = 'loan.transaction'
    _description = 'Giao dịch hợp đồng vay'
    _order = 'date asc, id asc'  # Sắp xếp mặc định theo ngày
    
    name = fields.Char(string='Mã giao dịch', readonly=True, default='New')

    contract_id = fields.Many2one(
        'loan.contract',
        string='Hợp đồng',
        required=True,
        ondelete='cascade'  # Xóa giao dịch nếu xóa hợp đồng
    )
    transaction_type = fields.Selection([
        ('principal', 'Trả gốc'),
        ('interest', 'Trả lãi'),
        ('additional', 'Vay thêm'),
        ('liquidation', 'Thanh lý tài sản'),
        ('settlement', 'Tất toán hợp đồng')
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
    
# Quy tac ngay giao dich tranh tinh lai sai    
    @api.constrains('date')
    def _check_date(self):
        for rec in self:
            disbursement_date = rec.contract_id.date_start
            today = dt_date.today()

            # ❌ Không được trước ngày giải ngân
            if rec.date and disbursement_date and rec.date < disbursement_date:
                raise ValidationError("Ngày giao dịch không được trước ngày giải ngân (date_start của hợp đồng).")

            # ❌ Không được sau ngày hiện tại
            if rec.date and rec.date > today:
                raise ValidationError("Ngày giao dịch không được sau ngày hiện tại.")

            # ❌ Nếu đã có giao dịch tất toán → cấm tạo giao dịch sau ngày đó (trừ chính bản thân nó)
            if rec.contract_id:
                settlement_txs = rec.contract_id.transaction_ids.filtered(
                    lambda tx: tx.transaction_type == 'settlement' and tx.id != rec.id
                )
                if settlement_txs:
                    settlement_date = min(settlement_txs.mapped('date'))
                    if rec.transaction_type != 'settlement' and rec.date and rec.date > settlement_date:
                        raise ValidationError("Không thể tạo giao dịch sau ngày tất toán hợp đồng.")

# Loai giao dich tra goc, tra lai phai la so am                 
    @api.constrains('amount', 'transaction_type')
    def _check_amount_sign(self):
        for rec in self:
            if rec.transaction_type in ['principal', 'interest', 'liquidation', 'settlement'] and rec.amount > 0:
                raise ValidationError("Số tiền phải là số âm đối với giao dịch trả gốc, trả lãi, thanh lý tài sản hoặc tất toán hợp đồng.")
            if rec.transaction_type == 'additional' and rec.amount < 0:
                raise ValidationError("Số tiền phải là số dương đối với giao dịch vay thêm.")

# Không cho user xoá giao dịch   
    @api.model
    def unlink(self):
        if not self.env.user.has_group('base.group_system'):
            raise ValidationError("Bạn chỉ được sửa chứ không được xóa giao dịch, để đảm bảo lịch sử các giao dịch vay được lưu trữ và theo dõi chính xác.")
        return super().unlink()
# Gửi lịch sử thay đổi vào chatter hợp đồng vay    
    

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
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

        records = super().create(vals_list)

        if not self.env.context.get('suppress_log'):
            for record in records:
                message = (
                    f"Giao dịch mới: {record.name} - loại {record.transaction_type}, "
                    f"số tiền {record.amount}, ngày {record.date}"
                )
                record.contract_id.message_post(body=message)

        return records

    def write(self, vals):
        significant_fields = {'amount', 'transaction_type', 'date'}
        log_needed = bool(significant_fields.intersection(vals.keys()))

        logs = []

        if log_needed and not self.env.context.get('suppress_log'):
            for rec in self:
                logs.append({
                    'rec': rec,
                    'old_amount': rec.amount,
                    'old_type': rec.transaction_type,
                    'old_date': rec.date,
                })

        res = super().write(vals)

        for log in logs:
            rec = log['rec']
            msg_parts = [f"{rec.name}"]

            if 'amount' in vals and log['old_amount'] != rec.amount:
                msg_parts.append(
                    f"Số tiền: {format(log['old_amount'], ',.0f')} → {format(rec.amount, ',.0f')}")
            if 'transaction_type' in vals and log['old_type'] != rec.transaction_type:
                msg_parts.append(f"Loại: {log['old_type']} → {rec.transaction_type}")
            if 'date' in vals and log['old_date'] != rec.date:
                msg_parts.append(f"Ngày: {log['old_date']} → {rec.date}")

            if len(msg_parts) > 1:
                message = "\n".join(msg_parts)
                rec.contract_id.message_post(body=message)

        return res




# Tính lãi trong noteboook

    @api.depends('date', 'amount', 'transaction_type', 'contract_id')
    def _compute_interest_details(self):
        for tx in self:
            contract = tx.contract_id

            # Nếu chưa có ID (chưa lưu vào DB), bỏ qua để tránh lỗi
            if not tx.id:
                tx.days_from_prev = 0
                tx.interest_for_period = 0
                tx.accumulated_interest = 0
                tx.principal_balance = contract.loan_amount
                continue

            # 👉 Bỏ qua giao dịch "thanh lý tài sản" khỏi tính toán
            if tx.transaction_type == 'liquidation':
                tx.days_from_prev = 0
                tx.interest_for_period = 0
                tx.accumulated_interest = 0
                tx.principal_balance = contract.loan_amount
                continue

            # 🔍 Tìm giao dịch trước đó (theo ngày và ID)
            prev_tx = self.search([
                ('contract_id', '=', contract.id),
                '|',
                ('date', '<', tx.date),
                '&',
                ('date', '=', tx.date),
                ('id', '<', tx.id),
                ('transaction_type', '!=', 'liquidation')  # loại trừ thanh lý
            ], order='date desc, id desc', limit=1)

            if prev_tx:
                tx.days_from_prev = (tx.date - prev_tx.date).days
                principal = prev_tx.principal_balance
                prev_accumulated_interest = prev_tx.accumulated_interest
            else:
                tx.days_from_prev = (tx.date - contract.date_start).days if contract.date_start else 0
                principal = contract.loan_amount
                prev_accumulated_interest = 0

            # 📈 Tính lãi phát sinh
            daily_rate = contract.interest_rate / 100 / 365
            tx.interest_for_period = principal * daily_rate * tx.days_from_prev

            # ➕ Tính lãi tích lũy
            tx.accumulated_interest = prev_accumulated_interest + tx.interest_for_period

            # 💰 Cập nhật dư nợ gốc
            if tx.transaction_type == 'principal':
                tx.principal_balance = principal + tx.amount
            elif tx.transaction_type == 'additional':
                tx.principal_balance = principal + tx.amount
            else:
                tx.principal_balance = principal  # trả lãi → gốc giữ nguyên


