# GFI SYSTÈME v7.0 — MODULE PLANIFICATION × SALAIRE × PERFORMANCE (SPI)

## SPÉCIFICATION ULTRA-DÉTAILLÉE — PLANIFICATION STRATÉGIQUE, PAIE INTELLIGENTE, BONUS/MALUS, KPI, PREUVE

**Groupe Dendani** — Bab Ezzouar, Alger  
**Classification :** CONFIDENTIEL  
**Version :** 7.0-SPI-DEFINITIVE  
**Date :** Mars 2026  

---

# TABLE DES MATIÈRES

**PARTIE I — CONTRAT & SALAIRE : LE DÉCLENCHEUR**
1. [Le contrat déclenche tout](#1-contrat)
2. [Structure salariale : base CNAS + variable SPI](#2-structure-salariale)
3. [Séparation absolue des flux salariaux](#3-séparation-flux)

**PARTIE II — PLANIFICATION : TOUT LE MONDE PEUT PROPOSER**
4. [Principe : la planification est ouverte](#4-planification-ouverte)
5. [Proposer un plan stratégique → prime 5%](#5-prime-plan)
6. [Validation : système + CEO + contre-proposition](#6-validation-plan)
7. [Dispatch automatique des tâches selon fiche de poste](#7-dispatch)
8. [Cascade : stratégique → opérationnel → tâche → sous-tâche](#8-cascade)

**PARTIE III — KPI : MESURER SANS VISION TUNNEL**
9. [Les 4 composantes du SPI](#9-composantes-spi)
10. [KPI par poste : adaptation automatique](#10-kpi-poste)
11. [Double vérification : système + humain](#11-double-vérification)
12. [Protection des bons employés : mécanisme anti-erreur](#12-protection)

**PARTIE IV — BONUS / MALUS : L'OFFRE DE PERFORMANCE**
13. [Principe : l'employé propose son taux bonus/malus](#13-offre-performance)
14. [Cycle offre → contre-offre → verrouillage](#14-cycle-offre)
15. [Même montant bonus = même montant malus](#15-symétrie)
16. [Calcul mensuel et accumulation](#16-calcul-mensuel)

**PARTIE V — SOUS-PERFORMANCE & SORTIE**
17. [2 mois consécutifs < 50% → procédure de sortie](#17-sous-performance)
18. [Sortie avec moindre dégât financier](#18-sortie-propre)
19. [Sauvegardes anti-erreur : ne pas licencier un bon employé](#19-sauvegardes)
20. [Procédure légale Code du travail algérien](#20-procédure-légale)

**PARTIE VI — COMMERCIAUX : POLITIQUE CRM**
21. [Objectifs vente + commissions par mode paiement](#21-commissions)
22. [Paliers mensuels : 0 vente → 5+ ventes](#22-paliers)
23. [Traçabilité CRM obligatoire pour toute commission](#23-traçabilité-crm)

**PARTIE VII — PREUVES & JUSTIFICATION**
24. [Zéro paiement sans preuve](#24-zéro-sans-preuve)
25. [Types de preuves acceptées](#25-types-preuves)
26. [Validation IA + humaine de chaque preuve](#26-validation-preuve)

**PARTIE VIII — TABLEAU DE BORD MOBILE**
27. [Dashboard employé sur téléphone](#27-dashboard-mobile)
28. [Dashboard manager](#28-dashboard-manager)
29. [Dashboard CEO/DAF](#29-dashboard-daf)
30. [Notifications et workflows mobiles](#30-notifications)

**PARTIE IX — LIEN AVEC LES AUTRES MODULES GFI**
31. [Lien Salaire → Trésorerie → Centre de Coût](#31-lien-trésorerie)
32. [Lien Tâches → Projets → Budgets](#32-lien-projets)
33. [Lien Performance → Comptabilité → Charges partagées](#33-lien-comptabilité)

**PARTIE X — MODÈLE DE DONNÉES & SCÉNARIOS**
34. [Modèle de données complet](#34-modèle-données)
35. [Scénarios réalistes de bout en bout](#35-scénarios)
36. [API Endpoints](#36-api)

---

# PARTIE I — CONTRAT & SALAIRE : LE DÉCLENCHEUR

---

# 1. LE CONTRAT DÉCLENCHE TOUT

## 1.1. Principe fondamental

Le **contrat de travail** est le point zéro. Rien n'existe dans le système avant la signature du contrat. Le contrat fixe :

- **Le salaire de base déclaré CNAS** — fixe, intangible, légal → ne peut JAMAIS être réduit par le système
- **La clause prime variable SPI** — avenant signé, expliquant le mécanisme bonus/malus
- **La fiche de poste** — compétences, missions, KPI métier attendus

```
SIGNATURE CONTRAT
    │
    ├── ① Contrat de travail signé (salaire base CNAS)
    ├── ② Avenant prime variable SPI (co-signé, accusé de réception)
    ├── ③ Fiche de poste chargée dans le système
    ├── ④ Profil créé dans GFI (accès, rôle RBAC, département)
    ├── ⑤ Formation SPI (J+3 : lecture dashboard, offre performance, upload preuves)
    ├── ⑥ Premier objectif assigné (J+3 à J+7 : acceptation ou contre-offre sous 48h)
    └── ⑦ Premier bilan SPI à J+30 (validation période d'essai si SPI ≥ 51%)
```

## 1.2. Données employé dans le système

```
EMPLOYE {
    id                      : UUID (PK)
    
    // ── IDENTITÉ ──
    nom, prenom             : String
    cin                     : String UNIQUE
    date_naissance          : Date
    adresse                 : String
    telephone               : String
    email                   : String
    photo                   : UUID → DocumentGED
    
    // ── CONTRAT ──
    numero_contrat          : String UNIQUE
    date_embauche           : Date
    type_contrat            : Enum [CDI, CDD, STAGE, INTERIM]
    duree_cdd_mois          : Integer (nullable)
    periode_essai_jours     : Integer
    statut_essai            : Enum [EN_COURS, VALIDE, NON_VALIDE]
    
    // ── SALAIRE BASE (CNAS déclaré) ──
    salaire_base_mensuel    : Decimal(12,2) — FIXE, intangible
    regime_cnas             : String
    numero_cnas             : String
    
    // ── PRIME VARIABLE SPI ──
    prime_spi_plafond       : Decimal(12,2) — Plafond mensuel de la prime variable
    avenant_spi_signe       : Boolean — OBLIGATOIRE avant tout calcul bonus/malus
    avenant_spi_doc_id      : UUID → DocumentGED
    
    // ── POSTE ──
    poste_id                : UUID → FK Poste
    departement_id          : UUID → FK Departement
    manager_id              : UUID → FK Employe (N+1)
    fiche_poste_id          : UUID → DocumentGED
    
    // ── AFFECTATION PROJETS ──
    projets_affectes : [{
        projet_id           : UUID
        pourcentage_temps   : Decimal(5,2) — % du temps de travail sur ce projet
    }]
    // Σ pourcentages = 100%
    
    // ── ENTITÉ JURIDIQUE ──
    entite_juridique_id     : UUID → FK
    
    // ── SPI ──
    spi_courant             : Decimal(5,2) — Score SPI du mois en cours (calculé)
    spi_historique          : Array[{mois, score, detail}]
    mois_consecutifs_sous_50 : Integer — Compteur pour procédure rupture
    mois_consecutifs_sous_70 : Integer — Compteur pour malus progressif
    statut_rh               : Enum [ACTIF, AVERTISSEMENT, SURVEILLANCE, PLAN_REDRESSEMENT, 
                                    EN_PROCEDURE_RUPTURE, SORTI]
    
    // ── SOLDE BONUS/MALUS ──
    solde_bonus_malus       : Decimal(12,2) — Cumulé (peut être négatif si malus > bonus)
    
    // ── COMMERCIAL (si applicable) ──
    est_commercial          : Boolean
    objectif_ventes_mensuel : Integer (nullable)
    palier_commercial       : Enum [ZERO, SOUS_PERF, CORRECT, OBJECTIF, EXCELLENCE] (nullable)
    
    // ── POINTAGE ──
    mode_pointage           : Enum [BIOMETRIQUE, QR_CODE, GEOLOCALISATION, MANUEL]
}
```

---

# 2. STRUCTURE SALARIALE

## 2.1. Formule universelle

```
SALAIRE_NET_MENSUEL =
    salaire_base_declaré            (contrat CNAS — INTANGIBLE)
    + prime_SPI                     (performance positive → depuis planification/CRM/tâches)
    − malus_SPI                     (sous-performance → calculé par le système)
    + commission_vente              (commerciaux uniquement → depuis CRM)
    + prime_plan_strategique        (5% si plan validé → depuis planification)
    + primes_exceptionnelles        (CEO → hors SPI)
    + indemnités_mission            (ordres de mission validés)
    − retenues_legales              (CNAS 9%, IRG barème)
```

## 2.2. Sources de chaque composante

| Composante | Source dans GFI | Qui décide | Peut être réduite ? |
|-----------|----------------|-----------|-------------------|
| Salaire base CNAS | Contrat de travail | Légal | **JAMAIS** |
| Prime SPI | Module SPI (tâches + qualité + comportement + KPI métier) | Système + Manager + CEO | Oui par malus SPI |
| Commission vente | Module CRM (ventes encaissées × taux) | Automatique | Non — palier fixe |
| Prime plan stratégique | Module Planification (plan validé) | CEO + Système | Non |
| Primes exceptionnelles | Décision CEO | CEO | Non |
| Indemnités mission | Ordres de mission validés | DAF | Non |

## 2.3. Ce qui est déclaré vs ce qui est interne

| Flux | Déclaré CNAS/Fisc | Compta officielle | Compta interne GFI |
|------|-------------------|-------------------|-------------------|
| Salaire base | ✅ OUI | ✅ OUI | ✅ OUI |
| Prime SPI (si déclarée) | ✅ OUI | ✅ OUI | ✅ OUI |
| Prime SPI (part non déclarée) | ❌ NON | ❌ NON | ✅ OUI (RF2) |
| Commission vente | Selon contrat | Selon RF | ✅ OUI |
| Prime plan | Selon décision | Selon RF | ✅ OUI |

---

# 3. SÉPARATION ABSOLUE DES FLUX SALARIAUX

Le salaire de base déclaré CNAS est **SACRÉ**. Le système ne peut **JAMAIS** le toucher, le réduire, le conditionner. C'est la loi.

Le SPI ne touche que la **prime variable**. Si un employé a un SPI de 0%, il reçoit quand même son salaire de base complet.

```
EXEMPLE :
    Salaire base CNAS : 80 000 DA/mois
    Prime SPI plafond  : 40 000 DA/mois
    
    CAS 1 : SPI = 95% (excellence)
    → Base 80 000 + Prime 40 000 × 110% = 80 000 + 44 000 = 124 000 DA
    
    CAS 2 : SPI = 75% (standard)
    → Base 80 000 + Prime 40 000 × 105% = 80 000 + 42 000 = 122 000 DA
    
    CAS 3 : SPI = 60% (sous-performance)
    → Base 80 000 + Prime 40 000 × 80% = 80 000 + 32 000 = 112 000 DA
    
    CAS 4 : SPI = 30% (défaillance)
    → Base 80 000 + Prime 0 DA = 80 000 DA (base seule)
    → + Malus accumulé dans le solde négatif (sera déduit des futurs bonus)
```

---

# PARTIE II — PLANIFICATION : TOUT LE MONDE PEUT PROPOSER

---

# 4. PRINCIPE : LA PLANIFICATION EST OUVERTE

## 4.1. Qui peut proposer un plan ?

**TOUT LE MONDE.** Le CEO, un manager, un employé, le magasinier, le comptable — n'importe qui dans le système peut proposer un plan stratégique, une amélioration opérationnelle, une nouvelle tâche, un objectif.

**Le but : les gens capables ne doivent pas être bloqués pour gagner de l'argent.** Si quelqu'un a une bonne idée qui fait avancer l'entreprise → il doit pouvoir la proposer et être récompensé.

## 4.2. Types de propositions

| Type | Qui peut proposer | Portée | Exemple |
|------|------------------|--------|---------|
| **Plan stratégique** | Tout le monde | Entreprise entière | "Lancer une campagne digitale pour AURÉA ciblant diaspora" |
| **Objectif opérationnel** | Tout le monde | Département / projet | "Réduire délai livraison béton de 48h à 24h sur IRENE" |
| **Tâche / mission** | Tout le monde | Pour soi ou pour d'autres | "Négocier prix ciment avec 3 fournisseurs alternatifs" |
| **Amélioration process** | Tout le monde | Transversal | "Automatiser les relances clients en retard de paiement" |
| **Correction / alerte** | Tout le monde | Ponctuel | "Le mur du bloc 3 IRENE présente une fissure — à vérifier" |

---

# 5. PROPOSER UN PLAN STRATÉGIQUE → PRIME 5%

## 5.1. Mécanisme

```
EMPLOYÉ PROPOSE UN PLAN
    │
    ├── ① SOUMISSION via mobile/PC
    │     → Titre, description, objectif mesurable, KPIs proposés
    │     → Horizon (1 mois, 3 mois, 6 mois, 12 mois)
    │     → Bénéfice estimé pour l'entreprise (qualitatif ou chiffré)
    │     → Ressources nécessaires
    │     → Documents joints (étude, benchmark, données...)
    │
    ├── ② ANALYSE SYSTÈME (automatique)
    │     → Cohérence avec objectifs stratégiques existants
    │     → Faisabilité (charge de travail, budget disponible)
    │     → Détection de doublons (plan similaire déjà en cours)
    │     → Score de pertinence IA (0-100%)
    │     → Proposition d'améliorations ou corrections
    │
    ├── ③ VALIDATION CEO (ou manager N+2 selon portée)
    │     → VALIDÉ tel quel
    │     → VALIDÉ avec modifications (le CEO propose des ajustements)
    │     → CONTRE-PROPOSITION (reformulé, l'employé doit accepter ou ajuster)
    │     → DÉCLINÉ avec justification obligatoire
    │
    ├── ④ SI VALIDÉ :
    │     → PRIME DE 5% du salaire mensuel (base + prime SPI) versée au proposeur
    │     → Le plan est ENREGISTRÉ et DISPATCHÉ
    │     → L'employé proposeur peut être nommé chef de ce plan
    │     → Les tâches sont créées et assignées (voir §7)
    │
    └── ⑤ SI DÉCLINÉ :
          → Justification visible pour l'employé
          → L'employé peut reproposer une version améliorée
          → Aucune pénalité pour une proposition déclinée (JAMAIS punir l'initiative)
```

## 5.2. Structure de données — Plan stratégique

```
PLAN_STRATEGIQUE {
    id                      : UUID
    reference               : String ("PLAN-{YYYY}-{SEQ}")
    
    // ── PROPOSEUR ──
    proposeur_id            : UUID → FK Employe
    date_proposition        : DateTime
    
    // ── CONTENU ──
    titre                   : String (5-200 chars)
    description             : Text (min 100 chars)
    objectif_mesurable      : String
    kpis_proposes           : Array[{indicateur, cible, unite}]
    horizon                 : Enum [MOIS_1, MOIS_3, MOIS_6, MOIS_12]
    benefice_estime         : Text
    ressources_necessaires  : Text
    documents_joints        : Array[UUID] → FK DocumentGED
    
    // ── ANALYSE SYSTÈME ──
    score_pertinence_ia     : Decimal(5,2)
    doublons_detectes       : Array[UUID] (plans similaires)
    ameliorations_proposees : Text (suggestions IA)
    faisabilite_score       : Decimal(5,2)
    
    // ── VALIDATION ──
    statut                  : Enum [SOUMIS, EN_ANALYSE, VALIDE, CONTRE_PROPOSITION, 
                                    DECLINE, EN_EXECUTION, TERMINE, ABANDONNE]
    valideur_id             : UUID → FK (CEO ou manager)
    date_validation         : DateTime (nullable)
    modifications_valideur  : Text (nullable)
    justification_refus     : Text (nullable — OBLIGATOIRE si DECLINE)
    
    // ── PRIME ──
    prime_versee            : Boolean
    montant_prime           : Decimal(12,2) — 5% du salaire mensuel du proposeur
    mouvement_paie_id       : UUID → FK (nullable)
    
    // ── EXÉCUTION ──
    taches_generees         : Array[UUID] → FK Tache
    avancement_pct          : Decimal(5,2) — Calculé depuis les tâches
    
    // ── RATTACHEMENT GFI ──
    projet_id               : UUID (nullable — si lié à un projet spécifique)
    entite_juridique_id     : UUID (nullable)
    centre_cout_id          : UUID (nullable)
}
```

## 5.3. Règles anti-abus

| Règle | Description |
|-------|-----------|
| Max 3 plans/mois/employé | Éviter le spam de propositions non sérieuses |
| Min 100 caractères description | Assurer un minimum de réflexion |
| Pas de prime si plan = tâche déjà assignée | Éviter de repackager une tâche existante comme "plan" |
| Prime sur validation, pas sur résultat | L'initiative est récompensée même si l'exécution échoue ensuite |
| CEO peut déléguer validation | Au manager N+2 pour les plans de portée départementale |

---

# 6. VALIDATION : SYSTÈME + CEO + CONTRE-PROPOSITION

## 6.1. Processus de validation en 3 couches

```
COUCHE 1 — SYSTÈME (automatique, immédiat)
    → Vérification cohérence
    → Détection doublons
    → Score faisabilité
    → Estimation impact budget
    → Suggestions d'amélioration
    → Le système NE BLOQUE JAMAIS une proposition — il analyse et transmet

COUCHE 2 — CEO / MANAGER (humain, 72h max)
    → Lit la proposition + analyse système
    → Décide : VALIDE / CONTRE-PROPOSITION / DÉCLINE
    → Si CONTRE-PROPOSITION :
      → CEO reformule l'objectif ou ajuste le périmètre
      → L'employé reçoit la contre-proposition
      → L'employé accepte ou ajuste (48h)
      → Si accord → plan VALIDÉ
    → Si DÉCLINE : justification OBLIGATOIRE (pas de refus sans explication)

COUCHE 3 — VERROUILLAGE (automatique)
    → Plan verrouillé numériquement (signature digitale employé + valideur)
    → Prime 5% calculée et ajoutée à la paie du mois
    → Tâches générées et dispatchées
    → Aucune modification sans avenant co-signé
```

---

# 7. DISPATCH AUTOMATIQUE DES TÂCHES SELON FICHE DE POSTE

## 7.1. Le système est le dispatching intelligent

Quand un plan ou objectif est validé, le système **décompose automatiquement** en tâches et les assigne aux employés en fonction de :

| Critère d'assignation | Comment le système le vérifie | Source |
|----------------------|------------------------------|--------|
| Compétences | Fiche de poste vs description tâche | Module RH |
| Charge de travail actuelle | Nb tâches en cours + deadlines | Module Planification |
| Historique performance | SPI moyen sur les tâches similaires | Module SPI |
| Disponibilité | Congés, absences, missions en cours | Module RH |
| Affectation projet | % temps alloué au projet concerné | Profil employé |
| Dépendances | Tâches prédécesseurs | Module Planification |

## 7.2. Structure tâche

```
TACHE {
    id                      : UUID
    reference               : String ("TACHE-{YYYY}-{SEQ}")
    
    // ── ORIGINE ──
    source_type             : Enum [PLAN_STRATEGIQUE, OBJECTIF_CEO, OBJECTIF_MANAGER, 
                                    AUTO_PROPOSEE, CRM, MAINTENANCE, URGENCE]
    source_id               : UUID (plan, objectif, etc.)
    plan_strategique_id     : UUID (nullable)
    
    // ── CONTENU ──
    titre                   : String
    description             : Text
    criteres_acceptation    : Text — Ce qui fait qu'une tâche est "terminée"
    livrables_attendus      : Array[{type, description}]
    
    // ── ASSIGNATION ──
    assignee_id             : UUID → FK Employe
    assigneur_id            : UUID → FK (système, manager, CEO)
    departement_id          : UUID
    
    // ── TEMPORALITÉ ──
    date_creation           : DateTime
    date_debut_prevue       : Date
    date_fin_prevue         : Date
    date_debut_reelle       : Date (nullable)
    date_fin_reelle         : Date (nullable)
    duree_estimee_heures    : Decimal
    
    // ── DÉPENDANCES ──
    taches_predecesseurs    : Array[UUID]
    taches_successeurs      : Array[UUID]
    est_bloquee             : Boolean — true si prédécesseur non terminé
    
    // ── PERFORMANCE (OFFRE/CONTRE-OFFRE) ──
    // L'employé propose son taux bonus/malus pour cette tâche
    offre_performance : {
        bonus_propose_pct       : Decimal(5,2) — % de la prime SPI proposé par l'employé
        malus_identique         : Boolean (TOUJOURS true — même montant)
        statut_offre            : Enum [EN_ATTENTE, CONTRE_OFFRE_MANAGER, ACCEPTEE, VERROUILLEE]
        bonus_final_pct         : Decimal(5,2) — Après négociation
        montant_bonus_da        : Decimal(12,2) — Calculé = prime_plafond × bonus_final_pct
        montant_malus_da        : Decimal(12,2) — = montant_bonus_da (symétrique)
    }
    
    // ── KPI SPÉCIFIQUES ──
    kpis : [{
        indicateur              : String
        cible                   : Decimal
        unite                   : String
        poids_pct               : Decimal(5,2) — Poids dans l'évaluation de la tâche
        valeur_reelle           : Decimal (nullable — rempli à l'évaluation)
        score_kpi               : Decimal (nullable — calculé)
    }]
    
    // ── PREUVES ──
    preuves : [{
        type_preuve             : Enum [PHOTO, DOCUMENT, FICHIER, RAPPORT, VIDEO, CAPTURE_ECRAN]
        document_ged_id         : UUID → FK
        date_upload             : DateTime
        uploade_par             : UUID
        validee_ia              : Boolean (nullable)
        validee_manager         : Boolean (nullable)
        commentaire_validation  : String (nullable)
    }]
    
    // ── ÉVALUATION ──
    score_execution         : Decimal(5,2) — 0-100 (respect délai)
    score_qualite           : Decimal(5,2) — 0-100 (qualité livrable)
    score_global_tache      : Decimal(5,2) — Pondéré
    
    // ── VALIDATION ──
    valide_par_systeme      : Boolean (nullable)
    valide_par_manager      : Boolean (nullable)
    valide_par_ceo          : Boolean (nullable — si tâche critique)
    date_validation         : DateTime (nullable)
    
    // ── STATUT ──
    statut                  : Enum [PROPOSEE, ASSIGNEE, OFFRE_EN_COURS, VERROUILLEE, 
                                    EN_COURS, EN_REVUE, VALIDEE, REJETEE, ANNULEE]
    
    // ── RATTACHEMENT GFI ──
    projet_id               : UUID (nullable)
    centre_cout_id          : UUID (nullable)
    entite_juridique_id     : UUID
    
    // ── PRIORITÉ ──
    priorite                : Enum [CRITIQUE, ELEVEE, NORMALE, BASSE]
    
    // ── CONTESTATION ──
    est_contestee           : Boolean
    contestation            : {motif, date, statut, resolution}
}
```

---

# 8. CASCADE : STRATÉGIQUE → OPÉRATIONNEL → TÂCHE → SOUS-TÂCHE

```
PLAN STRATÉGIQUE (validé, ex: "Livrer AURÉA à 100% en Q4 2026")
    │
    ├── OBJECTIF OPÉRATIONNEL 1 : "Finaliser gros œuvre Tour A — Oct 2026"
    │   ├── TÂCHE 1.1 : "Commander béton C35 — M. Kamel — 15/10 — KPI: livré à temps"
    │   │   ├── Sous-tâche 1.1.1 : "Valider bon de commande — Approbation Manager — 12/10"
    │   │   └── Sous-tâche 1.1.2 : "Vérifier livraison — Magasinier — 16/10"
    │   ├── TÂCHE 1.2 : "Coulage dalle niveau 8 — Chef chantier — 20/10"
    │   └── TÂCHE 1.3 : "PV réception gros œuvre — BET — 31/10"
    │
    ├── OBJECTIF OPÉRATIONNEL 2 : "Vendre 80% des lots restants — Dec 2026"
    │   ├── TÂCHE 2.1 : "Campagne pub digitale — Marketing — Nov 2026"
    │   ├── TÂCHE 2.2 : "Relancer 50 prospects chauds — Commercial — Nov 2026"
    │   └── TÂCHE 2.3 : "Organiser journée portes ouvertes — ADV — Dec 2026"
    │
    └── CHAQUE TÂCHE :
        → Assignée selon fiche de poste
        → Offre bonus/malus proposée par l'employé
        → KPI définis (délai, qualité, quantité)
        → Preuves requises
        → Double validation (système + humain)
```

---

# PARTIE III — KPI : MESURER SANS VISION TUNNEL

---

# 9. LES 4 COMPOSANTES DU SPI

| Composante | Poids standard | Ce qui est mesuré | Sources GFI |
|-----------|---------------|-------------------|-------------|
| **C1 — Planification & exécution** | 30% | Tâches réalisées / promises. Respect délais. Précocité récompensée. | Module Planification |
| **C2 — Qualité du livrable** | 25% | Validé sans retour: 100pts. Avec corrections: 60pts. Refusé: 0pt. | Module Preuves + IA + Manager |
| **C3 — Comportement & disponibilité** | 25% | Présence, ponctualité, absences, réactivité, comportement. | Module RH + Pointage |
| **C4 — Performance métier directe** | 20% | KPIs spécifiques au poste (ventes, leads, dossiers, chantier...) | CRM + Achats + Projets |

**L'IA adapte les poids automatiquement selon la fiche de poste :**

| Poste | C1 | C2 | C3 | C4 |
|-------|----|----|----|----|
| Commercial | 15% | 10% | 10% | **65%** (ventes) |
| Chef chantier | **40%** (planif) | 20% | 15% | 25% |
| Comptable | 25% | **35%** (qualité) | 20% | 20% |
| Secrétaire | 20% | 20% | **35%** (dispo) | 25% |
| Magasinier | 30% | **30%** (qualité stock) | 20% | 20% |
| Architecte | 25% | **35%** (qualité) | 15% | 25% |

Σ poids = 100% TOUJOURS.

## 9.1. Calcul C1 — Exécution

| Situation tâche | Score C1 | Conséquence |
|----------------|----------|-------------|
| Livrée AVANT délai + qualité validée | 100 pts + bonus précocité 10 pts (plafonné 100) | Bonus extra |
| Livrée DANS le délai + qualité validée | 100 pts | Standard |
| Livrée 1–2 jours retard, validée | 75 pts | Retard mineur |
| Livrée 3–7 jours retard, validée | 50 pts | Retard significatif |
| Non livrée ou retard > 7 jours | 0 pt | Défaillance |

## 9.2. Calcul C2 — Qualité

| Résultat validation | Score C2 |
|--------------------|----------|
| Validé IA + Manager sans retour | 100 pts |
| Validé après 1 correction mineure | 80 pts |
| Validé après corrections majeures | 60 pts |
| Refusé par IA mais validé par Manager | 70 pts (l'humain prime) |
| Refusé par Manager | 0 pt |

## 9.3. Calcul C3 — Comportement

| Situation | Impact C3 |
|-----------|----------|
| Présent, ponctuel, professionnel | 100 pts |
| Retard (par occurrence > 3/mois) | −10 pts par retard |
| Absence injustifiée ≤ 1 jour | −15 pts |
| Absence injustifiée 2–3 jours | −30 pts |
| Absence injustifiée > 3 jours | C3 = 0 |
| Rappel verbal comportement | −5 pts |
| Avertissement écrit | −15 pts |

## 9.4. Formule SPI mensuel

```
SPI_mensuel = (C1 × w1) + (C2 × w2) + (C3 × w3) + (C4 × w4)

Où wi = poids adapté par le poste, Σ wi = 100%
Chaque Ci = 0-100 pts
Résultat SPI = 0-100
```

---

# 10-11. DOUBLE VÉRIFICATION : SYSTÈME + HUMAIN

## 10.1. Pourquoi double vérification

Le système seul peut se tromper (bug, mauvaise interprétation). L'humain seul peut être partial (favoritisme, vengeance). La double vérification **protège tout le monde** — l'entreprise ET l'employé.

## 10.2. Matrice de validation

| Quoi | Vérification système | Vérification humaine | Résultat final |
|------|---------------------|---------------------|---------------|
| Tâche livrée à temps ? | Horodatage upload preuve vs deadline | Manager confirme | Les 2 doivent converger |
| Qualité du livrable ? | IA analyse document (complétude, format, cohérence) | Manager évalue le fond | Si IA refuse mais Manager valide → Manager gagne (score 70) |
| Présence/absence ? | Pointage biométrique/QR/géoloc | Manager peut justifier exception | Justificatif uploadé → comptabilisé |
| KPI métier atteint ? | Données système (CRM, stock, compta) | Manager confirme contexte | Système calcule, Manager ajuste ±10% si contexte exceptionnel |

## 10.3. Règle d'arbitrage

```
SI système_valide ET humain_valide → VALIDÉ (100%)
SI système_valide ET humain_refuse → REFUSÉ (humain prime sur fond)
SI système_refuse ET humain_valide → VALIDÉ À 70% (humain override avec trace)
SI système_refuse ET humain_refuse → REFUSÉ (0%)

Tout override humain est TRACÉ avec justification obligatoire.
L'employé peut CONTESTER toute évaluation sous 5 jours.
```

---

# 12. PROTECTION DES BONS EMPLOYÉS : MÉCANISME ANTI-ERREUR

## 12.1. Le risque : mal mesurer et licencier un bon employé

Le système doit être **ULTRA-INTELLIGENT** pour ne pas commettre d'injustice. Voici les 8 garde-fous :

| # | Garde-fou | Comment ça marche |
|---|-----------|------------------|
| 1 | **Contexte externe** | Si un retard est dû à un fournisseur en retard ou une décision management → le système ajuste automatiquement le délai. L'employé n'est pas pénalisé pour ce qui n'est pas sa faute. |
| 2 | **Dépendances bloquantes** | Si la tâche de l'employé dépend d'un prédécesseur non terminé par un collègue → le compteur est suspendu tant que le blocage existe. |
| 3 | **Surcharge détectée** | Si l'employé a > 120% de charge théorique → le système alerte le manager et propose un rééquilibrage. Le SPI est pondéré par la charge réelle. |
| 4 | **Maladie / événement personnel** | Congé maladie justifié = SPI calculé UNIQUEMENT sur les jours travaillés. Pas de pénalité. |
| 5 | **Contestation avec gel** | Tant qu'une contestation est EN COURS → aucun malus ni action RH ne peut être exécuté. |
| 6 | **Historique positif** | Si un employé a 6 mois d'excellence (SPI > 85%) et 1 mois de sous-performance → le système recommande une investigation avant action. Un bon employé ne devient pas mauvais en 1 mois. |
| 7 | **Entretien OBLIGATOIRE** | Avant toute action RH (avertissement, malus, rupture) → entretien documenté entre employé + manager + RH. Pas d'action automatique sans dialogue humain. |
| 8 | **3ème avis** | Si le manager veut pénaliser mais le système détecte une incohérence (ex: employé a livré mais avec retard dû à une surcharge) → le système demande un 3ème avis (N+2 ou DG). |

## 12.2. Score de fiabilité de la mesure

Pour chaque SPI mensuel, le système calcule un **score de fiabilité** :

```
FIABILITE_SPI(employe, mois) =
    (Nb tâches avec données complètes / Nb tâches total) × 30%
    + (Pas de contestation en cours) × 20%
    + (Pas de facteur externe non résolu) × 20%
    + (Convergence système-manager) × 20%
    + (Historique stable, pas de chute brutale inexpliquée) × 10%

SI fiabilité < 70% → SPI MARQUÉ "À CONFIRMER"
    → Aucune action RH possible tant que non confirmé
    → Manager DOIT investiguer et confirmer ou corriger sous 5 jours
```

---

# PARTIE IV — BONUS / MALUS : L'OFFRE DE PERFORMANCE

---

# 13. L'EMPLOYÉ PROPOSE SON TAUX BONUS/MALUS

## 13.1. Principe révolutionnaire

Pour chaque tâche assignée, l'employé **propose lui-même** le taux de bonus qu'il souhaite recevoir s'il réussit. Et **le même montant** sera son malus s'il échoue.

C'est un **contrat de performance bilatéral** : l'employé choisit le niveau de risque/récompense.

## 13.2. Workflow offre de performance

```
TÂCHE ASSIGNÉE À L'EMPLOYÉ
    │
    ├── ① EMPLOYÉ PROPOSE (sous 48h)
    │     → "Je propose un bonus de 8% de ma prime SPI pour cette tâche"
    │     → "Délai : je peux livrer en 5 jours au lieu de 7"
    │     → "Si je réussis : +8% prime = +3 200 DA"
    │     → "Si j'échoue : −8% prime = −3 200 DA" (MÊME MONTANT)
    │
    ├── ② MANAGER ÉVALUE (sous 24h)
    │     → ACCEPTE tel quel → verrouillé
    │     → CONTRE-OFFRE : "Je propose 5% car la tâche est plus simple que tu ne penses"
    │     → L'employé accepte ou ajuste (24h)
    │
    ├── ③ SYSTÈME VÉRIFIE
    │     → Le taux proposé est-il cohérent avec la complexité de la tâche ?
    │     → Le bonus total du mois ne dépasse-t-il pas le plafond prime SPI ?
    │     → L'employé a-t-il assez de "marge" en cas de malus cumulé ?
    │
    ├── ④ VERROUILLAGE NUMÉRIQUE
    │     → Offre signée numériquement : employé + manager
    │     → Montant bonus = montant malus (symétrie absolue)
    │     → Aucune modification sans avenant
    │
    └── ⑤ RÉSULTAT FIN DE TÂCHE
          → SI tâche validée (système + manager) → bonus crédité
          → SI tâche non validée → malus débité
          → Tout est traçé dans le solde bonus/malus de l'employé
```

---

# 14. CYCLE OFFRE → CONTRE-OFFRE → VERROUILLAGE

```
OFFRE_PERFORMANCE {
    id                      : UUID
    tache_id                : UUID → FK
    employe_id              : UUID → FK
    
    // ── PROPOSITION EMPLOYÉ ──
    bonus_propose_pct       : Decimal(5,2) — % de la prime SPI plafond
    bonus_propose_da        : Decimal(12,2) — Montant calculé
    delai_propose           : Date (nullable — si l'employé propose un délai différent)
    justification_employe   : Text
    date_proposition        : DateTime
    
    // ── CONTRE-OFFRE MANAGER (nullable) ──
    bonus_contre_offre_pct  : Decimal(5,2) (nullable)
    justification_manager   : Text (nullable)
    date_contre_offre       : DateTime (nullable)
    
    // ── ACCEPTATION ──
    bonus_final_pct         : Decimal(5,2) — Le taux accepté par les 2 parties
    bonus_final_da          : Decimal(12,2)
    malus_final_da          : Decimal(12,2) — = bonus_final_da (TOUJOURS)
    
    // ── VERROUILLAGE ──
    statut                  : Enum [PROPOSEE, CONTRE_OFFRE, ACCEPTEE, VERROUILLEE, EXECUTEE]
    date_verrouillage       : DateTime (nullable)
    signature_employe       : Boolean
    signature_manager       : Boolean
    
    // ── RÉSULTAT ──
    resultat                : Enum [EN_ATTENTE, BONUS_VERSE, MALUS_APPLIQUE, CONTESTEE] (nullable)
    montant_applique        : Decimal(12,2) (nullable) — Positif si bonus, négatif si malus
}
```

---

# 15. SYMÉTRIE : MÊME MONTANT BONUS = MÊME MONTANT MALUS

**RÈGLE ABSOLUE :** Le montant du bonus est EXACTEMENT égal au montant du malus. Si l'employé propose 5 000 DA de bonus → il risque 5 000 DA de malus. Pas de négociation séparée.

```
EXEMPLE :
    Employé : Prime SPI plafond = 40 000 DA
    Tâche A : bonus proposé 10% = 4 000 DA → malus si échec = 4 000 DA
    Tâche B : bonus proposé 5% = 2 000 DA → malus si échec = 2 000 DA
    Tâche C : bonus proposé 15% = 6 000 DA → malus si échec = 6 000 DA
    
    RÉSULTAT DU MOIS :
    Tâche A : livrée à temps, qualité validée → BONUS +4 000 DA ✅
    Tâche B : retard 4 jours, refusée → MALUS −2 000 DA ❌
    Tâche C : livrée en avance, excellente qualité → BONUS +6 000 DA ✅
    
    SOLDE BONUS/MALUS DU MOIS = +4 000 − 2 000 + 6 000 = +8 000 DA
    
    PAIE :
    Salaire base 80 000 + Prime SPI (selon score global) + Solde B/M +8 000
```

**Si solde négatif :** Le malus est **CRÉDITÉ** (non déduit du salaire base — JAMAIS). Il est reporté sur les bonus futurs. L'employé doit "rembourser" ses malus avant de toucher de nouveaux bonus.

---

# 16. CALCUL MENSUEL ET ACCUMULATION

```
SOLDE_EMPLOYE(mois) = 
    SOLDE_PRECEDENT 
    + Σ(bonus tâches validées du mois)
    − Σ(malus tâches non validées du mois)

SI SOLDE ≥ 0 → versement = SOLDE (plafonné à prime_spi_plafond × 1.10)
SI SOLDE < 0 → versement = 0 DA (malus reporté, déduit des futurs bonus)
                Le salaire BASE est INTOUCHÉ.
```

---

# PARTIE V — SOUS-PERFORMANCE & SORTIE

---

# 17. 2 MOIS CONSÉCUTIFS < 50% → PROCÉDURE DE SORTIE

| Mois | Score SPI | Action automatique |
|------|----------|-------------------|
| M1 < 50% | Première sous-performance | Avertissement écrit + plan de redressement 30j + entretien manager+RH |
| M2 < 50% (consécutif) | Deuxième sous-performance | Convocation entretien préalable (délai légal 5j ouvrés) + DG notifié |
| Post-entretien | Décision | Notification rupture (48h) OU maintien si DG décide expressément |
| Solde de tout compte | Dans délais légaux | Certificat travail + attestation CNAS + solde + dernier bulletin |

## 17.1. MAIS : les garde-fous s'appliquent TOUJOURS

Avant que le mois soit comptabilisé comme "< 50%" :

```
VÉRIFICATIONS OBLIGATOIRES :
    ✓ Score de fiabilité SPI ≥ 70% ? Si non → mois NON COMPTABILISÉ
    ✓ Contestation en cours ? Si oui → mois SUSPENDU
    ✓ Facteur externe non résolu ? Si oui → SPI ajusté puis réévalué
    ✓ Surcharge > 120% ? Si oui → alerte + rééquilibrage avant comptage
    ✓ Historique 6 mois > 85% avant cette chute ? Si oui → investigation avant action
    ✓ Entretien physique effectué ? Si non → action RH BLOQUÉE
```

---

# 18. SORTIE AVEC MOINDRE DÉGÂT FINANCIER

```
OBJECTIF : Si l'employé doit sortir, minimiser le coût pour l'entreprise.

COMMENT LE SYSTÈME Y CONTRIBUE :
    │
    ├── Documentation complète automatique
    │   → Chaque SPI mensuel est documenté avec preuves
    │   → Chaque avertissement est tracé et signé
    │   → Le plan de redressement est dans le système
    │   → L'entretien est documenté
    │   → Résultat : dossier de rupture SOLIDE juridiquement
    │
    ├── Rupture pour insuffisance professionnelle (pas pour faute)
    │   → Basée sur des KPI mesurables et documentés
    │   → Procédure légale respectée (Code du travail algérien)
    │   → Indemnités minimales (pas de faute = pas de majorations)
    │
    ├── Détection précoce
    │   → Le système alerte dès M1 < 50%
    │   → Le plan de redressement est lancé immédiatement
    │   → Si ça ne marche pas en 30 jours → on ne traîne pas
    │
    └── Pas de malus accumulé non traité
          → Si le solde B/M est négatif → il est apuré au solde de tout compte
          → Le STC = salaire dû + congés non pris − malus restant
          → Transparent, calculé par le système, signé par les 2 parties
```

---

# PARTIE VI — COMMERCIAUX : POLITIQUE CRM

---

# 21. COMMISSIONS PAR MODE DE PAIEMENT

| Mode paiement client | Taux commission | Logique |
|---------------------|----------------|---------|
| Cash 100% immédiat | 1.00% du montant | Risque zéro → taux max |
| Apport 75% + solde différé | 0.75% | Risque faible |
| Apport 50% + solde différé | 0.60% | Risque moyen |
| Apport 30% + solde différé | 0.40% | Risque élevé |
| Crédit bancaire | 0.20% | Risque max (délai) → taux min |

**Commission = due UNIQUEMENT sur montants ENCAISSÉS.** Pas de commission sur promesse.

## Répartition entre acteurs

| Acteur | Part | Condition |
|--------|------|----------|
| Commercial direct | 70% | Vente réalisée + suivi encaissement |
| Dir. ventes/Manager | 15% | Auto sur ventes équipe |
| Marketing | 10% | Si lead tracé CRM à son nom |
| ADV/Recouvrement | 2.5% | Suivi admin + encaissement |
| Téléopérateur | 2.5% | Si lead qualifié et tracé |

---

# 22. PALIERS MENSUELS

| Ventes/mois | Salaire | Commission | Statut RH |
|------------|---------|-----------|-----------|
| 0 — Mois 1 | Base seule | 0 | Avertissement + plan 30j |
| 0 — Mois 2 consécutif | Base seule | 0 | **LICENCIEMENT** |
| 1 vente M1 | Négocié | 0 | Avertissement |
| 2 ventes | Base + commission partielle | 50% | Sous-performance |
| 3 ventes | Base + commission | 75% | Correct |
| 4 ventes | Base + commission pleine | 100% | Objectif atteint |
| 5+ ventes | Négocié + commission pleine | 100% + bonus 10% | Excellence |

---

# PARTIE VII — PREUVES & JUSTIFICATION

---

# 24. ZÉRO PAIEMENT SANS PREUVE

**RÈGLE ABSOLUE :** Aucun bonus, aucune commission, aucune prime, aucune indemnité n'est versée sans preuve uploadée et validée dans le système.

| Type de paiement | Preuve minimum requise |
|-----------------|----------------------|
| Bonus tâche | Livrable uploadé (document/photo/fichier) + validation manager |
| Commission vente | Contrat signé + reçu paiement + copie CIN client dans CRM |
| Prime plan stratégique | Plan validé dans le système + signature numérique CEO |
| Indemnité mission | Ordre de mission validé + justificatifs (factures, billets, photos) |
| Heures supplémentaires | Pointage biométrique/géoloc + validation manager |

---

# 25. TYPES DE PREUVES ACCEPTÉES

| Type | Format | Validation IA | Validation humaine |
|------|--------|--------------|-------------------|
| Photo chantier | JPG/PNG (géolocalisée + horodatée) | Métadonnées EXIF vérifiées | Manager confirme pertinence |
| Document rapport | PDF/DOCX | Complétude, format, cohérence | Manager évalue fond |
| Fichier technique | DWG/XLS/tout format | Présence vérifiée | Spécialiste évalue |
| Capture écran | PNG | Horodatage vérifié | Manager confirme |
| Vidéo | MP4 (max 2 min) | Durée et géoloc vérifiées | Manager visionne |
| Scan facture/reçu | PDF/JPG | OCR extraction montant/date | Comptable rapproche |

---

# PARTIE VIII — TABLEAU DE BORD MOBILE

---

# 27. DASHBOARD EMPLOYÉ SUR TÉLÉPHONE

```
╔══════════════════════════════════════════════════════════════╗
║  📱 GFI — MON TABLEAU DE BORD — M. KAMEL HASSANI           ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  🎯 MON SPI CE MOIS : 78/100 (Standard ✅)                 ║
║  ├── C1 Exécution : 82/100                                  ║
║  ├── C2 Qualité   : 75/100                                  ║
║  ├── C3 Comportement : 80/100                               ║
║  └── C4 Métier    : 72/100                                  ║
║                                                              ║
║  💰 PRÉVISION PAIE :                                        ║
║  Base CNAS     : 80 000 DA                                  ║
║  Prime SPI est.: 33 600 DA (84% du plafond)                ║
║  Solde B/M     : +5 200 DA                                  ║
║  TOTAL ESTIMÉ  : 118 800 DA                                 ║
║                                                              ║
║  📋 MES TÂCHES (5 actives) :                                ║
║  🟢 Commander ciment AURÉA — 3j restants — Bonus: 3 200 DA ║
║  🟡 Rapport mensuel stock — 1j retard — Malus risqué       ║
║  🔵 Négocier prix acier — En cours — Bonus: 2 000 DA       ║
║  ⚪ Inventaire magasin — Pas commencé — 5j restants         ║
║  🟢 Vérifier BL fournisseur — Terminé, en validation       ║
║                                                              ║
║  📌 ACTIONS REQUISES :                                      ║
║  ⚠️ Contre-offre manager sur Tâche #3 — Répondre < 24h    ║
║  📸 Upload preuve Tâche #5 — Photo BL signé                ║
║                                                              ║
║  💡 PROPOSER UN PLAN → [+]                                  ║
║                                                              ║
║  [Voir détail] [Contester] [Historique]                     ║
╚══════════════════════════════════════════════════════════════╝
```

## 28. DASHBOARD MANAGER

```
╔══════════════════════════════════════════════════════════════╗
║  📱 GFI — DASHBOARD MANAGER — M. BENALI (Dept. Achats)     ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  👥 MON ÉQUIPE (8 personnes) :                              ║
║  SPI moyen équipe : 72/100                                  ║
║  🟢 4 employés > 70% (standard)                             ║
║  🟡 3 employés 51-70% (surveillance)                        ║
║  🔴 1 employé < 50% (M1 — plan de redressement lancé)      ║
║                                                              ║
║  📌 ACTIONS REQUISES (7) :                                  ║
║  ⚠️ Valider offre performance Kamel — Tâche ciment         ║
║  ⚠️ Évaluer qualité livrable Rachid — Rapport stock         ║
║  ⚠️ Contre-offre de Samira à traiter — Délai 24h           ║
║  ⚠️ Entretien RH M. Kaci (SPI < 50%) — Planifier          ║
║  📸 3 preuves en attente de validation                      ║
║                                                              ║
║  📊 PERFORMANCE ÉQUIPE :                                    ║
║  Tâches terminées ce mois : 23/35 (66%)                    ║
║  Tâches en retard : 4                                       ║
║  Budget consommé : 82%                                      ║
║                                                              ║
║  [Détail employé] [Assigner tâche] [Proposer plan]          ║
╚══════════════════════════════════════════════════════════════╝
```

---

# PARTIE IX — LIEN AVEC LES AUTRES MODULES GFI

---

# 31. LIEN SALAIRE → TRÉSORERIE → CENTRE DE COÛT

```
PAIE MENSUELLE CALCULÉE
    │
    ├── MOUVEMENT TRÉSORERIE :
    │   → Décaissement salaire = mouvement trésorerie RF1 (base déclarée)
    │   → Si prime non déclarée (RF2) = mouvement trésorerie RF2 séparé
    │
    ├── COMPTABILITÉ :
    │   → D:631000 (Salaires bruts) / C:421000 (Personnel)
    │   → D:635000 (CNAS patronale) / C:431000 (CNAS à payer)
    │
    ├── CENTRE DE COÛT :
    │   → Si employé 100% sur projet AURÉA :
    │     CC-ENT5-CHERAGA-MASSE-SAL += salaire total
    │   → Si employé 60% AURÉA + 40% IRENE :
    │     CC-ENT5-CHERAGA-MASSE-SAL += salaire × 60%
    │     CC-ENT2-5H-MASSE-SAL += salaire × 40%
    │
    ├── BUDGET :
    │   → Budget masse salariale projet AURÉA consommé += part
    │
    └── ASSOCIÉS (quote-parts) :
          → Charge AURÉA → Ahmed 60%, Mohamed 20%, Lyazid 20%
          → Charge IRENE → % projet IRENE
```

---

# 32. LIEN TÂCHES → PROJETS → BUDGETS

```
TÂCHE "Commander ciment AURÉA" VALIDÉE
    │
    ├── PROJET AURÉA : avancement tâche marqué 100%
    ├── PLAN STRATÉGIQUE "Livrer AURÉA Q4" : avancement recalculé
    ├── BON DE COMMANDE : BC généré si achat matériel
    ├── BUDGET : consommation budget projet mise à jour
    ├── CENTRE DE COÛT : CC-ENT5-CHERAGA-ACHATS impacté
    └── SPI employé : C1 mis à jour (tâche livrée à temps)
```

---

# PARTIE X — MODÈLE DE DONNÉES & SCÉNARIOS

---

# 34. TABLES SQL PRINCIPALES

```sql
CREATE TABLE employe (
    id UUID PRIMARY KEY,
    nom VARCHAR(100) NOT NULL,
    prenom VARCHAR(100) NOT NULL,
    salaire_base_mensuel DECIMAL(12,2) NOT NULL,
    prime_spi_plafond DECIMAL(12,2) NOT NULL DEFAULT 0,
    avenant_spi_signe BOOLEAN NOT NULL DEFAULT false,
    poste_id UUID REFERENCES poste(id),
    manager_id UUID REFERENCES employe(id),
    entite_juridique_id UUID REFERENCES entite_juridique(id),
    solde_bonus_malus DECIMAL(12,2) NOT NULL DEFAULT 0,
    mois_consecutifs_sous_50 INTEGER NOT NULL DEFAULT 0,
    mois_consecutifs_sous_70 INTEGER NOT NULL DEFAULT 0,
    statut_rh VARCHAR(30) NOT NULL DEFAULT 'ACTIF'
);

CREATE TABLE plan_strategique (
    id UUID PRIMARY KEY,
    proposeur_id UUID NOT NULL REFERENCES employe(id),
    titre VARCHAR(200) NOT NULL,
    description TEXT NOT NULL CHECK (length(description) >= 100),
    statut VARCHAR(30) NOT NULL DEFAULT 'SOUMIS',
    valideur_id UUID REFERENCES employe(id),
    prime_versee BOOLEAN DEFAULT false,
    montant_prime DECIMAL(12,2),
    projet_id UUID REFERENCES projet(id),
    centre_cout_id UUID REFERENCES centre_cout(id)
);

CREATE TABLE tache (
    id UUID PRIMARY KEY,
    plan_strategique_id UUID REFERENCES plan_strategique(id),
    assignee_id UUID NOT NULL REFERENCES employe(id),
    titre VARCHAR(300) NOT NULL,
    date_fin_prevue DATE NOT NULL,
    date_fin_reelle DATE,
    priorite VARCHAR(20) NOT NULL DEFAULT 'NORMALE',
    statut VARCHAR(30) NOT NULL DEFAULT 'ASSIGNEE',
    score_execution DECIMAL(5,2),
    score_qualite DECIMAL(5,2),
    score_global DECIMAL(5,2),
    projet_id UUID REFERENCES projet(id),
    centre_cout_id UUID REFERENCES centre_cout(id)
);

CREATE TABLE offre_performance (
    id UUID PRIMARY KEY,
    tache_id UUID NOT NULL REFERENCES tache(id),
    employe_id UUID NOT NULL REFERENCES employe(id),
    bonus_propose_pct DECIMAL(5,2) NOT NULL,
    bonus_final_pct DECIMAL(5,2),
    bonus_final_da DECIMAL(12,2),
    malus_final_da DECIMAL(12,2), -- = bonus_final_da TOUJOURS
    statut VARCHAR(30) NOT NULL DEFAULT 'PROPOSEE',
    resultat VARCHAR(30), -- BONUS_VERSE, MALUS_APPLIQUE, CONTESTEE
    montant_applique DECIMAL(12,2),
    CONSTRAINT chk_symetrie CHECK (malus_final_da = bonus_final_da)
);

CREATE TABLE spi_mensuel (
    id UUID PRIMARY KEY,
    employe_id UUID NOT NULL REFERENCES employe(id),
    mois VARCHAR(7) NOT NULL, -- "2026-03"
    c1_execution DECIMAL(5,2) NOT NULL,
    c2_qualite DECIMAL(5,2) NOT NULL,
    c3_comportement DECIMAL(5,2) NOT NULL,
    c4_metier DECIMAL(5,2) NOT NULL,
    w1 DECIMAL(5,2) NOT NULL, -- Poids adapté au poste
    w2 DECIMAL(5,2) NOT NULL,
    w3 DECIMAL(5,2) NOT NULL,
    w4 DECIMAL(5,2) NOT NULL,
    score_spi DECIMAL(5,2) GENERATED ALWAYS AS (
        (c1_execution * w1 + c2_qualite * w2 + c3_comportement * w3 + c4_metier * w4) / 100
    ) STORED,
    fiabilite_score DECIMAL(5,2) NOT NULL,
    est_confirme BOOLEAN DEFAULT false,
    prime_calculee DECIMAL(12,2),
    malus_calcule DECIMAL(12,2),
    solde_bm_mois DECIMAL(12,2),
    UNIQUE(employe_id, mois),
    CONSTRAINT chk_poids CHECK (w1 + w2 + w3 + w4 = 100)
);

-- Trigger : après chaque SPI mensuel, vérifier compteur sous-performance
CREATE OR REPLACE FUNCTION check_sous_performance() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.score_spi < 50 AND NEW.fiabilite_score >= 70 AND NEW.est_confirme = true THEN
        UPDATE employe SET mois_consecutifs_sous_50 = mois_consecutifs_sous_50 + 1
        WHERE id = NEW.employe_id;
    ELSE
        UPDATE employe SET mois_consecutifs_sous_50 = 0
        WHERE id = NEW.employe_id;
    END IF;
    
    -- Alerte si 2 mois consécutifs
    IF (SELECT mois_consecutifs_sous_50 FROM employe WHERE id = NEW.employe_id) >= 2 THEN
        INSERT INTO alerte (type, employe_id, message, severite)
        VALUES ('RUPTURE_SPI', NEW.employe_id, 
                '2 mois consécutifs SPI < 50% — Procédure de rupture à initier', 'CRITIQUE');
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

---

# 35. SCÉNARIOS RÉALISTES

## Scénario 1 — Employé performant qui propose un plan

```
M. KAMEL (acheteur, projet AURÉA, salaire base 80K, prime plafond 40K)

MOIS DE MARS 2026 :

① Kamel propose un plan : "Négocier remise volume 15% avec 3 cimentiers"
   → Système analyse : pertinent, faisable, pas de doublon
   → CEO valide → PRIME PLAN 5% = (80K + 40K) × 5% = 6 000 DA ✅

② Plan dispatché en 3 tâches :
   T1: Contacter cimentier A — bonus proposé 8% = 3 200 DA
   T2: Contacter cimentier B — bonus proposé 5% = 2 000 DA
   T3: Rapport comparatif — bonus proposé 10% = 4 000 DA

③ Résultats :
   T1: Livré à temps, remise obtenue 12% → BONUS +3 200 DA
   T2: Livré 2j retard, remise obtenue 8% → score C1=75, BONUS PARTIEL +1 500 DA
   T3: Livré en avance, rapport excellent → BONUS +4 000 DA + précocité

④ SPI mensuel : C1=88, C2=90, C3=95, C4=82 → SPI = 88/100

⑤ PAIE :
   Base CNAS      :  80 000 DA
   Prime SPI      :  42 000 DA (105% × 40K)
   Solde B/M      :  +8 700 DA (3200 + 1500 + 4000)
   Prime plan     :   6 000 DA
   TOTAL          : 136 700 DA

⑥ CENTRE DE COÛT :
   CC-ENT5-CHERAGA-MASSE-SAL += 136 700 DA
   Quote-parts : Ahmed 60%=82 020, Mohamed 20%=27 340, Lyazid 20%=27 340
```

## Scénario 2 — Employé en sous-performance → sortie propre

```
M. KACI (ouvrier chantier, SPI en chute)

JANVIER 2026 : SPI = 45/100 (< 50%)
    → Fiabilité score : 85% → CONFIRMÉ
    → Avertissement écrit + plan de redressement 30j
    → Entretien manager + RH documenté
    → Plan : 5 tâches à livrer en février avec deadlines claires

FÉVRIER 2026 : SPI = 38/100 (< 50%, 2ème mois consécutif)
    → Fiabilité score : 90% → CONFIRMÉ
    → Vérification garde-fous :
      ✓ Pas de contestation en cours
      ✓ Pas de facteur externe non résolu
      ✓ Charge normale (pas de surcharge)
      ✓ Historique : SPI moyen 55% sur 6 mois (pas d'excellence antérieure)
      ✓ Entretien M1 effectué et documenté
    → PROCÉDURE DE RUPTURE ENCLENCHÉE
    → Convocation entretien préalable (délai légal 5j)

ENTRETIEN : Kaci + Manager + RH + délégué du personnel
    → Dossier constitué par le système : 2 mois SPI, preuves, avertissement, plan
    → Décision : RUPTURE pour insuffisance professionnelle

SOLDE DE TOUT COMPTE :
    → Salaire dû février : 80 000 DA (base intangible)
    → Congés non pris : 5 jours × 3 636 DA/jour = 18 180 DA
    → Solde B/M : −8 000 DA (malus accumulé) → déduit
    → Prime SPI février : 0 DA (SPI < 50%)
    → TOTAL STC : 80 000 + 18 180 − 8 000 = 90 180 DA
    → Certificat travail + attestation CNAS + bulletin final
    → Dégât financier entreprise = MINIMAL (pas de faute, pas de majorations)
```

## Scénario 3 — Bon employé protégé par le système

```
Mme SAMIRA (comptable, 12 mois SPI > 85%)

MARS 2026 : SPI = 42/100 (chute brutale)
    → Système détecte : historique 12 mois excellence → ALERTE PROTECTION
    → Fiabilité score : 62% (< 70%) → MARQUÉ "À CONFIRMER"
    
    POURQUOI fiabilité basse ?
    → 3 tâches sur 5 avaient des dépendances bloquées par un collègue
    → Surcharge détectée : 135% de charge théorique
    → Facteur externe : changement de logiciel comptable en cours
    
    RÉSULTAT :
    → SPI NON COMPTABILISÉ comme mois de sous-performance
    → Manager DOIT investiguer sous 5 jours
    → Charge rééquilibrée
    → Tâches bloquées réassignées
    → Samira reçoit un SPI ajusté : 71/100 (sur tâches réellement contrôlées)
    → AUCUNE action RH. Samira est protégée.
    → Le système a DÉTECTÉ que la chute n'était pas sa faute.
```

---

# 36. API ENDPOINTS

```
// Planification
POST   /api/v1/plans                        → Proposer un plan
GET    /api/v1/plans/{id}                   → Détail plan
PUT    /api/v1/plans/{id}/valider           → CEO valide
PUT    /api/v1/plans/{id}/decliner          → CEO décline (justification obligatoire)

// Tâches
GET    /api/v1/taches/mes-taches            → Mes tâches (mobile)
POST   /api/v1/taches/{id}/offre            → Proposer bonus/malus
PUT    /api/v1/taches/{id}/livrer           → Marquer livrée + upload preuve
PUT    /api/v1/taches/{id}/valider          → Manager valide

// SPI
GET    /api/v1/spi/mon-score                → Mon SPI actuel (mobile)
GET    /api/v1/spi/historique               → Historique mes SPI
GET    /api/v1/spi/equipe                   → SPI de mon équipe (manager)
POST   /api/v1/spi/{mois}/contester         → Contester mon SPI

// Paie
GET    /api/v1/paie/ma-prevision            → Prévision paie (mobile)
GET    /api/v1/paie/{mois}/bulletin         → Bulletin de paie PDF
GET    /api/v1/paie/solde-bm               → Mon solde bonus/malus

// Preuves
POST   /api/v1/preuves/upload              → Upload preuve (photo/doc)
GET    /api/v1/preuves/en-attente          → Preuves en attente validation

// Dashboard mobile
GET    /api/v1/dashboard/employe            → Dashboard employé complet
GET    /api/v1/dashboard/manager            → Dashboard manager
GET    /api/v1/dashboard/daf               → Dashboard DAF/CEO
GET    /api/v1/notifications               → Mes notifications

// CRM / Commissions
GET    /api/v1/crm/mes-ventes              → Mes ventes du mois
GET    /api/v1/crm/commission-prevue       → Commission estimée
GET    /api/v1/crm/palier                  → Mon palier actuel
```

---

**FIN DU DOCUMENT**

*Ce document couvre l'intégralité du module Planification × Salaire × Performance du GFI v7.0. Du contrat CNAS qui déclenche tout, à la proposition de plan stratégique par n'importe quel employé, au système bonus/malus symétrique proposé par l'employé lui-même, à la protection intelligente des bons employés, à la sortie propre des sous-performants avec moindre dégât financier.*

*Tout est mesuré, mais mesuré INTELLIGEMMENT. Tout est justifié avec preuves. Tout est sur le téléphone de chaque employé. Tout est relié aux projets, aux centres de coût, à la comptabilité, aux associés.*

*Les gens capables gagnent plus. Les gens qui ne travaillent pas sortent proprement. Le système ne punit pas l'initiative. Le système protège les bons employés des mauvaises mesures.*
