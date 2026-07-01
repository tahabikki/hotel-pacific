"""Vues de l'application."""
import calendar
import csv
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.db.models import ProtectedError, Sum, Count, Q
from django.db.models.functions import TruncMonth
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.utils import timezone

from .models import Facture, Client, ParametresHotel
from .forms import ClientForm, FactureForm, UserSettingsForm, FactureExtraFormSet
from .models import Extra, FactureExtra


ROOM_TYPES = {
    1: 'Twin',
    2: 'Single',
    3: 'Single',
    4: 'Double',
    5: 'Triple',
    6: 'Triple',
    7: 'Triple',
    8: 'Single',
    9: 'Double',
    10: 'Double',
    11: 'Single',
    12: 'Double',
    13: 'Double',
    14: 'Triple',
    15: 'Double',
    16: 'Triple',
    17: 'Triple',
}


def pagination_context(request):
    params = request.GET.copy()
    params.pop('page', None)
    encoded = params.urlencode()
    return f'&{encoded}' if encoded else ''


def planning_context(request, params):
    today = timezone.localdate()

    try:
        selected_date = date.fromisoformat(request.GET.get('date', ''))
    except (TypeError, ValueError):
        selected_date = today

    has_explicit_range = bool(request.GET.get('date_debut') and request.GET.get('date_fin'))

    if has_explicit_range:
        try:
            date_debut = date.fromisoformat(request.GET['date_debut'])
        except (TypeError, ValueError):
            date_debut = selected_date
        try:
            date_fin = date.fromisoformat(request.GET['date_fin'])
        except (TypeError, ValueError):
            date_fin = selected_date
        if date_debut > date_fin:
            date_debut, date_fin = date_fin, date_debut
    else:
        # Centered mode: show range around selected_date
        default_range = 14
        half = default_range // 2
        date_debut = selected_date - timedelta(days=half)
        date_fin = date_debut + timedelta(days=default_range - 1)

    range_size = (date_fin - date_debut).days + 1

    try:
        visible_month = date(
            int(request.GET.get('planner_year', selected_date.year)),
            int(request.GET.get('planner_month', selected_date.month)),
            1,
        )
    except (TypeError, ValueError):
        visible_month = date(selected_date.year, selected_date.month, 1)

    prev_month = visible_month.replace(day=1) - timedelta(days=1)
    next_month = (visible_month.replace(day=28) + timedelta(days=4)).replace(day=1)

    month_start = visible_month
    _, month_days_count = calendar.monthrange(visible_month.year, visible_month.month)
    month_end = visible_month.replace(day=month_days_count)

    month_factures = (
        Facture.objects
        .select_related('client')
        .filter(date_arrivee__lt=month_end + timedelta(days=1), date_depart__gt=month_start)
        .order_by('date_arrivee', 'numero_chambre')
    )

    calendar_weeks = []
    month_calendar = calendar.Calendar(firstweekday=0)
    for week in month_calendar.monthdatescalendar(visible_month.year, visible_month.month):
        week_days = []
        for day in week:
            day_reservations = [
                f for f in month_factures
                if f.date_arrivee <= day < f.date_depart
            ]
            arrivals = [f for f in month_factures if f.date_arrivee == day]
            departures = [f for f in month_factures if f.date_depart == day]
            occupancy = len(day_reservations)
            week_days.append({
                'date': day,
                'in_month': day.month == visible_month.month,
                'is_today': day == today,
                'is_selected': day == selected_date,
                'occupancy': occupancy,
                'arrivals': len(arrivals),
                'departures': len(departures),
                'reservations': day_reservations[:4],
                'level': 'high' if occupancy >= max(1, params.nombre_chambres * 0.75)
                         else 'medium' if occupancy >= max(1, params.nombre_chambres * 0.35)
                         else 'low' if occupancy else 'empty',
            })
        calendar_weeks.append(week_days)

    planner_start = date_debut
    planner_days = [planner_start + timedelta(days=i) for i in range(range_size)]
    planner_end = date_fin + timedelta(days=1)
    planner_factures = (
        Facture.objects
        .select_related('client')
        .filter(date_arrivee__lt=planner_end, date_depart__gt=planner_start)
        .order_by('numero_chambre', 'date_arrivee')
    )

    used_rooms = sorted({f.numero_chambre for f in planner_factures if f.numero_chambre})
    configured_rooms = list(range(1, params.nombre_chambres + 1))
    room_numbers = sorted(set(configured_rooms + used_rooms))
    room_rows = []
    for room in room_numbers:
        cells = []
        day_index = 0
        while day_index < len(planner_days):
            day = planner_days[day_index]
            reservations = [
                f for f in planner_factures
                if f.numero_chambre == room and f.date_arrivee <= day < f.date_depart
            ]
            if reservations:
                reservation = sorted(reservations, key=lambda f: (f.date_arrivee, f.pk))[0]
                visible_end = min(reservation.date_depart, planner_end)
                colspan = max(1, (visible_end - day).days)
                covered_days = planner_days[day_index:day_index + colspan]
                cells.append({
                    'date': day,
                    'reservations': [reservation],
                    'colspan': colspan,
                    'is_today': today in covered_days,
                    'is_selected': selected_date in covered_days,
                    'continues_from_before': reservation.date_arrivee < planner_start,
                    'continues_after': reservation.date_depart > planner_end,
                })
                day_index += colspan
            else:
                cells.append({
                    'date': day,
                    'reservations': [],
                    'colspan': 1,
                    'is_today': day == today,
                    'is_selected': day == selected_date,
                })
                day_index += 1
        room_rows.append({
            'room': room,
            'room_type': ROOM_TYPES.get(room, 'Double'),
            'cells': cells,
        })

    today_arrivals = Facture.objects.select_related('client').filter(date_arrivee=selected_date).order_by('numero_chambre')
    today_departures = Facture.objects.select_related('client').filter(date_depart=selected_date).order_by('numero_chambre')
    today_in_house = Facture.objects.select_related('client').filter(date_arrivee__lte=selected_date, date_depart__gt=selected_date).order_by('numero_chambre')

    previous_date = selected_date - timedelta(days=1)
    next_date = selected_date + timedelta(days=1)
    previous_date_debut = date_debut - timedelta(days=1) if previous_date < date_debut else date_debut
    previous_date_fin = date_fin - timedelta(days=1) if previous_date < date_debut else date_fin
    next_date_debut = date_debut + timedelta(days=1) if next_date > date_fin else date_debut
    next_date_fin = date_fin + timedelta(days=1) if next_date > date_fin else date_fin

    return {
        'today': today,
        'selected_date': selected_date,
        'date_debut': date_debut,
        'date_fin': date_fin,
        'previous_date': previous_date,
        'next_date': next_date,
        'previous_date_debut': previous_date_debut,
        'previous_date_fin': previous_date_fin,
        'next_date_debut': next_date_debut,
        'next_date_fin': next_date_fin,
        'visible_month': visible_month,
        'prev_month': prev_month,
        'next_month': next_month,
        'calendar_weeks': calendar_weeks,
        'planner_start': planner_start,
        'planner_days': planner_days,
        'room_rows': room_rows,
        'today_arrivals': today_arrivals,
        'today_departures': today_departures,
        'today_in_house': today_in_house,
    }


