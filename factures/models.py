"""
Modèles de la gestion des factures.
"""
from datetime import timedelta
from decimal import Decimal
from django.db import models
from django.urls import reverse
from django.utils import timezone


class ParametresHotel(models.Model):
    """Paramètres généraux de l'hôtel. Singleton (1 seule instance)."""
    nom = models.CharField(max_length=100, default='Hôtel pacific')
    adresse = models.CharField(max_length=200, default='40 rue du duc de guise')
    code_postal = models.CharField(max_length=10, default='62100')
    ville = models.CharField(max_length=100, default='Calais')
    telephone = models.CharField(max_length=30, default='0321345024')
    fax = models.CharField(max_length=30, default='0321975802', blank=True)
    email = models.EmailField(default='sunetap.yahi@gmail.com')
    siret = models.CharField(max_length=20, default='837873785')
    capital = models.CharField(max_length=20, default='1000 €')

    tva_defaut = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('10.00'),
        help_text='Taux de TVA par défaut (%)'
    )
    taxe_sejour_defaut = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('0.98'),
        help_text='Taxe de séjour par nuit/personne (€)'
    )
    taxe_sejour_pourcentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('2.00'),
        help_text='Taxe de séjour en pourcentage du montant HT (%)'
    )
    prix_chambre_defaut = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('52.96'),
        help_text='Prix chambre HT par nuit (€)'
    )
    nombre_chambres = models.PositiveIntegerField(
        default=17,
        help_text='Nombre total de chambres (pour statistiques d\'occupation)'
    )

    class Meta:
        verbose_name = 'Paramètres de l\'hôtel'
        verbose_name_plural = 'Paramètres de l\'hôtel'

    def __str__(self):
        return self.nom

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Client(models.Model):
    """Carnet d'adresses clients."""
    CIVILITE_CHOICES = [
        ('M.', 'Monsieur'),
        ('Mme', 'Madame'),
        ('Mlle', 'Mademoiselle'),
        ('Société', 'Société'),
    ]

    civilite = models.CharField(max_length=10, choices=CIVILITE_CHOICES, default='M.')
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    societe = models.CharField(max_length=150, blank=True, verbose_name='Societe')
    email = models.EmailField()
    telephone = models.CharField(max_length=30)
    adresse = models.TextField(blank=True)
    ville = models.CharField(max_length=100, blank=True)
    pays = models.CharField(max_length=100, blank=True, default='France')
    notes = models.TextField(blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nom', 'prenom']
        verbose_name = 'Client'
        verbose_name_plural = 'Clients'

    def __str__(self):
        identite = f'{self.civilite_abrev} {self.nom} {self.prenom}'.strip()
        return f'{identite} - {self.societe}' if self.societe else identite

    @property
    def civilite_abrev(self):
        if self.civilite and not self.civilite.endswith('.'):
            return self.civilite + '.'
        return self.civilite or ''

    def nom_complet_majuscule(self):
        civ = dict(self.CIVILITE_CHOICES).get(self.civilite, self.civilite)
        identite = f'{civ} {self.nom.upper()} {self.prenom.upper()}'.strip()
        return f'{identite} - {self.societe.upper()}' if self.societe else identite


class Extra(models.Model):
    """Service supplémentaire proposé par l'hôtel (Parking, Petit-déjeuner, etc.)."""
    nom = models.CharField(max_length=100, verbose_name='Nom')
    prix_defaut = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Prix par défaut'
    )
    actif = models.BooleanField(default=True, verbose_name='Actif')

    class Meta:
        verbose_name = 'Extra / Service'
        verbose_name_plural = 'Extras / Services'
        ordering = ['nom']

    def __str__(self):
        return self.nom


