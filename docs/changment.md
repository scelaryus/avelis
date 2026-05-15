# SPÉCIFICATION ULTRA-DÉTAILLÉE v6.0 — ANNEXE C
# Centre de Coût Temps Réel, RH/Paie D/ND, Caisse, Dashboard, Calculs, Écrans
## « Le développeur lit, le développeur code. Zéro question. »

**Version** : 6.0-C — Mars 2026
**Objectif** : Chaque calcul, chaque écran, chaque filtre, chaque élément d'entrée et de sortie est spécifié. Le développeur ne doit rien imaginer.

---

# CHAPITRE 1 — TAXONOMIE DES CHARGES : PROJET vs COMMUNE

## 1.1 — Définition fondamentale

Toute dépense dans le système appartient à exactement une de ces deux catégories :

**CHARGE PROJET (CP)** — Directement imputable à un seul projet identifié.
Le champ `projet_id` est renseigné (NOT NULL pour cette charge).

**CHARGE COMMUNE (CC)** — Bénéficie à plusieurs projets ou à l'entreprise globalement.
Le champ `projet_id` est NULL.

Le système ne permet jamais une charge sans catégorisation. Si l'utilisateur ne sait pas si c'est projet ou commune → BLOCAGE + demande de complétion.

## 1.2 — Classification détaillée par nature

### CHARGES TOUJOURS PROJET (projet_id obligatoire)

| Nature | Exemples concrets | Pourquoi c'est projet |
|--------|------------------|----------------------|
| Achat terrain | Achat du terrain pour LYS | Le terrain est pour un projet précis |
| Contrat de réalisation | Marché CES avec entreprise de construction pour IRENE | Le contrat porte sur un projet |
| Matériaux de construction | Ciment, fer, briques livrés au chantier MAGNOLIA | Le bon de livraison porte le nom du projet |
| Sous-traitance chantier | Plomberie, électricité pour AUREA | Le sous-traitant travaille sur un chantier précis |
| Études techniques | Étude de sol pour ASTERIA | L'étude porte sur un terrain/projet précis |
| Frais de notaire (acte) | Acte de vente terrain T2400 | L'acte concerne un projet |
| Publicité projet | Affichage publicitaire "Résidence Irène" | Le support mentionne le projet |
| Taxes foncières terrain | Taxe foncière du terrain LYS | Le terrain est rattaché à un projet |
| Assurance chantier | Assurance tous risques chantier MAGNOLIA | La police couvre un chantier précis |

### CHARGES TOUJOURS COMMUNES (projet_id = NULL)

| Nature | Exemples concrets | Pourquoi c'est commun |
|--------|------------------|----------------------|
| Loyer siège social | Loyer bureau SARL Dendani Promotion | Le bureau sert à tous les projets |
| Salaires administration | Salaire comptable, secrétaire, DAF | Ils travaillent pour tous les projets |
| Fournitures bureau | Papier, encre, stylos | Consommés par toute l'entreprise |
| Téléphone/Internet | Abonnement téléphonique siège | Utilisé pour tous les projets |
| Honoraires comptable externe | Expert comptable | Il fait la comptabilité de tous les projets |
| Frais bancaires généraux | Agios, frais de tenue de compte | Le compte est partagé |
| Marketing global | Publicité "Groupe Dendani" sans projet spécifique | Bénéficie à tous les projets |
| Assurance RC entreprise | Responsabilité civile professionnelle | Couvre toute l'activité |

### CHARGES MIXTES (peuvent être projet OU commune selon le cas)

| Nature | Quand c'est PROJET | Quand c'est COMMUNE |
|--------|-------------------|---------------------|
| Salaire ouvrier | Affecté à un seul chantier | Travaille sur 2+ chantiers → répartition |
| Véhicule | Véhicule dédié au chantier IRENE | Véhicule du directeur (tous projets) |
| Taxe G50 TVA | TVA sur facture projet | TVA sur charges communes |
| CNAS/CASNOS | CNAS d'un ouvrier chantier | CNAS du comptable (commun) |
| Carburant | Carburant engin de chantier LYS | Carburant véhicule direction |
| Gardiennage | Gardien du chantier MAGNOLIA | Gardien du siège |

**Règle pour les charges mixtes** : Si le système ne peut pas déterminer si c'est projet ou commun à 100% → BLOCAGE + demande à l'utilisateur de choisir.

---

# CHAPITRE 2 — CALCUL DU RATIO DE RÉPARTITION DES CHARGES COMMUNES

## 2.1 — Deux méthodes de calcul du ratio

Le système propose DEUX méthodes de calcul. L'administrateur choisit laquelle utiliser dans les paramètres. La méthode par défaut est la méthode CA.

### Méthode 1 — Ratio au Chiffre d'Affaires (MÉTHODE PAR DÉFAUT)

```
Ratio_projet_X = CA_projet_X / CA_total_tous_projets_actifs

Où :
  CA_projet_X = Somme(encaissements RD + encaissements RND) du projet X pour la période
  CA_total = Somme(CA de tous les projets actifs de la même entreprise) pour la période
```

**Exemple concret :**

```
Période : Janvier 2026
Entreprise : SARL Dendani Promotion (3 projets : OPERA, IRENE, AUREA)

CA OPERA janvier  =  5 000 000 DA (RD) +  2 000 000 DA (RND) =  7 000 000 DA
CA IRENE janvier  = 15 000 000 DA (RD) +  8 000 000 DA (RND) = 23 000 000 DA
CA AUREA janvier  =  4 000 000 DA (RD) +  1 000 000 DA (RND) =  5 000 000 DA
CA TOTAL          = 35 000 000 DA

Ratio OPERA = 7 000 000 / 35 000 000 = 20.00%
Ratio IRENE = 23 000 000 / 35 000 000 = 65.71%
Ratio AUREA = 5 000 000 / 35 000 000 = 14.29%
Vérification : 20.00% + 65.71% + 14.29% = 100.00% ✓

Charge commune : Loyer siège 500 000 DA
  → OPERA reçoit : 500 000 × 20.00% = 100 000 DA
  → IRENE reçoit : 500 000 × 65.71% = 328 571.43 DA
  → AUREA reçoit : 500 000 × 14.29% = 71 428.57 DA
  → Total réparti : 500 000.00 DA ✓ (vérification centime)
```

### Méthode 2 — Ratio aux Dépenses Directes

```
Ratio_projet_X = Dépenses_directes_projet_X / Dépenses_directes_total

Où :
  Dépenses_directes_projet_X = Somme(décaissements où projet_id = X) pour la période
  Dépenses_directes_total = Somme(décaissements où projet_id IS NOT NULL) pour la période
```

Cette méthode est utile quand un projet n'a pas encore de CA (début de chantier) mais a déjà des dépenses.

### Paramètre système

```sql
INSERT INTO parametres (cle, valeur, description) VALUES
  ('methode_ratio_charges_communes', 'CA', 
   'Méthode de répartition des charges communes : CA (chiffre affaires) ou DEPENSES (dépenses directes)');
```

## 2.2 — Périodicité du calcul

Le ratio est recalculé **mensuellement**. Chaque mois a son propre ratio parce que le CA et les dépenses varient d'un mois à l'autre.