@login_required(login_url='/admin/login/')
def dashboard(request):
    """Tableau de bord principal avec planning operationnel et statistiques."""
    params = ParametresHotel.get_solo()
    date_debut = request.GET.get('date_debut', '')
    date_fin = request.GET.get('date_fin', '')
    statut_filtre = request.GET.get('statut', '')
    paiement_filtre = request.GET.get('paiement', '')
    mois_filtre = request.GET.get('mois', '')
    annee_filtre = request.GET.get('annee', '')

    qs = Facture.objects.select_related('client')
    if date_debut:
        qs = qs.filter(date_arrivee__gte=date_debut)
    if date_fin:
        qs = qs.filter(date_depart__lte=date_fin)
    if statut_filtre:
        qs = qs.filter(statut=statut_filtre)
    if paiement_filtre:
        qs = qs.filter(moyen_paiement=paiement_filtre)
    if mois_filtre:
        qs = qs.filter(date_arrivee__month=mois_filtre)
    if annee_filtre:
        qs = qs.filter(date_arrivee__year=annee_filtre)

    total_factures = qs.count()
    total_factures_payees = qs.filter(statut='ACQUITTE').count()

    total_ht = Decimal('0.00')
    total_paye = Decimal('0.00')
    for f in qs:
        total_ht += f.montant_ht
        if f.statut == 'ACQUITTE':
            total_paye += f.total_ttc

    tva_rate = params.tva_defaut / Decimal('100')
    taxe_rate = params.taxe_sejour_pourcentage / Decimal('100')
    tva_total = (total_ht * tva_rate).quantize(Decimal('0.01'))
    taxe_sejour_total = (total_ht * taxe_rate).quantize(Decimal('0.01'))
    total_ttc = (total_ht + tva_total + taxe_sejour_total).quantize(Decimal('0.01'))

    paiements_stats = (
        qs.filter(moyen_paiement__gt='')
        .values('moyen_paiement')
        .annotate(
            total_ht_sum=Sum(
                'prix_chambre_ht',
                field="prix_chambre_ht * CAST((julianday(date_depart) - julianday(date_arrivee)) AS INTEGER)",
                default=0
            ),
            count=Count('id')
        )
        .order_by('-total_ht_sum')
    )
    for p in paiements_stats:
        ht = p['total_ht_sum'] or Decimal('0.00')
        p['total'] = (ht * (Decimal('1') + tva_rate + taxe_rate)).quantize(Decimal('0.01'))

    stats_mensuelles = []
    mois_stats = (
        Facture.objects
        .annotate(mois=TruncMonth('date_arrivee'))
        .values('mois')
        .annotate(
            arrivees=Count('id'),
            nuits_total=Sum(
                'id',
                field="CAST((julianday(date_depart) - julianday(date_arrivee)) AS INTEGER)",
                default=0
            ),
            personnes_total=Sum('nombre_personnes', default=0),
            revenu_ht=Sum(
                'prix_chambre_ht',
                field="prix_chambre_ht * CAST((julianday(date_depart) - julianday(date_arrivee)) AS INTEGER)",
                default=0
            ),
        )
        .order_by('-mois')[:12]
    )
    for m in mois_stats:
        ht = m['revenu_ht'] or Decimal('0.00')
        m['revenu_total'] = (ht * (Decimal('1') + tva_rate + taxe_rate)).quantize(Decimal('0.01'))

        mois_date = m['mois']
        clients_ids = list(
            Facture.objects
            .filter(date_arrivee__year=mois_date.year, date_arrivee__month=mois_date.month)
            .values_list('client_id', flat=True)
            .distinct()
        )
        m['clients_uniques'] = len(clients_ids)

        clients_francais_ids = list(
            Facture.objects
            .filter(
                date_arrivee__year=mois_date.year,
                date_arrivee__month=mois_date.month,
                client__pays='France'
            )
            .values_list('client_id', flat=True)
            .distinct()
        )
        m['clients_francais'] = len(clients_francais_ids)
        m['clients_etrangers'] = m['clients_uniques'] - m['clients_francais']

        if params.nombre_chambres > 0:
            jours_dans_mois = 30
            nuits_disponibles = params.nombre_chambres * jours_dans_mois
            nuits_occupees = int(m['nuits_total'] or 0)
            m['taux_occupation'] = round(nuits_occupees / nuits_disponibles * 100, 1) if nuits_disponibles > 0 else 0
            m['nuits_occupees'] = nuits_occupees
            m['nuits_disponibles'] = nuits_disponibles
        else:
            m['taux_occupation'] = 0

        stats_mensuelles.append(m)

    recent_factures = Facture.objects.select_related('client')[:6]

    total_extras_revenu = Decimal('0.00')
    extras_stats = Extra.objects.annotate(
        total_quantite=Sum('factureextra__quantite', filter=Q(factureextra__facture__in=qs)),
        total_revenu=Sum('factureextra__total_price', filter=Q(factureextra__facture__in=qs)),
    ).order_by('-total_revenu')
    for e in extras_stats:
        if e.total_revenu:
            total_extras_revenu += e.total_revenu

    today = timezone.localdate()
    try:
        planner_month = int(request.GET.get('planner_month', today.month))
        planner_year = int(request.GET.get('planner_year', today.year))
        visible_month = date(planner_year, planner_month, 1)
    except (TypeError, ValueError):
        visible_month = date(today.year, today.month, 1)

    prev_month = visible_month.replace(day=1) - timedelta(days=1)
    next_month = (visible_month.replace(day=28) + timedelta(days=4)).replace(day=1)

    month_start = visible_month
    _, month_days_count = calendar.monthrange(visible_month.year, visible_month.month)
    month_end = visible_month.replace(day=month_days_count)

    month_factures = (
        Facture.objects
        .select_related('client')
        .filter(date_arrivee__lt=month_end + timedelta(days=1), date_depart__gt=month_start)
        .order_by('date_arrivee', 'numero_chambre')
    )

    calendar_weeks = []
    month_calendar = calendar.Calendar(firstweekday=0)
    for week in month_calendar.monthdatescalendar(visible_month.year, visible_month.month):
        week_days = []
        for day in week:
            day_reservations = [
                f for f in month_factures
                if f.date_arrivee <= day < f.date_depart
            ]
            arrivals = [f for f in month_factures if f.date_arrivee == day]
            departures = [f for f in month_factures if f.date_depart == day]
            occupancy = len(day_reservations)
            week_days.append({
                'date': day,
                'in_month': day.month == visible_month.month,
                'is_today': day == today,
                'occupancy': occupancy,
                'arrivals': len(arrivals),
                'departures': len(departures),
                'reservations': day_reservations[:3],
                'level': 'high' if occupancy >= max(1, params.nombre_chambres * 0.75)
                         else 'medium' if occupancy >= max(1, params.nombre_chambres * 0.35)
                         else 'low' if occupancy else 'empty',
            })
        calendar_weeks.append(week_days)

    try:
        bd_date = date.fromisoformat(request.GET.get('bd_date', ''))
    except (TypeError, ValueError):
        bd_date = today

    has_bd_range = bool(request.GET.get('bd_debut') and request.GET.get('bd_fin'))
    if has_bd_range:
        try:
            bd_debut = date.fromisoformat(request.GET['bd_debut'])
        except (TypeError, ValueError):
            bd_debut = bd_date
        try:
            bd_fin = date.fromisoformat(request.GET['bd_fin'])
        except (TypeError, ValueError):
            bd_fin = bd_date
        if bd_debut > bd_fin:
            bd_debut, bd_fin = bd_fin, bd_debut
    else:
        default_bd_range = 14
        half = default_bd_range // 2
        bd_debut = bd_date - timedelta(days=half)
        bd_fin = bd_debut + timedelta(days=default_bd_range - 1)

    planner_start = bd_debut
    range_size = (bd_fin - bd_debut).days + 1
    planner_days = [planner_start + timedelta(days=i) for i in range(range_size)]
    planner_end = bd_fin + timedelta(days=1)
    planner_factures = (
        Facture.objects
        .select_related('client')
        .filter(date_arrivee__lt=planner_end, date_depart__gt=planner_start)
        .order_by('numero_chambre', 'date_arrivee')
    )

    used_rooms = sorted({f.numero_chambre for f in planner_factures if f.numero_chambre})
    configured_rooms = list(range(1, params.nombre_chambres + 1))
    room_numbers = sorted(set(configured_rooms + used_rooms))
    room_rows = []
    for room in room_numbers:
        cells = []
        day_index = 0
        while day_index < len(planner_days):
            day = planner_days[day_index]
            reservations = [
                f for f in planner_factures
                if f.numero_chambre == room and f.date_arrivee <= day < f.date_depart
            ]
            if reservations:
                reservation = sorted(reservations, key=lambda f: (f.date_arrivee, f.pk))[0]
                visible_end = min(reservation.date_depart, planner_end)
                colspan = max(1, (visible_end - day).days)
                covered_days = planner_days[day_index:day_index + colspan]
                cells.append({
                    'date': day,
                    'reservations': [reservation],
                    'colspan': colspan,
                    'is_today': today in covered_days,
                    'continues_from_before': reservation.date_arrivee < planner_start,
                    'continues_after': reservation.date_depart > planner_end,
                })
                day_index += colspan
            else:
                cells.append({
                    'date': day,
                    'reservations': [],
                    'colspan': 1,
                    'is_today': day == today,
                })
                day_index += 1
        room_rows.append({'room': room, 'cells': cells})

    today_arrivals = Facture.objects.select_related('client').filter(date_arrivee=today).order_by('numero_chambre')
    today_departures = Facture.objects.select_related('client').filter(date_depart=today).order_by('numero_chambre')
    today_in_house = Facture.objects.select_related('client').filter(date_arrivee__lte=today, date_depart__gt=today).order_by('numero_chambre')

    context = {
        'params': params,
        'total_factures': total_factures,
        'total_clients': Client.objects.count(),
        'total_ht': total_ht,
        'tva_total': tva_total,
        'taxe_sejour_total': taxe_sejour_total,
        'total_ttc': total_ttc,
        'total_factures_payees': total_factures_payees,
        'total_paye': total_paye,
        'paiements_stats': paiements_stats,
        'stats_mensuelles': stats_mensuelles,
        'recent_factures': recent_factures,
        'date_debut': date_debut,
        'date_fin': date_fin,
        'statut_filtre': statut_filtre,
        'paiement_filtre': paiement_filtre,
        'mois_filtre': mois_filtre,
        'annee_filtre': annee_filtre,
        'statut_choices': Facture.STATUT_CHOICES,
        'paiement_choices': [c for c in Facture.PAIEMENT_CHOICES if c[0]],
        'extras_stats': extras_stats,
        'total_extras_revenu': total_extras_revenu,
        'visible_month': visible_month,
        'prev_month': prev_month,
        'next_month': next_month,
        'calendar_weeks': calendar_weeks,
        'today': today,
        'bd_date': bd_date,
        'previous_bd_date': bd_date - timedelta(days=1),
        'next_bd_date': bd_date + timedelta(days=1),
        'planner_start': planner_start,
        'planner_days': planner_days,
        'bd_debut': bd_debut,
        'bd_fin': bd_fin,
        'room_rows': room_rows,
        'today_arrivals': today_arrivals,
        'today_departures': today_departures,
        'today_in_house': today_in_house,
    }
    return render(request, 'factures/dashboard.html', context)


