"""
apps/tenants/agency_models.py

Comprehensive models for the Agency Dashboard system.
Covers:
  - Settings (Agent, Company, Position, SelectionGrade)
  - Visa Lot Management
  - Candidate Registration & Connected Multi-Stage Workflows:
      * Selection Grading (Pending, Selected, Awaiting, Rejected)
      * Delegate Approval (Pending, Approved)
      * Medical Assessment (Pending, Fit, Unfit, Expired, Canceled)
      * Police Clearance (Pending, Cleared, Uncleared)
      * Visa Section (Mofa Pending/Cleared, Enjaz Pending/Completed, Finger Pending/Completed, Visa Pending/Completed)
      * Manpower Assessment (Training Pending/Completed, Manpower Approval/Completed)
      * Flight Management (Ticket Issue/Pending/Completed, NOC Approval/Completed)
  - Financial Requisitions & Vouchers:
      * Payment Requisitions (Direct, Indirect)
      * Receipt Requisitions (Direct, Indirect)
      * Contra Requisitions
      * Accounts & Vouchers (Bank Voucher, Cash Payment, Cheque Receipt, Cash Receipt, Journal Voucher)
  - HR & Daily Movement / Leave
"""
import uuid
from decimal import Decimal
from django.db import models
from django.utils import timezone


class AgencyAgent(models.Model):
    """Recruitment or travel sub-agent."""
    name = models.CharField(max_length=200)
    agent_code = models.CharField(max_length=50, unique=True, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    company_name = models.CharField(max_length=200, blank=True)
    address = models.TextField(blank=True)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.agent_code or 'Agent'})"

    def save(self, *args, **kwargs):
        if not self.agent_code:
            import random, string
            self.agent_code = 'AG-' + ''.join(random.choices(string.digits, k=5))
        super().save(*args, **kwargs)


class AgencyCompany(models.Model):
    """Foreign employer / sponsor company."""
    name = models.CharField(max_length=200)
    country = models.CharField(max_length=100, default='Saudi Arabia')
    contact_person = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Agency Companies'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.country})"


class AgencyPosition(models.Model):
    """Job positions for candidate recruitment."""
    title = models.CharField(max_length=150)
    code = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['title']

    def __str__(self):
        return self.title


class SelectionGrade(models.Model):
    """Grading categories for candidate selection."""
    grade_name = models.CharField(max_length=50) # e.g. Grade A, Grade B, Top Selection
    description = models.TextField(blank=True)

    def __str__(self):
        return self.grade_name


