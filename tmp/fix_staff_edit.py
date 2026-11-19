import re

filepath = 'apps/tenants/admin_views.py'
content = open(filepath, encoding='utf-8').read()

# Find the start of staff_edit function
start_marker = '@login_required\ndef staff_edit(request, pk):'
end_marker = '\n\n@login_required\ndef staff_toggle_ban'

start = content.find(start_marker)
end = content.find(end_marker)

if start == -1 or end == -1:
    print(f'ERROR: start={start}, end={end}')
    exit(1)

new_block = '''@login_required
def staff_edit(request, pk):
    """Agency Admin updates staff profile, password, and assigns B2B agents directly."""
    if not (request.user.is_tenant_admin or request.user.is_super_admin):
        messages.error(request, 'You do not have permission to edit staff accounts.')
        return redirect('admin_panel:dashboard')

    staff = get_object_or_404(User, pk=pk, tenant_id=request.user.tenant_id, role=User.Role.TENANT_STAFF)

    if request.method == 'POST':
        first_name   = request.POST.get('first_name', '').strip()
        last_name    = request.POST.get('last_name', '').strip()
        email        = request.POST.get('email', '').strip()
        mobile       = request.POST.get('mobile', '').strip()
        new_password = request.POST.get('new_password', '').strip()

        if not email:
            messages.error(request, 'Email address is required.')
            return redirect('admin_panel:staff_list')

        if email.lower() != staff.email.lower():
            if User.objects.filter(email__iexact=email).exclude(pk=staff.pk).exists():
                messages.error(request, f'An account with email "{email}" already exists.')
                return redirect('admin_panel:staff_list')
            staff.email = email

        staff.first_name = first_name
        staff.last_name  = last_name
        staff.mobile     = mobile

        if new_password:
            if len(new_password) < 6:
                messages.error(request, 'Password must be at least 6 characters.')
                return redirect('admin_panel:staff_list')
            staff.set_password(new_password)

        staff.save()

        db = get_tenant_db(request)
        staff_display_name = staff.get_full_name() or staff.email

        from apps.tenants.agency_models import AgencyAgent

        if 'agent_assignments_submitted' in request.POST:
            # Parse submitted agent IDs safely
            selected_ids = []
            for aid in request.POST.getlist('assigned_agent_ids'):
                try:
                    selected_ids.append(int(aid))
                except (ValueError, TypeError):
                    pass

            try:
                # Step 1: Unassign agents previously owned by this staff that were unchecked
                AgencyAgent.objects.using(db).filter(
                    assigned_staff_id=staff.id
                ).exclude(id__in=selected_ids).update(
                    assigned_staff_id=None,
                    assigned_staff_name='',
                    assigned_staff_email='',
                )
                # Step 2: Assign all checked agents exclusively to this staff member
                if selected_ids:
                    AgencyAgent.objects.using(db).filter(id__in=selected_ids).update(
                        assigned_staff_id=staff.id,
                        assigned_staff_name=staff_display_name,
                        assigned_staff_email=staff.email,
                    )
                messages.success(
                    request,
                    f'Staff "{staff.email}" saved. {len(selected_ids)} B2B agent(s) assigned successfully.'
                )
            except Exception as exc:
                messages.warning(
                    request,
                    f'Staff details saved, but agent assignment failed: {exc}'
                )
        else:
            # No agent panel submitted — just refresh cached name/email on already-assigned agents
            try:
                AgencyAgent.objects.using(db).filter(assigned_staff_id=staff.id).update(
                    assigned_staff_name=staff_display_name,
                    assigned_staff_email=staff.email,
                )
            except Exception:
                pass
            messages.success(request, f'Staff member "{staff.email}" updated successfully!')

        return redirect('admin_panel:staff_list')

    return redirect('admin_panel:staff_list')'''

new_content = content[:start] + new_block + content[end:]
open(filepath, 'w', encoding='utf-8').write(new_content)
print('staff_edit replaced successfully')