@login_required(login_url='/admin/login/')
def planning_reservations(request):
    """Grand planning operationnel des reservations."""
    params = ParametresHotel.get_solo()
    if params.nombre_chambres < 17:
        params.nombre_chambres = 17
        params.save(update_fields=['nombre_chambres'])

    context = {
        'params': params,
        **planning_context(request, params),
    }
    template = 'factures/planning_partial.html' if request.headers.get('x-requested-with') == 'XMLHttpRequest' else 'factures/planning_reservations.html'
    return render(request, template, context)


@login_required(login_url='/admin/login/')
def user_settings(request):
    """Profil utilisateur et changement de mot de passe."""
    profile_form = UserSettingsForm(instance=request.user, prefix='profile')
    password_form = PasswordChangeForm(request.user, prefix='password')

    if request.method == 'POST':
        if request.POST.get('form_kind') == 'profile':
            profile_form = UserSettingsForm(request.POST, instance=request.user, prefix='profile')
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Profil mis a jour.')
                return redirect('user_settings')
        elif request.POST.get('form_kind') == 'password':
            password_form = PasswordChangeForm(request.user, request.POST, prefix='password')
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Mot de passe mis a jour.')
                return redirect('user_settings')

    return render(request, 'factures/user_settings.html', {
        'profile_form': profile_form,
        'password_form': password_form,
    })