class VisaLot(models.Model):
    """Visa Lot: a group of visas offered/managed by the agency."""

    class VisaType(models.TextChoices):
        WORK = 'work', 'Work Visa'
        TOURIST = 'tourist', 'Tourist Visa'
        BUSINESS = 'business', 'Business Visa'
        STUDENT = 'student', 'Student Visa'
        DOMESTIC = 'domestic', 'Domestic Worker Visa'
        TRANSIT = 'transit', 'Transit Visa'
        FAMILY = 'family', 'Family Visa'
        OTHER = 'other', 'Other'

    # Core (required)
    title = models.CharField(max_length=255, default='Visa Lot')
    lot_number = models.CharField(max_length=100, unique=True, blank=True)
    country = models.CharField(max_length=100, default='Saudi Arabia')
    quota = models.PositiveIntegerField(default=1)

    # Visa details (all optional)
    visa_type = models.CharField(
        max_length=20, choices=VisaType.choices, default=VisaType.WORK, blank=True
    )
    price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Visa fee per person (leave blank if not applicable)'
    )
    processing_time = models.CharField(
        max_length=150, blank=True,
        help_text='e.g. 7-10 business days'
    )
    description = models.TextField(blank=True)
    requirements = models.TextField(
        blank=True, help_text='List of required documents'
    )
    featured_image = models.ImageField(
        upload_to='visa_lots/', blank=True, null=True
    )
    sponsor_name = models.CharField(max_length=200, blank=True)
    sponsor_id = models.CharField(max_length=100, blank=True)

    # Status & visibility
    assigned_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    show_on_website = models.BooleanField(
        default=True, help_text='Display this visa lot on the agency public website'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} — {self.country} (Lot #{self.lot_number or 'N/A'})"

    @property
    def remaining_visas(self):
        """Calculates remaining available visa slots in this lot."""
        actual_count = self.candidates.count()
        return max(0, self.quota - actual_count)

    def update_assigned_count(self):
        """Syncs assigned_count field with actual candidate count."""
        self.assigned_count = self.candidates.count()
        self.save(update_fields=['assigned_count'])

    def save(self, *args, **kwargs):
        if not self.lot_number:
            import random, string
            self.lot_number = 'VL-' + ''.join(random.choices(string.digits, k=6))
        super().save(*args, **kwargs)


class Candidate(models.Model):
    """
    Main Candidate Model representing a person undergoing agency registration
    and full connected workflow tracking.
    """
    # Choice enumerations
    class SelectionStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SELECTED = 'selected', 'Selected'
        AWAITING = 'awaiting', 'Awaiting'
        REJECTED = 'rejected', 'Rejected'

    class DelegateStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'

    class MedicalStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        FIT = 'fit', 'Fit'
        UNFIT = 'unfit', 'Unfit'
        EXPIRED = 'expired', 'Expired'
        CANCELED = 'canceled', 'Canceled'

    class PoliceClearanceStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        CLEARED = 'cleared', 'Cleared'
        UNCLEARED = 'uncleared', 'Uncleared'

    class MofaStatus(models.TextChoices):
        PENDING = 'mofa_pending', 'Mofa Pending'
        CLEARED = 'mofa_cleared', 'Mofa Cleared'

    class EnjazStatus(models.TextChoices):
        PENDING = 'enjaz_pending', 'Enjaz/Money Trans. Pending'
        COMPLETED = 'enjaz_completed', 'Enjaz Completed'

    class FingerStatus(models.TextChoices):
        PENDING = 'finger_pending', 'Finger Pending'
        COMPLETED = 'finger_completed', 'Finger Completed'

    class VisaStampingStatus(models.TextChoices):
        PENDING = 'visa_pending', 'Visa Pending'
        COMPLETED = 'visa_completed', 'Visa Completed'

    class TrainingStatus(models.TextChoices):
        PENDING = 'training_pending', 'Training Pending'
        COMPLETED = 'training_completed', 'Training Completed'

    class ManpowerApprovalStatus(models.TextChoices):
        PENDING = 'manpower_pending', 'Manpower Approval Pending'
        COMPLETED = 'manpower_completed', 'Manpower Completed'

    class TicketStatus(models.TextChoices):
        ISSUE = 'ticket_issue', 'Ticket Issue'
        PENDING = 'ticket_pending', 'Ticket Pending'
        COMPLETED = 'ticket_completed', 'Ticket Completed'

    class NOCStatus(models.TextChoices):
        PENDING = 'noc_pending', 'NOC Approval Pending'
        COMPLETED = 'noc_completed', 'NOC Completed'

    # Primary Info
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    registration_id = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    passport_number = models.CharField(max_length=50, unique=True)
    passport_expiry = models.DateField(blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    mobile = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    gender = models.CharField(max_length=10, choices=[('male','Male'), ('female','Female'), ('other','Other')], default='male')
    address = models.TextField(blank=True)
    photo = models.ImageField(upload_to='candidates/photos/', blank=True, null=True)
    id_card_printed = models.BooleanField(default=False)

    # Master Relations
    country = models.CharField(max_length=100, default='Saudi Arabia')
    agent = models.ForeignKey(AgencyAgent, on_delete=models.SET_NULL, null=True, blank=True, related_name='candidates')
    company = models.ForeignKey(AgencyCompany, on_delete=models.SET_NULL, null=True, blank=True, related_name='candidates')
    position = models.ForeignKey(AgencyPosition, on_delete=models.SET_NULL, null=True, blank=True, related_name='candidates')
    selection_grade = models.ForeignKey(SelectionGrade, on_delete=models.SET_NULL, null=True, blank=True)
    visa_lot = models.ForeignKey(VisaLot, on_delete=models.SET_NULL, null=True, blank=True, related_name='candidates')
    interview_slot = models.CharField(max_length=100, blank=True, help_text='e.g. Slot A - 10:00 AM')

    # 1. Selection & Assessment Stages
    selection_status = models.CharField(max_length=20, choices=SelectionStatus.choices, default=SelectionStatus.PENDING)
    delegate_status = models.CharField(max_length=20, choices=DelegateStatus.choices, default=DelegateStatus.PENDING)

    # 2. Medical & Police Clearance
    medical_status = models.CharField(max_length=20, choices=MedicalStatus.choices, default=MedicalStatus.PENDING)
    medical_clinic = models.CharField(max_length=150, blank=True)
    medical_date = models.DateField(blank=True, null=True)
    medical_expiry = models.DateField(blank=True, null=True)

    police_clearance_status = models.CharField(max_length=20, choices=PoliceClearanceStatus.choices, default=PoliceClearanceStatus.PENDING)
    police_clearance_ref = models.CharField(max_length=100, blank=True)
    police_clearance_date = models.DateField(blank=True, null=True)

    # 3. Visa Section Workflow
    mofa_status = models.CharField(max_length=30, choices=MofaStatus.choices, default=MofaStatus.PENDING)
    mofa_number = models.CharField(max_length=100, blank=True)
    mofa_date = models.DateField(blank=True, null=True)

    enjaz_status = models.CharField(max_length=30, choices=EnjazStatus.choices, default=EnjazStatus.PENDING)
    enjaz_number = models.CharField(max_length=100, blank=True)

    finger_status = models.CharField(max_length=30, choices=FingerStatus.choices, default=FingerStatus.PENDING)
    finger_date = models.DateField(blank=True, null=True)

    visa_stamping_status = models.CharField(max_length=30, choices=VisaStampingStatus.choices, default=VisaStampingStatus.PENDING)
    visa_number = models.CharField(max_length=100, blank=True)
    visa_issue_date = models.DateField(blank=True, null=True)

    # 4. Manpower Assessment
    training_status = models.CharField(max_length=30, choices=TrainingStatus.choices, default=TrainingStatus.PENDING)
    training_center = models.CharField(max_length=150, blank=True)

    manpower_status = models.CharField(max_length=30, choices=ManpowerApprovalStatus.choices, default=ManpowerApprovalStatus.PENDING)
    bmet_card_number = models.CharField(max_length=100, blank=True)

    # 5. Flight & NOC Management
    travel_agency_name = models.CharField(max_length=150, blank=True)
    ticket_status = models.CharField(max_length=30, choices=TicketStatus.choices, default=TicketStatus.PENDING)
    airline = models.CharField(max_length=100, blank=True)
    pnr_number = models.CharField(max_length=50, blank=True)
    flight_date = models.DateTimeField(blank=True, null=True)
    ticket_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    noc_status = models.CharField(max_length=30, choices=NOCStatus.choices, default=NOCStatus.PENDING)
    noc_reference = models.CharField(max_length=100, blank=True)

    # 6. Candidate Financials (Total, Paid, Due)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text='Total agreed visa/package fee')
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text='Total amount collected so far')
    due_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text='Auto-calculated due balance')

    # 7. Sector Configuration
    applicable_sectors = models.JSONField(default=list, blank=True, help_text='List of required sectors for candidate workflow')

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.registration_id} - {self.name} ({self.passport_number})"

    def recalculate_financials(self):
        """Calculates total paid amount from CandidatePayment history and updates due_amount."""
        from django.db.models import Sum
        total_paid = self.payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        tot = Decimal(str(self.total_amount or '0.00'))
        paid = Decimal(str(total_paid or '0.00'))
        self.paid_amount = paid
        self.due_amount = max(Decimal('0.00'), tot - paid)
        self.save(update_fields=['paid_amount', 'due_amount'])

    @classmethod
    def get_next_registration_id(cls):
        candidates = cls.objects.filter(registration_id__startswith='REG-')
        max_num = 0
        for c in candidates:
            try:
                parts = c.registration_id.split('-')
                if len(parts) > 1 and parts[-1].isdigit():
                    num = int(parts[-1])
                    if num < 100000 and num > max_num:
                        max_num = num
            except Exception:
                pass
        return f"REG-{(max_num + 1):04d}"

    def save(self, *args, **kwargs):
        if not self.registration_id:
            self.registration_id = self.get_next_registration_id()
        # Auto-compute due amount on save safely using Decimal conversion
        tot = Decimal(str(self.total_amount or '0.00'))
        paid = Decimal(str(self.paid_amount or '0.00'))
        self.total_amount = tot
        self.paid_amount = paid
        self.due_amount = max(Decimal('0.00'), tot - paid)
        super().save(*args, **kwargs)