```
Table ratio_charges_communes :
  id UUID PK
  entreprise_id UUID FK NOT NULL
  exercice_id UUID FK NOT NULL
  mois INTEGER NOT NULL (1-12)
  annee INTEGER NOT NULL
  methode VARCHAR(20) NOT NULL         -- 'CA' ou 'DEPENSES'
  -- Détail par projet
  detail_projets JSONB NOT NULL        -- [{projet_id, projet_code, valeur_base, ratio_pct}]
  -- Totaux
  total_base NUMERIC(15,2) NOT NULL    -- CA total ou dépenses totales
  total_charges_communes NUMERIC(15,2) NOT NULL  -- Total charges communes du mois
  -- Vérification
  somme_ratios NUMERIC(8,4) NOT NULL   -- Doit être exactement 100.0000
  hash_verification VARCHAR(64)
  genere_automatiquement BOOLEAN DEFAULT TRUE
  valide_par UUID FK
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
  UNIQUE(entreprise_id, annee, mois)
```

**Le système génère le ratio automatiquement** le 1er de chaque mois (ou à la demande). Il prend les données du mois précédent, calcule le ratio, et l'applique à toutes les charges communes du mois.

## 2.3 — Cas limites

| Situation | Traitement |
|-----------|-----------|
| Un projet a un CA de 0 ce mois-ci | Ratio = 0%, il ne reçoit aucune charge commune ce mois |
| Tous les projets ont un CA de 0 | BLOCAGE — impossible de calculer le ratio, l'administrateur doit choisir une répartition manuelle |
| Un nouveau projet démarre en cours de mois | Il est inclus dans le ratio dès qu'il a du CA ou des dépenses |
| Un projet est abandonné (T5000) | Exclu des ratios des mois suivants (statut ABANDONNE) |
| La MOSQUÉE (0 recettes) | En méthode CA : ratio = 0%, ne reçoit pas de charges communes. En méthode DEPENSES : reçoit des charges communes si elle a des dépenses directes |

## 2.4 — Double computation du ratio

Le ratio est calculé deux fois par deux requêtes SQL différentes :

```
Chemin 1 : SELECT projet_id, SUM(montant) FROM encaissements WHERE ... GROUP BY projet_id
Chemin 2 : SELECT projet_id, SUM(total_credit) FROM ecritures_comptables ec 
           JOIN lignes_ecritures le ON ... WHERE compte LIKE '7%' GROUP BY projet_id
```

Si les deux chemins ne donnent pas le même ratio → BLOCAGE + alerte "Incohérence entre encaissements et écritures comptables".

---

# CHAPITRE 3 — CENTRE DE COÛT TEMPS RÉEL : FORMULES COMPLÈTES

## 3.1 — Structure du centre de coût par projet par mois

Pour chaque combinaison (projet, mois, année), le système calcule et stocke :

```
═══════════════════════════════════════════════════════════════
CENTRE DE COÛT — Projet IRENE — Janvier 2026
Entreprise : SARL Dendani Promotion
═══════════════════════════════════════════════════════════════

A. RECETTES
───────────────────────────────────────────────────────────────
A1. Encaissements Réels Déclarés (RD)
    = SUM(encaissements.montant) 
      WHERE projet_id = IRENE 
      AND statut_fiscal = 'REEL_DECLARE'
      AND mois = janvier 2026
    Exemple : 15 000 000 DA

A2. Encaissements Réels Non-Déclarés (RND)
    = SUM(encaissements.montant) 
      WHERE projet_id = IRENE 
      AND statut_fiscal = 'REEL_NON_DECLARE'
      AND mois = janvier 2026
    Exemple : 8 000 000 DA

A3. Gains Contentieux
    = SUM(decaissements.montant)
      WHERE projet_id = IRENE
      AND categorie_depense = 'CONTENTIEUX'
      AND sens = 'GAIN'
      AND mois = janvier 2026
    Exemple : 500 000 DA

A4. Libérations Transit Notaire (reçues)
    = SUM(comptes_transitoires_notaires.montant_tranche1_20pct)
      WHERE projet_id = IRENE
      AND statut IN ('VEFA_SIGNE_20PCT_LIBERE', 'PV_SIGNE_5PCT_LIBERE', 'CLOTURE')
      AND date_liberation_tranche1 dans janvier 2026
    + SUM(montant_tranche2_5pct) pour les tranche 2 libérées
    Exemple : 2 000 000 DA

───────────────────────────────────────────────────────────────
TOTAL RECETTES = A1 + A2 + A3 + A4
               = 15 000 000 + 8 000 000 + 500 000 + 2 000 000
               = 25 500 000 DA
───────────────────────────────────────────────────────────────

B. DÉPENSES DIRECTES PROJET
───────────────────────────────────────────────────────────────
B1. Décaissements Réels Déclarés (RD)
    = SUM(decaissements.montant)
      WHERE projet_id = IRENE
      AND statut_fiscal = 'REEL_DECLARE'
      AND categorie_depense != 'CONTENTIEUX' (ou sens != 'GAIN')
      AND mois = janvier 2026
    Exemple : 6 000 000 DA

B2. Décaissements Réels Non-Déclarés (RND)
    = SUM(decaissements.montant)
      WHERE projet_id = IRENE
      AND statut_fiscal = 'REEL_NON_DECLARE'
      AND mois = janvier 2026
    Exemple : 3 500 000 DA

B3. Coût des Factures Fictives Déclarées (FD)
    Le montant nominal de la facture fictive est stocké.
    Le COÛT RÉEL = montant nominal × taux_cout_fictif (paramètre, défaut 3%)
    
    = SUM(decaissements.montant) × taux_cout_fictif / 100
      WHERE projet_id = IRENE
      AND statut_fiscal = 'FICTIF_DECLARE'
      AND mois = janvier 2026
    
    Exemple : Factures fictives nominales = 10 000 000 DA
              Coût réel FD = 10 000 000 × 3% = 300 000 DA

B4. Coût des Factures Fictives Non-Déclarées (FND)
    Même logique que FD.
    Exemple : 0 DA

B5. Pertes Contentieux
    = SUM(decaissements.montant)
      WHERE projet_id = IRENE
      AND categorie_depense = 'CONTENTIEUX'
      AND sens = 'PERTE'
      AND mois = janvier 2026
    Exemple : 200 000 DA

B6. Stock Consommé (sorties valorisées au CUMP)
    = SUM(mouvements_stock.quantite × mouvements_stock.prix_unitaire)
      WHERE projet_id = IRENE
      AND type_mouvement = 'SORTIE'
      AND mois = janvier 2026
    Exemple : 1 200 000 DA

B7. Masse Salariale Directe Projet
    = SUM(imputation_paie_projets.montant_impute)
      WHERE projet_id = IRENE
      AND mois = janvier 2026
    (employés affectés directement à IRENE)
    Exemple : 2 800 000 DA

───────────────────────────────────────────────────────────────
TOTAL DÉPENSES DIRECTES = B1 + B2 + B3 + B4 + B5 + B6 + B7
                        = 6 000 000 + 3 500 000 + 300 000 + 0
                          + 200 000 + 1 200 000 + 2 800 000
                        = 14 000 000 DA
───────────────────────────────────────────────────────────────

C. CHARGES COMMUNES RÉPARTIES
───────────────────────────────────────────────────────────────
C1. Quote-part charges communes
    = Total_charges_communes_entreprise_janvier × Ratio_IRENE_janvier
    
    Total charges communes SARL-DP janvier = 3 000 000 DA
    Ratio IRENE janvier (méthode CA) = 65.71%
    
    C1 = 3 000 000 × 65.71% = 1 971 428.57 DA

───────────────────────────────────────────────────────────────
TOTAL DÉPENSES = DIRECTES + COMMUNES
               = 14 000 000 + 1 971 428.57
               = 15 971 428.57 DA
───────────────────────────────────────────────────────────────

D. RÉSULTAT
───────────────────────────────────────────────────────────────
D1. Résultat Ultra-Réel du mois
    = TOTAL RECETTES - TOTAL DÉPENSES
    = 25 500 000 - 15 971 428.57
    = 9 528 571.43 DA

D2. Résultat Fiscal (uniquement le déclaré)
    = (A1) - (B1 + montant nominal FD)
    = 15 000 000 - (6 000 000 + 10 000 000)
    = -1 000 000 DA (déficit fiscal grâce aux factures fictives)

D3. Résultat Cumulé (depuis le début du projet)
    = SUM(D1) pour tous les mois depuis le début

───────────────────────────────────────────────────────────────
E. INDICATEURS
───────────────────────────────────────────────────────────────
E1. Marge brute = D1 / TOTAL RECETTES × 100
    = 9 528 571.43 / 25 500 000 × 100 = 37.37%

E2. Ratio charges communes / dépenses totales
    = 1 971 428.57 / 15 971 428.57 × 100 = 12.34%

E3. Part du non-déclaré dans les recettes
    = A2 / (A1 + A2) × 100 = 8 000 000 / 23 000 000 × 100 = 34.78%

E4. Montants en transit chez les notaires (non encore reçus)
    = SUM(montant_tranche1_20pct + montant_tranche2_5pct)
      WHERE projet_id = IRENE
      AND statut NOT IN ('CLOTURE')
    Exemple : 4 500 000 DA encore chez les notaires

E5. Encaissements futurs attendus (reste à payer clients)
    = SUM(clients.reste_a_payer)
      WHERE projet_id = IRENE
    Exemple : 120 000 000 DA
═══════════════════════════════════════════════════════════════
```

