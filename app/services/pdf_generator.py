"""PDF generation service for financial documents.

Uses reportlab to generate printable PDFs for:
  - G50 monthly declaration
  - CNAS quarterly declaration
  - Journal entries listing (per entity/period)
  - Grand Livre (general ledger extract)
  - Balance des comptes (trial balance)
"""
import io
from datetime import datetime
from decimal import Decimal
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable,
)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT


def _fmt(n) -> str:
    """Format number as Algerian DA currency."""
    if n is None:
        return "0,00"
    v = float(n)
    integer = int(v)
    decimals = abs(v - integer)
    int_str = f"{integer:,}".replace(",", " ")
    return f"{int_str},{decimals * 100:02.0f}"


def _header(story, styles, title: str, entity_name: str, period: str):
    """Add standard header to PDF."""
    story.append(Paragraph("Groupe Dendani", styles["Title"]))
    story.append(Paragraph(entity_name, styles["Heading2"]))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(title, styles["Heading1"]))
    story.append(Paragraph(f"Periode : {period}", styles["Normal"]))
    story.append(Spacer(1, 2 * mm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0d9488")))
    story.append(Spacer(1, 6 * mm))


def _footer_style():
    return ParagraphStyle(
        "Footer", fontSize=7, textColor=colors.grey,
        alignment=TA_CENTER,
    )


def _build_pdf(story, title="Document") -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=20 * mm,
        title=title,
    )
    doc.build(story)
    return buf.getvalue()


def _table_style():
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d9488")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ])


# ═══════════════════════════════════════════════════════════════════════════
# G50 Monthly Declaration PDF
# ═══════════════════════════════════════════════════════════════════════════

def generate_g50_pdf(data: dict, entity_name: str) -> bytes:
    """Generate G50 monthly tax declaration PDF."""
    styles = getSampleStyleSheet()
    story = []

    MOIS = ["", "Janvier", "Fevrier", "Mars", "Avril", "Mai", "Juin",
            "Juillet", "Aout", "Septembre", "Octobre", "Novembre", "Decembre"]
    mois_label = MOIS[data.get("mois", 0)]
    period = f"{mois_label} {data.get('annee', '')}"

    _header(story, styles, "Declaration G50 — Serie G N 50", entity_name, period)

    # Info block
    info_data = [
        ["NIF :", "A renseigner", "Exercice :", str(data.get("annee", ""))],
        ["Activite :", "Promotion immobiliere", "Mois :", mois_label],
    ]
    info_table = Table(info_data, colWidths=[3 * cm, 5 * cm, 3 * cm, 5 * cm])
    info_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 8 * mm))

    # Main table
    rows = [
        ["Code", "Designation", "Base (DA)", "Taux", "Montant (DA)"],
        ["I", "Chiffre d'affaires HT", _fmt(data.get("ca_ht")), "", ""],
        ["II", "TVA Collectee", _fmt(data.get("ca_ht")), "19%", _fmt(data.get("tva_collectee"))],
        ["III", "TVA Deductible", "", "", _fmt(data.get("tva_deductible"))],
        ["IV", "TVA Nette a payer (II - III)", "", "", _fmt(data.get("tva_nette"))],
        ["V", "TAP — Taxe sur l'Activite Professionnelle", _fmt(data.get("ca_ht")), "2%", _fmt(data.get("tap"))],
        ["VI", "IBS — Acompte provisionnel", "", "", _fmt(data.get("ibs_acompte"))],
        ["VII", "IRG — Retenu a la source (salaires)", "", "", _fmt(data.get("irg"))],
        ["VIII", "Timbre fiscal", "", "", _fmt(data.get("timbre"))],
        ["", "", "", "", ""],
        ["", "TOTAL A PAYER", "", "", _fmt(data.get("total_a_payer"))],
    ]

    col_widths = [1.5 * cm, 8 * cm, 3 * cm, 1.8 * cm, 3.5 * cm]
    table = Table(rows, colWidths=col_widths)
    style = _table_style()
    # Right-align amounts
    style.add("ALIGN", (2, 1), (2, -1), "RIGHT")
    style.add("ALIGN", (4, 1), (4, -1), "RIGHT")
    # Bold total row
    style.add("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")
    style.add("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f0fdfa"))
    style.add("FONTSIZE", (4, -1), (4, -1), 11)
    table.setStyle(style)
    story.append(table)

    story.append(Spacer(1, 15 * mm))
    story.append(Paragraph(
        f"Document genere le {datetime.now().strftime('%d/%m/%Y a %H:%M')} — GFI v7.0",
        _footer_style(),
    ))

    return _build_pdf(story, f"G50_{data.get('periode', '')}")