class CandidatePayment(models.Model):
    """
    Individual payment installment record for a Candidate with date tracking.
    """
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateField(default=timezone.now)
    payment_method = models.CharField(
        max_length=50, default='Cash',
        choices=[
            ('Cash', 'Cash'),
            ('Bank Transfer', 'Bank Transfer'),
            ('bKash / Mobile Banking', 'bKash / Mobile Banking'),
            ('Cheque', 'Cheque'),
            ('Other', 'Other'),
        ]
    )
    reference_no = models.CharField(max_length=100, blank=True, help_text='Txn ID / Cheque # / Slip #')
    voucher = models.ForeignKey('AccountVoucher', on_delete=models.SET_NULL, null=True, blank=True, related_name='candidate_payments')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-payment_date', '-created_at']

    def __str__(self):
        return f"{self.candidate.name} - ৳{self.amount} ({self.payment_date})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.candidate.recalculate_financials()

    def delete(self, *args, **kwargs):
        cand = self.candidate
        super().delete(*args, **kwargs)
        cand.recalculate_financials()


class CandidateDocument(models.Model):
    """
    Attached document for candidate recruitment sectors (Medical, Police Clearance, MOFA, etc.).
    """
    SECTOR_CHOICES = [
        ('passport', 'Passport / Bio Data'),
        ('selection', 'Selection & Assessment'),
        ('medical', 'Medical Clearance'),
        ('police_clearance', 'Police Clearance'),
        ('mofa', 'MOFA Document'),
        ('enjaz', 'Enjaz / Payment Receipt'),
        ('fingerprint', 'Biometric / Fingerprint'),
        ('visa_stamping', 'Visa Stamping Document'),
        ('training', 'Training Certificate'),
        ('manpower', 'Manpower / BMET Smart Card'),
        ('flight', 'Ticket & NOC Approval'),
        ('other', 'Other Document'),
    ]

    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='documents')
    sector = models.CharField(max_length=30, choices=SECTOR_CHOICES, default='passport')
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to='candidate_documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.candidate.name} - {self.get_sector_display()} ({self.title})"