class ClientListView(LoginRequiredMixin, ListView):
    """Liste des clients avec recherche."""
    model = Client
    template_name = 'factures/clients_liste.html'
    context_object_name = 'clients'
    paginate_by = 50

    def get_queryset(self):
        qs = Client.objects.all()
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(nom__icontains=q) |
                Q(prenom__icontains=q) |
                Q(email__icontains=q) |
                Q(telephone__icontains=q)
            )
        return qs.order_by('nom', 'prenom')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        ctx['page_query'] = pagination_context(self.request)
        return ctx


class FactureListView(LoginRequiredMixin, ListView):
    """Liste des factures avec recherche."""
    model = Facture
    template_name = 'factures/facture_liste.html'
    context_object_name = 'factures'
    paginate_by = 20

    def get_queryset(self):
        qs = Facture.objects.select_related('client')
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(numero_reservation__icontains=q) |
                Q(client__nom__icontains=q) |
                Q(client__prenom__icontains=q)
            )
        statut = self.request.GET.get('statut', '').strip()
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        ctx['statut'] = self.request.GET.get('statut', '')
        ctx['statuts'] = Facture.STATUT_CHOICES
        ctx['page_query'] = pagination_context(self.request)
        return ctx


@login_required(login_url='/admin/login/')
def client_create(request):
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            client = form.save()
            messages.success(request, 'Client cree.')
            return redirect('clients_liste')
    else:
        form = ClientForm()

    return render(request, 'factures/client_form.html', {
        'form': form,
        'titre': 'Nouveau client',
    })


