"""
Génération PDF d'une facture via ReportLab.
Reproduit fidèlement le format Hôtel pacific.
"""
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas

from .models import ParametresHotel


def _euro(value):
    """Format français 54,02 €."""
    return f'{value:.2f} €'.replace('.', ',')


def _date_fr(d):
    return d.strftime('%d/%m/%Y')


def _draw_hotel_header(c, page_w, y, params):
    c.setFont('Helvetica-Bold', 16)
    c.drawCentredString(page_w / 2, y, params.nom)
    y -= 7 * mm
    c.setFont('Helvetica', 11)
    c.drawCentredString(page_w / 2, y, params.adresse)
    y -= 5 * mm
    c.drawCentredString(page_w / 2, y, f'{params.code_postal}  {params.ville}')
    y -= 5 * mm
    c.drawCentredString(page_w / 2, y, f'Tél. : {params.telephone} Fax : {params.fax}')
    y -= 5 * mm
    c.drawCentredString(page_w / 2, y, params.email)
    y -= 12 * mm
    return y


def _draw_header(c, page_w, y, params, facture):
    y = _draw_hotel_header(c, page_w, y, params)

    c.setFont('Helvetica', 10)
    c.drawRightString(page_w - 20 * mm, y, f'Éditée le {_date_fr(facture.date_edition)}')
    y -= 12 * mm

    statut_label = dict(facture.STATUT_CHOICES).get(facture.statut, facture.statut).upper()
    c.setFont('Helvetica-Bold', 11)
    c.drawString(20 * mm, y, statut_label)
    c.setFont('Helvetica', 10)
    pn = c.getPageNumber()
    c.drawRightString(page_w - 20 * mm, y, f'Page   {pn}')
    y -= 8 * mm

    c.setFont('Helvetica', 10)
    c.drawString(20 * mm, y, f'Réservation n° {facture.numero_reservation}')
    c.setFont('Helvetica-Bold', 12)
    c.drawCentredString(page_w / 2, y, facture.client.nom_complet_majuscule())
    c.setFont('Helvetica', 10)
    y -= 6 * mm
    c.drawString(20 * mm, y, f'Arrivée : {_date_fr(facture.date_arrivee)}')
    y -= 5 * mm
    c.drawString(20 * mm, y, f'Départ : {_date_fr(facture.date_depart)}')
    y -= 5 * mm
    mp = facture.get_moyen_paiement_display()
    if mp:
        c.setFont('Helvetica', 10)
        c.drawString(20 * mm, y, f'Paiement : {mp}')
    y -= 10 * mm
    return y


def _draw_footer(c, page_w, params):
    c.setFont('Helvetica', 9)
    c.drawCentredString(page_w / 2, 15 * mm, f'{params.nom.upper()} Capital : {params.capital}')
    c.drawCentredString(page_w / 2, 11 * mm, f'SIRET : {params.siret}')


def _new_page(c, page_w, params, facture):
    _draw_footer(c, page_w, params)
    c.showPage()
    return _draw_hotel_header(c, page_w, A4[1] - 20 * mm, params)