# ═══════════════════════════════════════════════════════════════════════════
# CNAS Quarterly Declaration PDF
# ═══════════════════════════════════════════════════════════════════════════

def generate_cnas_pdf(data: dict, entity_name: str) -> bytes:
    """Generate CNAS quarterly declaration PDF."""
    styles = getSampleStyleSheet()
    story = []

    period = data.get("periode", "")
    _header(story, styles, "Declaration CNAS Trimestrielle", entity_name, period)

    rows = [
        ["Designation", "Montant (DA)"],
        ["Masse salariale brute", _fmt(data.get("masse_salariale_brute"))],
        ["Cotisation patronale (26%)", _fmt(data.get("cotisation_patronale"))],
        ["Cotisation salariale (9%)", _fmt(data.get("cotisation_salariale"))],
        ["", ""],
        ["TOTAL COTISATIONS", _fmt(data.get("total_cotisations"))],
    ]

    table = Table(rows, colWidths=[10 * cm, 6 * cm])
    style = _table_style()
    style.add("ALIGN", (1, 1), (1, -1), "RIGHT")
    style.add("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")
    style.add("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f0fdfa"))
    table.setStyle(style)
    story.append(table)

    story.append(Spacer(1, 15 * mm))
    story.append(Paragraph(
        f"Document genere le {datetime.now().strftime('%d/%m/%Y a %H:%M')} — GFI v7.0",
        _footer_style(),
    ))

    return _build_pdf(story, f"CNAS_{period}")


# ═══════════════════════════════════════════════════════════════════════════
# Journal Entries PDF (per entity/period)
# ═══════════════════════════════════════════════════════════════════════════

def generate_journal_pdf(
    entries: list[dict],
    entity_name: str,
    period: str,
    journal_label: str = "Tous journaux",
) -> bytes:
    """Generate printable journal entries listing."""
    styles = getSampleStyleSheet()
    story = []

    _header(story, styles, f"Journal Comptable — {journal_label}", entity_name, period)

    rows = [["Date", "Ref", "Compte", "Libelle", "Debit (DA)", "Credit (DA)"]]
    total_d = Decimal(0)
    total_c = Decimal(0)

    for entry in entries:
        # Entry header row
        rows.append([
            entry.get("entry_date", "")[:10],
            entry.get("reference", ""),
            "", entry.get("description", ""), "", "",
        ])
        for line in entry.get("lines", []):
            d = Decimal(str(line.get("debit", 0)))
            c = Decimal(str(line.get("credit", 0)))
            total_d += d
            total_c += c
            rows.append([
                "", "",
                line.get("account_code", ""),
                line.get("label", "")[:50],
                _fmt(d) if d else "",
                _fmt(c) if c else "",
            ])

    rows.append(["", "", "", "TOTAUX", _fmt(total_d), _fmt(total_c)])

    col_widths = [2.2 * cm, 2.2 * cm, 1.8 * cm, 6 * cm, 2.8 * cm, 2.8 * cm]
    table = Table(rows, colWidths=col_widths)
    style = _table_style()
    style.add("ALIGN", (4, 0), (5, -1), "RIGHT")
    style.add("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")
    style.add("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f0fdfa"))
    table.setStyle(style)
    story.append(table)

    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(f"{len(entries)} ecriture(s)", styles["Normal"]))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(
        f"Document genere le {datetime.now().strftime('%d/%m/%Y a %H:%M')} — GFI v7.0",
        _footer_style(),
    ))

    return _build_pdf(story, f"Journal_{entity_name}_{period}")


# ═══════════════════════════════════════════════════════════════════════════
# Balance des Comptes (Trial Balance) PDF
# ═══════════════════════════════════════════════════════════════════════════

def generate_balance_pdf(
    accounts: list[dict],
    entity_name: str,
    period: str,
) -> bytes:
    """Generate trial balance (balance des comptes) PDF."""
    styles = getSampleStyleSheet()
    story = []

    _header(story, styles, "Balance des Comptes", entity_name, period)

    rows = [["Compte", "Libelle", "Total Debit (DA)", "Total Credit (DA)", "Solde (DA)"]]
    grand_d = Decimal(0)
    grand_c = Decimal(0)

    for acc in accounts:
        d = Decimal(str(acc.get("total_debit", 0)))
        c = Decimal(str(acc.get("total_credit", 0)))
        solde = d - c
        grand_d += d
        grand_c += c
        rows.append([
            acc.get("code", ""),
            acc.get("label", "")[:40],
            _fmt(d) if d else "",
            _fmt(c) if c else "",
            _fmt(solde),
        ])

    rows.append(["", "TOTAUX", _fmt(grand_d), _fmt(grand_c), _fmt(grand_d - grand_c)])

    col_widths = [2 * cm, 6 * cm, 3 * cm, 3 * cm, 3 * cm]
    table = Table(rows, colWidths=col_widths)
    style = _table_style()
    style.add("ALIGN", (2, 0), (4, -1), "RIGHT")
    style.add("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")
    style.add("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f0fdfa"))
    table.setStyle(style)
    story.append(table)

    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(
        f"Document genere le {datetime.now().strftime('%d/%m/%Y a %H:%M')} — GFI v7.0",
        _footer_style(),
    ))

    return _build_pdf(story, f"Balance_{entity_name}_{period}")