## 3.2 — Table SQL centre_cout_mensuel

```sql
CREATE TABLE centre_cout_mensuel (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    projet_id UUID NOT NULL REFERENCES projets(id),
    entreprise_id UUID NOT NULL REFERENCES entreprises(id),
    exercice_id UUID NOT NULL REFERENCES exercices(id),
    mois INTEGER NOT NULL CHECK (mois >= 1 AND mois <= 12),
    annee INTEGER NOT NULL,
    
    -- A. RECETTES
    encaissements_rd NUMERIC(15,2) NOT NULL DEFAULT 0,
    encaissements_rnd NUMERIC(15,2) NOT NULL DEFAULT 0,
    gains_contentieux NUMERIC(15,2) NOT NULL DEFAULT 0,
    liberations_transit NUMERIC(15,2) NOT NULL DEFAULT 0,
    total_recettes NUMERIC(15,2) GENERATED ALWAYS AS (
        encaissements_rd + encaissements_rnd + gains_contentieux + liberations_transit
    ) STORED,
    
    -- B. DÉPENSES DIRECTES
    decaissements_rd NUMERIC(15,2) NOT NULL DEFAULT 0,
    decaissements_rnd NUMERIC(15,2) NOT NULL DEFAULT 0,
    cout_fictif_fd NUMERIC(15,2) NOT NULL DEFAULT 0,
    cout_fictif_fnd NUMERIC(15,2) NOT NULL DEFAULT 0,
    montant_nominal_fd NUMERIC(15,2) NOT NULL DEFAULT 0,
    montant_nominal_fnd NUMERIC(15,2) NOT NULL DEFAULT 0,
    pertes_contentieux NUMERIC(15,2) NOT NULL DEFAULT 0,
    stock_consomme_cump NUMERIC(15,2) NOT NULL DEFAULT 0,
    masse_salariale_directe NUMERIC(15,2) NOT NULL DEFAULT 0,
    total_depenses_directes NUMERIC(15,2) GENERATED ALWAYS AS (
        decaissements_rd + decaissements_rnd + cout_fictif_fd + cout_fictif_fnd
        + pertes_contentieux + stock_consomme_cump + masse_salariale_directe
    ) STORED,
    
    -- C. CHARGES COMMUNES
    ratio_pct NUMERIC(8,4) NOT NULL DEFAULT 0,
    charges_communes_montant NUMERIC(15,2) NOT NULL DEFAULT 0,
    
    -- D. TOTAUX
    total_depenses NUMERIC(15,2) GENERATED ALWAYS AS (
        decaissements_rd + decaissements_rnd + cout_fictif_fd + cout_fictif_fnd
        + pertes_contentieux + stock_consomme_cump + masse_salariale_directe
        + charges_communes_montant
    ) STORED,
    resultat_ultra_reel NUMERIC(15,2) GENERATED ALWAYS AS (
        (encaissements_rd + encaissements_rnd + gains_contentieux + liberations_transit)
        - (decaissements_rd + decaissements_rnd + cout_fictif_fd + cout_fictif_fnd
           + pertes_contentieux + stock_consomme_cump + masse_salariale_directe
           + charges_communes_montant)
    ) STORED,
    resultat_fiscal NUMERIC(15,2) NOT NULL DEFAULT 0,
    
    -- E. INDICATEURS
    marge_brute_pct NUMERIC(8,2),
    ratio_cc_depenses_pct NUMERIC(8,2),
    part_non_declare_pct NUMERIC(8,2),
    montant_transit_notaire NUMERIC(15,2) NOT NULL DEFAULT 0,
    reste_a_payer_clients NUMERIC(15,2) NOT NULL DEFAULT 0,
    
    -- Vérification
    hash_verification VARCHAR(64),
    est_test_fictif BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    UNIQUE(projet_id, annee, mois)
);
```

## 3.3 — Fonction de calcul automatique

