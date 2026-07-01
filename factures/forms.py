"""Formulaires Django."""
from django import forms
from django.contrib.auth.models import User
from django.forms import inlineformset_factory
from .models import Facture, Client, FactureExtra, Extra


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['civilite', 'nom', 'prenom', 'email', 'telephone',
                  'adresse', 'ville', 'pays', 'notes']
        widgets = {
            'adresse': forms.Textarea(attrs={'rows': 2}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


class UserSettingsForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']


class FactureExtraForm(forms.ModelForm):
    class Meta:
        model = FactureExtra
        fields = ['extra', 'quantite', 'prix_unitaire']
        widgets = {
            'extra': forms.Select(attrs={'class': 'extra-select'}),
            'quantite': forms.NumberInput(attrs={'class': 'extra-quantite', 'min': 1}),
            'prix_unitaire': forms.NumberInput(attrs={'class': 'extra-prix', 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['extra'].queryset = Extra.objects.filter(actif=True)
        self.fields['extra'].empty_label = 'Choisir Extra'
        self.fields['extra'].label_from_instance = lambda obj: obj.nom


FactureExtraFormSet = inlineformset_factory(
    Facture, FactureExtra,
    form=FactureExtraForm,
    extra=3,
    can_delete=True,
    min_num=0,
)


class FactureForm(forms.ModelForm):
    nouveau_client = forms.BooleanField(
        required=False, label='Créer un nouveau client',
        initial=False
    )
    civilite = forms.ChoiceField(
        choices=Client.CIVILITE_CHOICES, required=False, label='Civilité'
    )
    nom = forms.CharField(max_length=100, label='Nom')
    prenom = forms.CharField(max_length=100, label='Prénom')
    email = forms.EmailField(label='Email')
    telephone = forms.CharField(max_length=30, label='Téléphone')

    class Meta:
        model = Facture
        fields = [
            'client',
            'date_arrivee', 'date_depart', 'date_edition',
            'numero_chambre', 'nombre_personnes', 'type_sejour',
            'prix_chambre_ht', 'taux_tva', 'taux_taxe_sejour',
            'taxe_sejour_unitaire',
            'statut', 'notes',
        ]
        widgets = {
            'date_arrivee': forms.DateInput(attrs={'type': 'date'}),
            'date_depart': forms.DateInput(attrs={'type': 'date'}),
            'date_edition': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['client'].required = False
        self.fields['client'].empty_label = '— Sélectionner un client —'
        self.fields['taxe_sejour_unitaire'].required = False
        self.fields['numero_chambre'].required = False
        self.fields['nombre_personnes'].required = False
        self.fields['type_sejour'].required = False
        self.fields['statut'].required = False
        self.fields['nom'].required = False
        self.fields['prenom'].required = False
        self.fields['email'].required = False
        self.fields['telephone'].required = False

    def clean(self):
        cleaned = super().clean()
        nouveau = cleaned.get('nouveau_client')
        client = cleaned.get('client')

        if nouveau:
            if not cleaned.get('nom') or not cleaned.get('prenom'):
                raise forms.ValidationError(
                    'Si "Nouveau client" est coché, nom et prénom sont obligatoires.'
                )
        elif not client:
            raise forms.ValidationError(
                'Sélectionne un client existant ou coche "Nouveau client".'
            )

        da = cleaned.get('date_arrivee')
        dd = cleaned.get('date_depart')
        if da and dd and dd <= da:
            raise forms.ValidationError('La date de départ doit être postérieure à l\'arrivée.')

        return cleaned

    def save(self, commit=True):
        if self.cleaned_data.get('nouveau_client'):
            client = Client.objects.create(
                civilite=self.cleaned_data['civilite'],
                nom=self.cleaned_data['nom'],
                prenom=self.cleaned_data['prenom'],
                email=self.cleaned_data.get('email', ''),
                telephone=self.cleaned_data.get('telephone', ''),
            )
            self.instance.client = client
        return super().save(commit=commit)


class PaymentForm(forms.Form):
    moyen_paiement = forms.ChoiceField(
        choices=[c for c in Facture.PAIEMENT_CHOICES if c[0] != ''],
        label='Moyen de paiement',
        widget=forms.RadioSelect
    )