# ═══════════════════════════════════════════════════════════════════════════
# Grand Livre PDF
# ═══════════════════════════════════════════════════════════════════════════

def generate_grand_livre_pdf(
    accounts: list[dict],
    entity_name: str,
    period: str,
) -> bytes:
    """Generate Grand Livre (general ledger detail) PDF.

    Each account shows its individual movements.
    """
    styles = getSampleStyleSheet()
    story = []

    _header(story, styles, "Grand Livre", entity_name, period)

    for acc in accounts:
        if not acc.get("movements"):
            continue
        story.append(Paragraph(
            f"<b>{acc['code']}</b> — {acc.get('label', '')}",
            styles["Heading3"],
        ))
        rows = [["Date", "Ref", "Libelle", "Debit (DA)", "Credit (DA)"]]
        acc_d = Decimal(0)
        acc_c = Decimal(0)
        for mv in acc["movements"]:
            d = Decimal(str(mv.get("debit", 0)))
            c = Decimal(str(mv.get("credit", 0)))
            acc_d += d
            acc_c += c
            rows.append([
                mv.get("date", "")[:10],
                mv.get("reference", ""),
                mv.get("label", "")[:45],
                _fmt(d) if d else "",
                _fmt(c) if c else "",
            ])
        rows.append(["", "", "Solde", _fmt(acc_d), _fmt(acc_c)])

        col_widths = [2.2 * cm, 2.5 * cm, 6.5 * cm, 3 * cm, 3 * cm]
        table = Table(rows, colWidths=col_widths)
        style = _table_style()
        style.add("ALIGN", (3, 0), (4, -1), "RIGHT")
        style.add("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")
        table.setStyle(style)
        story.append(table)
        story.append(Spacer(1, 6 * mm))

    story.append(Paragraph(
        f"Document genere le {datetime.now().strftime('%d/%m/%Y a %H:%M')} — GFI v7.0",
        _footer_style(),
    ))

    return _build_pdf(story, f"GrandLivre_{entity_name}_{period}")


# ═══════════════════════════════════════════════════════════════════════════
# Fiche de Paie (Payslip) PDF — EX-RH-002
# ═══════════════════════════════════════════════════════════════════════════

