"""
apps/tenants/agency_views.py

Comprehensive Django views for the Agency Management Dashboard.
Handles:
  1. Candidate Registration & List with Search & Filtering
  2. Candidate Add, Edit, Delete, Details
  3. Bulk ID Card Printing (`id_card_print`)
  4. Connected Multi-Stage Workflows:
     - Selection Grading (Pending, Selected, Awaiting, Rejected)
     - Delegate Approval (Pending, Approved)
     - Medical Assessment (Pending, Fit, Unfit, Expired, Canceled)
     - Police Clearance (Pending, Cleared, Uncleared)
     - Visa Section (Mofa, Enjaz, Fingerprint, Visa Stamping)
     - Manpower Assessment (Training, Manpower Approval)
     - Flight & NOC (Ticket Issue/Pending/Completed, NOC Approval/Completed)
  5. Okala & Visa Lot Management
  6. Financial Requisitions (Payment, Receipt, Contra)
  7. Accounts & Vouchers (BV, Cash Payment, Cheque Receipt, Cash Receipt, JV)
  8. HR Management (Daily Movement & Leave Submission)
  9. Integrated Agency Reports Engine (14 Reports)
 10. Master Settings (Country, Agent, Company, Position, Selection Grade)
"""
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count
from django.utils import timezone

from .agency_models import (
    AgencyAgent, AgencyCompany, AgencyPosition, SelectionGrade,
    VisaLot, Candidate, CandidatePayment, CandidateDocument, Requisition, AccountHeadGroup,
    ChartOfAccount, AccountVoucher, DailyMovement, LeaveSubmission, OfficeExpense,
    B2BAgentStaff, B2BTransaction
)
from apps.destinations.models import Country

from django.conf import settings
from apps.tenants.models import Tenant
from apps.tenants.routers import set_tenant_db

def get_tenant_db(request):
    """Return database alias for current tenant, dynamically registering DB config if missing."""
    tenant_slug = None
    if hasattr(request, 'user') and getattr(request.user, 'tenant_id', None):
        tenant_slug = request.user.tenant_id
    elif getattr(request, 'tenant', None):
        tenant_slug = request.tenant.slug

    if tenant_slug:
        db_alias = f'tenant_{tenant_slug}'
        if db_alias not in settings.DATABASES:
            try:
                tenant_obj = getattr(request, 'tenant', None)
                if not tenant_obj:
                    tenant_obj = Tenant.objects.filter(slug=tenant_slug).first()
                if tenant_obj:
                    settings.DATABASES[db_alias] = tenant_obj.get_db_config()
            except Exception:
                return 'default'

        if db_alias in settings.DATABASES:
            set_tenant_db(db_alias)
            return db_alias

    return 'default'


# ── HELPER: Seed Default Settings Data if Empty ──────────────────────────────
def ensure_default_settings(db='default'):
    """Ensure basic positions, grades, account heads, agents, and destination countries exist for agency tenant."""
    try:
        # 1. Countries
        if not Country.objects.using(db).exists():
            default_countries = [
                ('Saudi Arabia', 'SAU'),
                ('United Arab Emirates', 'ARE'),
                ('Qatar', 'QAT'),
                ('Oman', 'OMN'),
                ('Kuwait', 'KWT'),
                ('Singapore', 'SGP'),
                ('Malaysia', 'MYS'),
                ('Bahrain', 'BHR'),
                ('Jordan', 'JOR'),
                ('Maldives', 'MDV'),
            ]
            for c_name, c_code in default_countries:
                Country.objects.using(db).create(name=c_name, code=c_code, is_active=True)

        for vl_country in VisaLot.objects.using(db).values_list('country', flat=True).distinct():
            if vl_country and vl_country.strip() and not Country.objects.using(db).filter(name__iexact=vl_country.strip()).exists():
                Country.objects.using(db).create(name=vl_country.strip(), is_active=True)

        if not AgencyPosition.objects.using(db).exists():
            positions = ['Electrician', 'Driver', 'Mason', 'Plumber', 'Construction Worker', 'Welder', 'Cook', 'Maid', 'General Worker']
            for p in positions:
                AgencyPosition.objects.using(db).create(title=p)

        if not SelectionGrade.objects.using(db).exists():
            grades = ['Grade A (Primary)', 'Grade B (Secondary)', 'Grade C (Standard)', 'VVIP Selection']
            for g in grades:
                SelectionGrade.objects.using(db).create(grade_name=g)

        if not AgencyAgent.objects.using(db).exists():
            def_agent = AgencyAgent.objects.using(db).create(
                name='Global Overseas Agency',
                phone='+8801700000000',
                email='agent@globaloverseas.com',
                company_name='Global Overseas Ltd',
                agent_type='b2b',
                credit_limit=500000.00,
                commission_rate=5.00
            )
            B2BAgentStaff.objects.using(db).create(
                agent=def_agent,
                name='Senior Visa Executive',
                phone='+8801700000001',
                email='executive@globaloverseas.com',
                designation='Visa & Ticket Officer'
            )

        if not AgencyCompany.objects.using(db).exists():
            AgencyCompany.objects.using(db).create(name='Al-Falah General Trading LLC', country='Saudi Arabia', contact_person='Ahmed Al-Mansoor')

        if not AccountHeadGroup.objects.using(db).exists():
            groups = [
                ('Current Assets', 'asset'), ('Fixed Assets', 'asset'),
                ('Accounts Payable', 'liability'), ('Current Liabilities', 'liability'),
                ('Agency Service Revenue', 'income'), ('Commission Income', 'income'),
                ('Visa & Document Expense', 'expense'), ('Flight Ticket Expense', 'expense'),
                ('Office Operational Expense', 'expense'), ('Owner Equity', 'equity')
            ]
            for name, cat in groups:
                AccountHeadGroup.objects.using(db).create(name=name, type_category=cat)

        if not ChartOfAccount.objects.using(db).exists() and AccountHeadGroup.objects.using(db).exists():
            asset_grp = AccountHeadGroup.objects.using(db).filter(type_category='asset').first()
            income_grp = AccountHeadGroup.objects.using(db).filter(type_category='income').first()
            exp_grp = AccountHeadGroup.objects.using(db).filter(type_category='expense').first()

            if asset_grp:
                ChartOfAccount.objects.using(db).create(account_name='Cash in Hand', account_code='1001', head_group=asset_grp, current_balance=50000.00)
                ChartOfAccount.objects.using(db).create(account_name='Islami Bank Bangladesh', account_code='1002', head_group=asset_grp, current_balance=250000.00)
            if income_grp:
                ChartOfAccount.objects.using(db).create(account_name='Visa Processing Revenue', account_code='4001', head_group=income_grp)
            if exp_grp:
                ChartOfAccount.objects.using(db).create(account_name='Medical & PC Expenses', account_code='5001', head_group=exp_grp)
    except Exception:
        pass


