"""Interface admin Django."""
from django.contrib import admin
from .models import Client, Facture, ParametresHotel, Extra, FactureExtra


class FactureExtraInline(admin.TabularInline):
    model = FactureExtra
    extra = 1
    fields = ('extra', 'quantite', 'prix_unitaire', 'total_price')
    readonly_fields = ('total_price',)


@admin.register(ParametresHotel)
class ParametresHotelAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Identité', {
            'fields': ('nom', 'adresse', 'code_postal', 'ville',
                       'telephone', 'fax', 'email', 'siret', 'capital')
        }),
        ('Tarifs par défaut', {
            'fields': ('tva_defaut', 'taxe_sejour_defaut',
                       'taxe_sejour_pourcentage', 'prix_chambre_defaut')
        }),
        ('Hôtel', {
            'fields': ('nombre_chambres',)
        }),
    )

    def has_add_permission(self, request):
        return not ParametresHotel.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Extra)
class ExtraAdmin(admin.ModelAdmin):
    list_display = ('nom', 'prix_defaut', 'actif')
    list_filter = ('actif',)
    search_fields = ('nom',)


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('nom', 'prenom', 'civilite', 'email',
                    'telephone', 'ville', 'pays', 'cree_le')
    search_fields = ('nom', 'prenom', 'email', 'ville')
    list_filter = ('civilite', 'pays')
    ordering = ('nom', 'prenom')
    fieldsets = (
        ('Identité', {
            'fields': ('civilite', 'nom', 'prenom')
        }),
        ('Contact', {
            'fields': ('email', 'telephone', 'adresse', 'ville', 'pays')
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )


@admin.register(Facture)
class FactureAdmin(admin.ModelAdmin):
    list_display = (
        'numero_reservation', 'client', 'date_arrivee', 'date_depart',
        'statut', 'moyen_paiement', 'total_ttc_display'
    )
    list_filter = ('statut', 'moyen_paiement', 'date_arrivee')
    search_fields = ('numero_reservation', 'client__nom', 'client__prenom')
    date_hierarchy = 'date_arrivee'
    autocomplete_fields = ('client',)
    inlines = [FactureExtraInline]

    fieldsets = (
        ('Identification', {
            'fields': ('numero_reservation', 'client', 'date_edition', 'statut')
        }),
        ('Séjour', {
            'fields': ('date_arrivee', 'date_depart', 'numero_chambre',
                       'nombre_personnes', 'type_sejour')
        }),
        ('Tarification', {
            'fields': ('prix_chambre_ht', 'taux_tva', 'taux_taxe_sejour',
                       'taxe_sejour_unitaire', 'extras')
        }),
        ('Paiement', {
            'fields': ('moyen_paiement',)
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description='Total TTC')
    def total_ttc_display(self, obj):
        return f'{obj.total_ttc} \u20ac'