def generate_fiche_paie_pdf(data: dict, entity_name: str) -> bytes:
    """Generate an individual payslip PDF.

    data keys: employee_name, employee_number, position, periode,
               salaire_base, prime_spi, bonus_malus, commission, prime_plan,
               salaire_brut, cnas_salarie, cnas_patronal, irg, salaire_net,
               spi_score, jours_travailles
    """
    styles = getSampleStyleSheet()
    story = []

    _header(story, styles, "Fiche de Paie", entity_name, data.get("periode", ""))

    # Employee info
    emp_data = [
        ["Employe :", data.get("employee_name", ""), "Matricule :", data.get("employee_number", "")],
        ["Poste :", data.get("position", ""), "SPI Score :", f"{data.get('spi_score', 0)}/100"],
    ]
    emp_table = Table(emp_data, colWidths=[3 * cm, 5 * cm, 3 * cm, 5 * cm])
    emp_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(emp_table)
    story.append(Spacer(1, 8 * mm))

    # Earnings
    rows = [
        ["Designation", "Base", "Taux / Qte", "Montant (DA)"],
        ["Salaire de base", _fmt(data.get("salaire_base")), f"{data.get('jours_travailles', 30)} jrs", _fmt(data.get("salaire_base"))],
    ]
    if data.get("prime_spi"):
        rows.append(["Prime SPI", "", f"SPI {data.get('spi_score', 0)}%", _fmt(data.get("prime_spi"))])
    if data.get("bonus_malus") and float(data.get("bonus_malus", 0)) != 0:
        label = "Bonus" if float(data["bonus_malus"]) > 0 else "Malus"
        rows.append([label, "", "", _fmt(data.get("bonus_malus"))])
    if data.get("commission"):
        rows.append(["Commission commerciale", "", "", _fmt(data.get("commission"))])
    if data.get("prime_plan"):
        rows.append(["Prime plan strategique", "", "", _fmt(data.get("prime_plan"))])

    rows.append(["", "", "", ""])
    rows.append(["SALAIRE BRUT", "", "", _fmt(data.get("salaire_brut"))])
    rows.append(["", "", "", ""])
    rows.append(["Retenues:", "", "", ""])
    rows.append(["  CNAS Salariale (9%)", _fmt(data.get("salaire_brut")), "9%", f"-{_fmt(data.get('cnas_salarie'))}"])
    rows.append(["  IRG", "", "bareme", f"-{_fmt(data.get('irg'))}"])
    rows.append(["", "", "", ""])
    rows.append(["SALAIRE NET A PAYER", "", "", _fmt(data.get("salaire_net"))])
    rows.append(["", "", "", ""])
    rows.append(["Charges patronales:", "", "", ""])
    rows.append(["  CNAS Patronale (26%)", _fmt(data.get("salaire_brut")), "26%", _fmt(data.get("cnas_patronal"))])

    col_widths = [6 * cm, 3 * cm, 3 * cm, 4 * cm]
    table = Table(rows, colWidths=col_widths)
    style = _table_style()
    style.add("ALIGN", (1, 1), (3, -1), "RIGHT")
    # Bold brut and net rows
    for i, row in enumerate(rows):
        if row[0] in ("SALAIRE BRUT", "SALAIRE NET A PAYER"):
            style.add("FONTNAME", (0, i), (-1, i), "Helvetica-Bold")
            style.add("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f0fdfa"))
            style.add("FONTSIZE", (3, i), (3, i), 11)
        if row[0].startswith("Retenues:") or row[0].startswith("Charges patronales:"):
            style.add("FONTNAME", (0, i), (-1, i), "Helvetica-Bold")
    table.setStyle(style)
    story.append(table)

    story.append(Spacer(1, 15 * mm))

    # Signature line
    sig_data = [
        ["Fait a Alger, le " + datetime.now().strftime("%d/%m/%Y"), "", "Signature employeur"],
    ]
    sig_table = Table(sig_data, colWidths=[6 * cm, 4 * cm, 6 * cm])
    sig_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (2, 0), (2, 0), "RIGHT"),
    ]))
    story.append(sig_table)

    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(
        f"Document genere le {datetime.now().strftime('%d/%m/%Y a %H:%M')} — GFI v7.0",
        _footer_style(),
    ))

    return _build_pdf(story, f"FichePaie_{data.get('employee_number', '')}_{data.get('periode', '')}")


# ═══════════════════════════════════════════════════════════════════════════
# EDD — Etat Descriptif et Divisif PDF
# ═══════════════════════════════════════════════════════════════════════════