```python
def calculer_centre_cout_mensuel(projet_id, entreprise_id, mois, annee):
    """
    Calcule le centre de coût d'un projet pour un mois donné.
    Appelé automatiquement quand :
    - Un encaissement est enregistré
    - Un décaissement est enregistré
    - Un mouvement de stock est enregistré
    - Un bulletin de paie est saisi
    - Une charge commune est ajoutée
    - Un transit notaire est libéré
    C'est-à-dire : À CHAQUE OPÉRATION FINANCIÈRE.
    """
    
    # Bornes de date
    date_debut = f"{annee}-{mois:02d}-01"
    date_fin = dernier_jour_du_mois(annee, mois)
    
    # A. RECETTES
    encaissements_rd = query("""
        SELECT COALESCE(SUM(montant), 0) FROM encaissements
        WHERE projet_id = %s AND statut_fiscal = 'REEL_DECLARE'
        AND date_encaissement BETWEEN %s AND %s AND is_deleted = FALSE
    """, projet_id, date_debut, date_fin)
    
    encaissements_rnd = query("""
        SELECT COALESCE(SUM(montant), 0) FROM encaissements
        WHERE projet_id = %s AND statut_fiscal = 'REEL_NON_DECLARE'
        AND date_encaissement BETWEEN %s AND %s AND is_deleted = FALSE
    """, projet_id, date_debut, date_fin)
    
    gains_contentieux = query("""
        SELECT COALESCE(SUM(montant), 0) FROM decaissements
        WHERE projet_id = %s AND categorie_depense = 'CONTENTIEUX' AND sens = 'GAIN'
        AND date_decaissement BETWEEN %s AND %s AND is_deleted = FALSE
    """, projet_id, date_debut, date_fin)
    
    liberations_transit = query("""
        SELECT COALESCE(SUM(
            CASE WHEN date_liberation_tranche1 BETWEEN %s AND %s THEN montant_tranche1_20pct ELSE 0 END
            + CASE WHEN date_liberation_tranche2 BETWEEN %s AND %s THEN montant_tranche2_5pct ELSE 0 END
        ), 0) FROM comptes_transitoires_notaires
        WHERE projet_id = %s
    """, date_debut, date_fin, date_debut, date_fin, projet_id)
    
    # B. DÉPENSES DIRECTES
    decaissements_rd = query("""
        SELECT COALESCE(SUM(montant), 0) FROM decaissements
        WHERE projet_id = %s AND statut_fiscal = 'REEL_DECLARE'
        AND (categorie_depense != 'CONTENTIEUX' OR sens != 'GAIN')
        AND date_decaissement BETWEEN %s AND %s AND is_deleted = FALSE
    """, projet_id, date_debut, date_fin)
    
    decaissements_rnd = query("""...""")  # Même chose avec REEL_NON_DECLARE
    
    # Factures fictives : montant nominal et coût réel
    taux_fictif = get_parametre('taux_cout_fictif')  # Défaut 3%
    
    montant_nominal_fd = query("""
        SELECT COALESCE(SUM(montant), 0) FROM decaissements
        WHERE projet_id = %s AND statut_fiscal = 'FICTIF_DECLARE'
        AND date_decaissement BETWEEN %s AND %s
    """, projet_id, date_debut, date_fin)
    cout_fictif_fd = montant_nominal_fd * taux_fictif / 100
    
    montant_nominal_fnd = query("""...""")  # FICTIF_NON_DECLARE
    cout_fictif_fnd = montant_nominal_fnd * taux_fictif / 100
    
    pertes_contentieux = query("""
        SELECT COALESCE(SUM(montant), 0) FROM decaissements
        WHERE projet_id = %s AND categorie_depense = 'CONTENTIEUX' AND sens = 'PERTE'
        AND date_decaissement BETWEEN %s AND %s
    """, projet_id, date_debut, date_fin)
    
    stock_consomme_cump = query("""
        SELECT COALESCE(SUM(quantite * prix_unitaire), 0) FROM mouvements_stock
        WHERE projet_id = %s AND type_mouvement = 'SORTIE'
        AND date_mouvement BETWEEN %s AND %s
    """, projet_id, date_debut, date_fin)
    
    masse_salariale_directe = query("""
        SELECT COALESCE(SUM(ip.montant_impute), 0)
        FROM imputation_paie_projets ip
        JOIN bulletins_paie bp ON bp.id = ip.bulletin_id
        WHERE ip.projet_id = %s AND bp.mois = %s AND bp.annee = %s
    """, projet_id, mois, annee)
    
    # C. CHARGES COMMUNES
    ratio = get_ratio_mensuel(entreprise_id, mois, annee, projet_id)
    total_cc = query("""
        SELECT COALESCE(SUM(montant), 0) FROM decaissements
        WHERE entreprise_id = %s AND projet_id IS NULL
        AND date_decaissement BETWEEN %s AND %s AND is_deleted = FALSE
    """, entreprise_id, date_debut, date_fin)
    charges_communes = total_cc * ratio / 100
    
    # D. RÉSULTAT FISCAL
    resultat_fiscal = encaissements_rd - (decaissements_rd + montant_nominal_fd)
    
    # SAUVEGARDER (UPSERT)
    # ... INSERT ON CONFLICT UPDATE
    
    # RECALCULER LES INDICATEURS
    total_recettes = encaissements_rd + encaissements_rnd + gains_contentieux + liberations_transit
    total_depenses = (decaissements_rd + decaissements_rnd + cout_fictif_fd + cout_fictif_fnd
                      + pertes_contentieux + stock_consomme_cump + masse_salariale_directe
                      + charges_communes)
    
    marge = (total_recettes - total_depenses) / total_recettes * 100 if total_recettes > 0 else 0
    
    # HASH pour non-régression
    # ... calculer et stocker
```

---

# CHAPITRE 4 — RH / PAIE : ASSIETTE PC PAIE + DÉCLARÉ / NON-DÉCLARÉ

## 4.1 — Le double registre des employés

Chaque employé a **deux fiches de paie** :

1. **Paie déclarée (RD)** : le bulletin officiel déclaré à la CNAS, utilisé pour le G50, la DADS, l'IBS. C'est ce que l'administration voit. C'est l'assiette PC Paie officielle.

2. **Paie non-déclarée (RND)** : le complément versé en espèces, non déclaré. L'employé reçoit un salaire réel = déclaré + non-déclaré. Le système trace les deux.

## 4.2 — Structure de la table bulletins_paie enrichie

```sql
-- Le bulletin existant + enrichissement
ALTER TABLE bulletins_paie ADD COLUMN IF NOT EXISTS
    -- Complément non-déclaré
    complement_nd NUMERIC(12,2) NOT NULL DEFAULT 0,
    -- Salaire réel total
    salaire_reel_total NUMERIC(12,2) GENERATED ALWAYS AS (salaire_net + complement_nd) STORED,
    -- Référence fiche caisse (pour le ND)
    reference_fiche_caisse VARCHAR(100),
    -- Imputation projets (si mono-projet)
    projet_id UUID REFERENCES projets(id);
```

## 4.3 — Table imputation_paie_projets (répartition multi-projets)

Quand un employé travaille sur plusieurs projets dans le même mois :

```sql
CREATE TABLE imputation_paie_projets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    bulletin_id UUID NOT NULL REFERENCES bulletins_paie(id) ON DELETE CASCADE,
    projet_id UUID NOT NULL REFERENCES projets(id),
    pourcentage NUMERIC(6,2) NOT NULL CHECK (pourcentage > 0 AND pourcentage <= 100),
    -- Montants calculés automatiquement
    montant_impute_rd NUMERIC(12,2) NOT NULL,   -- Part déclarée
    montant_impute_rnd NUMERIC(12,2) NOT NULL,  -- Part non-déclarée
    montant_impute_total NUMERIC(12,2) NOT NULL, -- Total
    -- Charges patronales imputées
    cnas_patronal_impute NUMERIC(12,2) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(bulletin_id, projet_id)
);

-- Trigger : vérifier que la somme des % = 100% par bulletin
CREATE OR REPLACE FUNCTION check_imputation_paie_sum()
RETURNS TRIGGER AS $$
DECLARE total NUMERIC;
BEGIN
    SELECT COALESCE(SUM(pourcentage), 0) INTO total
    FROM imputation_paie_projets WHERE bulletin_id = NEW.bulletin_id;
    IF total > 100.01 THEN
        RAISE EXCEPTION 'Somme des imputations paie dépasse 100%% (actuel: %%)',
            total;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

## 4.4 — Calcul détaillé d'un bulletin de paie

```
ENTRÉE : Employé Karim, Janvier 2026, SARL Dendani Promotion