def generer_pdf_facture(facture):
    """Génère le PDF d'une facture et retourne les bytes."""
    params = ParametresHotel.get_solo()
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    page_w, page_h = A4

    y = _draw_header(c, page_w, page_h - 20 * mm, params, facture)

    # === TABLEAU SÉJOUR ===
    table_x = 20 * mm
    table_w = page_w - 40 * mm

    col_widths = [
        25 * mm,  # Date
        15 * mm,  # Chb
        15 * mm,  # vide
        15 * mm,  # Pers.
        20 * mm,  # vide
        25 * mm,  # Occupant
        25 * mm,  # Taxe séjour
        30 * mm,  # Chambre
    ]

    def x_col(i):
        return table_x + sum(col_widths[:i])

    row_h = 7 * mm

    # Ligne titre "Hôtel | Séjour : ..."
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.5)
    c.rect(table_x, y - row_h, table_w, row_h, stroke=1, fill=0)
    c.setFont('Helvetica-BoldOblique', 10)
    c.drawString(table_x + 2 * mm, y - row_h + 2 * mm, 'Hôtel')
    c.setFont('Helvetica', 10)
    c.drawString(table_x + 25 * mm, y - row_h + 2 * mm, f'Séjour :   {facture.type_sejour}')
    y -= row_h

    # En-tête colonnes
    c.rect(table_x, y - row_h, table_w, row_h, stroke=1, fill=0)
    c.setFont('Helvetica-Bold', 9)
    headers = ['Date', 'Chb', '', 'Pers.', '', 'Occupant', 'Taxe séjour', 'Chambre']
    for i, h in enumerate(headers):
        if i > 0:
            c.line(x_col(i), y, x_col(i), y - row_h)
        if h:
            if i >= 6:
                c.drawRightString(x_col(i) + col_widths[i] - 2 * mm, y - row_h + 2 * mm, h)
            else:
                c.drawString(x_col(i) + 2 * mm, y - row_h + 2 * mm, h)
    y -= row_h

    # Lignes de données (une par nuit)
    c.setFont('Helvetica', 9)
    taxe_par_nuit = facture.taxe_sejour_par_nuit
    prix_ttc_par_nuit = facture.prix_chambre_ttc_par_nuit

    for date_nuit in facture.dates_nuitees:
        c.rect(table_x, y - row_h, table_w, row_h, stroke=1, fill=0)
        for i in range(1, len(col_widths)):
            c.line(x_col(i), y, x_col(i), y - row_h)

        c.drawString(x_col(0) + 2 * mm, y - row_h + 2 * mm, _date_fr(date_nuit))
        c.drawString(x_col(1) + 2 * mm, y - row_h + 2 * mm, str(facture.numero_chambre))
        c.drawString(x_col(3) + 2 * mm, y - row_h + 2 * mm, str(facture.nombre_personnes))
        c.drawRightString(x_col(6) + col_widths[6] - 2 * mm, y - row_h + 2 * mm, _euro(taxe_par_nuit))
        c.drawRightString(x_col(7) + col_widths[7] - 2 * mm, y - row_h + 2 * mm, _euro(prix_ttc_par_nuit))

        y -= row_h

    # === TOTAUX SÉJOUR ===
    val_col_x = x_col(7)
    val_col_w = col_widths[7]
    taxe_col_x = x_col(6)
    taxe_col_w = col_widths[6]

    def ligne_total(label, val_chambre=None, val_taxe=None, bold=False):
        nonlocal y
        if val_taxe is not None:
            c.rect(taxe_col_x, y - row_h, taxe_col_w, row_h, stroke=1, fill=0)
        if val_chambre is not None:
            c.rect(val_col_x, y - row_h, val_col_w, row_h, stroke=1, fill=0)

        c.setFont('Helvetica-Bold' if bold else 'Helvetica', 9)
        c.drawRightString(taxe_col_x - 2 * mm, y - row_h + 2 * mm, label)
        if val_taxe is not None:
            c.drawRightString(taxe_col_x + taxe_col_w - 2 * mm, y - row_h + 2 * mm, _euro(val_taxe))
        if val_chambre is not None:
            c.drawRightString(val_col_x + val_col_w - 2 * mm, y - row_h + 2 * mm, _euro(val_chambre))
        y -= row_h

    ligne_total('Total séjour', val_chambre=facture.total_chambre, val_taxe=facture.total_taxe_sejour, bold=True)

    y -= 6 * mm

    # === SECTION EXTRAS ===
    extras = list(facture.facture_extras.all())
    if y < 35 * mm:
        y = _new_page(c, page_w, params, facture)
    if extras:
        # Titre extras
        c.setFont('Helvetica-BoldOblique', 10)
        c.drawString(20 * mm, y, 'Extras / Services supplémentaires')
        y -= row_h

        # En-tête
        c.setFont('Helvetica-Bold', 9)
        ext_cols = [40 * mm, 20 * mm, 30 * mm, 30 * mm]
        ext_x = 20 * mm
        ext_headers = ['Description', 'Quantité', 'Prix unitaire', 'Total']
        for i, (h, w) in enumerate(zip(ext_headers, ext_cols)):
            if h in ('Prix unitaire', 'Total'):
                c.drawRightString(ext_x + sum(ext_cols[:i+1]) - 2 * mm, y, h)
            else:
                c.drawString(ext_x + sum(ext_cols[:i]) + 2 * mm, y, h)
        y -= row_h

        # Données
        c.setFont('Helvetica', 9)
        for e in extras:
            d = [e.extra.nom, str(e.quantite), _euro(e.prix_unitaire), _euro(e.total_price)]
            for i, (val, w) in enumerate(zip(d, ext_cols)):
                if i >= 2:
                    c.drawRightString(ext_x + sum(ext_cols[:i+1]) - 2 * mm, y, val)
                else:
                    c.drawString(ext_x + sum(ext_cols[:i]) + 2 * mm, y, val)
            y -= row_h
        y -= 3 * mm

    # === TOTAUX GÉNÉRAUX ===
    if y < 60 * mm:
        y = _new_page(c, page_w, params, facture)
    c.setFont('Helvetica-Bold', 10)
    c.drawString(20 * mm, y, 'Total HT séjour')
    c.drawRightString(page_w - 20 * mm, y, _euro(facture.montant_sejour_ht))
    y -= 6 * mm

    if extras:
        c.setFont('Helvetica', 10)
        c.drawString(20 * mm, y, 'Total extras')
        c.drawRightString(page_w - 20 * mm, y, _euro(facture.total_extras_calcule))
        y -= 6 * mm

    c.setFont('Helvetica-Bold', 10)
    c.drawString(20 * mm, y, 'Total HT')
    c.drawRightString(page_w - 20 * mm, y, _euro(facture.montant_ht))
    y -= 6 * mm

    c.setFont('Helvetica', 10)
    c.drawString(20 * mm, y, f'TVA {facture.taux_tva}%')
    c.drawRightString(page_w - 20 * mm, y, _euro(facture.montant_tva))
    y -= 6 * mm

    c.drawString(20 * mm, y, f'Taxe séjour {facture.taux_taxe_sejour}%')
    c.drawRightString(page_w - 20 * mm, y, _euro(facture.montant_taxe_sejour))
    y -= 8 * mm

    c.setFont('Helvetica-Bold', 12)
    c.drawString(20 * mm, y, 'Total TTC')
    c.drawRightString(page_w - 20 * mm, y, _euro(facture.total_ttc))
    y -= 8 * mm

    c.setFont('Helvetica-Bold', 10)
    c.drawString(20 * mm, y, 'Reste dû')
    c.drawRightString(page_w - 20 * mm, y, _euro(facture.reste_du))

    _draw_footer(c, page_w, params)
    c.showPage()
    c.save()

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