@login_required(login_url='/admin/login/')
def client_update(request, pk):
    client = get_object_or_404(Client, pk=pk)
    if request.method == 'POST':
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            form.save()
            messages.success(request, 'Client mis a jour.')
            return redirect('clients_liste')
    else:
        form = ClientForm(instance=client)

    return render(request, 'factures/client_form.html', {
        'form': form,
        'client': client,
        'titre': 'Modifier client',
    })


@login_required(login_url='/admin/login/')
def client_delete(request, pk):
    client = get_object_or_404(Client, pk=pk)
    if request.method == 'POST':
        try:
            client.delete()
            messages.success(request, 'Client supprime.')
        except ProtectedError:
            messages.error(request, 'Ce client possede des factures et ne peut pas etre supprime.')
        return redirect('clients_liste')
    return render(request, 'factures/client_confirm_delete.html', {'client': client})


@login_required(login_url='/admin/login/')
def facture_create(request):
    """Création d'une facture."""
    params = ParametresHotel.get_solo()
    initial = {
        'date_edition': timezone.localdate(),
        'taux_tva': str(params.tva_defaut),
        'taux_taxe_sejour': str(params.taxe_sejour_pourcentage),
        'taxe_sejour_unitaire': str(params.taxe_sejour_defaut),
        'prix_chambre_ht': str(params.prix_chambre_defaut),
    }
    if request.GET.get('date_arrivee'):
        initial['date_arrivee'] = request.GET.get('date_arrivee')
        try:
            initial['date_depart'] = (
                date.fromisoformat(request.GET.get('date_arrivee')) + timedelta(days=1)
            ).isoformat()
        except ValueError:
            pass
    if request.GET.get('numero_chambre'):
        initial['numero_chambre'] = request.GET.get('numero_chambre')
    paiement_choices = [c for c in Facture.PAIEMENT_CHOICES if c[0]]
    if request.method == 'POST':
        form = FactureForm(request.POST)
        formset = FactureExtraFormSet(request.POST)
        if form.is_valid():
            facture = form.save()
            mp = request.POST.get('moyen_paiement', '')
            if mp:
                facture.moyen_paiement = mp
                facture.statut = 'ACQUITTE'
                facture.save(update_fields=['moyen_paiement', 'statut'])
            formset = FactureExtraFormSet(request.POST, instance=facture)
            if formset.is_valid():
                formset.save()
                messages.success(request, 'Facture n\u00b0{} cr\u00e9\u00e9e.'.format(facture.numero_reservation))
                return redirect('facture_liste')
    else:
        form = FactureForm(initial=initial)
        formset = FactureExtraFormSet(instance=Facture())

    extras_list = Extra.objects.filter(actif=True).order_by('nom')
    return render(request, 'factures/facture_form.html', {
        'form': form,
        'formset': formset,
        'titre': 'Nouvelle facture',
        'paiement_choices': paiement_choices,
        'extras_list': extras_list,
    })