PAIE DÉCLARÉE (RD) — Assiette PC Paie officielle :
  Salaire de base          : 45 000 DA
  Heures supplémentaires   :  5 000 DA
  Prime de rendement       :  3 000 DA
  Indemnités               :  2 000 DA
  ─────────────────────────────────────
  SALAIRE BRUT             : 55 000 DA
  
  Retenues :
    CNAS salarié (9%)      : -4 950 DA
    IRG (barème progressif) : -3 200 DA
    Autres retenues        :      0 DA
  ─────────────────────────────────────
  TOTAL RETENUES           : -8 150 DA
  
  SALAIRE NET DÉCLARÉ      : 46 850 DA
  
  Charges patronales :
    CNAS patronal (26%)    : 14 300 DA
    CACOBATPH (1.75%)      :    962 DA
  ─────────────────────────────────────
  COÛT TOTAL EMPLOYEUR (RD): 70 262 DA

PAIE NON-DÉCLARÉE (RND) — Complément espèces :
  Complément ND            : 20 000 DA
  Référence fiche caisse   : CAISSE-2026-01-047
  ─────────────────────────────────────
  SALAIRE RÉEL TOTAL       : 66 850 DA (46 850 + 20 000)

IMPUTATION PROJETS :
  Karim travaille 60% IRENE, 40% AUREA ce mois
  
  IRENE :
    Montant RD  = 70 262 × 60% = 42 157.20 DA
    Montant RND = 20 000 × 60% = 12 000.00 DA
    Total imputé IRENE = 54 157.20 DA
  
  AUREA :
    Montant RD  = 70 262 × 40% = 28 104.80 DA
    Montant RND = 20 000 × 40% =  8 000.00 DA
    Total imputé AUREA = 36 104.80 DA
  
  Vérification : 42 157.20 + 28 104.80 = 70 262.00 DA ✓ (part RD)
                 12 000.00 + 8 000.00  = 20 000.00 DA ✓ (part RND)
```

## 4.5 — Fichier Caisse (Circuit Espèces)

Les paiements non-déclarés (compléments salaires ND, paiements fournisseurs en espèces ND) passent par la caisse. Le système trace chaque mouvement :

```sql
CREATE TABLE mouvements_caisse (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entreprise_id UUID NOT NULL REFERENCES entreprises(id),
    projet_id UUID REFERENCES projets(id),
    date_mouvement DATE NOT NULL,
    sens VARCHAR(10) NOT NULL CHECK (sens IN ('ENTREE', 'SORTIE')),
    montant NUMERIC(15,2) NOT NULL CHECK (montant > 0),
    motif TEXT NOT NULL,
    beneficiaire VARCHAR(300),
    reference_fiche VARCHAR(100) NOT NULL,     -- Numéro de la fiche papier
    -- Lien avec opérations
    bulletin_paie_id UUID REFERENCES bulletins_paie(id),
    decaissement_id UUID REFERENCES decaissements(id),
    encaissement_id UUID REFERENCES encaissements(id),
    -- Le solde caisse ne doit jamais être négatif
    solde_avant NUMERIC(15,2),
    solde_apres NUMERIC(15,2),
    -- Statut fiscal : toujours RND ou FND pour la caisse
    statut_fiscal statut_fiscal_enum NOT NULL,
    -- Document (photo de la fiche)
    document_id UUID REFERENCES documents(id),
    est_test_fictif BOOLEAN NOT NULL DEFAULT FALSE,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CHECK (statut_fiscal IN ('REEL_NON_DECLARE', 'FICTIF_NON_DECLARE'))
);
```

---

# CHAPITRE 5 — CLIENTS, FOURNISSEURS, RH : TOUJOURS DÉCLARÉ / NON-DÉCLARÉ

## 5.1 — Clients : Double réalité

Chaque client peut avoir des paiements déclarés ET non-déclarés :

```
Client Hamidi K. — Projet IRENE — Lot B3-E2-L04

Contrat total : 12 000 000 DA

Paiements déclarés (RD) :
  15/01/2026 : Chèque CNEP 3 000 000 DA → RD
  20/02/2026 : Virement BNA 2 000 000 DA → RD
  Total RD : 5 000 000 DA

Paiements non-déclarés (RND) :
  10/01/2026 : Espèces 1 500 000 DA → RND
  05/03/2026 : Espèces 1 000 000 DA → RND
  Total RND : 2 500 000 DA

RÉSUMÉ CLIENT :
  Total payé réel    : 7 500 000 DA (RD + RND)
  Reste à payer réel : 4 500 000 DA
  Total payé déclaré : 5 000 000 DA (RD seul)
  Reste déclaré      : 7 000 000 DA
  Avancement réel    : 62.50%
  Avancement déclaré : 41.67%
```

## 5.2 — Fournisseurs : Double réalité

```
Fournisseur SARL Béton Plus — Ciment pour IRENE

Facture FAC-2026-0234 :
  Montant HT  : 5 000 000 DA
  TVA 19%     :   950 000 DA
  TTC         : 5 950 000 DA
  Statut      : REEL_DECLARE

Paiement complémentaire hors facture :
  Espèces : 500 000 DA
  Motif   : "Complément négocié"
  Statut  : REEL_NON_DECLARE

Le centre de coût IRENE reçoit :
  RD  : 5 950 000 DA
  RND :   500 000 DA
  Total réel : 6 450 000 DA