# ── 1. CANDIDATE REGISTRATION & LIST ─────────────────────────────────────────
@login_required
def candidate_list(request):
    """Candidate master list with multi-filter, country-wise search, date-range search."""
    db = get_tenant_db(request)
    ensure_default_settings(db)

    query = request.GET.get('q', '').strip()
    selected_country = request.GET.get('country', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    sel_status = request.GET.get('selection_status', '')
    med_status = request.GET.get('medical_status', '')
    visa_status = request.GET.get('visa_status', '')
    client_type = request.GET.get('client_type', '').strip()
    agent_filter = request.GET.get('agent_id', '').strip()
    staff_filter = request.GET.get('staff_id', '').strip()

    try:
        candidates_qs = Candidate.objects.using(db).select_related('b2b_agent', 'b2b_staff', 'agent', 'visa_lot').all()
        if query:
            candidates_qs = candidates_qs.filter(
                Q(name__icontains=query) |
                Q(passport_number__icontains=query) |
                Q(registration_id__icontains=query) |
                Q(mobile__icontains=query)
            )
        if selected_country:
            candidates_qs = candidates_qs.filter(
                Q(country__iexact=selected_country) |
                Q(visa_lot__country__iexact=selected_country)
            )
        if date_from:
            candidates_qs = candidates_qs.filter(created_at__date__gte=date_from)
        if date_to:
            candidates_qs = candidates_qs.filter(created_at__date__lte=date_to)
        if sel_status:
            candidates_qs = candidates_qs.filter(selection_status=sel_status)
        if med_status:
            candidates_qs = candidates_qs.filter(medical_status=med_status)
        if visa_status:
            candidates_qs = candidates_qs.filter(visa_stamping_status=visa_status)
        if client_type in ['b2b', 'b2c']:
            candidates_qs = candidates_qs.filter(client_type=client_type)
        if agent_filter:
            candidates_qs = candidates_qs.filter(Q(b2b_agent_id=agent_filter) | Q(agent_id=agent_filter))
        if staff_filter:
            candidates_qs = candidates_qs.filter(b2b_staff_id=staff_filter)
            
        candidates = list(candidates_qs)

        ALL_SECTORS_DEF = [
            {'key': 'selection', 'name': 'Selection & Grade', 'icon': 'fa-user-check', 'color': '#4f46e5'},
            {'key': 'medical', 'name': 'Medical Clearance', 'icon': 'fa-heart-pulse', 'color': '#10b981'},
            {'key': 'police_clearance', 'name': 'Police Clearance', 'icon': 'fa-shield-halved', 'color': '#f59e0b'},
            {'key': 'mofa', 'name': 'MOFA / Enjaz', 'icon': 'fa-file-shield', 'color': '#7c3aed'},
            {'key': 'fingerprint', 'name': 'Biometric / Finger', 'icon': 'fa-fingerprint', 'color': '#0284c7'},
            {'key': 'visa_stamping', 'name': 'Visa Stamping', 'icon': 'fa-passport', 'color': '#2563eb'},
            {'key': 'training', 'name': 'Training', 'icon': 'fa-chalkboard-user', 'color': '#0ea5e9'},
            {'key': 'manpower', 'name': 'Manpower / BMET', 'icon': 'fa-id-card', 'color': '#4f46e5'},
            {'key': 'flight', 'name': 'Flight & NOC', 'icon': 'fa-plane-departure', 'color': '#ef4444'},
        ]
        SECTOR_NAME_MAP = {s['key']: s['name'] for s in ALL_SECTORS_DEF}

        for c in candidates:
            secs = c.applicable_sectors if isinstance(c.applicable_sectors, list) else []
            if not secs:
                secs = [s['key'] for s in ALL_SECTORS_DEF]
            c.ordered_workflow = [
                {'key': s, 'name': SECTOR_NAME_MAP.get(s, s.replace('_', ' ').title()), 'step': idx + 1}
                for idx, s in enumerate(secs)
                if s in SECTOR_NAME_MAP
            ]
            c.sector_step_map = {s: idx + 1 for idx, s in enumerate(secs)}
            c.applicable_sectors_list = [s for s in secs if s in SECTOR_NAME_MAP]

        countries = list(Country.objects.using(db).filter(is_active=True).order_by('name'))
        agents = list(AgencyAgent.objects.using(db).filter(is_active=True))
        b2b_agents = [a for a in agents if getattr(a, 'agent_type', 'b2b') == 'b2b']
        b2b_staff_members = list(B2BAgentStaff.objects.using(db).filter(is_active=True).select_related('agent'))
        positions = list(AgencyPosition.objects.using(db).filter(is_active=True))
        companies = list(AgencyCompany.objects.using(db).filter(is_active=True))
        grades = list(SelectionGrade.objects.using(db).all())
        visa_lots = list(VisaLot.objects.using(db).filter(is_active=True))
        accounts = list(ChartOfAccount.objects.using(db).all())
        existing_vouchers = list(AccountVoucher.objects.using(db).all())
        
        totals = Candidate.objects.using(db).aggregate(
            total_value=Sum('total_amount'),
            total_paid=Sum('paid_amount'),
            total_due=Sum('due_amount')
        )
        total_candidates = Candidate.objects.using(db).count()
        selected_count = Candidate.objects.using(db).filter(selection_status='selected').count()
        medical_fit_count = Candidate.objects.using(db).filter(medical_status='fit').count()
        visa_completed_count = Candidate.objects.using(db).filter(visa_stamping_status='visa_completed').count()
        next_cr_serial = AccountVoucher.get_next_serial('cr_cash')

    except Exception:
        candidates = countries = agents = b2b_agents = b2b_staff_members = positions = companies = grades = visa_lots = accounts = existing_vouchers = []
        totals = {'total_value': 0, 'total_paid': 0, 'total_due': 0}
        total_candidates = selected_count = medical_fit_count = visa_completed_count = 0
        next_cr_serial = 'VCH-0001'

    context = {
        'candidates': candidates,
        'query': query,
        'selected_country': selected_country,
        'date_from': date_from,
        'date_to': date_to,
        'client_type': client_type,
        'agent_filter': agent_filter,
        'staff_filter': staff_filter,
        'countries': countries,
        'agents': agents,
        'b2b_agents': b2b_agents,
        'b2b_staff_members': b2b_staff_members,
        'positions': positions,
        'companies': companies,
        'grades': grades,
        'visa_lots': visa_lots,
        'total_candidates': total_candidates,
        'selected_count': selected_count,
        'medical_fit_count': medical_fit_count,
        'visa_completed_count': visa_completed_count,
        'total_package_value': totals['total_value'] or Decimal('0.00'),
        'total_collected': totals['total_paid'] or Decimal('0.00'),
        'total_due': totals['total_due'] or Decimal('0.00'),
        'accounts': accounts,
        'next_cr_serial': next_cr_serial,
        'existing_vouchers': existing_vouchers,
        'all_sectors_def': ALL_SECTORS_DEF,
    }
    return render(request, 'admin_panel/agency/candidate_list.html', context)


@login_required
def candidate_create(request):
    """Register a new candidate."""
    db = get_tenant_db(request)
    ensure_default_settings(db)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        passport_number = request.POST.get('passport_number', '').strip().upper()
        passport_expiry = request.POST.get('passport_expiry') or None
        date_of_birth = request.POST.get('date_of_birth') or None
        mobile = request.POST.get('mobile', '').strip()
        email = request.POST.get('email', '').strip()
        gender = request.POST.get('gender', 'male')
        country = request.POST.get('country', 'Saudi Arabia')
        interview_slot = request.POST.get('interview_slot', '').strip()
        notes = request.POST.get('notes', '').strip()

        agent_id = request.POST.get('agent')
        client_type = request.POST.get('client_type', 'b2c').strip().lower()
        if client_type not in ['b2b', 'b2c']:
            client_type = 'b2c'
        b2b_agent_id = request.POST.get('b2b_agent') or (agent_id if client_type == 'b2b' else None)
        b2b_staff_id = request.POST.get('b2b_staff')

        b2b_agent = AgencyAgent.objects.using(db).filter(pk=b2b_agent_id).first() if b2b_agent_id else None
        b2b_staff = B2BAgentStaff.objects.using(db).filter(pk=b2b_staff_id).first() if b2b_staff_id else None

        if client_type == 'b2b' and b2b_agent:
            agent = b2b_agent
        else:
            client_type = 'b2c'
            b2b_agent = None
            b2b_staff = None

        position_id = request.POST.get('position')
        company_id = request.POST.get('company')
        grade_id = request.POST.get('selection_grade')
        visa_lot_id = request.POST.get('visa_lot')

        total_amount_val = request.POST.get('total_amount', '0').strip()
        initial_payment_val = request.POST.get('initial_payment', '0').strip()
        payment_date_val = request.POST.get('payment_date') or timezone.now().date()
        payment_method = request.POST.get('payment_method', 'Cash')
        payment_ref = request.POST.get('reference_no', '').strip()

        agent = AgencyAgent.objects.using(db).filter(pk=agent_id).first() if agent_id else None
        position = AgencyPosition.objects.using(db).filter(pk=position_id).first() if position_id else None
        company = AgencyCompany.objects.using(db).filter(pk=company_id).first() if company_id else None
        grade = SelectionGrade.objects.using(db).filter(pk=grade_id).first() if grade_id else None
        visa_lot = VisaLot.objects.using(db).filter(pk=visa_lot_id).first() if visa_lot_id else None

        applicable_sectors = request.POST.getlist('applicable_sectors')

        if Candidate.objects.using(db).filter(passport_number=passport_number).exists():
            messages.error(request, f'A candidate with passport number "{passport_number}" already exists.')
            return redirect('admin_panel:candidate_list')

        try:
            total_amt = Decimal(str(total_amount_val)) if total_amount_val else Decimal('0.00')
        except Exception:
            total_amt = Decimal('0.00')

        if not total_amt and visa_lot and visa_lot.price:
            total_amt = Decimal(str(visa_lot.price))

        # Tag candidate with Agency Staff ownership
        agency_staff_id = request.user.id if request.user.is_tenant_staff else (
            b2b_agent.assigned_staff_id if (b2b_agent and b2b_agent.assigned_staff_id) else None
        )
        agency_staff_name = (request.user.get_full_name() or request.user.email) if request.user.is_tenant_staff else (
            b2b_agent.assigned_staff_name if (b2b_agent and b2b_agent.assigned_staff_name) else ''
        )

        cand = Candidate.objects.using(db).create(
            name=name,
            passport_number=passport_number,
            passport_expiry=passport_expiry,
            date_of_birth=date_of_birth,
            mobile=mobile,
            email=email,
            gender=gender,
            country=country,
            interview_slot=interview_slot,
            agent=agent,
            client_type=client_type,
            b2b_agent=b2b_agent,
            b2b_staff=b2b_staff,
            agency_staff_id=agency_staff_id,
            agency_staff_name=agency_staff_name,
            position=position,
            company=company,
            selection_grade=grade,
            visa_lot=visa_lot,
            total_amount=total_amt,
            applicable_sectors=applicable_sectors,
            notes=notes,
        )

        # Log B2B debit transaction if applicable
        if client_type == 'b2b' and b2b_agent and total_amt > 0:
            B2BTransaction.objects.using(db).create(
                agent=b2b_agent,
                staff=b2b_staff,
                agency_staff_id=agency_staff_id,
                agency_staff_name=agency_staff_name,
                candidate=cand,
                txn_type=B2BTransaction.TxnType.SERVICE_CHARGE,
                amount=total_amt,
                balance_after=b2b_agent.outstanding_balance + total_amt,
                description=f"Registration Service Fee: {cand.name} ({cand.registration_id})",
                reference_no=cand.registration_id,
                txn_date=payment_date_val or timezone.now().date()
            )
            b2b_agent.recalculate_outstanding(using=db)

        if visa_lot:
            visa_lot.update_assigned_count()

        if 'photo' in request.FILES:
            cand.photo = request.FILES['photo']
            cand.save()

        # Handle initial Sector Document Uploads from registration form
        sector_file_keys = [
            ('doc_passport', 'passport', 'Passport / Bio Data'),
            ('doc_selection', 'selection', 'Selection & Assessment Doc'),
            ('doc_medical', 'medical', 'Medical Report'),
            ('doc_police_clearance', 'police_clearance', 'Police Clearance Cert.'),
            ('doc_mofa', 'mofa', 'MOFA Document'),
            ('doc_enjaz', 'enjaz', 'Enjaz Receipt'),
            ('doc_fingerprint', 'fingerprint', 'Fingerprint Biometric Doc'),
            ('doc_visa_stamping', 'visa_stamping', 'Visa Copy / Stamping Doc'),
            ('doc_training', 'training', 'Training Certificate'),
            ('doc_manpower', 'manpower', 'BMET Smart Card / Manpower'),
            ('doc_flight', 'flight', 'Flight Ticket / NOC'),
            ('doc_other', 'other', 'General Document'),
        ]
        for field_key, sector_code, default_title in sector_file_keys:
            if field_key in request.FILES:
                file_obj = request.FILES[field_key]
                CandidateDocument.objects.using(db).create(
                    candidate=cand,
                    sector=sector_code,
                    title=f"{cand.name} - {default_title}",
                    file=file_obj,
                    notes='Uploaded during candidate registration'
                )

        # Handle Initial Payment if entered
        account_id = request.POST.get('account_id')
        voucher_no_val = request.POST.get('voucher_no', '').strip()
        init_paid = Decimal(initial_payment_val) if initial_payment_val else Decimal('0.00')
        if init_paid > 0:
            pay = CandidatePayment.objects.using(db).create(
                candidate=cand,
                amount=init_paid,
                payment_date=payment_date_val,
                payment_method=payment_method,
                reference_no=payment_ref,
                notes='Initial payment at candidate registration'
            )
            acc = ChartOfAccount.objects.using(db).filter(pk=account_id).first() if account_id else (ChartOfAccount.objects.using(db).filter(account_name__icontains='Cash').first() or ChartOfAccount.objects.using(db).first())
            if acc:
                v = None
                if voucher_no_val:
                    v = AccountVoucher.objects.using(db).filter(voucher_no=voucher_no_val).first()
                if not v:
                    v_type = 'cr_cheque' if payment_method == 'Cheque' else 'cr_cash'
                    v_kwargs = {
                        'voucher_type': v_type,
                        'account': acc,
                        'amount': init_paid,
                        'narration': f"Candidate Reg. Payment: {cand.name} ({cand.registration_id})",
                        'reference_no': payment_ref,
                        'voucher_date': payment_date_val
                    }
                    if voucher_no_val:
                        v_kwargs['voucher_no'] = voucher_no_val
                    v = AccountVoucher.objects.using(db).create(**v_kwargs)
                pay.voucher = v
                pay.save(using=db, update_fields=['voucher'])
                acc.current_balance += init_paid
                acc.save(using=db)

            # Record B2B transaction for initial payment
            if client_type == 'b2b' and b2b_agent:
                B2BTransaction.objects.using(db).create(
                    agent=b2b_agent,
                    staff=b2b_staff,
                    candidate=cand,
                    txn_type=B2BTransaction.TxnType.PAYMENT_RECEIVED,
                    amount=init_paid,
                    balance_after=max(Decimal('0.00'), b2b_agent.outstanding_balance - init_paid),
                    description=f"Initial Reg. Payment: {cand.name} ({cand.registration_id})",
                    reference_no=payment_ref or cand.registration_id,
                    txn_date=payment_date_val or timezone.now().date()
                )
                b2b_agent.recalculate_outstanding(using=db)

        messages.success(request, f'Candidate "{name}" registered successfully with Registration ID {cand.registration_id}!')
        return redirect('admin_panel:candidate_list')

    return redirect('admin_panel:candidate_list')


@login_required
def candidate_upload_document(request, pk):
    """Upload an attached document for any specific candidate recruitment sector."""
    candidate = get_object_or_404(Candidate, pk=pk)

    if request.method == 'POST':
        sector = request.POST.get('sector', 'other')
        title = request.POST.get('title', '').strip() or f"{candidate.get_sector_display if hasattr(candidate, 'get_sector_display') else sector.title()} Document"
        notes = request.POST.get('notes', '').strip()

        if 'file' in request.FILES:
            doc = CandidateDocument.objects.create(
                candidate=candidate,
                sector=sector,
                title=title,
                file=request.FILES['file'],
                notes=notes,
            )
            messages.success(request, f'Document "{doc.title}" attached successfully for {sector.replace("_"," ").title()}!')
        else:
            messages.error(request, 'Please choose a document file to upload.')

    next_url = request.META.get('HTTP_REFERER', 'admin_panel:candidate_list')
    return redirect(next_url)


@login_required
def candidate_delete_document(request, doc_pk):
    """Delete an attached candidate sector document."""
    doc = get_object_or_404(CandidateDocument, pk=doc_pk)
    title = doc.title
    cand_name = doc.candidate.name
    doc.delete()
    messages.success(request, f'Document "{title}" deleted for {cand_name}.')
    next_url = request.META.get('HTTP_REFERER', 'admin_panel:candidate_list')
    return redirect(next_url)


@login_required
def candidate_add_payment(request, pk):
    """Record a new payment installment for a candidate."""
    db = get_tenant_db(request)
    candidate = get_object_or_404(Candidate.objects.using(db), pk=pk)

    if request.method == 'POST':
        amount_str = request.POST.get('amount', '0').strip()
        payment_date_val = request.POST.get('payment_date') or timezone.now().date()
        payment_method = request.POST.get('payment_method', 'Cash')
        reference_no = request.POST.get('reference_no', '').strip()
        notes = request.POST.get('notes', '').strip()
        account_id = request.POST.get('account_id')
        voucher_no_val = request.POST.get('voucher_no', '').strip()

        try:
            amt = Decimal(amount_str)
        except Exception:
            amt = Decimal('0.00')

        if amt > 0:
            pay = CandidatePayment.objects.using(db).create(
                candidate=candidate,
                amount=amt,
                payment_date=payment_date_val,
                payment_method=payment_method,
                reference_no=reference_no,
                notes=notes,
            )
            acc = ChartOfAccount.objects.using(db).filter(pk=account_id).first() if account_id else (ChartOfAccount.objects.using(db).filter(account_name__icontains='Cash').first() or ChartOfAccount.objects.using(db).first())
            if acc:
                v = None
                if voucher_no_val:
                    v = AccountVoucher.objects.using(db).filter(voucher_no=voucher_no_val).first()
                if not v:
                    v_type = 'cr_cheque' if payment_method == 'Cheque' else 'cr_cash'
                    v_kwargs = {
                        'voucher_type': v_type,
                        'account': acc,
                        'amount': amt,
                        'narration': f"Candidate Payment: {candidate.name} ({candidate.registration_id})",
                        'reference_no': reference_no,
                        'voucher_date': payment_date_val
                    }
                    if voucher_no_val:
                        v_kwargs['voucher_no'] = voucher_no_val
                    v = AccountVoucher.objects.using(db).create(**v_kwargs)
                pay.voucher = v
                pay.save(using=db, update_fields=['voucher'])
                acc.current_balance += amt
                acc.save(using=db)

            # Record B2B ledger transaction if candidate is connected to a B2B agent
            if candidate.client_type == 'b2b' and candidate.b2b_agent:
                B2BTransaction.objects.using(db).create(
                    agent=candidate.b2b_agent,
                    staff=candidate.b2b_staff,
                    candidate=candidate,
                    txn_type=B2BTransaction.TxnType.PAYMENT_RECEIVED,
                    amount=amt,
                    balance_after=max(Decimal('0.00'), candidate.b2b_agent.outstanding_balance - amt),
                    description=f"Candidate Payment: {candidate.name} ({candidate.registration_id})",
                    reference_no=reference_no or candidate.registration_id,
                    txn_date=payment_date_val
                )
                candidate.b2b_agent.recalculate_outstanding(using=db)

            messages.success(request, f'Payment of ৳{amt:,.2f} recorded on {payment_date_val} for {candidate.name}!')
        else:
            messages.error(request, 'Please enter a valid payment amount greater than zero.')

    return redirect('admin_panel:candidate_list')


@login_required
def candidate_edit(request, pk):
    """Edit candidate details."""
    db = get_tenant_db(request)
    candidate = get_object_or_404(Candidate.objects.using(db), pk=pk)

    if request.method == 'POST':
        candidate.name = request.POST.get('name', '').strip()
        candidate.passport_number = request.POST.get('passport_number', '').strip().upper()
        if request.POST.get('passport_expiry'):
            candidate.passport_expiry = request.POST.get('passport_expiry')
        if request.POST.get('date_of_birth'):
            candidate.date_of_birth = request.POST.get('date_of_birth')
        candidate.mobile = request.POST.get('mobile', '').strip()
        candidate.email = request.POST.get('email', '').strip()
        candidate.gender = request.POST.get('gender', 'male')
        candidate.country = request.POST.get('country', 'Saudi Arabia')
        candidate.interview_slot = request.POST.get('interview_slot', '').strip()

        if 'total_amount' in request.POST:
            try:
                tot_val = Decimal(request.POST.get('total_amount', '0').strip() or '0')
                candidate.total_amount = max(Decimal('0.00'), tot_val)
                candidate.due_amount = max(Decimal('0.00'), candidate.total_amount - candidate.paid_amount)
            except Exception:
                pass

        agent_id = request.POST.get('agent')
        client_type = request.POST.get('client_type', candidate.client_type or 'b2c').strip().lower()
        b2b_agent_id = request.POST.get('b2b_agent') or (agent_id if client_type == 'b2b' else None)
        b2b_staff_id = request.POST.get('b2b_staff')

        if client_type == 'b2b' and b2b_agent_id:
            candidate.client_type = 'b2b'
            candidate.b2b_agent = AgencyAgent.objects.using(db).filter(pk=b2b_agent_id).first()
            candidate.b2b_staff = B2BAgentStaff.objects.using(db).filter(pk=b2b_staff_id).first() if b2b_staff_id else None
            candidate.agent = candidate.b2b_agent
        else:
            candidate.client_type = 'b2c'
            candidate.b2b_agent = None
            candidate.b2b_staff = None
            candidate.agent = AgencyAgent.objects.using(db).filter(pk=agent_id).first() if agent_id else None

        position_id = request.POST.get('position')
        company_id = request.POST.get('company')
        grade_id = request.POST.get('selection_grade')
        visa_lot_id = request.POST.get('visa_lot')

        candidate.position = AgencyPosition.objects.using(db).filter(pk=position_id).first() if position_id else None
        candidate.company = AgencyCompany.objects.using(db).filter(pk=company_id).first() if company_id else None
        candidate.selection_grade = SelectionGrade.objects.using(db).filter(pk=grade_id).first() if grade_id else None
        if visa_lot_id:
            old_lot = candidate.visa_lot
            candidate.visa_lot = VisaLot.objects.using(db).filter(pk=visa_lot_id).first()
            if old_lot and old_lot != candidate.visa_lot:
                old_lot.update_assigned_count()
            if candidate.visa_lot:
                candidate.visa_lot.update_assigned_count()

        if 'applicable_sectors_submitted' in request.POST or 'applicable_sectors' in request.POST:
            candidate.applicable_sectors = request.POST.getlist('applicable_sectors')

        if 'photo' in request.FILES:
            candidate.photo = request.FILES['photo']

        candidate.save(using=db)
        messages.success(request, f'Candidate "{candidate.name}" updated successfully!')
        return redirect('admin_panel:candidate_list')

    return redirect('admin_panel:candidate_list')


@login_required
def candidate_update_package_fee(request, pk):
    """Update agreed total package fee for a candidate and recalculate due balance."""
    db = get_tenant_db(request)
    candidate = get_object_or_404(Candidate.objects.using(db), pk=pk)
    if request.method == 'POST':
        fee_raw = request.POST.get('total_amount', '').strip()
        try:
            old_fee = candidate.total_amount
            new_fee = Decimal(fee_raw)
            if new_fee < Decimal('0.00'):
                new_fee = Decimal('0.00')
            candidate.total_amount = new_fee
            candidate.due_amount = max(Decimal('0.00'), new_fee - candidate.paid_amount)
            candidate.save(using=db, update_fields=['total_amount', 'due_amount'])

            # Log adjustment in B2B ledger if linked to B2B Agent
            if candidate.client_type == 'b2b' and candidate.b2b_agent:
                diff = new_fee - old_fee
                if diff != Decimal('0.00'):
                    txn_t = B2BTransaction.TxnType.ADJUSTMENT_DEBIT if diff > 0 else B2BTransaction.TxnType.ADJUSTMENT_CREDIT
                    B2BTransaction.objects.using(db).create(
                        agent=candidate.b2b_agent,
                        staff=candidate.b2b_staff,
                        candidate=candidate,
                        txn_type=txn_t,
                        amount=abs(diff),
                        balance_after=candidate.b2b_agent.outstanding_balance + diff,
                        description=f"Fee adjustment for {candidate.name} ({candidate.registration_id}) from ৳{old_fee:,.2f} to ৳{new_fee:,.2f}",
                        txn_date=timezone.now().date()
                    )
                    candidate.b2b_agent.recalculate_outstanding(using=db)

            messages.success(request, f'Total package fee for {candidate.registration_id} ({candidate.name}) updated to ৳{new_fee:,.2f}!')
        except Exception as e:
            messages.error(request, f'Invalid package fee amount: {e}')
    next_url = request.META.get('HTTP_REFERER', 'admin_panel:candidate_list')
    return redirect(next_url)


@login_required
def candidate_delete(request, pk):
    """Delete a candidate."""
    db = get_tenant_db(request)
    candidate = get_object_or_404(Candidate.objects.using(db), pk=pk)
    name = candidate.name
    reg_id = candidate.registration_id
    candidate.delete()
    messages.success(request, f'Candidate {name} ({reg_id}) deleted successfully.')
    return redirect('admin_panel:candidate_list')


@login_required
def candidate_download(request, pk):
    """Download candidate info summary + all uploaded documents as a ZIP file."""
    import zipfile
    import io
    import os
    from django.http import HttpResponse

    candidate = get_object_or_404(Candidate, pk=pk)

    # Build text summary
    lines = [
        f"CANDIDATE INFORMATION SHEET",
        f"=" * 50,
        f"Registration ID   : {candidate.registration_id}",
        f"Full Name         : {candidate.name}",
        f"Passport No.      : {candidate.passport_number}",
        f"Passport Expiry   : {candidate.passport_expiry or '—'}",
        f"Date of Birth     : {candidate.date_of_birth or '—'}",
        f"Gender            : {candidate.get_gender_display()}",
        f"Mobile            : {candidate.mobile or '—'}",
        f"Email             : {candidate.email or '—'}",
        f"Country           : {candidate.country}",
        f"Interview Slot    : {candidate.interview_slot or '—'}",
        f"Position          : {candidate.position or '—'}",
        f"Agent             : {candidate.agent or '—'}",
        f"Company/Sponsor   : {candidate.company or '—'}",
        f"Selection Grade   : {candidate.selection_grade or '—'}",
        f"Visa Lot          : {candidate.visa_lot.title if candidate.visa_lot else '—'}",
        f"Registered On     : {candidate.created_at.strftime('%Y-%m-%d')}",
        f"",
        f"FINANCIAL SUMMARY",
        f"-" * 30,
        f"Total Fee         : ৳{candidate.total_amount:.2f}",
        f"Total Paid        : ৳{candidate.paid_amount:.2f}",
        f"Due Balance       : ৳{candidate.due_amount:.2f}",
        f"",
        f"WORKFLOW STAGES",
        f"-" * 30,
        f"Selection         : {candidate.get_selection_status_display()}",
        f"Delegate          : {candidate.get_delegate_status_display()}",
        f"Medical           : {candidate.get_medical_status_display()}",
        f"Medical Clinic    : {candidate.medical_clinic or '—'}",
        f"Police Clearance  : {candidate.get_police_clearance_status_display()}",
        f"PC Reference      : {candidate.police_clearance_ref or '—'}",
        f"MOFA Status       : {candidate.get_mofa_status_display()}",
        f"MOFA Number       : {candidate.mofa_number or '—'}",
        f"Fingerprint       : {candidate.get_finger_status_display()}",
        f"Visa Stamping     : {candidate.get_visa_stamping_status_display()}",
        f"Visa Number       : {candidate.visa_number or '—'}",
        f"Training          : {candidate.get_training_status_display()}",
        f"Manpower          : {candidate.get_manpower_status_display()}",
        f"BMET Card         : {candidate.bmet_card_number or '—'}",
        f"Ticket Status     : {candidate.get_ticket_status_display()}",
        f"Airline           : {candidate.airline or '—'}",
        f"PNR Number        : {candidate.pnr_number or '—'}",
        f"NOC Status        : {candidate.get_noc_status_display()}",
        f"",
        f"PAYMENT HISTORY",
        f"-" * 30,
    ]
    for p in candidate.payments.all():
        lines.append(
            f"  {p.payment_date}  ৳{p.amount:.2f}  [{p.payment_method}]"
            + (f"  Voucher: {p.voucher.voucher_no}" if p.voucher else "")
            + (f"  Ref: {p.reference_no}" if p.reference_no else "")
        )
    if not candidate.payments.exists():
        lines.append("  No payments recorded.")
    lines.append("")
    lines.append(f"ATTACHED DOCUMENTS")
    lines.append(f"-" * 30)
    for doc in candidate.documents.all():
        lines.append(f"  [{doc.get_sector_display()}]  {doc.title}  —  Uploaded: {doc.uploaded_at.strftime('%Y-%m-%d')}")
    if not candidate.documents.exists():
        lines.append("  No documents uploaded.")
    if candidate.notes:
        lines.extend(["", f"NOTES", f"-" * 30, candidate.notes])

    info_text = "\n".join(lines)

    # Build ZIP in memory
    zip_buffer = io.BytesIO()
    safe_name = "".join(c for c in candidate.name if c.isalnum() or c in " _-").strip().replace(" ", "_")
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add info text
        zf.writestr(f"{candidate.registration_id}_{safe_name}_info.txt", info_text.encode('utf-8'))

        # Add each document file
        for doc in candidate.documents.all():
            try:
                file_path = doc.file.path
                if os.path.exists(file_path):
                    sector_label = doc.get_sector_display().replace(" ", "_").replace("/", "-")
                    ext = os.path.splitext(file_path)[1]
                    archive_name = f"documents/{sector_label}_{doc.id}{ext}"
                    zf.write(file_path, archive_name)
            except Exception:
                pass

    zip_buffer.seek(0)
    response = HttpResponse(zip_buffer.read(), content_type='application/zip')
    response['Content-Disposition'] = (
        f'attachment; filename="{candidate.registration_id}_{safe_name}_files.zip"'
    )
    return response


@login_required
def candidate_invoice(request, pk):
    """Display and optionally save editable invoice for a candidate."""
    get_tenant_db(request)
    candidate = get_object_or_404(Candidate, pk=pk)

    if request.method == 'POST':
        # Save editable invoice fields back to candidate
        invoice_title = request.POST.get('invoice_title', '').strip()
        invoice_notes = request.POST.get('invoice_notes', '').strip()
        total_amount_raw = request.POST.get('total_amount', '').strip()

        if total_amount_raw:
            try:
                candidate.total_amount = Decimal(total_amount_raw)
            except Exception:
                pass

        if invoice_notes:
            candidate.notes = invoice_notes
        candidate.save()
        messages.success(request, f'Invoice for {candidate.name} saved successfully!')

    payments = candidate.payments.all()
    context = {
        'candidate': candidate,
        'payments': payments,
        'invoice_number': f'INV-{candidate.registration_id}',
    }
    return render(request, 'admin_panel/agency/candidate_invoice.html', context)

@login_required
def candidate_id_card_bulk(request):
    """Bulk ID Card Print View."""
    db = get_tenant_db(request)
    cand_ids = request.GET.getlist('ids')
    if cand_ids:
        candidates = Candidate.objects.using(db).filter(id__in=cand_ids)
    else:
        candidates = Candidate.objects.using(db).all()[:12]

    # Mark as printed
    for c in candidates:
        if not c.id_card_printed:
            c.id_card_printed = True
            c.save(using=db)

    return render(request, 'admin_panel/agency/id_card_bulk.html', {'candidates': candidates})


# ── 2. CONNECTED WORKFLOW STAGE MANAGEMENT ─────────────────────────────────
@login_required
def candidate_update_stage(request, pk):
    """Quick 1-click updates for candidate connected workflow stages with document attachment."""
    candidate = get_object_or_404(Candidate, pk=pk)

    if request.method == 'POST':
        # Selection & Delegate
        if 'selection_status' in request.POST:
            candidate.selection_status = request.POST.get('selection_status')
        if 'delegate_status' in request.POST:
            candidate.delegate_status = request.POST.get('delegate_status')

        # Medical & PC
        if 'medical_status' in request.POST:
            candidate.medical_status = request.POST.get('medical_status')
            candidate.medical_clinic = request.POST.get('medical_clinic', candidate.medical_clinic)
            if request.POST.get('medical_date'):
                candidate.medical_date = request.POST.get('medical_date')

        if 'police_clearance_status' in request.POST:
            candidate.police_clearance_status = request.POST.get('police_clearance_status')
            candidate.police_clearance_ref = request.POST.get('police_clearance_ref', candidate.police_clearance_ref)

        # Visa Section
        if 'mofa_status' in request.POST:
            candidate.mofa_status = request.POST.get('mofa_status')
            candidate.mofa_number = request.POST.get('mofa_number', candidate.mofa_number)

        if 'enjaz_status' in request.POST:
            candidate.enjaz_status = request.POST.get('enjaz_status')
            candidate.enjaz_number = request.POST.get('enjaz_number', candidate.enjaz_number)

        if 'finger_status' in request.POST:
            candidate.finger_status = request.POST.get('finger_status')

        if 'visa_stamping_status' in request.POST:
            candidate.visa_stamping_status = request.POST.get('visa_stamping_status')
            candidate.visa_number = request.POST.get('visa_number', candidate.visa_number)

        # Manpower Assessment
        if 'training_status' in request.POST:
            candidate.training_status = request.POST.get('training_status')
        if 'manpower_status' in request.POST:
            candidate.manpower_status = request.POST.get('manpower_status')
            candidate.bmet_card_number = request.POST.get('bmet_card_number', candidate.bmet_card_number)

        # Flight & NOC
        if 'ticket_status' in request.POST:
            candidate.ticket_status = request.POST.get('ticket_status')
            candidate.airline = request.POST.get('airline', candidate.airline)
            candidate.pnr_number = request.POST.get('pnr_number', candidate.pnr_number)

        if 'noc_status' in request.POST:
            candidate.noc_status = request.POST.get('noc_status')

        candidate.save()

        # Handle optional sector document uploaded during stage update
        stage_sector = request.POST.get('stage_sector')
        if stage_sector and 'stage_document' in request.FILES:
            file_obj = request.FILES['stage_document']
            doc_title = request.POST.get('document_title', '').strip() or f"{candidate.name} - {stage_sector.replace('_', ' ').title()} Attachment"
            CandidateDocument.objects.create(
                candidate=candidate,
                sector=stage_sector,
                title=doc_title,
                file=file_obj,
                notes=f'Uploaded via {stage_sector.replace("_", " ").title()} stage update modal'
            )

        messages.success(request, f'Updated workflow stage status for {candidate.name}!')

    next_url = request.META.get('HTTP_REFERER', 'admin_panel:candidate_list')
    return redirect(next_url)


@login_required
def stage_view(request, stage_name):
    """
    Universal view to display filtered candidate stages:
    - selection, delegate, medical, police, visa_section, manpower, flight
    """
    db = get_tenant_db(request)
    ensure_default_settings(db)

    active_sub = request.GET.get('sub', 'all')
    
    try:
        candidates_qs = Candidate.objects.using(db).all()
        title = "Stage Management"
        sub_tabs = []

        if stage_name == 'selection':
            title = "Selection Grading (Primary)"
            sub_tabs = [
                ('all', 'All Candidates'),
                ('pending', 'Pending'),
                ('selected', 'Selected'),
                ('awaiting', 'Awaiting'),
                ('rejected', 'Rejected')
            ]
            if active_sub != 'all':
                candidates_qs = candidates_qs.filter(selection_status=active_sub)

        elif stage_name == 'delegate':
            title = "Delegate Approval"
            sub_tabs = [
                ('all', 'All'),
                ('pending', 'Pending'),
                ('approved', 'Approved')
            ]
            if active_sub != 'all':
                candidates_qs = candidates_qs.filter(delegate_status=active_sub)

        elif stage_name == 'medical':
            title = "Medical Assessment"
            sub_tabs = [
                ('all', 'All'),
                ('pending', 'Pending'),
                ('fit', 'Fit'),
                ('unfit', 'Unfit'),
                ('expired', 'Expired'),
                ('canceled', 'Canceled')
            ]
            if active_sub != 'all':
                candidates_qs = candidates_qs.filter(medical_status=active_sub)

        elif stage_name == 'police':
            title = "Police Clearance"
            sub_tabs = [
                ('all', 'All'),
                ('pending', 'Pending'),
                ('cleared', 'Cleared'),
                ('uncleared', 'Uncleared')
            ]
            if active_sub != 'all':
                candidates_qs = candidates_qs.filter(police_clearance_status=active_sub)

        elif stage_name == 'visa_section':
            title = "Visa Section Operations"
            sub_tabs = [
                ('all', 'All'),
                ('mofa_pending', 'Mofa Pending'),
                ('enjaz_pending', 'Enjaz/Money Trans. Pending'),
                ('mofa_cleared', 'Mofa Cleared'),
                ('finger_pending', 'Finger Pending'),
                ('finger_completed', 'Finger Completed'),
                ('visa_pending', 'Visa Pending'),
                ('visa_completed', 'Visa Completed')
            ]
            if active_sub == 'mofa_pending':
                candidates_qs = candidates_qs.filter(mofa_status='mofa_pending')
            elif active_sub == 'mofa_cleared':
                candidates_qs = candidates_qs.filter(mofa_status='mofa_cleared')
            elif active_sub == 'enjaz_pending':
                candidates_qs = candidates_qs.filter(enjaz_status='enjaz_pending')
            elif active_sub == 'finger_pending':
                candidates_qs = candidates_qs.filter(finger_status='finger_pending')
            elif active_sub == 'finger_completed':
                candidates_qs = candidates_qs.filter(finger_status='finger_completed')
            elif active_sub == 'visa_pending':
                candidates_qs = candidates_qs.filter(visa_stamping_status='visa_pending')
            elif active_sub == 'visa_completed':
                candidates_qs = candidates_qs.filter(visa_stamping_status='visa_completed')

        elif stage_name == 'manpower':
            title = "Manpower Assessment"
            sub_tabs = [
                ('all', 'All'),
                ('training_pending', 'Training Pending'),
                ('training_completed', 'Training Completed'),
                ('manpower_pending', 'Manpower Approval'),
                ('manpower_completed', 'Manpower Completed')
            ]
            if active_sub == 'training_pending':
                candidates_qs = candidates_qs.filter(training_status='training_pending')
            elif active_sub == 'training_completed':
                candidates_qs = candidates_qs.filter(training_status='training_completed')
            elif active_sub == 'manpower_pending':
                candidates_qs = candidates_qs.filter(manpower_status='manpower_pending')
            elif active_sub == 'manpower_completed':
                candidates_qs = candidates_qs.filter(manpower_status='manpower_completed')

        elif stage_name == 'flight':
            title = "Flight Management & NOC"
            sub_tabs = [
                ('all', 'All'),
                ('agency', 'Travel Agency List'),
                ('ticket_issue', 'Ticket Issue'),
                ('ticket_pending', 'Ticket Pending'),
                ('ticket_completed', 'Ticket Completed'),
                ('noc_pending', 'NOC Approval'),
                ('noc_completed', 'NOC Completed')
            ]
            if active_sub == 'ticket_issue':
                candidates_qs = candidates_qs.filter(ticket_status='ticket_issue')
            elif active_sub == 'ticket_pending':
                candidates_qs = candidates_qs.filter(ticket_status='ticket_pending')
            elif active_sub == 'ticket_completed':
                candidates_qs = candidates_qs.filter(ticket_status='ticket_completed')
            elif active_sub == 'noc_pending':
                candidates_qs = candidates_qs.filter(noc_status='noc_pending')
            elif active_sub == 'noc_completed':
                candidates_qs = candidates_qs.filter(noc_status='noc_completed')
            
        candidates = list(candidates_qs)
    except Exception:
        candidates = []
        if 'title' not in locals():
            title = "Stage Management"
            sub_tabs = []

    context = {
        'stage_name': stage_name,
        'title': title,
        'sub_tabs': sub_tabs,
        'active_sub': active_sub,
        'candidates': candidates,
    }
    return render(request, 'admin_panel/agency/stage_management.html', context)


# ── 3. VISA LOT MANAGEMENT ───────────────────────────────────────────────────
@login_required
def okala_list(request):
    """Manage Visa Lots (displayed on agency website when show_on_website=True)."""
    db = get_tenant_db(request)
    ensure_default_settings(db)
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_lot':
            title = request.POST.get('title', '').strip() or 'Visa Lot'
            country = request.POST.get('country', 'Saudi Arabia').strip()
            quota = request.POST.get('quota', '1')
            visa_type = request.POST.get('visa_type', 'work')
            price_raw = request.POST.get('price', '').strip()
            processing_time = request.POST.get('processing_time', '').strip()
            description = request.POST.get('description', '').strip()
            requirements = request.POST.get('requirements', '').strip()
            sponsor_name = request.POST.get('sponsor_name', '').strip()
            sponsor_id = request.POST.get('sponsor_id', '').strip()
            show_on_website = request.POST.get('show_on_website') == 'on'

            if country and not Country.objects.using(db).filter(name__iexact=country).exists():
                Country.objects.using(db).create(name=country, is_active=True)

            lot = VisaLot(
                title=title,
                country=country,
                quota=int(quota) if quota.isdigit() else 1,
                visa_type=visa_type,
                price=Decimal(price_raw) if price_raw else None,
                processing_time=processing_time,
                description=description,
                requirements=requirements,
                sponsor_name=sponsor_name,
                sponsor_id=sponsor_id,
                show_on_website=show_on_website,
                is_active=True,
            )
            if 'featured_image' in request.FILES:
                lot.featured_image = request.FILES['featured_image']
            lot.save(using=db)
            messages.success(request, f'Visa Lot "{title}" ({lot.lot_number}) added successfully!')

        elif action == 'quick_add_country':
            name = request.POST.get('name', '').strip()
            code = request.POST.get('code', '').strip().upper()
            if name:
                if not Country.objects.using(db).filter(name__iexact=name).exists():
                    Country.objects.using(db).create(name=name, code=code if code else None, is_active=True)
                    messages.success(request, f'Country "{name}" added successfully! You can now select it.')
                else:
                    messages.info(request, f'Country "{name}" already exists.')
            else:
                messages.error(request, 'Country name is required.')
            return redirect('admin_panel:okala_list')

        elif action == 'toggle_lot':
            lot_id = request.POST.get('lot_id')
            lot = VisaLot.objects.using(db).filter(pk=lot_id).first()
            if lot:
                lot.is_active = not lot.is_active
                lot.save(using=db)
                status_label = 'Active' if lot.is_active else 'Closed'
                messages.success(request, f'Visa Lot "{lot.title}" is now {status_label}.')

        elif action == 'edit_lot':
            lot_id = request.POST.get('lot_id')
            lot = VisaLot.objects.using(db).filter(pk=lot_id).first()
            if lot:
                lot.title = request.POST.get('title', '').strip() or 'Visa Lot'
                lot.country = request.POST.get('country', 'Saudi Arabia').strip()
                if lot.country and not Country.objects.using(db).filter(name__iexact=lot.country).exists():
                    Country.objects.using(db).create(name=lot.country, is_active=True)
                quota = request.POST.get('quota', '1')
                lot.quota = int(quota) if quota.isdigit() else 1
                lot.visa_type = request.POST.get('visa_type', 'work')
                price_raw = request.POST.get('price', '').strip()
                lot.price = Decimal(price_raw) if price_raw else None
                lot.processing_time = request.POST.get('processing_time', '').strip()
                lot.description = request.POST.get('description', '').strip()
                lot.requirements = request.POST.get('requirements', '').strip()
                lot.sponsor_name = request.POST.get('sponsor_name', '').strip()
                lot.sponsor_id = request.POST.get('sponsor_id', '').strip()
                lot.show_on_website = request.POST.get('show_on_website') == 'on'

                if 'featured_image' in request.FILES:
                    lot.featured_image = request.FILES['featured_image']
                
                lot.save(using=db)
                messages.success(request, f'Visa Lot "{lot.title}" ({lot.lot_number}) updated successfully!')

        elif action == 'delete_lot':
            lot_id = request.POST.get('lot_id')
            lot = VisaLot.objects.using(db).filter(pk=lot_id).first()
            if lot:
                title = lot.title
                lot.delete()
                messages.success(request, f'Visa Lot "{title}" deleted successfully.')

        return redirect('admin_panel:okala_list')

    try:
        visa_lots = list(VisaLot.objects.using(db).all())
    except Exception:
        visa_lots = []
    
    countries = list(Country.objects.using(db).filter(is_active=True).order_by('name'))
    return render(request, 'admin_panel/agency/okala_list.html', {
        'visa_lots': visa_lots,
        'countries': countries,
    })


# ── 4. FINANCIAL REQUISITIONS & ACCOUNTS ────────────────────────────────────
@login_required
def requisitions_list(request):
    """Payment, Receipt, and Contra Requisitions view."""
    db = get_tenant_db(request)
    req_type = request.GET.get('type', 'all')
    
    try:
        requisitions_qs = Requisition.objects.using(db).all()
        if req_type == 'payment':
            requisitions = list(requisitions_qs.filter(category__startswith='payment'))
        elif req_type == 'receipt':
            requisitions = list(requisitions_qs.filter(category__startswith='receipt'))
        elif req_type == 'contra':
            requisitions = list(requisitions_qs.filter(category='contra'))
        else:
            requisitions = list(requisitions_qs)
    except Exception:
        requisitions = []

    if request.method == 'POST':
        category = request.POST.get('category')
        payee_or_payer = request.POST.get('payee_or_payer', '').strip()
        amount = request.POST.get('amount', '0')
        purpose = request.POST.get('purpose', '').strip()
        from_acc = request.POST.get('transfer_from_account', '').strip()
        to_acc = request.POST.get('transfer_to_account', '').strip()

        Requisition.objects.using(db).create(
            category=category,
            payee_or_payer=payee_or_payer,
            amount=Decimal(amount),
            purpose=purpose,
            transfer_from_account=from_acc,
            transfer_to_account=to_acc,
        )
        messages.success(request, 'Requisition created successfully!')
        return redirect('admin_panel:requisitions_list')

    context = {
        'requisitions': requisitions,
        'req_type': req_type,
    }
    return render(request, 'admin_panel/agency/requisitions.html', context)


@login_required
def accounts_vouchers(request):
    """Chart of Accounts & Vouchers (Bank, Cash Payment, Cheque/Cash Receipt, Journal)."""
    db = get_tenant_db(request)
    ensure_default_settings(db)

    active_tab = request.GET.get('tab', 'vouchers')
    
    try:
        vouchers = list(AccountVoucher.objects.using(db).all())
        accounts = list(ChartOfAccount.objects.using(db).all())
        groups = list(AccountHeadGroup.objects.using(db).all())
    except Exception:
        vouchers = []
        accounts = []
        groups = []

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_voucher':
            voucher_type = request.POST.get('voucher_type')
            account_id = request.POST.get('account_id')
            amount = request.POST.get('amount', '0')
            narration = request.POST.get('narration', '').strip()
            reference_no = request.POST.get('reference_no', '').strip()

            acc = get_object_or_404(ChartOfAccount.objects.using(db), pk=account_id)
            v = AccountVoucher.objects.using(db).create(
                voucher_type=voucher_type,
                account=acc,
                amount=Decimal(amount),
                narration=narration,
                reference_no=reference_no,
            )
            # update balance
            if voucher_type in ['cr_cash', 'cr_cheque']:
                acc.current_balance += Decimal(amount)
            else:
                acc.current_balance -= Decimal(amount)
            acc.save(using=db)

            messages.success(request, f'Voucher {v.voucher_no} recorded successfully!')

        elif action == 'add_account':
            account_name = request.POST.get('account_name', '').strip()
            account_code = request.POST.get('account_code', '').strip()
            head_group_id = request.POST.get('head_group_id')
            tds_section = request.POST.get('tds_section', '').strip()
            balance = request.POST.get('balance', '0')

            grp = get_object_or_404(AccountHeadGroup.objects.using(db), pk=head_group_id)
            ChartOfAccount.objects.using(db).create(
                account_name=account_name,
                account_code=account_code,
                head_group=grp,
                tds_section=tds_section,
                current_balance=Decimal(balance),
            )
            messages.success(request, f'Account Head [{account_code}] {account_name} created successfully!')

        elif action == 'edit_account':
            account_id = request.POST.get('account_id')
            acc = get_object_or_404(ChartOfAccount.objects.using(db), pk=account_id)
            acc.account_name = request.POST.get('account_name', '').strip()
            acc.account_code = request.POST.get('account_code', '').strip()
            head_group_id = request.POST.get('head_group_id')
            if head_group_id:
                acc.head_group = get_object_or_404(AccountHeadGroup.objects.using(db), pk=head_group_id)
            acc.tds_section = request.POST.get('tds_section', '').strip()
            balance_val = request.POST.get('balance', '0').strip()
            try:
                acc.current_balance = Decimal(balance_val)
            except Exception:
                pass
            acc.save(using=db)
            messages.success(request, f'Account Head [{acc.account_code}] {acc.account_name} updated successfully!')

        elif action == 'delete_account':
            account_id = request.POST.get('account_id')
            acc = get_object_or_404(ChartOfAccount.objects.using(db), pk=account_id)
            acc_name = acc.account_name
            if acc.vouchers.exists():
                messages.error(request, f'Cannot delete account "{acc_name}" because it has {acc.vouchers.count()} recorded voucher(s).')
            else:
                acc.delete()
                messages.success(request, f'Account "{acc_name}" deleted successfully.')

        elif action == 'edit_voucher':
            voucher_id = request.POST.get('voucher_id')
            v = get_object_or_404(AccountVoucher.objects.using(db), pk=voucher_id)
            old_acc = v.account
            old_amount = v.amount
            old_type = v.voucher_type

            # Reverse old balance effect
            if old_type in ['cr_cash', 'cr_cheque']:
                old_acc.current_balance -= old_amount
            else:
                old_acc.current_balance += old_amount
            old_acc.save(using=db)

            new_type = request.POST.get('voucher_type', old_type)
            new_account_id = request.POST.get('account_id')
            new_amount_str = request.POST.get('amount', str(old_amount))
            narration = request.POST.get('narration', '').strip()
            reference_no = request.POST.get('reference_no', '').strip()

            new_acc = get_object_or_404(ChartOfAccount.objects.using(db), pk=new_account_id) if new_account_id else old_acc
            try:
                new_amount = Decimal(new_amount_str)
            except Exception:
                new_amount = old_amount

            v.voucher_type = new_type
            v.account = new_acc
            v.amount = new_amount
            v.narration = narration
            v.reference_no = reference_no
            v.save(using=db)

            # Apply new balance effect
            new_acc.refresh_from_db()
            if new_type in ['cr_cash', 'cr_cheque']:
                new_acc.current_balance += new_amount
            else:
                new_acc.current_balance -= new_amount
            new_acc.save(using=db)

            messages.success(request, f'Voucher {v.voucher_no} updated successfully!')

        elif action == 'delete_voucher':
            voucher_id = request.POST.get('voucher_id')
            v = get_object_or_404(AccountVoucher.objects.using(db), pk=voucher_id)
            v_no = v.voucher_no
            acc = v.account
            if v.voucher_type in ['cr_cash', 'cr_cheque']:
                acc.current_balance -= v.amount
            else:
                acc.current_balance += v.amount
            acc.save(using=db)
            v.delete()
            messages.success(request, f'Voucher {v_no} deleted successfully.')

        url = reverse('admin_panel:accounts_vouchers')
        if active_tab:
            url += f'?tab={active_tab}'
        return redirect(url)

    context = {
        'active_tab': active_tab,
        'vouchers': vouchers,
        'accounts': accounts,
        'groups': groups,
    }
    return render(request, 'admin_panel/agency/accounts_vouchers.html', context)


# ── 5. HR & DAILY MOVEMENT / LEAVE ──────────────────────────────────────────
@login_required
def hr_movement_leave(request):
    """Daily Movement log and Leave submissions."""
    db = get_tenant_db(request)
    try:
        movements = list(DailyMovement.objects.using(db).all())
        leaves = list(LeaveSubmission.objects.using(db).all())
    except Exception:
        movements = []
        leaves = []

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_movement':
            person_name = request.POST.get('person_name', '').strip()
            purpose = request.POST.get('purpose', '').strip()
            destination = request.POST.get('destination', '').strip()

            DailyMovement.objects.using(db).create(
                person_name=person_name,
                purpose=purpose,
                destination=destination,
                status='pending'
            )
            messages.success(request, 'Daily Movement request submitted!')

        elif action == 'add_leave':
            employee_name = request.POST.get('employee_name', '').strip()
            leave_type = request.POST.get('leave_type', 'casual')
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            reason = request.POST.get('reason', '').strip()

            LeaveSubmission.objects.using(db).create(
                employee_name=employee_name,
                leave_type=leave_type,
                start_date=start_date,
                end_date=end_date,
                reason=reason,
                status='pending'
            )
            messages.success(request, 'Leave application submitted!')

        return redirect('admin_panel:hr_movement_leave')

    return render(request, 'admin_panel/agency/hr_movement_leave.html', {
        'movements': movements,
        'leaves': leaves
    })


# ── 6. INTEGRATED REPORTS HUB ────────────────────────────────────────────────
@login_required
def reports_hub(request):
    """Dynamic Reports Engine covering all 14 Agency Reports."""
    db = get_tenant_db(request)
    report_type = request.GET.get('report', 'summary')
    title = "Summary Report"

    data = []
    headers = []

    candidates = Candidate.objects.using(db).all()

    if report_type == 'agent_ledger':
        title = "Agent Ledger Report"
        headers = ['Agent Name', 'Code', 'Phone', 'Assigned Candidates', 'Balance / Commission']
        agents = AgencyAgent.objects.using(db).all()
        for a in agents:
            data.append({
                'col1': a.name,
                'col2': a.agent_code,
                'col3': a.phone or 'N/A',
                'col4': a.candidates.count(),
                'col5': f"৳{a.balance:,.2f}"
            })

    elif report_type == 'registration_report':
        title = "Registration Report"
        headers = ['Reg ID', 'Candidate Name', 'Passport No', 'Mobile', 'Position', 'Country', 'Reg Date']
        for c in candidates:
            data.append({
                'col1': c.registration_id,
                'col2': c.name,
                'col3': c.passport_number,
                'col4': c.mobile or 'N/A',
                'col5': c.position.title if c.position else 'N/A',
                'col6': c.country,
                'col7': c.created_at.strftime('%Y-%m-%d')
            })

    elif report_type == 'available_reg':
        title = "Available Registration List"
        headers = ['Reg ID', 'Candidate Name', 'Passport No', 'Interview Slot', 'Status']
        for c in candidates.filter(selection_status='pending'):
            data.append({
                'col1': c.registration_id,
                'col2': c.name,
                'col3': c.passport_number,
                'col4': c.interview_slot or 'Standard Slot',
                'col5': 'Available for Selection'
            })

    elif report_type == 'selection_grading':
        title = "Selection Grading Report"
        headers = ['Reg ID', 'Candidate Name', 'Passport No', 'Grade', 'Selection Status']
        for c in candidates:
            data.append({
                'col1': c.registration_id,
                'col2': c.name,
                'col3': c.passport_number,
                'col4': c.selection_grade.grade_name if c.selection_grade else 'Unassigned',
                'col5': c.get_selection_status_display()
            })

    elif report_type == 'passport_report':
        title = "Passport Status Report"
        headers = ['Reg ID', 'Candidate Name', 'Passport No', 'Expiry Date', 'Validity Check']
        for c in candidates:
            validity = 'Valid'
            if c.passport_expiry and c.passport_expiry < timezone.now().date():
                validity = 'EXPIRED'
            data.append({
                'col1': c.registration_id,
                'col2': c.name,
                'col3': c.passport_number,
                'col4': c.passport_expiry or 'N/A',
                'col5': validity
            })

    elif report_type == 'medical_report':
        title = "Medical Assessment Report"
        headers = ['Reg ID', 'Candidate Name', 'Passport No', 'Clinic', 'Medical Status']
        for c in candidates:
            data.append({
                'col1': c.registration_id,
                'col2': c.name,
                'col3': c.passport_number,
                'col4': c.medical_clinic or 'Pending Clinic',
                'col5': c.get_medical_status_display()
            })

    elif report_type == 'police_report':
        title = "Police Clearance Report"
        headers = ['Reg ID', 'Candidate Name', 'Passport No', 'Clearance Ref', 'Clearance Status']
        for c in candidates:
            data.append({
                'col1': c.registration_id,
                'col2': c.name,
                'col3': c.passport_number,
                'col4': c.police_clearance_ref or 'N/A',
                'col5': c.get_police_clearance_status_display()
            })

    elif report_type == 'mofa_report':
        title = "MOFA Clearance Report"
        headers = ['Reg ID', 'Candidate Name', 'Passport No', 'Mofa Number', 'MOFA Status']
        for c in candidates:
            data.append({
                'col1': c.registration_id,
                'col2': c.name,
                'col3': c.passport_number,
                'col4': c.mofa_number or 'Pending Mofa',
                'col5': c.get_mofa_status_display()
            })

    elif report_type == 'training_report':
        title = "Training Assessment Report"
        headers = ['Reg ID', 'Candidate Name', 'Passport No', 'Training Center', 'Training Status']
        for c in candidates:
            data.append({
                'col1': c.registration_id,
                'col2': c.name,
                'col3': c.passport_number,
                'col4': c.training_center or 'N/A',
                'col5': c.get_training_status_display()
            })

    elif report_type == 'visa_report':
        title = "Visa Clearance Report"
        headers = ['Reg ID', 'Candidate Name', 'Passport No', 'Visa Number', 'Stamping Status']
        for c in candidates:
            data.append({
                'col1': c.registration_id,
                'col2': c.name,
                'col3': c.passport_number,
                'col4': c.visa_number or 'N/A',
                'col5': c.get_visa_stamping_status_display()
            })

    elif report_type == 'manpower_report':
        title = "Manpower Clearance Report"
        headers = ['Reg ID', 'Candidate Name', 'Passport No', 'BMET Card No', 'Manpower Status']
        for c in candidates:
            data.append({
                'col1': c.registration_id,
                'col2': c.name,
                'col3': c.passport_number,
                'col4': c.bmet_card_number or 'N/A',
                'col5': c.get_manpower_status_display()
            })

    elif report_type == 'ticket_report':
        title = "Flight Ticket Report"
        headers = ['Reg ID', 'Candidate Name', 'Airline', 'PNR Number', 'Ticket Price', 'Ticket Status']
        for c in candidates:
            data.append({
                'col1': c.registration_id,
                'col2': c.name,
                'col3': c.airline or 'N/A',
                'col4': c.pnr_number or 'N/A',
                'col5': f"৳{c.ticket_price:,.2f}",
                'col6': c.get_ticket_status_display()
            })

    elif report_type == 'noc_report':
        title = "NOC Clearance Report"
        headers = ['Reg ID', 'Candidate Name', 'Passport No', 'NOC Reference', 'NOC Status']
        for c in candidates:
            data.append({
                'col1': c.registration_id,
                'col2': c.name,
                'col3': c.passport_number,
                'col4': c.noc_reference or 'N/A',
                'col5': c.get_noc_status_display()
            })

    else:
        title = "Agency Overall Summary Report"
        headers = ['Metric Category', 'Total Count', 'Percentage Progress']
        total = max(1, candidates.count())
        data = [
            {'col1': 'Total Candidates Registered', 'col2': candidates.count(), 'col3': '100%'},
            {'col1': 'Candidates Selected', 'col2': candidates.filter(selection_status='selected').count(), 'col3': f"{int(candidates.filter(selection_status='selected').count() / total * 100)}%"},
            {'col1': 'Medical Fit Candidates', 'col2': candidates.filter(medical_status='fit').count(), 'col3': f"{int(candidates.filter(medical_status='fit').count() / total * 100)}%"},
            {'col1': 'MOFA Cleared', 'col2': candidates.filter(mofa_status='mofa_cleared').count(), 'col3': f"{int(candidates.filter(mofa_status='mofa_cleared').count() / total * 100)}%"},
            {'col1': 'Visa Completed', 'col2': candidates.filter(visa_stamping_status='visa_completed').count(), 'col3': f"{int(candidates.filter(visa_stamping_status='visa_completed').count() / total * 100)}%"},
            {'col1': 'Tickets Issued', 'col2': candidates.filter(ticket_status='ticket_completed').count(), 'col3': f"{int(candidates.filter(ticket_status='ticket_completed').count() / total * 100)}%"},
        ]

    context = {
        'report_type': report_type,
        'title': title,
        'headers': headers,
        'data': data,
    }
    return render(request, 'admin_panel/agency/reports_hub.html', context)


# ── 7. MASTER SETTINGS (Country, Agent, Company, Position, Grade) ───────────
@login_required
def master_settings(request):
    """Master agency settings management."""
    db = get_tenant_db(request)
    ensure_default_settings(db)

    active_tab = request.GET.get('tab', 'agents')

    agents = AgencyAgent.objects.using(db).all()
    companies = AgencyCompany.objects.using(db).all()
    positions = AgencyPosition.objects.using(db).all()
    grades = SelectionGrade.objects.using(db).all()

    if request.method == 'POST':
        action = request.POST.get('action')

        # ── AGENT ACTIONS ─────────────────────────────────────────────────────
        if action == 'add_agent':
            name = request.POST.get('name', '').strip()
            phone = request.POST.get('phone', '').strip()
            email = request.POST.get('email', '').strip()
            comp = request.POST.get('company_name', '').strip()
            address = request.POST.get('address', '').strip()
            agent_type = request.POST.get('agent_type', 'b2b')
            notes = request.POST.get('notes', '').strip()

            try:
                comm_rate = Decimal(request.POST.get('commission_rate', '0').strip() or '0')
            except Exception:
                comm_rate = Decimal('0.00')

            try:
                credit_lim = Decimal(request.POST.get('credit_limit', '0').strip() or '0')
            except Exception:
                credit_lim = Decimal('0.00')

            if name:
                agent = AgencyAgent.objects.using(db).create(
                    name=name,
                    phone=phone,
                    email=email,
                    company_name=comp,
                    address=address,
                    agent_type=agent_type,
                    commission_rate=comm_rate,
                    credit_limit=credit_lim,
                    notes=notes,
                    is_active=True
                )
                messages.success(request, f'Agent "{name}" ({agent.agent_code}) added successfully!')
            else:
                messages.error(request, 'Agent name is required.')

        elif action == 'edit_agent':
            agent_id = request.POST.get('agent_id')
            agent = AgencyAgent.objects.using(db).filter(pk=agent_id).first()
            if agent:
                agent.name = request.POST.get('name', agent.name).strip()
                agent.phone = request.POST.get('phone', agent.phone).strip()
                agent.email = request.POST.get('email', agent.email).strip()
                agent.company_name = request.POST.get('company_name', agent.company_name).strip()
                agent.address = request.POST.get('address', agent.address).strip()
                agent.agent_type = request.POST.get('agent_type', agent.agent_type)
                agent.notes = request.POST.get('notes', agent.notes).strip()
                agent.is_active = (request.POST.get('is_active') == 'on')

                try:
                    agent.commission_rate = Decimal(request.POST.get('commission_rate', '0').strip() or '0')
                except Exception:
                    pass

                try:
                    agent.credit_limit = Decimal(request.POST.get('credit_limit', '0').strip() or '0')
                except Exception:
                    pass

                agent.save(using=db)
                messages.success(request, f'Agent "{agent.name}" updated successfully!')
            else:
                messages.error(request, 'Agent not found.')

        elif action == 'delete_agent':
            agent_id = request.POST.get('agent_id')
            agent = AgencyAgent.objects.using(db).filter(pk=agent_id).first()
            if agent:
                cands_count = Candidate.objects.using(db).filter(Q(b2b_agent=agent) | Q(agent=agent)).count()
                if cands_count > 0:
                    messages.error(
                        request,
                        f'Cannot delete agent "{agent.name}" because {cands_count} candidate(s) are linked to this agent. '
                        'Please reassign the candidates or deactivate the agent instead.'
                    )
                else:
                    name = agent.name
                    B2BAgentStaff.objects.using(db).filter(agent=agent).delete()
                    B2BTransaction.objects.using(db).filter(agent=agent).delete()
                    agent.delete(using=db)
                    messages.success(request, f'Agent "{name}" deleted successfully.')
            else:
                messages.error(request, 'Agent not found.')

        # ── COMPANY ACTIONS ───────────────────────────────────────────────────
        elif action == 'add_company':
            name = request.POST.get('name', '').strip()
            country = request.POST.get('country', 'Saudi Arabia')
            contact = request.POST.get('contact_person', '').strip()
            phone = request.POST.get('phone', '').strip()
            email = request.POST.get('email', '').strip()
            if name:
                AgencyCompany.objects.using(db).create(name=name, country=country, contact_person=contact, phone=phone, email=email)
                messages.success(request, f'Company "{name}" added successfully!')
            else:
                messages.error(request, 'Company name is required.')

        elif action == 'edit_company':
            company_id = request.POST.get('company_id')
            company = AgencyCompany.objects.using(db).filter(pk=company_id).first()
            if company:
                company.name = request.POST.get('name', company.name).strip()
                company.country = request.POST.get('country', company.country).strip()
                company.contact_person = request.POST.get('contact_person', company.contact_person).strip()
                company.phone = request.POST.get('phone', company.phone).strip()
                company.email = request.POST.get('email', company.email).strip()
                company.is_active = (request.POST.get('is_active') == 'on')
                company.save(using=db)
                messages.success(request, f'Company "{company.name}" updated successfully!')

        elif action == 'delete_company':
            company_id = request.POST.get('company_id')
            company = AgencyCompany.objects.using(db).filter(pk=company_id).first()
            if company:
                c_count = Candidate.objects.using(db).filter(company=company).count()
                if c_count > 0:
                    messages.error(request, f'Cannot delete company "{company.name}" because {c_count} candidates are associated with it.')
                else:
                    name = company.name
                    company.delete(using=db)
                    messages.success(request, f'Company "{name}" deleted.')

        # ── POSITION ACTIONS ──────────────────────────────────────────────────
        elif action == 'add_position':
            title = request.POST.get('title', '').strip()
            code = request.POST.get('code', '').strip()
            if title:
                AgencyPosition.objects.using(db).create(title=title, code=code)
                messages.success(request, f'Position "{title}" added successfully!')
            else:
                messages.error(request, 'Position title is required.')

        elif action == 'edit_position':
            position_id = request.POST.get('position_id')
            pos = AgencyPosition.objects.using(db).filter(pk=position_id).first()
            if pos:
                pos.title = request.POST.get('title', pos.title).strip()
                pos.code = request.POST.get('code', pos.code).strip()
                pos.is_active = (request.POST.get('is_active') == 'on')
                pos.save(using=db)
                messages.success(request, f'Position "{pos.title}" updated successfully!')

        elif action == 'delete_position':
            position_id = request.POST.get('position_id')
            pos = AgencyPosition.objects.using(db).filter(pk=position_id).first()
            if pos:
                c_count = Candidate.objects.using(db).filter(position=pos).count()
                if c_count > 0:
                    messages.error(request, f'Cannot delete position "{pos.title}" because {c_count} candidates are assigned to it.')
                else:
                    title = pos.title
                    pos.delete(using=db)
                    messages.success(request, f'Position "{title}" deleted.')

        # ── GRADE ACTIONS ─────────────────────────────────────────────────────
        elif action == 'add_grade':
            grade_name = request.POST.get('grade_name', '').strip()
            desc = request.POST.get('description', '').strip()
            if grade_name:
                SelectionGrade.objects.using(db).create(grade_name=grade_name, description=desc)
                messages.success(request, f'Selection Grade "{grade_name}" added successfully!')
            else:
                messages.error(request, 'Grade name is required.')

        elif action == 'edit_grade':
            grade_id = request.POST.get('grade_id')
            grade = SelectionGrade.objects.using(db).filter(pk=grade_id).first()
            if grade:
                grade.grade_name = request.POST.get('grade_name', grade.grade_name).strip()
                grade.description = request.POST.get('description', grade.description).strip()
                grade.save(using=db)
                messages.success(request, f'Grade "{grade.grade_name}" updated successfully!')

        elif action == 'delete_grade':
            grade_id = request.POST.get('grade_id')
            grade = SelectionGrade.objects.using(db).filter(pk=grade_id).first()
            if grade:
                c_count = Candidate.objects.using(db).filter(selection_grade=grade).count()
                if c_count > 0:
                    messages.error(request, f'Cannot delete grade "{grade.grade_name}" because {c_count} candidates are graded with it.')
                else:
                    name = grade.grade_name
                    grade.delete(using=db)
                    messages.success(request, f'Grade "{name}" deleted.')

        return redirect(f'/admin-panel/master-settings/?tab={active_tab}')

    context = {
        'active_tab': active_tab,
        'agents': agents,
        'companies': companies,
        'positions': positions,
        'grades': grades,
    }
    return render(request, 'admin_panel/agency/settings_master.html', context)


# ── OFFICE EXPENSE MANAGEMENT ─────────────────────────────────────────────────
@login_required
def office_expense_list(request):
    """Manage office expenses — add, edit, delete, filter."""
    from django.db.models import Sum
    db = get_tenant_db(request)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add':
            title = request.POST.get('title', '').strip()
            category = request.POST.get('category', 'other')
            amount_raw = request.POST.get('amount', '0').strip()
            expense_date = request.POST.get('expense_date') or timezone.now().date()
            payment_method = request.POST.get('payment_method', 'cash')
            paid_to = request.POST.get('paid_to', '').strip()
            reference_no = request.POST.get('reference_no', '').strip()
            notes = request.POST.get('notes', '').strip()

            try:
                amount = Decimal(amount_raw)
            except Exception:
                amount = Decimal('0.00')

            if title and amount > 0:
                expense = OfficeExpense(
                    title=title,
                    category=category,
                    amount=amount,
                    expense_date=expense_date,
                    payment_method=payment_method,
                    paid_to=paid_to,
                    reference_no=reference_no,
                    notes=notes,
                )
                if 'receipt_file' in request.FILES:
                    expense.receipt_file = request.FILES['receipt_file']
                expense.save(using=db)
                messages.success(request, f'Expense "{title}" of ৳{amount:,.2f} added successfully!')
            else:
                messages.error(request, 'Please provide a title and a valid amount.')

        elif action == 'delete':
            pk = request.POST.get('expense_id')
            expense = OfficeExpense.objects.using(db).filter(pk=pk).first()
            if expense:
                title = expense.title
                expense.delete()
                messages.success(request, f'Expense "{title}" deleted.')

        elif action == 'edit':
            pk = request.POST.get('expense_id')
            expense = OfficeExpense.objects.using(db).filter(pk=pk).first()
            if expense:
                expense.title = request.POST.get('title', expense.title).strip()
                expense.category = request.POST.get('category', expense.category)
                amount_raw = request.POST.get('amount', str(expense.amount)).strip()
                try:
                    expense.amount = Decimal(amount_raw)
                except Exception:
                    pass
                if request.POST.get('expense_date'):
                    expense.expense_date = request.POST.get('expense_date')
                expense.payment_method = request.POST.get('payment_method', expense.payment_method)
                expense.paid_to = request.POST.get('paid_to', expense.paid_to).strip()
                expense.reference_no = request.POST.get('reference_no', expense.reference_no).strip()
                expense.notes = request.POST.get('notes', expense.notes).strip()
                if 'receipt_file' in request.FILES:
                    expense.receipt_file = request.FILES['receipt_file']
                expense.save(using=db)
                messages.success(request, f'Expense "{expense.title}" updated.')

        return redirect('admin_panel:office_expense_list')

    # Filters
    cat_filter = request.GET.get('category', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    expenses = OfficeExpense.objects.using(db).all()
    if cat_filter:
        expenses = expenses.filter(category=cat_filter)
    if date_from:
        expenses = expenses.filter(expense_date__gte=date_from)
    if date_to:
        expenses = expenses.filter(expense_date__lte=date_to)

    # Aggregates
    total_expense = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    month_expense = OfficeExpense.objects.using(db).filter(
        expense_date__year=timezone.now().year,
        expense_date__month=timezone.now().month
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # Category breakdown
    from django.db.models import Sum as DSum
    category_totals = (
        OfficeExpense.objects.using(db).values('category')
        .annotate(total=DSum('amount'))
        .order_by('-total')
    )

    context = {
        'expenses': expenses,
        'cat_filter': cat_filter,
        'date_from': date_from,
        'date_to': date_to,
        'total_expense': total_expense,
        'month_expense': month_expense,
        'category_totals': category_totals,
        'category_choices': OfficeExpense.CATEGORY_CHOICES,
        'payment_method_choices': OfficeExpense.PAYMENT_METHOD_CHOICES,
    }
    return render(request, 'admin_panel/agency/office_expense.html', context)


# ══════════════════════════════════════════════════════════════════════════════
# 11. B2B & B2C NETWORK MANAGEMENT SYSTEM
# ══════════════════════════════════════════════════════════════════════════════

def get_tenant_agency_staff(request):
    """Fetch all active TENANT_STAFF users belonging to current agency tenant."""
    from apps.accounts.models import User
    tenant_slug = getattr(request.user, 'tenant_id', None)
    if not tenant_slug and hasattr(request, 'tenant') and request.tenant:
        tenant_slug = request.tenant.slug
    if not tenant_slug:
        return []
    return list(User.objects.filter(tenant_id=tenant_slug, role=User.Role.TENANT_STAFF, is_banned=False).order_by('first_name', 'email'))


@login_required
def api_b2b_staff_by_agent(request, agent_id):
    """API endpoint to dynamically fetch staff members for a specific B2B agent."""
    db = get_tenant_db(request)
    staff_qs = B2BAgentStaff.objects.using(db).filter(agent_id=agent_id, is_active=True).values(
        'id', 'name', 'staff_code', 'designation', 'phone'
    )
    return JsonResponse({'status': 'ok', 'staff': list(staff_qs)})


@login_required
def b2b_dashboard(request):
    """High-level B2B vs B2C Network Dashboard with live metrics and recent activity."""
    db = get_tenant_db(request)
    ensure_default_settings(db)

    is_staff = request.user.is_tenant_staff

    # 1. High level counters
    if is_staff:
        agents_base = AgencyAgent.objects.using(db).filter(agent_type='b2b', assigned_staff_id=request.user.id, is_active=True)
        assigned_agent_ids = list(agents_base.values_list('id', flat=True))
        b2b_cand_qs = Candidate.objects.using(db).filter(
            Q(agency_staff_id=request.user.id) | Q(b2b_agent_id__in=assigned_agent_ids)
        )
        b2c_cand_qs = Candidate.objects.none()
    else:
        agents_base = AgencyAgent.objects.using(db).filter(agent_type='b2b', is_active=True)
        b2b_cand_qs = Candidate.objects.using(db).filter(client_type='b2b')
        b2c_cand_qs = Candidate.objects.using(db).filter(client_type='b2c')

    total_b2b_agents = agents_base.count()
    total_b2b_staff = get_tenant_agency_staff(request)

    b2b_candidates_count = b2b_cand_qs.count()
    b2c_candidates_count = b2c_cand_qs.count()

    b2b_fin = b2b_cand_qs.aggregate(
        total_billing=Sum('total_amount'),
        total_collected=Sum('paid_amount'),
        total_due=Sum('due_amount')
    )
    b2c_fin = b2c_cand_qs.aggregate(
        total_billing=Sum('total_amount'),
        total_collected=Sum('paid_amount'),
        total_due=Sum('due_amount')
    )

    b2b_billing = b2b_fin['total_billing'] or Decimal('0.00')
    b2b_collected = b2b_fin['total_collected'] or Decimal('0.00')
    b2b_due = b2b_fin['total_due'] or Decimal('0.00')

    b2c_billing = b2c_fin['total_billing'] or Decimal('0.00')
    b2c_collected = b2c_fin['total_collected'] or Decimal('0.00')
    b2c_due = b2c_fin['total_due'] or Decimal('0.00')

    total_revenue_collected = b2b_collected + b2c_collected

    # Top B2B agents by volume
    agents = list(agents_base)
    agents_summary = []
    for ag in agents:
        cands = Candidate.objects.using(db).filter(Q(b2b_agent=ag) | Q(agent=ag))
        c_count = cands.count()
        c_fin = cands.aggregate(tot=Sum('total_amount'), paid=Sum('paid_amount'), due=Sum('due_amount'))
        billed = c_fin['tot'] or Decimal('0.00')
        paid = c_fin['paid'] or Decimal('0.00')
        due = c_fin['due'] or Decimal('0.00')
        agents_summary.append({
            'agent': ag,
            'candidates_count': c_count,
            'billed': billed,
            'paid': paid,
            'due': due,
            'outstanding': ag.outstanding_balance or due,
            'staff_count': 1 if ag.assigned_staff_id else 0,
        })
    agents_summary.sort(key=lambda x: x['billed'], reverse=True)

    # Recent Transactions
    if is_staff:
        recent_txns = list(
            B2BTransaction.objects.using(db)
            .filter(Q(agency_staff_id=request.user.id) | Q(agent__assigned_staff_id=request.user.id))
            .select_related('agent', 'candidate')
            .order_by('-txn_date', '-created_at')[:12]
        )
    else:
        recent_txns = list(
            B2BTransaction.objects.using(db)
            .select_related('agent', 'candidate')
            .order_by('-txn_date', '-created_at')[:12]
        )

    context = {
        'total_b2b_agents': total_b2b_agents,
        'total_b2b_staff': total_b2b_staff,
        'b2b_candidates_count': b2b_candidates_count,
        'b2c_candidates_count': b2c_candidates_count,
        'b2b_billing': b2b_billing,
        'b2b_collected': b2b_collected,
        'b2b_due': b2b_due,
        'b2c_billing': b2c_billing,
        'b2c_collected': b2c_collected,
        'b2c_due': b2c_due,
        'total_revenue_collected': total_revenue_collected,
        'agents_summary': agents_summary[:6],
        'recent_txns': recent_txns,
    }
    return render(request, 'admin_panel/agency/b2b_dashboard.html', context)


@login_required
def b2b_agent_list(request):
    """List B2B agents with running balances, credit limits, and agency staff ownership."""
    db = get_tenant_db(request)
    ensure_default_settings(db)

    is_staff_view = request.user.is_tenant_staff
    query = request.GET.get('q', '').strip()
    selected_staff_id = request.GET.get('staff_id', '').strip()

    agents_qs = AgencyAgent.objects.using(db).filter(agent_type='b2b')

    # Security: If Agency Staff is logged in, they can ONLY see their own assigned agents!
    if is_staff_view:
        agents_qs = agents_qs.filter(assigned_staff_id=request.user.id)
    elif selected_staff_id and selected_staff_id.isdigit():
        agents_qs = agents_qs.filter(assigned_staff_id=int(selected_staff_id))

    if query:
        agents_qs = agents_qs.filter(
            Q(name__icontains=query) |
            Q(agent_code__icontains=query) |
            Q(company_name__icontains=query) |
            Q(phone__icontains=query) |
            Q(email__icontains=query) |
            Q(assigned_staff_name__icontains=query)
        )

    agents = list(agents_qs.order_by('name'))
    agent_items = []
    tot_all_billed = Decimal('0.00')
    tot_all_collected = Decimal('0.00')
    tot_all_due = Decimal('0.00')

    for ag in agents:
        cands = Candidate.objects.using(db).filter(Q(b2b_agent=ag) | Q(agent=ag))
        c_fin = cands.aggregate(tot=Sum('total_amount'), paid=Sum('paid_amount'), due=Sum('due_amount'))
        billed = c_fin['tot'] or Decimal('0.00')
        paid = c_fin['paid'] or Decimal('0.00')
        due = c_fin['due'] or Decimal('0.00')
        
        tot_all_billed += billed
        tot_all_collected += paid
        tot_all_due += due

        # Credit utilization
        limit = ag.credit_limit or Decimal('0.00')
        current_bal = ag.outstanding_balance or due
        utilization_pct = 0
        if limit > 0:
            utilization_pct = min(100, int((current_bal / limit) * 100))

        agent_items.append({
            'agent': ag,
            'candidates_count': cands.count(),
            'staff_count': ag.staff_members.count(),
            'billed': billed,
            'paid': paid,
            'due': due,
            'outstanding': current_bal,
            'utilization_pct': utilization_pct,
            'is_over_limit': (limit > 0 and current_bal > limit),
        })

    accounts = list(ChartOfAccount.objects.using(db).all())
    staff_list = get_tenant_agency_staff(request)

    context = {
        'agent_items': agent_items,
        'query': query,
        'selected_staff_id': selected_staff_id,
        'total_agents': len(agents),
        'tot_all_billed': tot_all_billed,
        'tot_all_collected': tot_all_collected,
        'tot_all_due': tot_all_due,
        'accounts': accounts,
        'staff_list': staff_list,
        'is_staff_view': is_staff_view,
    }
    return render(request, 'admin_panel/agency/b2b_agent_list.html', context)


@login_required
def b2b_agent_create(request):
    """Create a new B2B Agent. Staff creates under their account; Admin can assign to any staff."""
    db = get_tenant_db(request)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        company_name = request.POST.get('company_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()
        address = request.POST.get('address', '').strip()
        nid_number = request.POST.get('nid_number', '').strip()
        notes = request.POST.get('notes', '').strip()
        
        try:
            commission_rate = Decimal(request.POST.get('commission_rate', '0').strip() or '0')
        except Exception:
            commission_rate = Decimal('0.00')

        try:
            credit_limit = Decimal(request.POST.get('credit_limit', '0').strip() or '0')
        except Exception:
            credit_limit = Decimal('0.00')

        if not name:
            messages.error(request, 'Agent name is required.')
            return redirect('admin_panel:b2b_agent_list')

        # Determine agency staff assignment
        assigned_staff_id = None
        assigned_staff_name = ''
        assigned_staff_email = ''

        if request.user.is_tenant_staff:
            # Agency Staff member creating agent: auto-assigned to self
            assigned_staff_id = request.user.id
            assigned_staff_name = request.user.get_full_name() or request.user.email
            assigned_staff_email = request.user.email
        else:
            # Agency Admin creating agent: can choose assigned staff
            staff_param = request.POST.get('assigned_staff_id', '').strip()
            if staff_param and staff_param.isdigit():
                from apps.accounts.models import User
                st_user = User.objects.filter(pk=int(staff_param), tenant_id=request.user.tenant_id).first()
                if st_user:
                    assigned_staff_id = st_user.id
                    assigned_staff_name = st_user.get_full_name() or st_user.email
                    assigned_staff_email = st_user.email

        agent = AgencyAgent.objects.using(db).create(
            name=name,
            company_name=company_name,
            phone=phone,
            email=email,
            address=address,
            agent_type='b2b',
            commission_rate=commission_rate,
            credit_limit=credit_limit,
            nid_number=nid_number,
            notes=notes,
            assigned_staff_id=assigned_staff_id,
            assigned_staff_name=assigned_staff_name,
            assigned_staff_email=assigned_staff_email,
            created_by_user_id=request.user.id,
            is_active=True
        )

        messages.success(request, f'B2B Agent "{agent.name}" ({agent.agent_code}) created successfully!')
        return redirect('admin_panel:b2b_agent_detail', pk=agent.id)

    return redirect('admin_panel:b2b_agent_list')


@login_required
def b2b_agent_edit(request, pk):
    """Update B2B Agent details. Agency Admin can also reassign agent to another Agency Staff member."""
    db = get_tenant_db(request)
    agent = get_object_or_404(AgencyAgent.objects.using(db), pk=pk)

    # Security check: if staff member is attempting to edit an agent not assigned to them
    if request.user.is_tenant_staff and agent.assigned_staff_id and agent.assigned_staff_id != request.user.id:
        messages.error(request, 'Access denied. You can only manage your own assigned B2B agents.')
        return redirect('admin_panel:b2b_agent_list')

    if request.method == 'POST':
        agent.name = request.POST.get('name', agent.name).strip()
        agent.company_name = request.POST.get('company_name', agent.company_name).strip()
        agent.phone = request.POST.get('phone', agent.phone).strip()
        agent.email = request.POST.get('email', agent.email).strip()
        agent.address = request.POST.get('address', agent.address).strip()
        agent.nid_number = request.POST.get('nid_number', agent.nid_number).strip()
        agent.notes = request.POST.get('notes', agent.notes).strip()
        agent.is_active = (request.POST.get('is_active') == 'on')

        try:
            agent.commission_rate = Decimal(request.POST.get('commission_rate', '0').strip() or '0')
        except Exception:
            pass

        try:
            agent.credit_limit = Decimal(request.POST.get('credit_limit', '0').strip() or '0')
        except Exception:
            pass

        # Only Agency Admin can reassign the agent from one staff member to another
        if not request.user.is_tenant_staff:
            new_staff_param = request.POST.get('assigned_staff_id', '').strip()
            if new_staff_param in ['none', '0', '']:
                agent.assigned_staff_id = None
                agent.assigned_staff_name = ''
                agent.assigned_staff_email = ''
            elif new_staff_param.isdigit():
                from apps.accounts.models import User
                st_user = User.objects.filter(pk=int(new_staff_param), tenant_id=request.user.tenant_id).first()
                if st_user:
                    agent.assigned_staff_id = st_user.id
                    agent.assigned_staff_name = st_user.get_full_name() or st_user.email
                    agent.assigned_staff_email = st_user.email

        agent.save(using=db)
        messages.success(request, f'B2B Agent "{agent.name}" updated successfully!')
        return redirect('admin_panel:b2b_agent_detail', pk=agent.id)

    return redirect('admin_panel:b2b_agent_list')


@login_required
def b2b_agent_delete(request, pk):
    """Delete a B2B agent safely if no linked candidates exist. Staff CANNOT delete agents."""
    db = get_tenant_db(request)
    agent = get_object_or_404(AgencyAgent.objects.using(db), pk=pk)

    # Staff permission guard: Agency Staff can NEVER delete an agent
    if request.user.is_tenant_staff:
        messages.error(request, '🚫 Staff members are not permitted to delete B2B agents. Only Agency Admin can delete.')
        return redirect('admin_panel:b2b_agent_detail', pk=agent.id)

    if request.method == 'POST':
        cands_count = Candidate.objects.using(db).filter(Q(b2b_agent=agent) | Q(agent=agent)).count()
        if cands_count > 0:
            messages.error(
                request,
                f'Cannot delete agent "{agent.name}" because {cands_count} candidate(s) are linked to this agent. '
                'Please reassign or delete those candidates first, or deactivate this agent.'
            )
            return redirect('admin_panel:b2b_agent_detail', pk=agent.id)

        name = agent.name
        B2BAgentStaff.objects.using(db).filter(agent=agent).delete()
        B2BTransaction.objects.using(db).filter(agent=agent).delete()
        agent.delete(using=db)
        messages.success(request, f'B2B Agent "{name}" has been deleted successfully.')
        return redirect('admin_panel:b2b_agent_list')

    return redirect('admin_panel:b2b_agent_detail', pk=agent.id)


@login_required
def b2b_agent_detail(request, pk):
    """Comprehensive Agent Profile with Staff Management, Connected Candidates, Visas, Tickets, and Ledger."""
    db = get_tenant_db(request)
    agent = get_object_or_404(AgencyAgent.objects.using(db), pk=pk)

    # Security check: Agency Staff cannot access another staff member's agent
    if request.user.is_tenant_staff and agent.assigned_staff_id and agent.assigned_staff_id != request.user.id:
        messages.error(request, 'Access denied. This agent is assigned to another staff member.')
        return redirect('admin_panel:b2b_agent_list')

    # 1. Staff Members
    staff_members = list(agent.staff_members.all().order_by('name'))

    # 2. Connected Candidates
    candidates = list(
        Candidate.objects.using(db)
        .filter(Q(b2b_agent=agent) | Q(agent=agent))
        .select_related('b2b_staff', 'visa_lot')
        .order_by('-created_at')
    )

    # 3. Connected Visa Lots
    visa_lot_ids = [c.visa_lot_id for c in candidates if c.visa_lot_id]
    visa_lots = list(VisaLot.objects.using(db).filter(id__in=visa_lot_ids))

    # 4. Flight Tickets connected to candidates
    flight_candidates = [c for c in candidates if c.ticket_status != Candidate.TicketStatus.PENDING or c.airline or c.pnr_number]

    # 5. Financial aggregates
    cand_fin = Candidate.objects.using(db).filter(Q(b2b_agent=agent) | Q(agent=agent)).aggregate(
        billed=Sum('total_amount'),
        paid=Sum('paid_amount'),
        due=Sum('due_amount')
    )
    total_billed = cand_fin['billed'] or Decimal('0.00')
    total_paid = cand_fin['paid'] or Decimal('0.00')
    total_due = cand_fin['due'] or Decimal('0.00')

    # Recalculate and fetch outstanding ledger balance
    agent.recalculate_outstanding(using=db)
    outstanding_balance = agent.outstanding_balance or total_due

    # Credit limit calculations
    credit_limit = agent.credit_limit or Decimal('0.00')
    available_credit = max(Decimal('0.00'), credit_limit - outstanding_balance) if credit_limit > 0 else Decimal('0.00')
    credit_utilization_pct = min(100, int((outstanding_balance / credit_limit) * 100)) if credit_limit > 0 else 0

    # Commission earned calculation (use stored value if set, else calculate from rate)
    comm_rate = agent.commission_rate or Decimal('0.00')
    total_commission = agent.commission_earned if agent.commission_earned > Decimal('0.00') else (
        (total_billed * comm_rate / Decimal('100.00')).quantize(Decimal('0.01'))
    )

    # 6. Ledger Transactions
    transactions = list(
        B2BTransaction.objects.using(db)
        .filter(agent=agent)
        .select_related('staff', 'candidate')
        .order_by('-txn_date', '-created_at')[:60]
    )

    accounts = list(ChartOfAccount.objects.using(db).all())

    # 7. Per-staff commission breakdown
    staff_commission_items = []
    for s in staff_members:
        s_cands = Candidate.objects.using(db).filter(b2b_staff=s)
        s_fin = s_cands.aggregate(billed=Sum('total_amount'), paid=Sum('paid_amount'))
        s_billed = s_fin['billed'] or Decimal('0.00')
        s_paid = s_fin['paid'] or Decimal('0.00')
        s_rate = s.commission_rate or Decimal('0.00')
        s_earned = s.commission_earned if s.commission_earned > Decimal('0.00') else (
            (s_billed * s_rate / Decimal('100.00')).quantize(Decimal('0.01'))
        )
        staff_commission_items.append({
            'staff': s,
            'candidates_count': s_cands.count(),
            'billed': s_billed,
            'paid': s_paid,
            'commission_rate': s_rate,
            'commission_earned': s_earned,
        })

    context = {
        'agent': agent,
        'staff_members': staff_members,
        'staff_commission_items': staff_commission_items,
        'candidates': candidates,
        'candidates_count': len(candidates),
        'visa_lots': visa_lots,
        'flight_candidates': flight_candidates,
        'total_billed': total_billed,
        'total_paid': total_paid,
        'total_due': total_due,
        'outstanding_balance': outstanding_balance,
        'credit_limit': credit_limit,
        'available_credit': available_credit,
        'credit_utilization_pct': credit_utilization_pct,
        'total_commission': total_commission,
        'transactions': transactions,
        'accounts': accounts,
        'staff_list': get_tenant_agency_staff(request),
        'is_staff_user': request.user.is_tenant_staff,
    }
    return render(request, 'admin_panel/agency/b2b_agent_detail.html', context)


@login_required
def b2b_agent_add_payment(request, pk):
    """Record direct bulk or settlement payment from a B2B agent."""
    db = get_tenant_db(request)
    agent = get_object_or_404(AgencyAgent.objects.using(db), pk=pk)

    # Security check: Agency Staff cannot record payment on an agent assigned to another staff
    if request.user.is_tenant_staff and agent.assigned_staff_id and agent.assigned_staff_id != request.user.id:
        messages.error(request, 'Access denied. You can only record payments for your assigned agents.')
        return redirect('admin_panel:b2b_agent_list')

    if request.method == 'POST':
        amount_raw = request.POST.get('amount', '0').strip()
        payment_date_val = request.POST.get('payment_date') or timezone.now().date()
        payment_method = request.POST.get('payment_method', 'Cash')
        reference_no = request.POST.get('reference_no', '').strip()
        staff_id = request.POST.get('staff_id')
        notes = request.POST.get('notes', '').strip()
        account_id = request.POST.get('account_id')

        try:
            amt = Decimal(amount_raw)
        except Exception:
            amt = Decimal('0.00')

        if amt <= Decimal('0.00'):
            messages.error(request, 'Please enter a payment amount greater than zero.')
            return redirect('admin_panel:b2b_agent_detail', pk=agent.id)

        staff = B2BAgentStaff.objects.using(db).filter(pk=staff_id).first() if staff_id else None

        # Record B2B transaction with Agency Staff details
        txn = B2BTransaction.objects.using(db).create(
            agent=agent,
            staff=staff,
            agency_staff_id=request.user.id,
            agency_staff_name=request.user.get_full_name() or request.user.email,
            txn_type=B2BTransaction.TxnType.PAYMENT_RECEIVED,
            amount=amt,
            balance_after=max(Decimal('0.00'), agent.outstanding_balance - amt),
            description=f"Agent Payment / Settlement from {agent.name}" + (f" ({notes})" if notes else ""),
            reference_no=reference_no,
            txn_date=payment_date_val
        )

        # Update running balance
        agent.recalculate_outstanding(using=db)

        # Post to Chart of Account & Voucher if selected
        acc = ChartOfAccount.objects.using(db).filter(pk=account_id).first() if account_id else (
            ChartOfAccount.objects.using(db).filter(account_name__icontains='Cash').first() or
            ChartOfAccount.objects.using(db).first()
        )
        if acc:
            v_type = 'cr_cheque' if payment_method == 'Cheque' else 'cr_cash'
            AccountVoucher.objects.using(db).create(
                voucher_type=v_type,
                account=acc,
                amount=amt,
                narration=f"B2B Agent Settlement: {agent.name} ({agent.agent_code})",
                reference_no=reference_no,
                voucher_date=payment_date_val
            )
            acc.current_balance += amt
            acc.save(using=db)

        messages.success(request, f'Payment of ৳{amt:,.2f} recorded for {agent.name}!')
        return redirect('admin_panel:b2b_agent_detail', pk=agent.id)

    return redirect('admin_panel:b2b_agent_detail', pk=agent.id)


@login_required
def b2b_agent_set_commission(request, pk):
    """
    Update an agent's commission rate and immediately recalculate commission_earned
    plus adjust the outstanding balance by posting/replacing the [AUTO-COMM] transaction.
    """
    db = get_tenant_db(request)
    agent = get_object_or_404(AgencyAgent.objects.using(db), pk=pk)

    if request.method == 'POST':
        try:
            new_rate = Decimal(request.POST.get('commission_rate', '0').strip() or '0')
        except Exception:
            new_rate = Decimal('0.00')

        # Clamp rate 0-100
        new_rate = max(Decimal('0.00'), min(Decimal('100.00'), new_rate))
        old_rate = agent.commission_rate

        agent.commission_rate = new_rate
        agent.save(using=db, update_fields=['commission_rate'])

        # Auto-recalculate commission & outstanding
        new_commission = agent.recalculate_commission(using=db)

        messages.success(
            request,
            f'Commission rate updated to {new_rate}% for {agent.name}. '
            f'Commission earned auto-calculated: ৳{new_commission:,.2f}. '
            f'Outstanding balance updated.'
        )

    return redirect('admin_panel:b2b_agent_detail', pk=agent.id)


@login_required
def b2b_staff_set_commission(request, pk):
    """
    Update a staff member's commission rate and recalculate their commission_earned
    based on candidates they handled.
    """
    db = get_tenant_db(request)
    staff = get_object_or_404(B2BAgentStaff.objects.using(db), pk=pk)

    if request.method == 'POST':
        try:
            new_rate = Decimal(request.POST.get('commission_rate', '0').strip() or '0')
        except Exception:
            new_rate = Decimal('0.00')

        new_rate = max(Decimal('0.00'), min(Decimal('100.00'), new_rate))
        staff.commission_rate = new_rate
        staff.save(using=db, update_fields=['commission_rate'])

        new_commission = staff.recalculate_commission(using=db)

        messages.success(
            request,
            f'Commission rate updated to {new_rate}% for staff "{staff.name}". '
            f'Commission earned: ৳{new_commission:,.2f}.'
        )

    return redirect('admin_panel:b2b_agent_detail', pk=staff.agent.id)


@login_required
def b2b_agent_recalculate(request, pk):
    """Force recalculate all balances and commission for an agent (useful after bulk data changes)."""
    db = get_tenant_db(request)
    agent = get_object_or_404(AgencyAgent.objects.using(db), pk=pk)

    if request.method == 'POST':
        # Recalculate commission if rate is set
        if agent.commission_rate and agent.commission_rate > Decimal('0.00'):
            comm = agent.recalculate_commission(using=db)
            messages.success(
                request,
                f'✅ Recalculated for {agent.name}: Commission = ৳{comm:,.2f}, '
                f'Outstanding = ৳{agent.outstanding_balance:,.2f}'
            )
        else:
            agent.recalculate_outstanding(using=db)
            messages.success(
                request,
                f'✅ Outstanding balance recalculated for {agent.name}: ৳{agent.outstanding_balance:,.2f}'
            )

        # Also recalculate all staff commission under this agent
        staff_members = B2BAgentStaff.objects.using(db).filter(agent=agent, is_active=True)
        staff_updated = 0
        for s in staff_members:
            if s.commission_rate and s.commission_rate > Decimal('0.00'):
                s.recalculate_commission(using=db)
                staff_updated += 1

        if staff_updated:
            messages.info(request, f'Staff commission recalculated for {staff_updated} active staff member(s).')

    return redirect('admin_panel:b2b_agent_detail', pk=agent.id)


@login_required
def b2b_staff_create(request, pk):
    """Add a staff member under a specific B2B Agent (agent chosen from form or URL pk)."""
    db = get_tenant_db(request)

    # pk=0 means agent is chosen from the form field
    if pk == 0:
        agent_id = request.POST.get('agent_id') if request.method == 'POST' else None
        agent = AgencyAgent.objects.using(db).filter(pk=agent_id).first() if agent_id else None
        if not agent:
            messages.error(request, 'Please select a valid B2B agent.')
            return redirect('admin_panel:b2b_staff_list')
    else:
        agent = get_object_or_404(AgencyAgent.objects.using(db), pk=pk)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()
        designation = request.POST.get('designation', '').strip() or 'Visa Processing Executive'
        nid_number = request.POST.get('nid_number', '').strip()
        notes = request.POST.get('notes', '').strip()
        password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()

        if not name:
            messages.error(request, 'Staff member name is required.')
            return redirect('admin_panel:b2b_agent_detail', pk=agent.id) if pk != 0 else redirect('admin_panel:b2b_staff_list')

        # Check email uniqueness if email provided
        if email:
            if B2BAgentStaff.objects.using(db).filter(email__iexact=email).exists():
                messages.error(request, f'A staff member with login email "{email}" already exists.')
                return redirect('admin_panel:b2b_agent_detail', pk=agent.id) if pk != 0 else redirect('admin_panel:b2b_staff_list')

        # Password validation (staff logs in with email + password)
        password_hash = ''
        if password:
            if not email:
                messages.error(request, 'An email address is required to set up portal login credentials.')
                return redirect('admin_panel:b2b_agent_detail', pk=agent.id) if pk != 0 else redirect('admin_panel:b2b_staff_list')
            if password != confirm_password:
                messages.error(request, 'Password and confirm password do not match.')
                return redirect('admin_panel:b2b_agent_detail', pk=agent.id) if pk != 0 else redirect('admin_panel:b2b_staff_list')
            if len(password) < 6:
                messages.error(request, 'Password must be at least 6 characters long.')
                return redirect('admin_panel:b2b_agent_detail', pk=agent.id) if pk != 0 else redirect('admin_panel:b2b_staff_list')
            import hashlib
            password_hash = hashlib.sha256(password.encode()).hexdigest()

        staff = B2BAgentStaff.objects.using(db).create(
            agent=agent,
            name=name,
            phone=phone,
            email=email,
            designation=designation,
            username=email,  # Staff login identifier is their email
            password_hash=password_hash,
            nid_number=nid_number,
            notes=notes,
            is_active=True
        )
        messages.success(request, f'Staff member "{staff.name}" ({staff.staff_code}) added under {agent.name}!')

        if pk != 0:
            return redirect('admin_panel:b2b_agent_detail', pk=agent.id)
        return redirect('admin_panel:b2b_staff_list')

    if pk != 0:
        return redirect('admin_panel:b2b_agent_detail', pk=agent.id)
    return redirect('admin_panel:b2b_staff_list')


@login_required
def b2b_staff_list(request):
    """List all staff accounts across all B2B agents with their individual activity and candidates."""
    db = get_tenant_db(request)
    ensure_default_settings(db)

    selected_agent_id = request.GET.get('agent_id', '').strip()
    query = request.GET.get('q', '').strip()

    staff_qs = B2BAgentStaff.objects.using(db).select_related('agent').all()
    if selected_agent_id:
        staff_qs = staff_qs.filter(agent_id=selected_agent_id)
    if query:
        staff_qs = staff_qs.filter(
            Q(name__icontains=query) |
            Q(staff_code__icontains=query) |
            Q(phone__icontains=query) |
            Q(email__icontains=query) |
            Q(agent__name__icontains=query)
        )

    staff_list = list(staff_qs.order_by('agent__name', 'name'))
    staff_items = []
    for s in staff_list:
        cands = Candidate.objects.using(db).filter(b2b_staff=s)
        c_fin = cands.aggregate(tot=Sum('total_amount'), paid=Sum('paid_amount'), due=Sum('due_amount'))
        staff_items.append({
            'staff': s,
            'candidates_count': cands.count(),
            'revenue_handled': c_fin['tot'] or Decimal('0.00'),
            'paid_handled': c_fin['paid'] or Decimal('0.00'),
            'due_handled': c_fin['due'] or Decimal('0.00'),
        })

    agents = list(AgencyAgent.objects.using(db).filter(agent_type='b2b', is_active=True).order_by('name'))

    # Extra stats for summary cards
    all_staff_qs = B2BAgentStaff.objects.using(db)
    active_staff_count = all_staff_qs.filter(is_active=True).count()
    agents_with_staff = all_staff_qs.values('agent_id').distinct().count()
    total_candidates_handled = Candidate.objects.using(db).filter(b2b_staff__isnull=False).count()

    context = {
        'staff_items': staff_items,
        'agents': agents,
        'selected_agent_id': selected_agent_id,
        'query': query,
        'total_staff': len(staff_items),
        'active_staff_count': active_staff_count,
        'agents_with_staff': agents_with_staff,
        'total_candidates_handled': total_candidates_handled,
    }
    return render(request, 'admin_panel/agency/b2b_staff_list.html', context)


@login_required
def b2b_staff_toggle(request, pk):
    """Toggle staff account active/inactive."""
    db = get_tenant_db(request)
    staff = get_object_or_404(B2BAgentStaff.objects.using(db), pk=pk)
    staff.is_active = not staff.is_active
    staff.save(using=db, update_fields=['is_active'])
    status_str = "activated" if staff.is_active else "deactivated"
    messages.success(request, f'Staff member "{staff.name}" has been {status_str}.')
    next_url = request.META.get('HTTP_REFERER', 'admin_panel:b2b_staff_list')
    return redirect(next_url)


@login_required
def b2b_staff_edit(request, pk):
    """Update staff member profile and optionally reset password."""
    db = get_tenant_db(request)
    staff = get_object_or_404(B2BAgentStaff.objects.using(db), pk=pk)
    if request.method == 'POST':
        staff.name = request.POST.get('name', staff.name).strip()
        staff.phone = request.POST.get('phone', staff.phone).strip()
        new_email = request.POST.get('email', staff.email).strip()
        staff.designation = request.POST.get('designation', staff.designation).strip()
        staff.nid_number = request.POST.get('nid_number', staff.nid_number).strip()
        staff.notes = request.POST.get('notes', staff.notes).strip()
        staff.is_active = (request.POST.get('is_active') == 'on')

        # Email update & check uniqueness (email is login identifier)
        if new_email and new_email.lower() != (staff.email or '').lower():
            if B2BAgentStaff.objects.using(db).filter(email__iexact=new_email).exclude(pk=staff.pk).exists():
                messages.error(request, f'A staff member with login email "{new_email}" already exists.')
                next_url = request.META.get('HTTP_REFERER', 'admin_panel:b2b_staff_list')
                return redirect(next_url)
            staff.email = new_email
            staff.username = new_email
        elif new_email:
            staff.email = new_email
            staff.username = new_email

        new_agent_id = request.POST.get('agent_id')
        if new_agent_id:
            new_agent = AgencyAgent.objects.using(db).filter(pk=new_agent_id).first()
            if new_agent:
                staff.agent = new_agent

        # Password reset (only if new password provided)
        new_password = request.POST.get('new_password', '').strip()
        if new_password:
            confirm_password = request.POST.get('confirm_password', '').strip()
            if not staff.email:
                messages.error(request, 'Staff must have an email address to set a portal password.')
                next_url = request.META.get('HTTP_REFERER', 'admin_panel:b2b_staff_list')
                return redirect(next_url)
            if new_password != confirm_password:
                messages.error(request, 'New password and confirm password do not match.')
                next_url = request.META.get('HTTP_REFERER', 'admin_panel:b2b_staff_list')
                return redirect(next_url)
            if len(new_password) < 6:
                messages.error(request, 'Password must be at least 6 characters.')
                next_url = request.META.get('HTTP_REFERER', 'admin_panel:b2b_staff_list')
                return redirect(next_url)
            import hashlib
            staff.password_hash = hashlib.sha256(new_password.encode()).hexdigest()

        staff.save(using=db)
        messages.success(request, f'Staff member "{staff.name}" updated successfully!')
    next_url = request.META.get('HTTP_REFERER', 'admin_panel:b2b_staff_list')
    return redirect(next_url)


@login_required
def b2b_staff_delete(request, pk):
    """Delete a B2B agent staff member safely."""
    db = get_tenant_db(request)
    staff = get_object_or_404(B2BAgentStaff.objects.using(db), pk=pk)

    if request.method == 'POST':
        # Check if any candidates are linked to this staff
        cand_count = Candidate.objects.using(db).filter(b2b_staff=staff).count()
        if cand_count > 0:
            messages.error(
                request,
                f'Cannot delete staff member "{staff.name}" because {cand_count} candidate(s) are linked to them. '
                'Please reassign those candidates first.'
            )
            return redirect('admin_panel:b2b_staff_list')

        name = staff.name
        staff.delete(using=db)
        messages.success(request, f'Staff member "{name}" has been deleted successfully.')
        return redirect('admin_panel:b2b_staff_list')

    return redirect('admin_panel:b2b_staff_list')


@login_required
def b2b_ledger(request):
    """Complete Agency B2B Ledger: filterable transaction audit trail with debit/credit running balances."""
    db = get_tenant_db(request)
    ensure_default_settings(db)

    agent_id = request.GET.get('agent_id', '').strip()
    staff_id = request.GET.get('staff_id', '').strip()
    txn_type = request.GET.get('txn_type', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()

    txns_qs = B2BTransaction.objects.using(db).select_related('agent', 'staff', 'candidate').all()
    if agent_id:
        txns_qs = txns_qs.filter(agent_id=agent_id)
    if staff_id:
        txns_qs = txns_qs.filter(staff_id=staff_id)
    if txn_type:
        txns_qs = txns_qs.filter(txn_type=txn_type)
    if date_from:
        txns_qs = txns_qs.filter(txn_date__gte=date_from)
    if date_to:
        txns_qs = txns_qs.filter(txn_date__lte=date_to)

    txns = list(txns_qs.order_by('-txn_date', '-created_at'))

    # Totals
    total_debit = Decimal('0.00')
    total_credit = Decimal('0.00')
    for t in txns:
        if t.txn_type in ['debit', 'service_charge', 'adjustment_debit']:
            total_debit += t.amount
        else:
            total_credit += t.amount

    agents = list(AgencyAgent.objects.using(db).filter(agent_type='b2b', is_active=True).order_by('name'))
    staff_members = list(B2BAgentStaff.objects.using(db).filter(is_active=True).select_related('agent').order_by('name'))

    context = {
        'txns': txns,
        'agents': agents,
        'staff_members': staff_members,
        'selected_agent_id': agent_id,
        'selected_staff_id': staff_id,
        'selected_txn_type': txn_type,
        'date_from': date_from,
        'date_to': date_to,
        'total_debit': total_debit,
        'total_credit': total_credit,
        'net_ledger_balance': total_debit - total_credit,
        'txn_types': B2BTransaction.TxnType.choices,
    }
    return render(request, 'admin_panel/agency/b2b_ledger.html', context)


@login_required
def b2b_analytics(request):
    """
    Comprehensive Monthly Profit & Performance Analysis:
      1. Individual Candidate / Customer-wise Breakdown (B2B & B2C)
      2. Individual B2B Agency Agent-wise Breakdown & Commissions
      3. Individual Staff-wise Breakdown
      4. Month-by-Month Financial Trend & Net Agency Profit Analysis
    """
    db = get_tenant_db(request)
    ensure_default_settings(db)

    # Filter params
    current_year = timezone.now().year
    try:
        year = int(request.GET.get('year', current_year))
    except (ValueError, TypeError):
        year = current_year

    month_filter = request.GET.get('month', '').strip()
    agent_filter = request.GET.get('agent_id', '').strip()
    client_type_filter = request.GET.get('client_type', '').strip()

    # Base candidate queryset
    cands_qs = Candidate.objects.using(db).select_related('b2b_agent', 'b2b_staff', 'visa_lot').filter(created_at__year=year)
    if month_filter and month_filter.isdigit():
        cands_qs = cands_qs.filter(created_at__month=int(month_filter))
    if agent_filter:
        cands_qs = cands_qs.filter(Q(b2b_agent_id=agent_filter) | Q(agent_id=agent_filter))
    if client_type_filter in ['b2b', 'b2c']:
        cands_qs = cands_qs.filter(client_type=client_type_filter)

    candidates = list(cands_qs.order_by('-created_at'))

    # 1. Candidate-wise Profit Analysis
    candidate_items = []
    tot_cand_billing = Decimal('0.00')
    tot_cand_collected = Decimal('0.00')
    tot_cand_due = Decimal('0.00')
    tot_cand_est_cost = Decimal('0.00')
    tot_cand_net_profit = Decimal('0.00')

    for c in candidates:
        fee = c.total_amount or Decimal('0.00')
        paid = c.paid_amount or Decimal('0.00')
        due = c.due_amount or Decimal('0.00')

        # Estimated cost: air ticket price if recorded + visa lot base cost (assumed ~60% of lot price or ticket price)
        est_cost = Decimal('0.00')
        if c.ticket_price and c.ticket_price > 0:
            est_cost += Decimal(str(c.ticket_price))
        if c.visa_lot and c.visa_lot.price:
            # Assume 50% lot cost base if ticket is separate
            est_cost += (Decimal(str(c.visa_lot.price)) * Decimal('0.50')).quantize(Decimal('0.01'))
        elif fee > 0:
            # Baseline processing cost assumption 40% if no other breakdown
            est_cost += (fee * Decimal('0.40')).quantize(Decimal('0.01'))

        # Agent commission deduction if B2B
        comm_amt = Decimal('0.00')
        if c.client_type == 'b2b' and c.b2b_agent and c.b2b_agent.commission_rate:
            comm_amt = (fee * c.b2b_agent.commission_rate / Decimal('100.00')).quantize(Decimal('0.01'))

        net_profit = max(Decimal('0.00'), fee - est_cost - comm_amt)
        profit_margin_pct = int((net_profit / fee) * 100) if fee > 0 else 0

        tot_cand_billing += fee
        tot_cand_collected += paid
        tot_cand_due += due
        tot_cand_est_cost += est_cost
        tot_cand_net_profit += net_profit

        candidate_items.append({
            'candidate': c,
            'fee': fee,
            'paid': paid,
            'due': due,
            'est_cost': est_cost,
            'comm_amt': comm_amt,
            'net_profit': net_profit,
            'margin_pct': profit_margin_pct,
        })

    # 2. Agent-wise Profit Analysis
    b2b_agents = list(AgencyAgent.objects.using(db).filter(agent_type='b2b').order_by('name'))
    agent_items = []
    tot_agent_revenue = Decimal('0.00')
    tot_agent_collected = Decimal('0.00')
    tot_agent_due = Decimal('0.00')
    tot_agent_comm = Decimal('0.00')
    tot_agent_net_profit = Decimal('0.00')

    for ag in b2b_agents:
        ag_cands = Candidate.objects.using(db).filter(Q(b2b_agent=ag) | Q(agent=ag), created_at__year=year)
        if month_filter and month_filter.isdigit():
            ag_cands = ag_cands.filter(created_at__month=int(month_filter))

        c_fin = ag_cands.aggregate(tot=Sum('total_amount'), paid=Sum('paid_amount'), due=Sum('due_amount'))
        billed = c_fin['tot'] or Decimal('0.00')
        paid = c_fin['paid'] or Decimal('0.00')
        due = c_fin['due'] or Decimal('0.00')
        comm_rate = ag.commission_rate or Decimal('0.00')
        comm_earned = (billed * comm_rate / Decimal('100.00')).quantize(Decimal('0.01'))
        est_cost = (billed * Decimal('0.45')).quantize(Decimal('0.01'))
        agency_profit = max(Decimal('0.00'), billed - comm_earned - est_cost)

        tot_agent_revenue += billed
        tot_agent_collected += paid
        tot_agent_due += due
        tot_agent_comm += comm_earned
        tot_agent_net_profit += agency_profit

        agent_items.append({
            'agent': ag,
            'candidates_count': ag_cands.count(),
            'staff_count': ag.staff_members.count(),
            'billed': billed,
            'paid': paid,
            'due': due,
            'comm_rate': comm_rate,
            'comm_earned': comm_earned,
            'agency_profit': agency_profit,
        })
    agent_items.sort(key=lambda x: x['billed'], reverse=True)

    # 3. Agency Staff-wise Performance & Monthly Profit Analysis
    agency_staff_all = get_tenant_agency_staff(request)
    if request.user.is_tenant_staff:
        agency_staff_all = [s for s in agency_staff_all if s.id == request.user.id]

    staff_items = []
    for s in agency_staff_all:
        assigned_agents = list(AgencyAgent.objects.using(db).filter(assigned_staff_id=s.id))
        assigned_agents_ids = [ag.id for ag in assigned_agents]

        s_cands = Candidate.objects.using(db).filter(
            Q(agency_staff_id=s.id) | Q(b2b_agent_id__in=assigned_agents_ids),
            created_at__year=year
        )
        if month_filter and month_filter.isdigit():
            s_cands = s_cands.filter(created_at__month=int(month_filter))
        if agent_filter:
            s_cands = s_cands.filter(b2b_agent_id=agent_filter)

        s_fin = s_cands.aggregate(tot=Sum('total_amount'), paid=Sum('paid_amount'), due=Sum('due_amount'))
        rev = s_fin['tot'] or Decimal('0.00')
        col = s_fin['paid'] or Decimal('0.00')
        due = s_fin['due'] or Decimal('0.00')

        tot_comm = Decimal('0.00')
        for c in s_cands:
            if c.b2b_agent and c.b2b_agent.commission_rate and c.total_amount:
                tot_comm += (c.total_amount * c.b2b_agent.commission_rate / Decimal('100.00')).quantize(Decimal('0.01'))

        profit_contrib = max(Decimal('0.00'), rev - (rev * Decimal('0.40')) - tot_comm).quantize(Decimal('0.01'))

        staff_items.append({
            'staff': s,
            'name': s.get_full_name() or s.email,
            'email': s.email,
            'assigned_agents_count': len(assigned_agents),
            'candidates_count': s_cands.count(),
            'revenue_handled': rev,
            'paid_handled': col,
            'due_handled': due,
            'commission_generated': tot_comm,
            'profit_contribution': profit_contrib,
        })
    staff_items.sort(key=lambda x: x['revenue_handled'], reverse=True)

    # 4. Month-by-Month Trend Analysis (Jan - Dec for selected year)
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    monthly_trend = []
    year_b2b_tot = Decimal('0.00')
    year_b2c_tot = Decimal('0.00')
    year_profit_tot = Decimal('0.00')

    for m_idx, m_name in enumerate(month_names, start=1):
        m_cands = Candidate.objects.using(db).filter(created_at__year=year, created_at__month=m_idx)
        b2b_m = m_cands.filter(client_type='b2b')
        b2c_m = m_cands.filter(client_type='b2c')

        b2b_val = b2b_m.aggregate(s=Sum('total_amount'))['s'] or Decimal('0.00')
        b2b_col = b2b_m.aggregate(s=Sum('paid_amount'))['s'] or Decimal('0.00')
        b2c_val = b2c_m.aggregate(s=Sum('total_amount'))['s'] or Decimal('0.00')
        b2c_col = b2c_m.aggregate(s=Sum('paid_amount'))['s'] or Decimal('0.00')

        tot_rev = b2b_col + b2c_col
        # Est. Commission expense
        comm_m = (b2b_val * Decimal('0.05')).quantize(Decimal('0.01'))
        # Est. direct costs
        cost_m = ((b2b_val + b2c_val) * Decimal('0.40')).quantize(Decimal('0.01'))
        est_profit_m = max(Decimal('0.00'), (b2b_val + b2c_val) - comm_m - cost_m)

        year_b2b_tot += b2b_val
        year_b2c_tot += b2c_val
        year_profit_tot += est_profit_m

        monthly_trend.append({
            'month_num': m_idx,
            'month_name': m_name,
            'b2b_count': b2b_m.count(),
            'b2c_count': b2c_m.count(),
            'total_count': m_cands.count(),
            'b2b_revenue': b2b_val,
            'b2c_revenue': b2c_val,
            'total_revenue': b2b_val + b2c_val,
            'total_collected': tot_rev,
            'commission': comm_m,
            'est_profit': est_profit_m,
        })

    # Available years for filter (current year - 2 to current year + 1)
    years_list = [current_year - 2, current_year - 1, current_year, current_year + 1]

    context = {
        'year': year,
        'years_list': years_list,
        'month_filter': month_filter,
        'agent_filter': agent_filter,
        'client_type_filter': client_type_filter,
        'all_agents': b2b_agents,
        'candidate_items': candidate_items,
        'agent_items': agent_items,
        'staff_items': staff_items,
        'monthly_trend': monthly_trend,
        'tot_cand_billing': tot_cand_billing,
        'tot_cand_collected': tot_cand_collected,
        'tot_cand_due': tot_cand_due,
        'tot_cand_net_profit': tot_cand_net_profit,
        'tot_agent_revenue': tot_agent_revenue,
        'tot_agent_comm': tot_agent_comm,
        'tot_agent_net_profit': tot_agent_net_profit,
        'year_b2b_tot': year_b2b_tot,
        'year_b2c_tot': year_b2c_tot,
        'year_profit_tot': year_profit_tot,
    }
    return render(request, 'admin_panel/agency/b2b_analytics.html', context)

