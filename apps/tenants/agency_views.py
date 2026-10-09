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
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count
from django.utils import timezone

from .agency_models import (
    AgencyAgent, AgencyCompany, AgencyPosition, SelectionGrade,
    VisaLot, Candidate, CandidatePayment, CandidateDocument, Requisition, AccountHeadGroup,
    ChartOfAccount, AccountVoucher, DailyMovement, LeaveSubmission, OfficeExpense
)

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
    """Ensure basic positions, grades, account heads, and agents exist for new agency tenant."""
    if not AgencyPosition.objects.using(db).exists():
        positions = ['Electrician', 'Driver', 'Mason', 'Plumber', 'Construction Worker', 'Welder', 'Cook', 'Maid', 'General Worker']
        for p in positions:
            AgencyPosition.objects.using(db).create(title=p)

    if not SelectionGrade.objects.using(db).exists():
        grades = ['Grade A (Primary)', 'Grade B (Secondary)', 'Grade C (Standard)', 'VVIP Selection']
        for g in grades:
            SelectionGrade.objects.using(db).create(grade_name=g)

    if not AgencyAgent.objects.using(db).exists():
        AgencyAgent.objects.using(db).create(name='Global Overseas Agency', phone='+8801700000000', email='agent@globaloverseas.com')

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