```

## 5.3 — Vue unifiée D/ND pour chaque tiers

Le système génère pour chaque tiers (client, fournisseur, employé) un résumé :

| Champ | Formule |
|-------|---------|
| Total opérations RD | SUM(montants WHERE statut_fiscal = RD) |
| Total opérations RND | SUM(montants WHERE statut_fiscal = RND) |
| Total opérations FD | SUM(montants WHERE statut_fiscal = FD) |
| Total opérations FND | SUM(montants WHERE statut_fiscal = FND) |
| Total réel | RD + RND |
| Total fiscal | RD + nominal FD |
| Écart réel vs fiscal | Total réel − Total fiscal |

---

# CHAPITRE 6 — DASHBOARD ULTRA-DÉTAILLÉ

## 6.1 — Page d'accueil : Vue d'ensemble

```
┌─────────────────────────────────────────────────────────────────────┐
│  GFI System v6.0 — Tableau de Bord                   [Entreprise ▼] │
│                                                       [Période   ▼] │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │ 🔴 7     │  │ 📊 12    │  │ 💰 45.2M │  │ 📦 3     │           │
│  │ Blocages │  │ Projets  │  │ CA Mois  │  │ Alertes  │           │
│  │ actifs   │  │ actifs   │  │ (DA)     │  │ stock    │           │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘           │
│                                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │ 🏦 12.5M │  │ 👥 1454  │  │ 📋 23    │  │ ⚖️ 8.3M  │           │
│  │ Transit  │  │ Clients  │  │ Docs en  │  │ Résultat │           │
│  │ notaire  │  │ total    │  │ attente  │  │ mois     │           │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘           │
│                                                                     │
│  ══════════════════════════════════════════════════════════════════  │
│  ACTIONS REQUISES (classées par priorité)                           │
│  ──────────────────────────────────────────────────────────────────  │
│  🔴 [CRITIQUE] Facture FAC-2026-0847 : TTC incohérent    [Résoudre]│
│  🔴 [CRITIQUE] 3 employés sans bulletin janvier          [Saisir]  │
│  🟡 [IMPORTANT] Transit Maître Izouine : VEFA à libérer  [Libérer] │
│  🟡 [IMPORTANT] 5 documents non classifiés               [Classer] │
│  🟢 [NORMAL] Ratio charges communes février à valider    [Valider] │
│  ──────────────────────────────────────────────────────────────────  │
│                                                                     │
│  ══════════════════════════════════════════════════════════════════  │
│  CENTRE DE COÛT — VUE TEMPS RÉEL                                    │
│  ──────────────────────────────────────────────────────────────────  │
│  [Graphique barres empilées : recettes vs dépenses par projet]      │
│  [Chaque barre décomposée : RD | RND | FD | CC]                    │
│                                                                     │
│  ══════════════════════════════════════════════════════════════════  │
│  POSITION ASSOCIÉS                                                   │
│  ──────────────────────────────────────────────────────────────────  │
│  Ahmed    : +45 230 000 DA  ████████████████████░░  [Détail]        │
│  Mohamed  : +12 800 000 DA  ██████░░░░░░░░░░░░░░░  [Détail]        │
│  Yazid    : +11 200 000 DA  █████░░░░░░░░░░░░░░░░  [Détail]        │
│  Yamina   :  +3 400 000 DA  ██░░░░░░░░░░░░░░░░░░░  [Détail]        │
└─────────────────────────────────────────────────────────────────────┘
```

## 6.2 — Écran Centre de Coût par Projet

### Filtres disponibles (en haut de l'écran)

| Filtre | Type | Options |
|--------|------|---------|
| Entreprise | Dropdown | Toutes / ETS-DK / SARL-DP / SARL-DBPI / SARL-OC / SARL-SEN |
| Projet | Dropdown (filtré par entreprise) | Tous / JASMIN / EDEN / ... |
| Période | Sélecteur date | Mois/Année ou plage personnalisée |
| Vue | Toggle | Mensuel / Cumulé / Annuel |
| Réalité | Multi-select | RD ☑ / RND ☑ / FD ☑ / FND ☑ / Tout ☑ |
| Affichage charges communes | Toggle | Incluses / Exclues / Détail séparé |

### Tableau principal

```
Centre de Coût — IRENE — Janvier 2026
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RECETTES                          RD            RND          TOTAL
─────────────────────────────────────────────────────────────────
Encaissements clients      15 000 000    8 000 000    23 000 000
Gains contentieux                  0      500 000       500 000
Libérations transit notaire 2 000 000            0     2 000 000
─────────────────────────────────────────────────────────────────
TOTAL RECETTES             17 000 000    8 500 000    25 500 000

DÉPENSES DIRECTES                 RD            RND          TOTAL
─────────────────────────────────────────────────────────────────
Matériaux & fournitures     2 500 000    1 200 000     3 700 000
Sous-traitance              1 800 000      800 000     2 600 000
Main d'œuvre directe        1 700 000    1 500 000     3 200 000
  dont RH déclarée          1 700 000                  1 700 000
  dont complément ND                     1 500 000     1 500 000
Études & honoraires           500 000            0       500 000
Transport                     300 000      200 000       500 000
Assurances chantier           200 000            0       200 000
Frais notaire (actes)         150 000            0       150 000
─────────────────────────────────────────────────────────────────
Sous-total dépenses dir.    7 150 000    3 700 000    10 850 000

Coût factures fictives       FD nominal   Coût réel
  FD (taux 3%)              10 000 000      300 000       300 000
  FND                                0            0             0

Pertes contentieux                                       200 000
Stock consommé (CUMP)                                  1 200 000
Masse salariale directe                                2 800 000
  (via imputation projets)
─────────────────────────────────────────────────────────────────
TOTAL DÉPENSES DIRECTES                               14 000 000

CHARGES COMMUNES (ratio 65.71%)
─────────────────────────────────────────────────────────────────
Loyer siège (500K × 65.71%)                              328 571
Salaires admin (1.5M × 65.71%)                           985 714
Fournitures bureau (200K × 65.71%)                       131 429
Téléphone/Internet (100K × 65.71%)                        65 714
Frais bancaires (300K × 65.71%)                          197 143
Honoraires comptable (400K × 65.71%)                     262 857
─────────────────────────────────────────────────────────────────
TOTAL CHARGES COMMUNES                                 1 971 429

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOTAL DÉPENSES                                        15 971 429
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RÉSULTAT ULTRA-RÉEL                                    9 528 571
Marge brute                                               37.37%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RÉSULTAT FISCAL (déclaré uniquement)                  -1 000 000
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

INDICATEURS COMPLÉMENTAIRES
─────────────────────────────────────────────────────────────────
Transit notaire en attente                             4 500 000
Reste à payer clients                                120 000 000
Avancement encaissements                                  15.9%
Nombre de clients                                           692
  dont en retard > 30j                                       23
  dont en retard > 90j                                        5
```

### Boutons d'action sur cet écran

| Bouton | Action |
|--------|--------|
| 🖨️ Imprimer | Génère une version imprimable (CSS @media print, format A4 paysage) |
| 📥 Export Excel | Exporte le tableau en .xlsx avec les mêmes colonnes |
| 📥 Export PDF | Exporte en PDF formaté avec en-tête entreprise |
| 📊 Graphique | Bascule vers une vue graphique (barres empilées RD/RND/FD) |
| 🔄 Recalculer | Force le recalcul du centre de coût (double computation) |
| 📅 Comparer | Compare avec un autre mois (vue côte à côte) |

## 6.3 — Écran Centre de Coût CONSOLIDÉ tous projets

Même structure que le 6.2 mais agrégé sur tous les projets d'une entreprise, avec une ligne par projet.

```
Consolidation — SARL Dendani Promotion — Janvier 2026

Projet    | Recettes    | Dép. dir.  | CC        | Total dép. | Résultat   | Marge
──────────┼─────────────┼────────────┼───────────┼────────────┼────────────┼──────
OPERA     |  7 000 000  | 4 200 000  |   600 000 | 4 800 000  |  2 200 000 | 31.4%
IRENE     | 25 500 000  |14 000 000  | 1 971 429 |15 971 429  |  9 528 571 | 37.4%
AUREA     |  5 000 000  | 3 100 000  |   428 571 | 3 528 571  |  1 471 429 | 29.4%
──────────┼─────────────┼────────────┼───────────┼────────────┼────────────┼──────
TOTAL     | 37 500 000  |21 300 000  | 3 000 000 |24 300 000  | 13 200 000 | 35.2%
```

## 6.4 — Écran Employés / Paie

### Liste des employés

```
Filtres : [Entreprise ▼] [Projet ▼] [Mois ▼] [Statut ▼] [D/ND ▼]

