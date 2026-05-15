from app.services.employee_import import normalize_import_employee_row, split_employee_name


def test_split_employee_name_uses_email_hint_for_surname_first_names():
    first_name, last_name = split_employee_name("ADJAOUD DJAMEL", "djamel.adjaoud@promo-avelis.com")
    assert first_name == "Djamel"
    assert last_name == "ADJAOUD"


def test_split_employee_name_uses_email_hint_for_first_name_first_rows():
    first_name, last_name = split_employee_name("Abdallah Abir", "abdallah.abir@promo-avelis.com")
    assert first_name == "Abdallah"
    assert last_name == "ABIR"


def test_normalize_import_employee_row_maps_hr_sheet_columns():
    payload = normalize_import_employee_row(
        {
            "actif": "True",
            "activites": "Suivi RH",
            "adresse_email_professionnelle": "djamel.adjaoud@promo-avelis.com",
            "adresse_professionnelle": "Avelis Promotion immobiliere",
            "date_limite_de_l_activite_a_venir": "2026-04-01",
            "departement": "Direction Generale / Departement Ressources Humaines (RH)",
            "manager": "Ahmed Dendani",
            "mentor": "Ahmed Dendani",
            "nom_de_l_employe": "ADJAOUD DJAMEL",
            "poste": "Office Manager / RH",
            "societe": "SARL AVELIS PROMOTION",
            "status": "draft",
            "telephone_professionnel": "0560582000",
        }
    )

    assert payload is not None
    assert payload["first_name"] == "Djamel"
    assert payload["last_name"] == "ADJAOUD"
    assert payload["status"] == "ACTIVE"
    assert payload["is_active"] is True
    assert payload["company"] == "SARL AVELIS PROMOTION"
    assert payload["manager_name"] == "Ahmed Dendani"