@login_required(login_url='/admin/login/')
def facture_update(request, pk):
    """Édition d'une facture."""
    facture = get_object_or_404(Facture, pk=pk)
    paiement_choices = [c for c in Facture.PAIEMENT_CHOICES if c[0]]
    if request.method == 'POST':
        form = FactureForm(request.POST, instance=facture)
        formset = FactureExtraFormSet(request.POST, instance=facture)
        if form.is_valid() and formset.is_valid():
            facture = form.save()
            mp = request.POST.get('moyen_paiement', '')
            if mp:
                facture.moyen_paiement = mp
                facture.statut = 'ACQUITTE'
            else:
                facture.moyen_paiement = ''
            facture.save(update_fields=['moyen_paiement', 'statut'])
            formset.save()
            messages.success(request, 'Facture mise \u00e0 jour.')
            return redirect('facture_detail', pk=facture.pk)
    else:
        form = FactureForm(instance=facture)
        formset = FactureExtraFormSet(instance=facture)

    extras_list = Extra.objects.filter(actif=True).order_by('nom')
    return render(request, 'factures/facture_form.html', {
        'form': form,
        'formset': formset,
        'facture': facture,
        'titre': f'Modifier facture n\u00b0{facture.numero_reservation}',
        'paiement_choices': paiement_choices,
        'extras_list': extras_list,
    })


@login_required(login_url='/admin/login/')
def facture_detail(request, pk):
    """Détail d'une facture (aperçu HTML)."""
    facture = get_object_or_404(Facture, pk=pk)
    extras = facture.facture_extras.all()
    previous_facture = (
        Facture.objects
        .filter(date_arrivee__lt=facture.date_arrivee)
        .order_by('-date_arrivee', '-pk')
        .first()
    ) or (
        Facture.objects
        .filter(date_arrivee=facture.date_arrivee, pk__lt=facture.pk)
        .order_by('-pk')
        .first()
    )
    next_facture = (
        Facture.objects
        .filter(date_arrivee__gt=facture.date_arrivee)
        .order_by('date_arrivee', 'pk')
        .first()
    ) or (
        Facture.objects
        .filter(date_arrivee=facture.date_arrivee, pk__gt=facture.pk)
        .order_by('pk')
        .first()
    )
    return render(request, 'factures/facture_detail.html', {
        'facture': facture,
        'extras': extras,
        'previous_facture': previous_facture,
        'next_facture': next_facture,
    })


@login_required(login_url='/admin/login/')
def facture_delete(request, pk):
    """Suppression."""
    facture = get_object_or_404(Facture, pk=pk)
    if request.method == 'POST':
        num = facture.numero_reservation
        facture.delete()
        messages.success(request, f'Facture n\u00b0{num} supprim\u00e9e.')
        return redirect('facture_liste')
    return render(request, 'factures/facture_confirm_delete.html', {
        'facture': facture,
    })


@login_required(login_url='/admin/login/')
def facture_pdf(request, pk):
    """Génération PDF."""
    from .pdf_generator import generer_pdf_facture

    facture = get_object_or_404(Facture, pk=pk)
    pdf_bytes = generer_pdf_facture(facture)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    filename = f'Facture_{facture.numero_reservation}_{facture.client.nom}.pdf'
    disposition = request.GET.get('disposition', 'inline')
    response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
    return response