Mat.  | Nom Prénom      | Poste           | Brut     | Net RD   | Compl.ND | Réel     | Projets
──────┼─────────────────┼─────────────────┼──────────┼──────────┼──────────┼──────────┼────────
K-001 | Karim Benali    | Chef chantier   |  55 000  |  46 850  |  20 000  |  66 850  | IRENE 60%, AUREA 40%
K-002 | Said Hamidi      | Maçon           |  40 000  |  34 200  |  15 000  |  49 200  | IRENE 100%
K-003 | Fatima Zerhouni  | Comptable       |  50 000  |  42 500  |  10 000  |  52 500  | COMMUNE
K-004 | Omar Slimani     | Commercial      |  45 000  |  38 250  |  12 000  |  50 250  | AUREA 50%, IRENE 50%

[+ Ajouter employé]  [📥 Import PC Paie]  [🖨️ Imprimer]  [📥 Export]
```

### Fiche de paie détaillée (clic sur un employé)

```
BULLETIN DE PAIE — Janvier 2026
═══════════════════════════════════════════
Employeur : SARL Dendani Promotion
Employé   : KARIM Benali (Mat. K-001)
Poste     : Chef de chantier
N° SS     : 12345678901234

RÉMUNÉRATION DÉCLARÉE (Assiette PC Paie)
─────────────────────────────────────────
Salaire de base ............ 45 000.00
Heures supplémentaires .....  5 000.00
Prime de rendement .........  3 000.00
Indemnités .................  2 000.00
                              ─────────
SALAIRE BRUT ............... 55 000.00

RETENUES
─────────────────────────────────────────
CNAS salarié (9%) ......... -4 950.00
IRG (barème) .............. -3 200.00
                              ─────────
TOTAL RETENUES ............ -8 150.00

SALAIRE NET DÉCLARÉ ........ 46 850.00

CHARGES PATRONALES
─────────────────────────────────────────
CNAS patronal (26%) ....... 14 300.00
CACOBATPH (1.75%) .........    962.50
                              ─────────
COÛT EMPLOYEUR TOTAL (RD) . 70 262.50

═══════════════════════════════════════════
COMPLÉMENT NON-DÉCLARÉ
─────────────────────────────────────────
Complément espèces ND ...... 20 000.00
Réf. fiche caisse : CAISSE-2026-01-047

SALAIRE RÉEL TOTAL ......... 66 850.00
═══════════════════════════════════════════

IMPUTATION PROJETS
─────────────────────────────────────────
IRENE (60%) :
  RD  = 70 262.50 × 60% = 42 157.50
  RND = 20 000.00 × 60% = 12 000.00
  Total IRENE = 54 157.50

AUREA (40%) :
  RD  = 70 262.50 × 40% = 28 105.00
  RND = 20 000.00 × 40% =  8 000.00
  Total AUREA = 36 105.00
═══════════════════════════════════════════

[🖨️ Imprimer bulletin RD]  [🖨️ Imprimer fiche complète]
```

## 6.5 — Écran Caisse (Mouvements espèces)

```
Filtres : [Entreprise ▼] [Période ▼] [Projet ▼] [Type D/ND ▼]

CAISSE — SARL Dendani Promotion — Janvier 2026
Solde d'ouverture : 2 500 000 DA

Date       | Réf. fiche      | Motif                        | Entrée     | Sortie     | Solde
───────────┼─────────────────┼──────────────────────────────┼────────────┼────────────┼───────────
02/01/2026 | CAISSE-01-001   | Approvisionnement caisse     | 5 000 000  |            | 7 500 000
05/01/2026 | CAISSE-01-002   | Compl. salaire Karim (IRENE) |            |    20 000  | 7 480 000
05/01/2026 | CAISSE-01-003   | Compl. salaire Said (IRENE)  |            |    15 000  | 7 465 000
10/01/2026 | CAISSE-01-004   | Encaiss. client Hamidi ND    | 1 500 000  |            | 8 965 000
12/01/2026 | CAISSE-01-005   | Paiement fournisseur ND      |            |   500 000  | 8 465 000
15/01/2026 | CAISSE-01-006   | Frais divers chantier        |            |   120 000  | 8 345 000
...

Solde de clôture : 8 345 000 DA

Résumé :
  Total entrées   :  6 500 000 DA
  Total sorties   :    655 000 DA
  Variation       : +5 845 000 DA

[🖨️ Imprimer]  [📥 Export]  [+ Nouveau mouvement]
```

## 6.6 — Écran Clients par Projet

```
Filtres : [Projet ▼] [Statut ▼] [Retard ▼] [Recherche nom/lot]

Projet IRENE — 692 clients
                                                          Payé RD    Payé RND   Payé Total  Reste    %
Lot       | Nom              | Type | Contrat     | Statut | (déclaré) | (ND)     | (réel)    | à payer | Avanc.
──────────┼──────────────────┼──────┼─────────────┼────────┼───────────┼──────────┼───────────┼─────────┼──────
B1-E1-L01 | Benali Karim     | F3   | 10 000 000  | VENDU  | 5 000 000 | 1 500 000| 6 500 000 | 3 500 000| 65.0%
B1-E1-L02 | Hamidi Slimane   | F4   | 12 000 000  | VENDU  | 5 000 000 | 2 500 000| 7 500 000 | 4 500 000| 62.5%
B1-E1-L03 | Zerhouni Fatma   | F3   |  9 500 000  | RESERVE| 2 000 000 |   500 000| 2 500 000 | 7 000 000| 26.3%
B1-E2-L01 | ─ DISPONIBLE ─   | F3   |  9 800 000  | DISPO  |         0 |         0|         0 | 9 800 000|  0.0%
...

TOTAUX :
  Lots disponibles : 45
  Lots réservés    : 23
  Lots vendus      : 612
  Lots livrés      : 12
  
  CA total contrats : 6 920 000 000 DA
  Total encaissé RD : 3 200 000 000 DA
  Total encaissé RND: 1 100 000 000 DA
  Total encaissé    : 4 300 000 000 DA
  Reste à payer     : 2 620 000 000 DA
  Avancement global : 62.1%

  Retards > 30j : 23 clients (signalés 🟡)
  Retards > 60j : 8 clients (signalés 🟠)
  Retards > 90j : 5 clients (signalés 🔴)

[🖨️ Imprimer]  [📥 Export clients]  [📥 Export échéancier]
```

## 6.7 — Écran Fournisseurs

```
Filtres : [Entreprise ▼] [Catégorie ▼] [Projet ▼] [D/ND ▼]

                                   Total RD      Total RND    Total Réel   Total FD
Code   | Raison sociale        | (déclaré)    | (non-décl.) | (réel)      | (fictif)
───────┼───────────────────────┼──────────────┼─────────────┼─────────────┼──────────
F-001  | SARL Béton Plus       | 25 000 000   |  3 000 000  | 28 000 000  |         0
F-002  | ETS Ferraille Ahmed   | 18 000 000   |  2 500 000  | 20 500 000  |         0
F-003  | SARL Plomberie Alger  |  8 000 000   |  1 000 000  |  9 000 000  |         0
F-004  | EURL Facture Service  |  5 000 000   |          0  |    150 000  | 5 000 000
        (fournisseur fictif)                                  (coût 3%)