# ── 1. CANDIDATE REGISTRATION & LIST ─────────────────────────────────────────
@login_required
def candidate_list(request):
    """Candidate master list with multi-filter and search."""
    db = get_tenant_db(request)
    ensure_default_settings(db)

    query = request.GET.get('q', '').strip()
    sel_status = request.GET.get('selection_status', '')
    med_status = request.GET.get('medical_status', '')
    visa_status = request.GET.get('visa_status', '')

    candidates = Candidate.objects.using(db).all()

    if query:
        candidates = candidates.filter(
            Q(name__icontains=query) |
            Q(passport_number__icontains=query) |
            Q(registration_id__icontains=query) |
            Q(mobile__icontains=query)
        )
    if sel_status:
        candidates = candidates.filter(selection_status=sel_status)
    if med_status:
        candidates = candidates.filter(medical_status=med_status)
    if visa_status:
        candidates = candidates.filter(visa_stamping_status=visa_status)

    agents = AgencyAgent.objects.using(db).filter(is_active=True)
    positions = AgencyPosition.objects.using(db).filter(is_active=True)
    companies = AgencyCompany.objects.using(db).filter(is_active=True)
    grades = SelectionGrade.objects.using(db).all()
    visa_lots = VisaLot.objects.using(db).filter(is_active=True)

    # Compute total financial metrics across candidates
    totals = Candidate.objects.using(db).aggregate(
        total_value=Sum('total_amount'),
        total_paid=Sum('paid_amount'),
        total_due=Sum('due_amount')
    )

    context = {
        'candidates': candidates,
        'query': query,
        'agents': agents,
        'positions': positions,
        'companies': companies,
        'grades': grades,
        'visa_lots': visa_lots,
        'total_candidates': Candidate.objects.using(db).count(),
        'selected_count': Candidate.objects.using(db).filter(selection_status='selected').count(),
        'medical_fit_count': Candidate.objects.using(db).filter(medical_status='fit').count(),
        'visa_completed_count': Candidate.objects.using(db).filter(visa_stamping_status='visa_completed').count(),
        'total_package_value': totals['total_value'] or Decimal('0.00'),
        'total_collected': totals['total_paid'] or Decimal('0.00'),
        'total_due': totals['total_due'] or Decimal('0.00'),
        'accounts': ChartOfAccount.objects.using(db).all(),
        'next_cr_serial': AccountVoucher.get_next_serial('cr_cash'),
        'existing_vouchers': AccountVoucher.objects.using(db).all(),
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
            position=position,
            company=company,
            selection_grade=grade,
            visa_lot=visa_lot,
            total_amount=total_amt,
            applicable_sectors=applicable_sectors,
            notes=notes,
        )

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

        agent_id = request.POST.get('agent')
        position_id = request.POST.get('position')
        company_id = request.POST.get('company')
        grade_id = request.POST.get('selection_grade')

        candidate.agent = AgencyAgent.objects.using(db).filter(pk=agent_id).first() if agent_id else None
        candidate.position = AgencyPosition.objects.using(db).filter(pk=position_id).first() if position_id else None
        candidate.company = AgencyCompany.objects.using(db).filter(pk=company_id).first() if company_id else None
        candidate.selection_grade = SelectionGrade.objects.using(db).filter(pk=grade_id).first() if grade_id else None

        if 'applicable_sectors' in request.POST:
            candidate.applicable_sectors = request.POST.getlist('applicable_sectors')

        if 'photo' in request.FILES:
            candidate.photo = request.FILES['photo']

        candidate.save(using=db)
        messages.success(request, f'Candidate "{candidate.name}" updated successfully!')
        return redirect('admin_panel:candidate_list')

    return redirect('admin_panel:candidate_list')


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
    candidates = Candidate.objects.using(db).all()

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
            candidates = candidates.filter(selection_status=active_sub)

    elif stage_name == 'delegate':
        title = "Delegate Approval"
        sub_tabs = [
            ('all', 'All'),
            ('pending', 'Pending'),
            ('approved', 'Approved')
        ]
        if active_sub != 'all':
            candidates = candidates.filter(delegate_status=active_sub)

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
            candidates = candidates.filter(medical_status=active_sub)

    elif stage_name == 'police':
        title = "Police Clearance"
        sub_tabs = [
            ('all', 'All'),
            ('pending', 'Pending'),
            ('cleared', 'Cleared'),
            ('uncleared', 'Uncleared')
        ]
        if active_sub != 'all':
            candidates = candidates.filter(police_clearance_status=active_sub)

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
            candidates = candidates.filter(mofa_status='mofa_pending')
        elif active_sub == 'mofa_cleared':
            candidates = candidates.filter(mofa_status='mofa_cleared')
        elif active_sub == 'enjaz_pending':
            candidates = candidates.filter(enjaz_status='enjaz_pending')
        elif active_sub == 'finger_pending':
            candidates = candidates.filter(finger_status='finger_pending')
        elif active_sub == 'finger_completed':
            candidates = candidates.filter(finger_status='finger_completed')
        elif active_sub == 'visa_pending':
            candidates = candidates.filter(visa_stamping_status='visa_pending')
        elif active_sub == 'visa_completed':
            candidates = candidates.filter(visa_stamping_status='visa_completed')

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
            candidates = candidates.filter(training_status='training_pending')
        elif active_sub == 'training_completed':
            candidates = candidates.filter(training_status='training_completed')
        elif active_sub == 'manpower_pending':
            candidates = candidates.filter(manpower_status='manpower_pending')
        elif active_sub == 'manpower_completed':
            candidates = candidates.filter(manpower_status='manpower_completed')

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
            candidates = candidates.filter(ticket_status='ticket_issue')
        elif active_sub == 'ticket_pending':
            candidates = candidates.filter(ticket_status='ticket_pending')
        elif active_sub == 'ticket_completed':
            candidates = candidates.filter(ticket_status='ticket_completed')
        elif active_sub == 'noc_pending':
            candidates = candidates.filter(noc_status='noc_pending')
        elif active_sub == 'noc_completed':
            candidates = candidates.filter(noc_status='noc_completed')

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
            lot.save()
            messages.success(request, f'Visa Lot "{title}" ({lot.lot_number}) added successfully!')

        elif action == 'toggle_lot':
            lot_id = request.POST.get('lot_id')
            lot = VisaLot.objects.filter(pk=lot_id).first()
            if lot:
                lot.is_active = not lot.is_active
                lot.save()
                status_label = 'Active' if lot.is_active else 'Closed'
                messages.success(request, f'Visa Lot "{lot.title}" is now {status_label}.')

        elif action == 'edit_lot':
            lot_id = request.POST.get('lot_id')
            lot = VisaLot.objects.filter(pk=lot_id).first()
            if lot:
                lot.title = request.POST.get('title', '').strip() or 'Visa Lot'
                lot.country = request.POST.get('country', 'Saudi Arabia').strip()
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
                
                lot.save()
                messages.success(request, f'Visa Lot "{lot.title}" ({lot.lot_number}) updated successfully!')

        elif action == 'delete_lot':
            lot_id = request.POST.get('lot_id')
            lot = VisaLot.objects.filter(pk=lot_id).first()
            if lot:
                title = lot.title
                lot.delete()
                messages.success(request, f'Visa Lot "{title}" deleted successfully.')

        return redirect('admin_panel:okala_list')

    visa_lots = VisaLot.objects.all()
    return render(request, 'admin_panel/agency/okala_list.html', {'visa_lots': visa_lots})