def generate_edd_pdf(edd_report: dict) -> bytes:
    """Generate a structured EDD report PDF.

    edd_report: output of generate_edd() with keys:
      project, blocks[{block, levels[{level, units[...]}]}], summary
    """
    from reportlab.platypus import PageBreak

    styles = getSampleStyleSheet()
    story = []

    project = edd_report.get("project", {})
    summary = edd_report.get("summary", {})
    blocks = edd_report.get("blocks", [])

    project_name = f"{project.get('code', '')} — {project.get('name', '')}"
    generated_at = summary.get("generated_at", datetime.now().isoformat())[:10]

    # ── Header ──
    story.append(Paragraph("Groupe Dendani", styles["Title"]))
    story.append(Paragraph(project_name, styles["Heading2"]))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Etat Descriptif et Divisif (EDD)", styles["Heading1"]))
    story.append(Paragraph(f"Date de generation : {generated_at}", styles["Normal"]))
    story.append(Spacer(1, 2 * mm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0d9488")))
    story.append(Spacer(1, 6 * mm))

    # ── Project info ──
    info_rows = [
        ["Code projet", project.get("code", "—"),
         "Latitude", str(project.get("lat", "—"))],
        ["Nom", project.get("name", "—"),
         "Longitude", str(project.get("lon", "—"))],
    ]
    info_table = Table(info_rows, colWidths=[3 * cm, 5 * cm, 3 * cm, 5 * cm])
    info_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 6 * mm))

    # ── Summary box ──
    story.append(Paragraph("<b>Recapitulatif global</b>", styles["Heading3"]))
    summary_rows = [
        ["Total lots", str(summary.get("total_units", 0)),
         "Surface habitable totale (m2)", _fmt(summary.get("total_sh", 0))],
        ["Blocs", str(len(blocks)),
         "Surface utile totale (m2)", _fmt(summary.get("total_su", 0))],
    ]
    summary_table = Table(summary_rows, colWidths=[4 * cm, 3 * cm, 5.5 * cm, 3.5 * cm])
    summary_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0fdfa")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#0d9488")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 10 * mm))

    # ── Per-block / per-level unit tables ──
    for b_idx, block_data in enumerate(blocks):
        block = block_data.get("block", {})
        levels = block_data.get("levels", [])

        story.append(Paragraph(
            f"<b>Bloc {block.get('code', '?')}</b> — {block.get('name', '')}",
            styles["Heading2"],
        ))
        story.append(Spacer(1, 3 * mm))

        for level_data in levels:
            level = level_data.get("level", {})
            units = level_data.get("units", [])
            if not units:
                continue

            elev = level.get("elevation", 0)
            story.append(Paragraph(
                f"Niveau {level.get('code', '?')} — Elevation : {elev} m",
                styles["Heading3"],
            ))
            story.append(Spacer(1, 2 * mm))

            # Table header
            rows = [[
                "Code", "Typol.", "SH (m2)", "SU (m2)",
                "Balcon", "Terrasse", "Jardin",
                "Expo.", "Vue", "Prix (DA)", "Obs.",
            ]]

            level_sh = 0
            level_su = 0
            level_price = 0
            for u in units:
                sh = u.get("area_sh", 0)
                su = u.get("area_su", 0)
                price = u.get("price_total", 0) or u.get("price_base", 0)
                level_sh += sh
                level_su += su
                level_price += price

                obs = u.get("observations", "")
                obs_short = obs[:20] + "..." if len(obs) > 20 else obs

                rows.append([
                    u.get("code", "")[-8:],  # last segment for readability
                    u.get("typology", "—"),
                    f"{sh:.1f}",
                    f"{su:.1f}",
                    f"{u.get('area_sb', 0):.1f}" if u.get("area_sb") else "—",
                    f"{u.get('area_st', 0):.1f}" if u.get("area_st") else "—",
                    f"{u.get('area_sj', 0):.1f}" if u.get("area_sj") else "—",
                    u.get("exposure", "—") or "—",
                    u.get("view_class", "—") or "—",
                    _fmt(price) if price else "—",
                    obs_short,
                ])

            # Totals row
            rows.append([
                f"{len(units)} lots", "", f"{level_sh:.1f}", f"{level_su:.1f}",
                "", "", "", "", "", _fmt(level_price), "",
            ])

            col_widths = [
                1.8 * cm, 1.3 * cm, 1.5 * cm, 1.5 * cm,
                1.3 * cm, 1.3 * cm, 1.3 * cm,
                1.1 * cm, 1.3 * cm, 2.5 * cm, 2.3 * cm,
            ]
            table = Table(rows, colWidths=col_widths)
            style = _table_style()
            style.add("FONTSIZE", (0, 0), (-1, -1), 7)
            style.add("FONTSIZE", (0, 0), (-1, 0), 7)
            # Right-align numeric columns
            style.add("ALIGN", (2, 1), (6, -1), "RIGHT")
            style.add("ALIGN", (9, 1), (9, -1), "RIGHT")
            # Bold totals row
            style.add("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")
            style.add("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f0fdfa"))
            # Highlight missing observations in amber
            for row_idx in range(1, len(rows) - 1):
                if rows[row_idx][10]:  # has observations = missing fields
                    style.add("TEXTCOLOR", (10, row_idx), (10, row_idx), colors.HexColor("#d97706"))
            table.setStyle(style)
            story.append(table)
            story.append(Spacer(1, 5 * mm))

        # Page break between blocks (except last)
        if b_idx < len(blocks) - 1:
            story.append(PageBreak())

    # ── Footer ──
    story.append(Spacer(1, 10 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1")))
    story.append(Spacer(1, 4 * mm))

    # Signature area
    sig_rows = [
        ["Le promoteur", "", "Le geometre expert"],
        ["", "", ""],
        ["Signature : ____________________", "", "Signature : ____________________"],
    ]
    sig_table = Table(sig_rows, colWidths=[6 * cm, 4 * cm, 6 * cm])
    sig_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(sig_table)

    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(
        f"Document genere le {datetime.now().strftime('%d/%m/%Y a %H:%M')} — GFI v7.0",
        _footer_style(),
    ))

    return _build_pdf(story, f"EDD_{project.get('code', 'PROJET')}")