@login_required(login_url='/admin/login/')
def export_csv(request):
    """Export CSV des factures avec choix des colonnes."""
    columns = request.GET.getlist('cols')
    if not columns:
        columns = [
            'numero_reservation', 'client', 'date_arrivee', 'date_depart',
            'nombre_nuits', 'nombre_personnes', 'montant_ht', 'montant_tva',
            'montant_taxe_sejour', 'total_extras', 'total_ttc', 'moyen_paiement',
            'statut'
        ]

    date_debut = request.GET.get('date_debut', '')
    date_fin = request.GET.get('date_fin', '')
    statut_filtre = request.GET.get('statut', '')
    paiement_filtre = request.GET.get('paiement', '')
    client_filtre = request.GET.get('client', '')

    qs = Facture.objects.select_related('client')
    if date_debut:
        qs = qs.filter(date_arrivee__gte=date_debut)
    if date_fin:
        qs = qs.filter(date_depart__lte=date_fin)
    if statut_filtre:
        qs = qs.filter(statut=statut_filtre)
    if paiement_filtre:
        qs = qs.filter(moyen_paiement=paiement_filtre)
    if client_filtre:
        qs = qs.filter(client_id=client_filtre)

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="factures_export.csv"'
    response.write('\ufeff')

    writer = csv.writer(response)

    header_map = {
        'numero_reservation': 'N\u00b0 R\u00e9servation',
        'client': 'Client',
        'date_arrivee': 'Date arriv\u00e9e',
        'date_depart': 'Date d\u00e9part',
        'nombre_nuits': 'Nuits',
        'nombre_personnes': 'Personnes',
        'montant_ht': 'Montant HT',
        'montant_tva': 'TVA',
        'montant_taxe_sejour': 'Taxe s\u00e9jour',
        'total_ttc': 'Total TTC',
        'moyen_paiement': 'Moyen paiement',
        'statut': 'Statut',
        'date_edition': 'Date \u00e9dition',
        'numero_chambre': 'Chambre',
        'type_sejour': 'Type s\u00e9jour',
        'extras': 'Extras',
        'notes': 'Notes',
    }
    writer.writerow([header_map.get(c, c) for c in columns])

    for f in qs:
        row = []
        for col in columns:
            if col == 'client':
                row.append(str(f.client))
            elif col == 'statut':
                row.append(f.get_statut_display())
            elif col == 'moyen_paiement':
                row.append(f.get_moyen_paiement_display() if f.moyen_paiement else '')
            elif col in ('date_arrivee', 'date_depart', 'date_edition'):
                row.append(getattr(f, col).strftime('%d/%m/%Y'))
            elif col in ('montant_ht', 'montant_tva', 'montant_taxe_sejour', 'total_ttc', 'extras', 'total_extras'):
                if col == 'total_extras':
                    val = f.total_extras_calcule
                else:
                    val = getattr(f, col, Decimal('0.00'))
                row.append(f'{val:.2f}'.replace('.', ','))
            elif col == 'extras_detail':
                extras_list = f.facture_extras.all()
                if extras_list:
                    details = '; '.join(f'{e.extra.nom} x{e.quantite} = {e.total_price} €' for e in extras_list)
                    row.append(details)
                else:
                    row.append('')
            elif col == 'nombre_nuits':
                row.append(str(f.nombre_nuits))
            else:
                row.append(str(getattr(f, col, '')))
        writer.writerow(row)

    return response


@login_required(login_url='/admin/login/')
def bilan(request):
    """Page Bilan général avec tableau filtré et boutons d'export."""
    params = ParametresHotel.get_solo()

    date_debut = request.GET.get('date_debut', '')
    date_fin = request.GET.get('date_fin', '')
    statut_filtre = request.GET.get('statut', '')
    paiement_filtre = request.GET.get('paiement', '')
    client_filtre = request.GET.get('client', '')

    qs = Facture.objects.select_related('client').order_by('-date_arrivee')
    if date_debut:
        qs = qs.filter(date_arrivee__gte=date_debut)
    if date_fin:
        qs = qs.filter(date_depart__lte=date_fin)
    if statut_filtre:
        qs = qs.filter(statut=statut_filtre)
    if paiement_filtre:
        qs = qs.filter(moyen_paiement=paiement_filtre)
    if client_filtre:
        qs = qs.filter(client_id=client_filtre)

    total_ht = Decimal('0.00')
    total_tva = Decimal('0.00')
    total_taxe = Decimal('0.00')
    total_extras = Decimal('0.00')
    total_ttc = Decimal('0.00')
    for f in qs:
        total_ht += f.montant_ht
        total_tva += f.montant_tva
        total_taxe += f.montant_taxe_sejour
        total_extras += f.total_extras_calcule
        total_ttc += f.total_ttc

    clients = Client.objects.all().order_by('nom', 'prenom')

    template = 'factures/bilan_results.html' if request.GET.get('_ajax') else 'factures/bilan.html'
    return render(request, template, {
        'params': params,
        'factures': qs,
        'total_ht': total_ht,
        'total_tva': total_tva,
        'total_taxe': total_taxe,
        'total_extras': total_extras,
        'total_ttc': total_ttc,
        'total_factures': qs.count(),
        'date_debut': date_debut,
        'date_fin': date_fin,
        'statut_filtre': statut_filtre,
        'paiement_filtre': paiement_filtre,
        'client_filtre': client_filtre,
        'clients': clients,
        'statut_choices': Facture.STATUT_CHOICES,
        'paiement_choices': [c for c in Facture.PAIEMENT_CHOICES if c[0]],
    })