class Facture(models.Model):
    """Une facture de séjour."""
    STATUT_CHOICES = [
        ('PROVISOIRE', 'Document provisoire'),
        ('DEFINITIF', 'Facture définitive'),
        ('ACQUITTE', 'Facture acquittée'),
    ]

    PAIEMENT_CHOICES = [
        ('', 'Non spécifié'),
        ('Especes', 'Espèces'),
        ('Carte bancaire', 'Carte bancaire'),
        ('Virement', 'Virement'),
        ('Cheque', 'Chèque'),
        ('Booking', 'Booking / plateforme'),
    ]

    numero_reservation = models.CharField(
        max_length=20, unique=True, blank=True, null=True,
        verbose_name='N° réservation'
    )
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='factures')

    date_arrivee = models.DateField()
    date_depart = models.DateField()
    date_edition = models.DateField(default=timezone.localdate)

    numero_chambre = models.PositiveIntegerField(default=1)
    nombre_personnes = models.PositiveIntegerField(default=1)
    type_sejour = models.CharField(max_length=100, default='Standard Normal')

    prix_chambre_ht = models.DecimalField(
        max_digits=8, decimal_places=2,
        help_text='Prix HT par nuit'
    )
    taxe_sejour_unitaire = models.DecimalField(
        max_digits=6, decimal_places=2,
        default=Decimal('0.98'),
        help_text='Taxe séjour par nuit et par personne'
    )
    taux_tva = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=Decimal('10.00'),
        help_text='Taux de TVA en %'
    )
    taux_taxe_sejour = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=Decimal('2.00'),
        help_text='Taux de taxe de séjour en % du montant HT'
    )
    extras = models.DecimalField(
        max_digits=8, decimal_places=2,
        default=Decimal('0.00'),
        help_text='Ancien champ Extras (remplacé par FactureExtra)'
    )

    moyen_paiement = models.CharField(
        max_length=20, choices=PAIEMENT_CHOICES, blank=True,
        verbose_name='Moyen de paiement'
    )
    statut = models.CharField(
        max_length=20, choices=STATUT_CHOICES, default='PROVISOIRE'
    )
    notes = models.TextField(blank=True)

    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-cree_le']
        verbose_name = 'Facture'
        verbose_name_plural = 'Factures'

    def __str__(self):
        return f'Facture n°{self.numero_reservation} — {self.client}'

    def get_absolute_url(self):
        return reverse('facture_detail', kwargs={'pk': self.pk})

    def save(self, *args, **kwargs):
        if not self.numero_reservation:
            from django.utils import timezone
            now = timezone.localtime()
            base = now.strftime('HC%y%m%d%H%M')
            if not Facture.objects.filter(numero_reservation=base).exists():
                self.numero_reservation = base
            else:
                suffix = 1
                while Facture.objects.filter(numero_reservation=f'{base}{suffix}').exists():
                    suffix += 1
                self.numero_reservation = f'{base}{suffix}'
        super().save(*args, **kwargs)

    # === CALCULS ===

    @property
    def nombre_nuits(self):
        return max(1, (self.date_depart - self.date_arrivee).days)

    @property
    def dates_nuitees(self):
        nuits = []
        cur = self.date_arrivee
        while cur < self.date_depart:
            nuits.append(cur)
            cur += timedelta(days=1)
        return nuits

    @property
    def total_extras_calcule(self):
        extras_qs = self.facture_extras.all()
        if extras_qs.exists():
            return sum(e.total_price for e in extras_qs)
        return Decimal(self.extras or '0.00')

    @property
    def montant_sejour_ht(self):
        return (self.prix_chambre_ht * Decimal(self.nombre_nuits)).quantize(Decimal('0.01'))

    @property
    def montant_ht(self):
        return (self.montant_sejour_ht + self.total_extras_calcule).quantize(Decimal('0.01'))

    @property
    def montant_tva(self):
        return (self.montant_ht * self.taux_tva / Decimal('100')).quantize(Decimal('0.01'))

    @property
    def montant_taxe_sejour(self):
        return (self.montant_ht * self.taux_taxe_sejour / Decimal('100')).quantize(Decimal('0.01'))

    @property
    def total_ttc(self):
        return (self.montant_ht + self.montant_tva + self.montant_taxe_sejour).quantize(Decimal('0.01'))

    @property
    def reste_du(self):
        if self.statut == 'ACQUITTE':
            return Decimal('0.00')
        return self.total_ttc

    @property
    def total_ht(self):
        return self.montant_ht

    @property
    def total_tva(self):
        return self.montant_tva

    @property
    def total_taxe_sejour(self):
        return self.montant_taxe_sejour

    @property
    def total_hotel(self):
        return (self.total_ttc - self.total_extras_calcule).quantize(Decimal('0.01'))

    @property
    def tva_par_nuit(self):
        return (self.prix_chambre_ht * self.taux_tva / Decimal('100')).quantize(Decimal('0.01'))

    @property
    def prix_chambre_ttc_par_nuit(self):
        return (self.prix_chambre_ht + self.tva_par_nuit).quantize(Decimal('0.01'))

    @property
    def taxe_sejour_par_nuit(self):
        return (self.taxe_sejour_unitaire * Decimal(self.nombre_personnes)).quantize(Decimal('0.01'))

    @property
    def total_chambre(self):
        return (self.prix_chambre_ttc_par_nuit * Decimal(self.nombre_nuits)).quantize(Decimal('0.01'))

class FactureExtra(models.Model):
    """Lien entre une facture et un extra/service avec quantité et prix."""
    facture = models.ForeignKey(
        Facture, on_delete=models.CASCADE,
        related_name='facture_extras'
    )
    extra = models.ForeignKey(
        Extra, on_delete=models.PROTECT,
        verbose_name='Extra'
    )
    quantite = models.PositiveIntegerField(default=1, verbose_name='Quantité')
    prix_unitaire = models.DecimalField(
        max_digits=8, decimal_places=2,
        verbose_name='Prix unitaire'
    )
    total_price = models.DecimalField(
        max_digits=10, decimal_places=2,
        editable=False,
        verbose_name='Total'
    )

    class Meta:
        verbose_name = 'Extra de facture'
        verbose_name_plural = 'Extras de facture'

    def __str__(self):
        return f'{self.extra.nom} x{self.quantite}'

    def save(self, *args, **kwargs):
        self.total_price = (Decimal(str(self.quantite)) * self.prix_unitaire).quantize(Decimal('0.01'))
        super().save(*args, **kwargs)