class Requisition(models.Model):
    """Payment, Receipt, and Contra Requisitions."""
    class ReqCategory(models.TextChoices):
        PAYMENT_DIRECT = 'payment_direct', 'Direct Payment Requisition'
        PAYMENT_INDIRECT = 'payment_indirect', 'Indirect Payment Requisition'
        RECEIPT_DIRECT = 'receipt_direct', 'Direct Receipt Requisition'
        RECEIPT_INDIRECT = 'receipt_indirect', 'Indirect Receipt Requisition'
        CONTRA = 'contra', 'Contra Requisition'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    requisition_code = models.CharField(max_length=50, unique=True)
    category = models.CharField(max_length=30, choices=ReqCategory.choices)
    candidate = models.ForeignKey(Candidate, on_delete=models.SET_NULL, null=True, blank=True, related_name='requisitions')
    agent = models.ForeignKey(AgencyAgent, on_delete=models.SET_NULL, null=True, blank=True)
    payee_or_payer = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    purpose = models.TextField()
    transfer_from_account = models.CharField(max_length=150, blank=True)
    transfer_to_account = models.CharField(max_length=150, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.requisition_code} ({self.get_category_display()}) - {self.amount}"

    def save(self, *args, **kwargs):
        if not self.requisition_code:
            import random, string
            self.requisition_code = 'REQ-' + ''.join(random.choices(string.digits, k=6))
        super().save(*args, **kwargs)


class AccountHeadGroup(models.Model):
    """Account head group classification (Asset, Liability, Income, Expense, Equity)."""
    name = models.CharField(max_length=150, unique=True)
    type_category = models.CharField(max_length=20, choices=[
        ('asset', 'Asset'), ('liability', 'Liability'),
        ('income', 'Income'), ('expense', 'Expense'), ('equity', 'Equity')
    ])

    def __str__(self):
        return f"{self.name} ({self.get_type_category_display()})"


class ChartOfAccount(models.Model):
    """Chart of Accounts ledger."""
    account_name = models.CharField(max_length=200)
    account_code = models.CharField(max_length=50, unique=True)
    head_group = models.ForeignKey(AccountHeadGroup, on_delete=models.CASCADE, related_name='accounts')
    tds_section = models.CharField(max_length=50, blank=True, help_text='Section Number of TDS')
    current_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"[{self.account_code}] {self.account_name}"