@login_required(login_url='/admin/login/')
def export_pdf(request):
    """Export PDF d'un état financier."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas

    params = ParametresHotel.get_solo()

    date_debut = request.GET.get('date_debut', '')
    date_fin = request.GET.get('date_fin', '')
    statut_filtre = request.GET.get('statut', '')
    paiement_filtre = request.GET.get('paiement', '')
    client_filtre = request.GET.get('client', '')

    qs = Facture.objects.select_related('client')
    if date_debut:
        qs = qs.filter(date_arrivee__gte=date_debut)
    if date_fin:
        qs = qs.filter(date_depart__lte=date_fin)
    if statut_filtre:
        qs = qs.filter(statut=statut_filtre)
    if paiement_filtre:
        qs = qs.filter(moyen_paiement=paiement_filtre)
    if client_filtre:
        qs = qs.filter(client_id=client_filtre)

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    page_w, page_h = A4

    def _header(y):
        c.setFont('Helvetica-Bold', 16)
        c.drawCentredString(page_w / 2, y, params.nom)
        y -= 8 * mm
        c.setFont('Helvetica-Bold', 14)
        c.drawCentredString(page_w / 2, y, '\u00c9tat financier')
        y -= 8 * mm
        c.setFont('Helvetica', 10)
        today_str = "Aujourd'hui"
        debut_str = "Début"
        dash = "\u2014"
        periode = f'Période: {date_debut or debut_str} {dash} {date_fin or today_str}'
        c.drawCentredString(page_w / 2, y, periode)
        y -= 8 * mm
        edited_str = "Édité le"
        c.drawCentredString(page_w / 2, y, f'{edited_str} {timezone.localdate().strftime("%d/%m/%Y")}')
        y -= 15 * mm
        return y

    def _footer():
        c.setFont('Helvetica', 8)
        c.drawCentredString(page_w / 2, 15 * mm, f'{params.nom.upper()} | SIRET: {params.siret}')

    def _new_page():
        _footer()
        c.showPage()
        nonlocal y
        y = _header(page_h - 20 * mm)

    y = _header(page_h - 20 * mm)

    total_ht = Decimal('0.00')
    total_tva = Decimal('0.00')
    total_taxe = Decimal('0.00')
    total_extras = Decimal('0.00')
    total_factures = 0
    paiements = {}

    for f in qs:
        total_ht += f.montant_ht
        total_tva += f.montant_tva
        total_taxe += f.montant_taxe_sejour
        total_extras += f.total_extras_calcule
        total_factures += 1
        mp = f.moyen_paiement or 'Non sp\u00e9cifi\u00e9'
        paiements[mp] = paiements.get(mp, 0) + 1

    total_ttc = total_ht + total_tva + total_taxe

    def _euro(val):
        return f'{val:.2f} \u20ac'.replace('.', ',')

    # === Détail des factures ===
    y -= 10 * mm
    c.setFont('Helvetica-Bold', 12)
    c.drawString(20 * mm, y, 'D\u00e9tail des factures')
    y -= 8 * mm

    # En-tête de tableau
    c.setFont('Helvetica-Bold', 7)
    headers = ['N\u00b0', 'Client', 'Arriv\u00e9e', 'D\u00e9part', 'HT', 'Extras', 'TVA', 'Taxe', 'Total']
    col_widths = [20, 34, 20, 20, 16, 14, 14, 14, 18]
    x_start = 20 * mm
    for i, (h, w) in enumerate(zip(headers, col_widths)):
        c.drawString(x_start + sum(col_widths[:i]) * mm, y, h)
    y -= 6 * mm

    c.setFont('Helvetica', 7)
    for f in qs:
        if y < 30 * mm:
            _new_page()
            c.setFont('Helvetica', 7)
        data = [
            str(f.numero_reservation),
            str(f.client)[:16],
            f.date_arrivee.strftime('%d/%m/%Y'),
            f.date_depart.strftime('%d/%m/%Y'),
            _euro(f.montant_ht),
            _euro(f.total_extras_calcule),
            _euro(f.montant_tva),
            _euro(f.montant_taxe_sejour),
            _euro(f.total_ttc),
        ]
        for i, (d, w) in enumerate(zip(data, col_widths)):
            c.drawString(x_start + sum(col_widths[:i]) * mm, y, d)
        y -= 5 * mm

    # === Résumé ===
    if y < 50 * mm:
        _new_page()
    y -= 6 * mm

    c.setFont('Helvetica', 8)
    items = [
        ('Chiffre d\'affaires (HT)', _euro(total_ht)),
        ('TVA ({0}%)'.format(params.tva_defaut), _euro(total_tva)),
        ('Taxe s\u00e9jour ({0}%)'.format(params.taxe_sejour_pourcentage), _euro(total_taxe)),
    ]
    table_right = x_start + sum(col_widths) * mm
    for label, val in items:
        c.drawString(x_start, y, label)
        c.drawRightString(table_right, y, val)
        y -= 5 * mm

    c.setFont('Helvetica-Bold', 9)
    c.setStrokeColor(colors.HexColor('#3d1620'))
    c.setLineWidth(0.5)
    c.line(x_start, y, table_right, y)
    y -= 3 * mm
    c.drawString(x_start, y, 'Total TTC')
    c.drawRightString(table_right, y, _euro(total_ttc))

    _footer()
    c.save()
    pdf_bytes = buffer.getvalue()
    buffer.close()

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="etat_financier.pdf"'
    return response