# ── 4. FINANCIAL REQUISITIONS & ACCOUNTS ────────────────────────────────────
@login_required
def requisitions_list(request):
    """Payment, Receipt, and Contra Requisitions view."""
    req_type = request.GET.get('type', 'all')
    requisitions = Requisition.objects.all()

    if req_type == 'payment':
        requisitions = requisitions.filter(category__startswith='payment')
    elif req_type == 'receipt':
        requisitions = requisitions.filter(category__startswith='receipt')
    elif req_type == 'contra':
        requisitions = requisitions.filter(category='contra')

    if request.method == 'POST':
        category = request.POST.get('category')
        payee_or_payer = request.POST.get('payee_or_payer', '').strip()
        amount = request.POST.get('amount', '0')
        purpose = request.POST.get('purpose', '').strip()
        from_acc = request.POST.get('transfer_from_account', '').strip()
        to_acc = request.POST.get('transfer_to_account', '').strip()

        Requisition.objects.create(
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
    ensure_default_settings()

    active_tab = request.GET.get('tab', 'vouchers')
    vouchers = AccountVoucher.objects.all()
    accounts = ChartOfAccount.objects.all()
    groups = AccountHeadGroup.objects.all()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_voucher':
            voucher_type = request.POST.get('voucher_type')
            account_id = request.POST.get('account_id')
            amount = request.POST.get('amount', '0')
            narration = request.POST.get('narration', '').strip()
            reference_no = request.POST.get('reference_no', '').strip()

            acc = get_object_or_404(ChartOfAccount, pk=account_id)
            v = AccountVoucher.objects.create(
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
            acc.save()

            messages.success(request, f'Voucher {v.voucher_no} recorded successfully!')

        elif action == 'add_account':
            account_name = request.POST.get('account_name', '').strip()
            account_code = request.POST.get('account_code', '').strip()
            head_group_id = request.POST.get('head_group_id')
            tds_section = request.POST.get('tds_section', '').strip()
            balance = request.POST.get('balance', '0')

            grp = get_object_or_404(AccountHeadGroup, pk=head_group_id)
            ChartOfAccount.objects.create(
                account_name=account_name,
                account_code=account_code,
                head_group=grp,
                tds_section=tds_section,
                current_balance=Decimal(balance),
            )
            messages.success(request, f'Account Head [{account_code}] {account_name} created successfully!')

        elif action == 'edit_account':
            account_id = request.POST.get('account_id')
            acc = get_object_or_404(ChartOfAccount, pk=account_id)
            acc.account_name = request.POST.get('account_name', '').strip()
            acc.account_code = request.POST.get('account_code', '').strip()
            head_group_id = request.POST.get('head_group_id')
            if head_group_id:
                acc.head_group = get_object_or_404(AccountHeadGroup, pk=head_group_id)
            acc.tds_section = request.POST.get('tds_section', '').strip()
            balance_val = request.POST.get('balance', '0').strip()
            try:
                acc.current_balance = Decimal(balance_val)
            except Exception:
                pass
            acc.save()
            messages.success(request, f'Account Head [{acc.account_code}] {acc.account_name} updated successfully!')

        elif action == 'delete_account':
            account_id = request.POST.get('account_id')
            acc = get_object_or_404(ChartOfAccount, pk=account_id)
            acc_name = acc.account_name
            if acc.vouchers.exists():
                messages.error(request, f'Cannot delete account "{acc_name}" because it has {acc.vouchers.count()} recorded voucher(s).')
            else:
                acc.delete()
                messages.success(request, f'Account "{acc_name}" deleted successfully.')

        elif action == 'edit_voucher':
            voucher_id = request.POST.get('voucher_id')
            v = get_object_or_404(AccountVoucher, pk=voucher_id)
            old_acc = v.account
            old_amount = v.amount
            old_type = v.voucher_type

            # Reverse old balance effect
            if old_type in ['cr_cash', 'cr_cheque']:
                old_acc.current_balance -= old_amount
            else:
                old_acc.current_balance += old_amount
            old_acc.save()

            new_type = request.POST.get('voucher_type', old_type)
            new_account_id = request.POST.get('account_id')
            new_amount_str = request.POST.get('amount', str(old_amount))
            narration = request.POST.get('narration', '').strip()
            reference_no = request.POST.get('reference_no', '').strip()

            new_acc = get_object_or_404(ChartOfAccount, pk=new_account_id) if new_account_id else old_acc
            try:
                new_amount = Decimal(new_amount_str)
            except Exception:
                new_amount = old_amount

            v.voucher_type = new_type
            v.account = new_acc
            v.amount = new_amount
            v.narration = narration
            v.reference_no = reference_no
            v.save()

            # Apply new balance effect
            new_acc.refresh_from_db()
            if new_type in ['cr_cash', 'cr_cheque']:
                new_acc.current_balance += new_amount
            else:
                new_acc.current_balance -= new_amount
            new_acc.save()

            messages.success(request, f'Voucher {v.voucher_no} updated successfully!')

        elif action == 'delete_voucher':
            voucher_id = request.POST.get('voucher_id')
            v = get_object_or_404(AccountVoucher, pk=voucher_id)
            v_no = v.voucher_no
            acc = v.account
            if v.voucher_type in ['cr_cash', 'cr_cheque']:
                acc.current_balance -= v.amount
            else:
                acc.current_balance += v.amount
            acc.save()
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
    movements = DailyMovement.objects.all()
    leaves = LeaveSubmission.objects.all()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_movement':
            person_name = request.POST.get('person_name', '').strip()
            purpose = request.POST.get('purpose', '').strip()
            destination = request.POST.get('destination', '').strip()

            DailyMovement.objects.create(
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

            LeaveSubmission.objects.create(
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
    report_type = request.GET.get('report', 'summary')
    title = "Summary Report"

    data = []
    headers = []

    candidates = Candidate.objects.all()

    if report_type == 'agent_ledger':
        title = "Agent Ledger Report"
        headers = ['Agent Name', 'Code', 'Phone', 'Assigned Candidates', 'Balance / Commission']
        agents = AgencyAgent.objects.all()
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
    ensure_default_settings()

    active_tab = request.GET.get('tab', 'agents')

    agents = AgencyAgent.objects.all()
    companies = AgencyCompany.objects.all()
    positions = AgencyPosition.objects.all()
    grades = SelectionGrade.objects.all()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_agent':
            name = request.POST.get('name', '').strip()
            phone = request.POST.get('phone', '').strip()
            email = request.POST.get('email', '').strip()
            comp = request.POST.get('company_name', '').strip()
            AgencyAgent.objects.create(name=name, phone=phone, email=email, company_name=comp)
            messages.success(request, f'Agent "{name}" added successfully!')

        elif action == 'add_company':
            name = request.POST.get('name', '').strip()
            country = request.POST.get('country', 'Saudi Arabia')
            contact = request.POST.get('contact_person', '').strip()
            AgencyCompany.objects.create(name=name, country=country, contact_person=contact)
            messages.success(request, f'Company "{name}" added successfully!')

        elif action == 'add_position':
            title = request.POST.get('title', '').strip()
            code = request.POST.get('code', '').strip()
            AgencyPosition.objects.create(title=title, code=code)
            messages.success(request, f'Position "{title}" added successfully!')

        elif action == 'add_grade':
            grade_name = request.POST.get('grade_name', '').strip()
            desc = request.POST.get('description', '').strip()
            SelectionGrade.objects.create(grade_name=grade_name, description=desc)
            messages.success(request, f'Selection Grade "{grade_name}" added successfully!')

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
                expense.save()
                messages.success(request, f'Expense "{title}" of ৳{amount:,.2f} added successfully!')
            else:
                messages.error(request, 'Please provide a title and a valid amount.')

        elif action == 'delete':
            pk = request.POST.get('expense_id')
            expense = OfficeExpense.objects.filter(pk=pk).first()
            if expense:
                title = expense.title
                expense.delete()
                messages.success(request, f'Expense "{title}" deleted.')

        elif action == 'edit':
            pk = request.POST.get('expense_id')
            expense = OfficeExpense.objects.filter(pk=pk).first()
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
                expense.save()
                messages.success(request, f'Expense "{expense.title}" updated.')

        return redirect('admin_panel:office_expense_list')

    # Filters
    cat_filter = request.GET.get('category', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    expenses = OfficeExpense.objects.all()
    if cat_filter:
        expenses = expenses.filter(category=cat_filter)
    if date_from:
        expenses = expenses.filter(expense_date__gte=date_from)
    if date_to:
        expenses = expenses.filter(expense_date__lte=date_to)

    # Aggregates
    total_expense = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    month_expense = OfficeExpense.objects.filter(
        expense_date__year=timezone.now().year,
        expense_date__month=timezone.now().month
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # Category breakdown
    from django.db.models import Sum as DSum
    category_totals = (
        OfficeExpense.objects.values('category')
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