class AccountVoucher(models.Model):
    """Vouchers: Bank Voucher, Cash Payment, Cheque Receipt, Cash Receipt, Journal Voucher."""
    class VoucherType(models.TextChoices):
        BANK_VOUCHER = 'bv', 'Bank Voucher (BV)'
        CASH_PAYMENT = 'cpv', 'Cash Payment Voucher'
        CHEQUE_RECEIPT = 'cr_cheque', 'Cheque Receipt (CR)'
        CASH_RECEIPT = 'cr_cash', 'Cash Receipt (CR)'
        JOURNAL_VOUCHER = 'jv', 'Journal Voucher (JV)'

    voucher_no = models.CharField(max_length=50, unique=True)
    voucher_type = models.CharField(max_length=20, choices=VoucherType.choices)
    account = models.ForeignKey(ChartOfAccount, on_delete=models.CASCADE, related_name='vouchers')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    narration = models.TextField(blank=True)
    reference_no = models.CharField(max_length=100, blank=True)
    voucher_date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-voucher_date', '-created_at']

    def __str__(self):
        return f"{self.voucher_no} ({self.get_voucher_type_display()}) - {self.amount}"

    @classmethod
    def get_next_serial(cls, voucher_type='cr_cash'):
        prefix_map = {
            'bv': 'BV',
            'cpv': 'CPV',
            'cash_payment': 'CPV',
            'cr_cheque': 'CR',
            'cr_cash': 'CR',
            'jv': 'JV',
        }
        prefix = prefix_map.get(voucher_type, str(voucher_type).upper().replace('_', ''))
        vouchers = cls.objects.filter(voucher_no__startswith=f"{prefix}-")
        max_num = 0
        for v in vouchers:
            try:
                parts = v.voucher_no.split('-')
                if len(parts) > 1 and parts[-1].isdigit():
                    num = int(parts[-1])
                    if num < 50000 and num > max_num:
                        max_num = num
            except Exception:
                pass
        return f"{prefix}-{(max_num + 1):04d}"

    def save(self, *args, **kwargs):
        if not self.voucher_no:
            self.voucher_no = self.get_next_serial(self.voucher_type)
        super().save(*args, **kwargs)


class DailyMovement(models.Model):
    """Daily movement log for agency staff/candidates."""
    person_name = models.CharField(max_length=150)
    role_type = models.CharField(max_length=50, default='Candidate') # Candidate / Staff
    purpose = models.TextField()
    destination = models.CharField(max_length=150, blank=True)
    movement_date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')
    ], default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.person_name} - {self.movement_date} ({self.status})"


class LeaveSubmission(models.Model):
    """Leave submission and history for agency employees."""
    employee_name = models.CharField(max_length=150)
    leave_type = models.CharField(max_length=50, choices=[
        ('casual', 'Casual Leave'), ('sick', 'Sick Leave'), ('annual', 'Annual Leave'), ('other', 'Other')
    ])
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')
    ], default='pending')
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.employee_name} ({self.leave_type}) - {self.status}"


class OfficeExpense(models.Model):
    """Office expense tracking for the agency."""

    CATEGORY_CHOICES = [
        ('rent', 'Office Rent'),
        ('utilities', 'Electricity & Utilities'),
        ('internet', 'Internet & Phone'),
        ('salary', 'Staff Salary'),
        ('stationery', 'Stationery & Supplies'),
        ('transport', 'Transport & Fuel'),
        ('maintenance', 'Maintenance & Repair'),
        ('marketing', 'Marketing & Advertising'),
        ('food', 'Food & Entertainment'),
        ('equipment', 'Equipment & Furniture'),
        ('software', 'Software & Subscriptions'),
        ('medical', 'Medical/Health Expense'),
        ('government', 'Government Fees & Taxes'),
        ('other', 'Other Expense'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('bkash', 'bKash / Mobile Banking'),
        ('cheque', 'Cheque'),
        ('other', 'Other'),
    ]

    title = models.CharField(max_length=255, help_text='Short description of the expense')
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='other')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    expense_date = models.DateField(default=timezone.now)
    payment_method = models.CharField(max_length=30, choices=PAYMENT_METHOD_CHOICES, default='cash')
    paid_to = models.CharField(max_length=200, blank=True, help_text='Vendor / Payee name')
    reference_no = models.CharField(max_length=100, blank=True, help_text='Receipt/Invoice number')
    notes = models.TextField(blank=True)
    receipt_file = models.FileField(upload_to='office_expenses/receipts/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-expense_date', '-created_at']

    def __str__(self):
        return f"{self.get_category_display()} — {self.title} (৳{self.amount})"