[🖨️ Imprimer]  [📥 Export]  [+ Ajouter fournisseur]
```

---

# CHAPITRE 7 — ÉLÉMENTS IMPRIMABLES

Chaque écran qui contient des données a un bouton 🖨️ qui génère une version imprimable. Le système utilise CSS `@media print` avec les règles suivantes :

## 7.1 — Liste des documents imprimables

| Document | Format | Contenu |
|----------|--------|---------|
| Centre de coût mensuel | A4 paysage | Tableau complet recettes/dépenses/résultat |
| Centre de coût consolidé | A4 paysage | Tous les projets d'une entreprise |
| Consolidation par associé | A4 portrait | Position nette par projet + total |
| Consolidation par entreprise | A4 paysage | Tous les projets par entité |
| Liste clients projet | A4 paysage | Tous les clients avec avancement |
| Échéancier client | A4 portrait | Détail des échéances d'un client |
| Bulletin de paie RD | A4 portrait | Bulletin officiel (sans le ND) |
| Fiche de paie complète | A4 portrait | Bulletin RD + complément ND (usage interne) |
| Mouvement de caisse | A4 portrait | Journal de caisse avec solde |
| Fiche de stock article | A4 portrait | Historique mouvements d'un article |
| Ticket de stock (80mm) | Ticket 80mm | Entrée/sortie pour imprimante thermique |
| Situation client | A4 portrait | Résumé paiements + reste à payer |
| Ratio charges communes | A4 portrait | Détail du calcul du ratio du mois |
| État récapitulatif 4 réalités | A4 paysage | Matrice RD/RND/FD/FND par projet |
| Position nette associé | A4 portrait | Capital, retraits, résultat, solde |
| Transit notaire | A4 portrait | État des transits par notaire |

## 7.2 — En-tête standard des impressions

Chaque document imprimé contient :
```
[Logo entreprise si disponible]
[Raison sociale]
[NIF — RC — NIS — AI]
[Adresse]
[Téléphone — Email]

Titre du document
Période : Janvier 2026
Généré le : 01/02/2026 à 14:32:15
Généré par : Ahmed (Administrateur)
```

## 7.3 — Export Excel (.xlsx)

Chaque tableau exportable génère un fichier Excel avec :
- Onglet "Données" : les données brutes avec les mêmes colonnes que l'écran
- Onglet "Paramètres" : entreprise, période, filtres appliqués, date de génération
- Formules Excel pour les totaux (pas des valeurs figées)
- Mise en forme : en-têtes en gras, bordures, alternance de couleurs

## 7.4 — Export PDF

Utilisation de `weasyprint` ou `reportlab` pour générer des PDF formatés avec l'en-tête entreprise.

---

# CHAPITRE 8 — RÈGLES DE CALCUL EXHAUSTIVES

## 8.1 — IRG (Impôt sur le Revenu Global) — Barème progressif algérien

```python
def calculer_irg(salaire_imposable):
    """
    Barème IRG algérien (2024-2026)
    salaire_imposable = salaire_brut - CNAS salarié
    """
    if salaire_imposable <= 20000:
        return 0
    elif salaire_imposable <= 40000:
        return (salaire_imposable - 20000) * 0.23
    elif salaire_imposable <= 80000:
        return 4600 + (salaire_imposable - 40000) * 0.27
    elif salaire_imposable <= 160000:
        return 15400 + (salaire_imposable - 80000) * 0.30
    elif salaire_imposable <= 320000:
        return 39400 + (salaire_imposable - 160000) * 0.33
    else:
        return 92200 + (salaire_imposable - 320000) * 0.35
```

## 8.2 — CNAS (Caisse Nationale d'Assurances Sociales)

```
Part salarié  :  9% du salaire brut
Part patronal : 26% du salaire brut
CACOBATPH     : 1.75% du salaire brut (BTP uniquement)
CASNOS        : 15% (pour les dirigeants non-salariés)
```

## 8.3 — TVA

```
Taux normal  : 19%
Taux réduit  :  9% (certains produits)

Vérification systématique :
  montant_tva = montant_ht × taux_tva / 100
  montant_ttc = montant_ht + montant_tva
  Tolérance : 0.00 DA (zéro)
```

## 8.4 — CUMP (Coût Unitaire Moyen Pondéré)

```
Après chaque ENTRÉE :
  nouveau_cump = (ancien_stock × ancien_cump + quantite_entree × prix_entree) 
                 / (ancien_stock + quantite_entree)

Après chaque SORTIE :
  Le CUMP ne change pas.
  Valeur sortie = quantite_sortie × cump_actuel
```

## 8.5 — G50 mensuel

```
TVA collectée (ventes RD du mois)
- TVA déductible (achats RD du mois avec factures)
= TVA à payer

TAP = CA déclaré × 2%
IRG salaires = SUM(IRG de tous les bulletins RD)

Total G50 = TVA à payer + TAP + IRG salaires
```

---

# CHAPITRE 9 — PARAMÈTRES SYSTÈME COMPLETS

```sql
-- Paramètres avec leurs valeurs par défaut
INSERT INTO parametres (cle, valeur, description) VALUES
-- Taux fiscaux
('taux_tva_normal', '19', 'Taux TVA normal (%)'),
('taux_tva_reduit', '9', 'Taux TVA réduit (%)'),
('taux_tap', '2', 'Taux TAP (%)'),
('taux_ibs', '19', 'Taux IBS sociétés (%)'),
-- Taux sociaux
('cnas_taux_salarie', '9', 'CNAS part salariale (%)'),
('cnas_taux_patronal', '26', 'CNAS part patronale (%)'),
('cacobatph_taux', '1.75', 'CACOBATPH BTP (%)'),
('casnos_taux', '15', 'CASNOS dirigeants (%)'),
-- Centre de coût
('taux_cout_fictif', '3', 'Coût réel des factures fictives (%)'),
('methode_ratio_charges_communes', 'CA', 'Méthode ratio : CA ou DEPENSES'),
('delta_tolerance_da', '0.00', 'Delta toléré double computation (DA)'),
-- Alertes
('alerte_retard_j1', '30', 'Première alerte retard (jours)'),
('alerte_retard_j2', '60', 'Deuxième alerte retard (jours)'),
('alerte_retard_j3', '90', 'Troisième alerte retard (jours)'),
-- Blocages
('notification_blocage_4h', '4', 'Délai 1ère notification (heures)'),
('notification_blocage_24h', '24', 'Délai 2ème notification (heures)'),
('notification_blocage_72h', '72', 'Délai 3ème notification (heures)'),
-- Transit notaire
('transit_tranche1_pct', '20', 'Tranche 1 notaire (%)'),
('transit_tranche2_pct', '5', 'Tranche 2 notaire (%)'),
('transit_direct_pct', '75', 'Part directe banque (%)'),
-- Stock
('methode_valorisation_stock', 'CUMP', 'Méthode valorisation stock'),
('seuil_alerte_stock', '10', 'Seuil alerte stock minimum (%)'),
-- Devise
('devise_principale', 'DZD', 'Devise par défaut'),
('symbole_devise', 'DA', 'Symbole devise affiché');
```

---

**FIN DE L'ANNEXE C — SPÉCIFICATION ULTRA-DÉTAILLÉE**

Ce document est complémentaire au Blueprint v6.0 principal. Ensemble, ils forment la spécification complète. Le développeur lit ces deux documents et code sans poser aucune question. Chaque calcul est montré avec un exemple chiffré. Chaque écran est dessiné. Chaque filtre est listé. Chaque bouton est décrit. Chaque formule est écrite.
