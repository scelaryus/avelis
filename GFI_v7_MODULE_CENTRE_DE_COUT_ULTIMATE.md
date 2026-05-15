# GFI SYSTÈME v7.0 — MODULE CENTRE DE COÛT

## SPÉCIFICATION ULTRA-DÉTAILLÉE POUR L'IT

**Groupe Dendani** — Bab Ezzouar, Alger  
**Classification :** ULTRA-CONFIDENTIEL  
**Version :** 7.0-CC-DEFINITIVE  
**Date :** Mars 2026  
**Auteur :** Ahmed Dendani — DAF  
**Destinataire :** Équipe IT développement  

---

> **AVERTISSEMENT POUR L'IT :** Ce document est la SEULE référence pour le module Centre de Coût. Chaque ligne, chaque règle, chaque formule doit être implémentée à la lettre. Le système ne devine JAMAIS. Il calcule, il vérifie, il bloque, il demande. Si vous avez un doute → relisez ce document. Si le doute persiste → demandez à Ahmed. Ne codez JAMAIS une supposition.

---

# TABLE DES MATIÈRES

**BLOC A — FONDATIONS : COMPRENDRE LA RÉALITÉ**
1. [Pourquoi le Centre de Coût est critique](#1-pourquoi-le-centre-de-coût-est-critique)
2. [La réalité du Groupe Dendani que le CC doit refléter](#2-la-réalité-du-groupe)
3. [La distinction FATALE : % entreprise ≠ % projet](#3-distinction-fatale)
4. [Les alias à résoudre — Le système détecte seul](#4-alias)

**BLOC B — ARCHITECTURE DU CENTRE DE COÛT**
5. [Hiérarchie à 6 niveaux](#5-hiérarchie)
6. [Arbre complet des centres de coût](#6-arbre-complet)
7. [Structure de données — Table centre_cout](#7-structure-données)
8. [Règles de nommage et codification](#8-codification)

**BLOC C — ALIMENTATION : QUI NOURRIT LE CC ET COMMENT**
9. [Sources d'alimentation — 16 types de flux](#9-sources-alimentation)
10. [Encaissements → CC : rattachement lot EDD](#10-encaissements)
11. [Décaissements directs projet → CC](#11-décaissements-directs)
12. [Charges partagées → CC : ventilation intelligente](#12-charges-partagées)
13. [CFF → CC : imputation selon % ENTREPRISE émettrice](#13-cff)
14. [Inter-projets → CC : flux croisés caisse commune](#14-inter-projets)
15. [Achats/Stock → CC : consommation matières](#15-achats-stock)
16. [Capital associés / Retraits nature → CC](#16-capital-associés)
17. [Véhicules : achat → immatriculation → cession GACEB → déduction situation](#17-véhicules)
18. [Bureau BBZ → CC : charge commune groupe](#18-bureau-bbz)
19. [GACEB 120M : avance nature AMENFORT → CC EDEN](#19-gaceb-120m)

**BLOC D — DOUBLE POURCENTAGE : ENTREPRISE vs PROJET**
20. [Matrice complète % entreprise × % projet × associé](#20-matrice-complète)
21. [Règle CFF : TOUJOURS % entreprise émettrice](#21-règle-cff)
22. [Règle bénéfices : TOUJOURS % projet](#22-règle-bénéfices)
23. [Règle charges directes projet : % projet](#23-règle-charges)
24. [Règle charges société : % entreprise](#24-règle-société)
25. [Cas Dendani Promotion : 25% entreprise mais 60/20/20/0 projet](#25-cas-dendani-promo)
26. [Cas Yamina : 0% dans 5 entreprises, 25% dans 2, 0% projets spécifiques](#26-cas-yamina)

**BLOC E — COMPTABILITÉ DANS LE CC : RF1/RF2/RF3/RF4**
27. [RF2 dans le CC — OUI, toujours](#27-rf2-dans-cc)
28. [RF3 dans le CC — OUI + CFF associé](#28-rf3-dans-cc)
29. [Double vue CC : officiel vs interne](#29-double-vue)
30. [Compta officielle vs CC : ce qui entre où](#30-compta-vs-cc)

**BLOC F — CONSOLIDATION MULTI-AXES**
31. [Consolidation ascendante : sous-catégorie → catégorie → projet → société → groupe](#31-consolidation-ascendante)
32. [Consolidation par associé : quote-part nette](#32-consolidation-associé)
33. [Consolidation par RF](#33-consolidation-rf)
34. [Consolidation inter-projets : traçabilité des flux](#34-consolidation-inter-projets)
35. [Consolidation temporelle : mensuel / trimestriel / annuel / cumulé](#35-consolidation-temporelle)

**BLOC G — MOTEUR INTELLIGENT DE DÉTECTION**
36. [Détection automatique du CC depuis la base 400 Go](#36-détection-auto)
37. [Résolution des alias : projets, associés, fournisseurs](#37-résolution-alias)
38. [Détection des flux inter-projets (caisse commune)](#38-détection-flux)
39. [Détection des anomalies et incohérences](#39-détection-anomalies)
40. [Formulaires de réclamation quand info manquante](#40-formulaires)

**BLOC H — VÉRIFICATION MULTI-NIVEAUX**
41. [10 niveaux de vérification](#41-vérification)
42. [Contrôles automatiques quotidiens](#42-contrôles-quotidiens)
43. [Rapprochement croisé CC ↔ Trésorerie ↔ Comptabilité](#43-rapprochement)
44. [Test Actif = Passif (écart = 0 DA)](#44-actif-passif)
45. [Les 7 tests décisifs d'Ahmed](#45-tests-décisifs)

**BLOC I — RATIOS, REPORTING, TABLEAUX DE BORD**
46. [Ratios calculés automatiquement par CC](#46-ratios)
47. [Tableau de bord DAF — Vue Centre de Coût](#47-dashboard)
48. [Rapports automatiques périodiques](#48-rapports)

**BLOC J — SCÉNARIOS RÉALISTES COMPLETS**
49. [Scénarios de bout en bout](#49-scénarios)

**BLOC K — MODÈLE DE DONNÉES & API**
50. [Tables SQL complètes](#50-tables-sql)
51. [API Endpoints](#51-api)
52. [Index de performance](#52-index)

---

# BLOC A — FONDATIONS : COMPRENDRE LA RÉALITÉ

---

# 1. POURQUOI LE CENTRE DE COÛT EST CRITIQUE

Le Centre de Coût (CC) est le **miroir exact de la réalité financière** du Groupe Dendani. Si le CC est faux, TOUT est faux : les comptes associés sont faux, les rentabilités projet sont fausses, les décisions sont prises sur des mensonges.

Le CC doit répondre, à tout instant, à ces questions :

- **Par projet :** Combien a coûté EDEN ? Combien a rapporté EDEN ? Quelle est la marge réelle ?
- **Par entreprise :** Quel est le résultat réel de SARL Avelis Promotion ? Officiel ET interne ?
- **Par associé :** Combien revient à Ahmed sur le projet CHERAGA ? Après CFF ? Après retraits nature ?
- **Par RF :** Combien de l'argent est déclaré (RF1) ? Combien est caché (RF2) ? Combien de CFF (RF3) ?
- **Par nature :** Combien de masse salariale sur EDEN ? Combien de sous-traitance ? Combien de terrains ?
- **Par période :** Quel était l'état au 31/12/2025 ? Quelle est l'évolution mois par mois ?
- **Inter-projets :** Combien EDEN a-t-il prêté à JASMINS ? Ce prêt est-il remboursé ?

Si le CC ne peut pas répondre à UNE SEULE de ces questions avec certitude → **le CC est incomplet**.

---

# 2. LA RÉALITÉ DU GROUPE QUE LE CC DOIT REFLÉTER

## 2.1. Les 7 entreprises

| Code | Entreprise | Forme | Statut futur |
|------|-----------|-------|-------------|
| ENT-1 | ETS Dendani Khadidja | Établissement | À fermer |
| ENT-2 | SARL Dendani Promotion | SARL | À développer |
| ENT-3 | SARL DBPI Immobilier | SARL | À fermer après transfert siège |
| ENT-4 | SARL Omega Construction | SARL | À fermer |
| ENT-5 | SARL Avelis Promotion | SARL | À développer |
| ENT-6 | SARL Senimar | SARL | À développer |
| ENT-7 | EURL Bimha Construction | EURL | À développer |

## 2.2. Les 4 associés avec TOUS leurs alias

| Associé complet | Alias connus dans les écritures | Code GFI |
|----------------|-------------------------------|---------|
| **Ahmed Dendani** | HMED, A. DENDANI, AHMED D., DENDANI A. | ASS-AHMED |
| **Mohamed Dendani** | MOUH, M. DENDANI, MOHAMED D., DENDANI M. | ASS-MOHAMED |
| **Lyazid Bouabdellah** | YAZID, L. BOUABDELLAH, LYAZID B., BOUABDELLAH L. | ASS-LYAZID |
| **Yamina Ait Benamara** | YAMINA, Y. AIT BENAMARA, YAMINA A.B. | ASS-YAMINA |

**Le système DOIT résoudre ces alias automatiquement.** Quand il trouve "MOUH" dans un libellé comptable → c'est Mohamed Dendani.

## 2.3. Les projets avec TOUS leurs alias

| Code GFI | Nom officiel | Alias dans les écritures | Entreprise porteuse |
|---------|-------------|------------------------|-------------------|
| PROJ-EDEN | EDEN | EDEN, Projet 1, P1 | ENT-1 (ETS DK) |
| PROJ-JASMINS | LES JASMINS | SAHEL, JASMINS, Projet 2 | ENT-1 (ETS DK) |
| PROJ-OPERA | JARDIN DE L'OPÉRA | OPERA, JDO, JARDIN OPERA | ENT-2 (Dendani Promo) |
| PROJ-5H | 05 HECTARE (IRÈNE) | IRENE, 5 HECTARE, 5H, BOUMERDES | ENT-2 (Dendani Promo) |
| PROJ-EDRIVE | AVELIS DRIVE | E-DRIVE, AVELIS DR | ENT-2 (Dendani Promo) + ENT-7 (Bimha) |
| PROJ-ALLOMAISON | ALLO MAISON | AM, ALLO M | ENT-2 (Dendani Promo) |
| PROJ-LYS | LES LYS | 02 HECTARE, 02H, LYS | ENT-3 (DBPI) |
| PROJ-MAGNOLIA | LES MAGNOLIA | MAGNOLIA | ENT-4 (Omega) |
| PROJ-CHERAGA | CHERAGA (AURÉA) | AUREA, CHERAGA, CHE | ENT-5 (Avelis) |
| PROJ-ACHOUR | EL ACHOUR (ASTERIA) | ASTERIA, ACHOUR, EL A | ENT-6 (Senimar) |
| PROJ-PFSB | PFSB | PFSB | ENT-7 (Bimha) |

**⚠ CAS CRITIQUES D'ALIAS :**
- "LES LYS" et "02 HECTARE" = **MÊME PROJET** → le CC doit les fusionner en UN SEUL total
- "LES JASMINS" et "SAHEL" = **MÊME PROJET**
- "CHERAGA" et "AURÉA" = **MÊME PROJET**
- "EL ACHOUR" et "ASTERIA" = **MÊME PROJET**
- "05 HECTARE" et "IRÈNE" = **MÊME PROJET**

Si le système crée 2 CC séparés pour le même projet sous 2 alias → **ERREUR FATALE**.

## 2.4. Les entreprises tierces CFF

| Entreprise tierce | Rôle | CFF vers | Associés |
|------------------|------|---------|---------|
| SARL AMENFORT Béton | Émetteur factures fictives RF3 | ENT-1 (ETS DK) pour EDEN | Ahmed/Mohamed/Lyazid (PAS Yamina) |
| BAYTI / ALLO MAISON | Émetteur factures fictives RF3 | ENT-1 (ETS DK) pour JASMINS | À extraire de la base |

## 2.5. Le sous-traitant clé : GACEB Abderazak

GACEB intervient sur quasi tous les projets. Son mécanisme spécial :
- **120M DA matériel AMENFORT** = avance nature, déduite des situations EDEN
- **Véhicules cédés** = Range Rover Ahmed (4M), Passat Lyazid (6.5M), autres à extraire
- **Appartements JASMINS** = avance sur fourniture béton JARDIN DE L'OPÉRA
- **Aménagement oued JASMINS** = 20M DA travaux

Tout cela doit être dans le CC.

---

# 3. LA DISTINCTION FATALE : % ENTREPRISE ≠ % PROJET

## 3.1. Le piège que le système ne doit JAMAIS confondre

Dans le Groupe Dendani, les associés ont des **pourcentages DIFFÉRENTS** selon qu'on parle de l'entreprise ou du projet.

**Exemple CRITIQUE — SARL Dendani Promotion (ENT-2) :**

| | % ENTREPRISE (ENT-2) | % PROJET 05 Hectare | % PROJET Avelis Drive | % PROJET Allo Maison | % PROJET Jardin Opéra |
|---|---|---|---|---|---|
| Ahmed | **25%** | **60%** | **60%** | **60%** | À déterminer |
| Mohamed | **25%** | **20%** | **20%** | **20%** | À déterminer |
| Lyazid | **25%** | **20%** | **20%** | **20%** | À déterminer |
| Yamina | **25%** | **0%** | **0%** | **0%** | À déterminer |

**Ce que ça signifie pour le CC :**

| Type d'opération | Quel % utiliser | Exemple |
|-----------------|----------------|---------|
| **CFF** (coût fiscal fictif) | % ENTREPRISE ÉMETTRICE | Si Dendani Promo émet facture RF3 → Ahmed 25%, Yamina 25% |
| **Distribution bénéfices** d'un projet | % PROJET | Bénéfice 05 Hectare → Ahmed 60%, Yamina 0% |
| **Charges directes** d'un projet | % PROJET | Achat ciment 05 Hectare → Ahmed 60%, Yamina 0% |
| **Charges société** (siège, admin) | % ENTREPRISE | Loyer siège Dendani Promo → Ahmed 25%, Yamina 25% |
| **Charges partagées ventilées sur projet** | % PROJET du projet cible | Masse salariale ventilée sur 05H → Ahmed 60% |

**⚠ TEST DÉCISIF #2 D'AHMED :** "Ahmed CFF dans Dendani Promo = ?" → Réponse : **25%** (pas 60%). Si le système répond 60% → **REJET TOTAL**.

**⚠ TEST DÉCISIF #1 D'AHMED :** "Yamina CFF dans DBPI = ?" → Réponse : **0 DA**. Yamina est à 0% dans DBPI. Si le système lui impute du CFF → **REJET TOTAL**.

## 3.2. Matrice complète — CHAQUE combinaison entreprise × projet × associé

### ENT-1 — ETS Dendani Khadidja

| Associé | % Entreprise | % EDEN | % JASMINS |
|---------|-------------|--------|-----------|
| Ahmed | 25% | 25%* | 34% |
| Mohamed | 25% | 25%* | 33% |
| Lyazid | 25% | 25%* | 33% |
| Yamina | 25% | 25%* | 0%** |

*% EDEN = même que % entreprise (25/25/25/25)
**Yamina à 0% sur JASMINS selon nomenclature (pas de % JASMINS affiché pour elle)

**CFF AMENFORT → EDEN :** AMENFORT émet RF3 vers ETS DK. Associés AMENFORT = Ahmed/Mohamed/Lyazid (~33% chacun). **Yamina ne paie JAMAIS le CFF AMENFORT** car elle n'était pas dans AMENFORT.

### ENT-2 — SARL Dendani Promotion

| Associé | % Entreprise | % Jardin Opéra | % 05 Hectare | % Avelis Drive | % Allo Maison |
|---------|-------------|---------------|-------------|--------------|-------------|
| Ahmed | 25% | À extraire* | 60% | 60% | 60% |
| Mohamed | 25% | À extraire* | 20% | 20% | 20% |
| Lyazid | 25% | À extraire* | 20% | 20% | 20% |
| Yamina | 25% | À extraire* | 0% | 0% | 0% |

*% Jardin de l'Opéra non spécifié dans la nomenclature → formulaire si absent dans la base

### ENT-3 — SARL DBPI Immobilier

| Associé | % Entreprise | % Les Lys | % DG (Direction) |
|---------|-------------|----------|----------------|
| Ahmed | 60% | 60%* | 60% |
| Mohamed | 20% | 20%* | 20% |
| Lyazid | 20% | 20%* | 20% |
| Yamina | 0% | 0% | 0% |

*% LES LYS = même que % entreprise

### ENT-4 — SARL Omega Construction

| Associé | % Entreprise | % Magnolia |
|---------|-------------|-----------|
| Ahmed | 60% | 60% |
| Mohamed | 20% | 20% |
| Lyazid | 20% | 20% |
| Yamina | 0% | 0% |

### ENT-5 — SARL Avelis Promotion

| Associé | % Entreprise | % Cheraga (Auréa) |
|---------|-------------|-------------------|
| Ahmed | 60% | 60% |
| Mohamed | 20% | 20% |
| Lyazid | 20% | 20% |
| Yamina | 0% | 0% |

### ENT-6 — SARL Senimar

| Associé | % Entreprise | % El Achour (Asteria) |
|---------|-------------|---------------------|
| Ahmed | 60% | 60% |
| Mohamed | 20% | 20% |
| Lyazid | 20% | 20% |
| Yamina | 0% | 0% |

### ENT-7 — EURL Bimha Construction

| Associé | % Entreprise | % Avelis Drive | % PFSB |
|---------|-------------|--------------|--------|
| Ahmed | 60% | 60% | 60% |
| Mohamed | 20% | 20% | 20% |
| Lyazid | 20% | 20% | 20% |
| Yamina | 0% | 0% | 0% |

**⚠ CAS PROJET MULTI-ENTREPRISE — AVELIS DRIVE :**
Avelis Drive est porté par ENT-2 (Dendani Promo) ET ENT-7 (Bimha). Le CC doit gérer les deux rattachements. Les charges de Bimha sur Avelis Drive → % Bimha (60/20/20/0). Les charges de Dendani Promo sur Avelis Drive → % projet dans Dendani Promo (60/20/20/0 selon nomenclature). Les charges société de Dendani Promo ventilées sur Avelis Drive → d'abord ventilées par clé, PUIS distribuées aux associés au % projet.

---

# 4. ALIAS — LE SYSTÈME DÉTECTE SEUL

## 4.1. Table de résolution des alias

Le système scanne la base 400 Go et résout automatiquement les alias. La table suivante est la référence :

```
TABLE_ALIAS {
    id              : UUID
    entite_type     : Enum [PROJET, ASSOCIE, ENTREPRISE, FOURNISSEUR, SOUS_TRAITANT]
    entite_id       : UUID → FK vers l'entité canonique
    alias           : String (le nom tel qu'il apparaît dans les écritures)
    source          : String (fichier/cellule où trouvé)
    confiance       : Decimal (0-100%)
    valide_par      : UUID (nullable — validation humaine)
}
```

## 4.2. Comment le système détecte les alias

```
ALIAS PROJET :
    → Même terrain/adresse dans différents libellés
    → Même numéro de parcelle dans les actes
    → Comptes 580 (virements internes) entre les 2 alias
    → Même fournisseur/sous-traitant affecté aux 2

ALIAS ASSOCIÉ :
    → Noms similaires (distance Levenshtein < 3)
    → Même compte 455 avec libellés différents
    → Même NIN/CIN si disponible

ALIAS ENTREPRISE :
    → Même NIF dans des libellés différents
    → Même RC dans des documents différents
```

**RÈGLE ABSOLUE :** Si le système trouve 2 alias qui pointent vers la même entité → il FUSIONNE les totaux CC. Il ne crée JAMAIS 2 CC séparés.

---

# BLOC B — ARCHITECTURE DU CENTRE DE COÛT

---

# 5. HIÉRARCHIE À 6 NIVEAUX

```
NIVEAU 0 : GROUPE DENDANI (1 seul)
    │
    ├── NIVEAU 1 : ENTREPRISE (7 entreprises)
    │     │
    │     ├── NIVEAU 2 : PROJET ou FONCTION
    │     │     │  Ex: CC-ENT1-EDEN (projet EDEN dans ETS DK)
    │     │     │  Ex: CC-ENT2-SIEGE (fonction siège Dendani Promo)
    │     │     │  Ex: CC-ENT1-CFF-AMENFORT (CFF venant d'AMENFORT)
    │     │     │
    │     │     ├── NIVEAU 3 : CATÉGORIE DE COÛT
    │     │     │     │  Ex: CC-ENT1-EDEN-TERRAIN
    │     │     │     │  Ex: CC-ENT1-EDEN-CONSTRUCTION
    │     │     │     │  Ex: CC-ENT1-EDEN-VENTES
    │     │     │     │  Ex: CC-ENT1-EDEN-ASSOC (prélèvements associés)
    │     │     │     │
    │     │     │     └── NIVEAU 4 : SOUS-CATÉGORIE
    │     │     │           │  Ex: CC-ENT1-EDEN-CONSTRUCTION-GACEB
    │     │     │           │  Ex: CC-ENT1-EDEN-CONSTRUCTION-GROS-OEUVRE
    │     │     │           │  Ex: CC-ENT1-EDEN-ASSOC-AHMED (retraits Ahmed)
    │     │     │           │
    │     │     │           └── NIVEAU 5 : DÉTAIL (optionnel)
    │     │     │                 Ex: CC-ENT1-EDEN-CONSTRUCTION-GACEB-SIT01
    │     │     │                 Ex: CC-ENT1-EDEN-ASSOC-AHMED-F3 (appart F3)
    │     │     │
    │     │     └── NIVEAU 2 : CC-INTER-PROJETS (flux entre projets)
    │     │
    │     └── NIVEAU 1 : CC-ASSOCIES (vision transversale par associé)
    │           ├── CC-ASS-AHMED
    │           ├── CC-ASS-MOHAMED
    │           ├── CC-ASS-LYAZID
    │           └── CC-ASS-YAMINA
    │
    └── NIVEAU 1 : CC-INTER-ENTREPRISES (flux entre sociétés du groupe)
```

---

# 6. ARBRE COMPLET DES CENTRES DE COÛT

## 6.1. ENT-1 — ETS Dendani Khadidja

```
CC-ENT1                                          ETS DENDANI KHADIDJA (consolidé)
├── CC-ENT1-EDEN                                 PROJET EDEN (consolidé)
│   ├── CC-ENT1-EDEN-TERRAIN                     Acquisition terrain (~250M)
│   │   ├── CC-ENT1-EDEN-TERRAIN-ACHAT           Prix terrain
│   │   └── CC-ENT1-EDEN-TERRAIN-NOTAIRE         Frais notaire
│   │
│   ├── CC-ENT1-EDEN-CONSTRUCTION                Construction (consolidé)
│   │   ├── CC-ENT1-EDEN-CONSTR-GACEB            Sous-traitance GACEB
│   │   │   ├── CC-ENT1-EDEN-CONSTR-GACEB-SIT    Situations de travaux
│   │   │   ├── CC-ENT1-EDEN-CONSTR-GACEB-AV120M Avance matériel 120M AMENFORT
│   │   │   └── CC-ENT1-EDEN-CONSTR-GACEB-VEH    Véhicules cédés à GACEB
│   │   ├── CC-ENT1-EDEN-CONSTR-AUTRES-ST        Autres sous-traitants
│   │   ├── CC-ENT1-EDEN-CONSTR-MATERIAUX        Matériaux directs
│   │   └── CC-ENT1-EDEN-CONSTR-MO               Main d'œuvre directe
│   │
│   ├── CC-ENT1-EDEN-COMMERCIAL                  Commercial & ventes
│   │   ├── CC-ENT1-EDEN-COMM-PUBLICITE          Publicité
│   │   ├── CC-ENT1-EDEN-COMM-NOTAIRE-VENTE      Frais notaire côté vente
│   │   └── CC-ENT1-EDEN-COMM-COMMISSIONS        Commissions vente
│   │
│   ├── CC-ENT1-EDEN-VENTES                      Encaissements clients
│   │   ├── CC-ENT1-EDEN-VENTES-RF1              Encaissements déclarés
│   │   └── CC-ENT1-EDEN-VENTES-RF2              Encaissements non déclarés
│   │
│   ├── CC-ENT1-EDEN-ASSOC                       Prélèvements associés
│   │   ├── CC-ENT1-EDEN-ASSOC-AHMED             Ahmed : F3+F2 (25M → vendus 33M)
│   │   ├── CC-ENT1-EDEN-ASSOC-LYAZID            Lyazid : F3+F4 (25M → cédés Ahmed)
│   │   ├── CC-ENT1-EDEN-ASSOC-YAMINA            Yamina : F3+F3g (25M)
│   │   ├── CC-ENT1-EDEN-ASSOC-MOHAMED           Mohamed : à extraire
│   │   └── CC-ENT1-EDEN-ASSOC-KHADIDJA          F4 Khadidja (18M dette Ahmed)
│   │
│   ├── CC-ENT1-EDEN-FISCAL                      Charges fiscales directes
│   │   ├── CC-ENT1-EDEN-FISCAL-TVA              TVA
│   │   ├── CC-ENT1-EDEN-FISCAL-IBS              IBS
│   │   └── CC-ENT1-EDEN-FISCAL-TAP              TAP
│   │
│   ├── CC-ENT1-EDEN-CFF                         Coûts fiscaux fictifs sur EDEN
│   │   ├── CC-ENT1-EDEN-CFF-AMENFORT            CFF émis par AMENFORT (Ahmed/Moh/Lya)
│   │   └── CC-ENT1-EDEN-CFF-AUTRES              CFF autres émetteurs
│   │
│   ├── CC-ENT1-EDEN-ADMIN                       Frais administratifs projet
│   ├── CC-ENT1-EDEN-ASSURANCE                   Assurances chantier
│   └── CC-ENT1-EDEN-DIVERS                      Divers non classifié
│
├── CC-ENT1-JASMINS                              PROJET LES JASMINS (= SAHEL)
│   ├── CC-ENT1-JASMINS-TERRAIN                  Terrain (~50M)
│   │   ├── CC-ENT1-JASMINS-TERRAIN-PART-EDEN    35M venant de la caisse EDEN
│   │   └── CC-ENT1-JASMINS-TERRAIN-PART-AMENFORT ~15M résidu AMENFORT
│   │
│   ├── CC-ENT1-JASMINS-CONSTRUCTION             Construction
│   │   ├── CC-ENT1-JASMINS-CONSTR-GACEB         GACEB travaux + oued (20M)
│   │   └── CC-ENT1-JASMINS-CONSTR-AUTRES        Autres ST
│   │
│   ├── CC-ENT1-JASMINS-VENTES                   Encaissements
│   ├── CC-ENT1-JASMINS-APPARTS-GACEB            Appartements donnés à GACEB
│   ├── CC-ENT1-JASMINS-CFF                      CFF
│   │   └── CC-ENT1-JASMINS-CFF-BAYTI            CFF émis par BAYTI/Allo Maison
│   └── CC-ENT1-JASMINS-FISCAL                   Charges fiscales
│
├── CC-ENT1-SIEGE                                Charges siège ENT-1
│   ├── CC-ENT1-SIEGE-MASSE-SAL                  Masse salariale
│   ├── CC-ENT1-SIEGE-LOCAUX                     Loyer, énergie
│   └── CC-ENT1-SIEGE-ADMIN                      Administration
│
├── CC-ENT1-INTER-PROJETS                        Flux entre EDEN et JASMINS
│   └── CC-ENT1-INTER-EDEN-JASMINS               35M flux caisse commune
│
└── CC-ENT1-FISCAL-SOCIETE                       Charges fiscales société
```

## 6.2. ENT-2 — SARL Dendani Promotion (même structure détaillée)

```
CC-ENT2
├── CC-ENT2-OPERA            JARDIN DE L'OPÉRA
│   ├── CC-ENT2-OPERA-TERRAIN
│   ├── CC-ENT2-OPERA-CONSTRUCTION
│   │   └── CC-ENT2-OPERA-CONSTR-GACEB-BETON   (béton avance apparts JASMINS)
│   ├── CC-ENT2-OPERA-VENTES
│   ├── CC-ENT2-OPERA-CFF
│   └── CC-ENT2-OPERA-FISCAL
│
├── CC-ENT2-5H               05 HECTARE (= IRÈNE)
│   ├── (même structure détaillée)
│
├── CC-ENT2-EDRIVE            AVELIS DRIVE
├── CC-ENT2-ALLOMAISON        ALLO MAISON
├── CC-ENT2-SIEGE              Siège Dendani Promo
└── CC-ENT2-FISCAL-SOCIETE
```

## 6.3. Même logique pour ENT-3 à ENT-7

Chaque entreprise a la même structure : projet(s) → catégories → sous-catégories + siège + fiscal + inter-projets.

## 6.4. Centres de coût transversaux

```
CC-GROUPE                    CONSOLIDATION GROUPE DENDANI
├── CC-BBZ                   BUREAU BAB EZZOUAR
│   ├── CC-BBZ-AMENAGEMENT   Aménagement 60M
│   ├── CC-BBZ-LOYER         Location 200K/mois × 10 ans
│   └── CC-BBZ-AVANCE        Avance 10M
│
├── CC-INTER-ENTREPRISES     Flux entre sociétés du groupe
│
├── CC-ASS-AHMED             Consolidation Ahmed toutes sociétés
├── CC-ASS-MOHAMED           Consolidation Mohamed
├── CC-ASS-LYAZID            Consolidation Lyazid
└── CC-ASS-YAMINA            Consolidation Yamina
```

---

# 7. STRUCTURE DE DONNÉES — TABLE CENTRE_COUT

```
CENTRE_COUT {
    id                          : UUID (PK)
    code                        : String UNIQUE (ex: "CC-ENT1-EDEN-CONSTR-GACEB")
    libelle                     : String ("Sous-traitance GACEB sur EDEN")
    
    // ── HIÉRARCHIE ──
    niveau                      : Integer (0-5)
    parent_id                   : UUID → FK vers CentreCout (nullable si niveau 0)
    chemin_complet              : String ("CC-GROUPE/CC-ENT1/CC-ENT1-EDEN/CC-ENT1-EDEN-CONSTR/CC-ENT1-EDEN-CONSTR-GACEB")
    profondeur                  : Integer (calculé = nombre de "/" dans chemin)
    
    // ── RATTACHEMENTS ──
    entite_juridique_id         : UUID → FK (nullable pour niveau 0)
    projet_id                   : UUID → FK (nullable si CC société ou groupe)
    associe_id                  : UUID → FK (nullable sauf CC-ASS-xxx)
    
    // ── POURCENTAGES APPLICABLES ──
    // C'est ICI que la distinction fatale est gérée
    structure_distribution : [{
        associe_id              : UUID
        pct_entreprise          : Decimal(5,2) — % dans l'entreprise
        pct_projet              : Decimal(5,2) — % dans le projet (peut différer!)
        pct_applicable_charges  : Decimal(5,2) — % utilisé pour les charges (= pct_projet si CC projet, pct_entreprise si CC société)
        pct_applicable_cff      : Decimal(5,2) — % utilisé pour le CFF (= TOUJOURS pct_entreprise ÉMETTRICE)
        pct_applicable_benefice : Decimal(5,2) — % utilisé pour les bénéfices (= pct_projet)
    }]
    
    // ── BUDGET ──
    budget_annuel_prevu         : Decimal(15,2)
    budget_consomme             : Decimal(15,2)  — CALCULÉ en temps réel
    budget_reste                : Decimal(15,2)  — CALCULÉ
    taux_consommation_pct       : Decimal(5,2)   — CALCULÉ
    
    // ── AGRÉGATS TEMPS RÉEL (CALCULÉS, jamais saisis) ──
    // Encaissements
    total_encaissements         : Decimal(15,2)
    total_encaissements_rf1     : Decimal(15,2)
    total_encaissements_rf2     : Decimal(15,2)
    total_encaissements_rf3     : Decimal(15,2)
    total_encaissements_rf4     : Decimal(15,2)
    
    // Décaissements
    total_decaissements         : Decimal(15,2)
    total_decaissements_rf1     : Decimal(15,2)
    total_decaissements_rf2     : Decimal(15,2)
    total_decaissements_rf3     : Decimal(15,2)
    total_decaissements_rf4     : Decimal(15,2)
    
    // Solde net
    solde_net                   : Decimal(15,2)  — encaissements - décaissements
    solde_net_rf1               : Decimal(15,2)
    solde_net_rf2               : Decimal(15,2)
    
    // CFF
    total_cff                   : Decimal(15,2)  — CFF imputé à ce CC
    
    // Par associé (calculé selon le bon %)
    quote_parts_associes : [{
        associe_id              : UUID
        qp_encaissements        : Decimal(15,2)
        qp_decaissements        : Decimal(15,2)
        qp_solde_net            : Decimal(15,2)
        qp_cff                  : Decimal(15,2)
        qp_net_apres_cff        : Decimal(15,2)
    }]
    
    // ── VENTILATION (si CC reçoit des charges partagées) ──
    est_recepteur_ventilation   : Boolean
    total_ventile_recu          : Decimal(15,2) — Charges partagées reçues par ventilation
    
    // ── STATUT ──
    est_actif                   : Boolean
    date_ouverture              : Date
    date_cloture                : Date (nullable)
    accepte_imputation          : Boolean
    
    // ── AUDIT ──
    cree_par                    : UUID
    date_creation               : DateTime
    derniere_maj                : DateTime
    version                     : Integer
}
```

---

# 8. CODIFICATION

| Niveau | Format | Exemple |
|--------|--------|---------|
| 0 | CC-GROUPE | CC-GROUPE |
| 1 | CC-{ENT} | CC-ENT1, CC-ENT5 |
| 2 | CC-{ENT}-{PROJET/FONCTION} | CC-ENT1-EDEN, CC-ENT2-SIEGE |
| 3 | CC-{ENT}-{PROJ}-{CATEGORIE} | CC-ENT1-EDEN-CONSTR, CC-ENT1-EDEN-VENTES |
| 4 | CC-{ENT}-{PROJ}-{CAT}-{SOUS} | CC-ENT1-EDEN-CONSTR-GACEB |
| 5 | CC-{ENT}-{PROJ}-{CAT}-{SOUS}-{DETAIL} | CC-ENT1-EDEN-CONSTR-GACEB-SIT01 |

**Catégories standard (niveau 3) :**

| Code | Libellé | Type |
|------|---------|------|
| TERRAIN | Acquisition terrain + notaire | Charge |
| CONSTR | Construction, sous-traitance | Charge |
| COMMERCIAL | Vente, publicité, commissions | Charge |
| VENTES | Encaissements clients | Produit |
| ASSOC | Prélèvements associés | Charge/Produit |
| CFF | Coûts fiscaux fictifs | Charge |
| FISCAL | Impôts et taxes directs | Charge |
| ADMIN | Administration, honoraires | Charge |
| ASSURANCE | Assurances | Charge |
| MASSE-SAL | Masse salariale | Charge |
| LOCAUX | Loyer, énergie, entretien | Charge |
| ACHATS | Matériaux, fournitures | Charge |
| STOCK | Consommation stock | Charge |
| VEHICULES | Véhicules, transport | Charge |
| INTER-PROJ | Flux inter-projets | Neutre |
| DIVERS | Non classifié | Charge |

---

# BLOC C — ALIMENTATION : QUI NOURRIT LE CC ET COMMENT

---

# 9. SOURCES D'ALIMENTATION — 16 TYPES DE FLUX

Chaque mouvement financier du groupe génère une imputation CC. Voici les **16 types de flux** qui alimentent le CC :

| # | Type de flux | Sens CC | Exemple | CC cible |
|---|-------------|---------|---------|---------|
| 1 | Encaissement client RF1 | CRÉDIT (produit) | Chèque client lot EDEN | CC-ENT1-EDEN-VENTES-RF1 |
| 2 | Encaissement client RF2 | CRÉDIT (produit) | Espèces client lot EDEN | CC-ENT1-EDEN-VENTES-RF2 |
| 3 | Décaissement fournisseur projet | DÉBIT (charge) | Paiement ciment EDEN | CC-ENT1-EDEN-CONSTR-MATERIAUX |
| 4 | Décaissement sous-traitant projet | DÉBIT (charge) | Situation GACEB EDEN | CC-ENT1-EDEN-CONSTR-GACEB-SIT |
| 5 | Charge partagée ventilée | DÉBIT (charge) | Masse salariale siège | CC-ENT1-EDEN-MASSE-SAL (part ventilée) |
| 6 | CFF (facture fictive RF3) | DÉBIT (charge) | AMENFORT facture ETS DK | CC-ENT1-EDEN-CFF-AMENFORT |
| 7 | Flux inter-projet | DÉBIT/CRÉDIT | 35M EDEN → JASMINS | CC-ENT1-INTER-EDEN-JASMINS |
| 8 | Achat stocké (entrée magasin) | DÉBIT (charge) | 500 sacs ciment | CC-ENT5-CHERAGA-ACHATS |
| 9 | Sortie stock (consommation) | DÉBIT (charge) | Ciment consommé chantier | CC-ENT5-CHERAGA-CONSTR-MATERIAUX |
| 10 | Retrait associé espèces | DÉBIT (charge associé) | Ahmed retire 500K | CC-ASS-AHMED |
| 11 | Retrait associé nature (appart) | DÉBIT (charge associé) | Ahmed prend F3 EDEN 25M | CC-ENT1-EDEN-ASSOC-AHMED |
| 12 | Retrait associé nature (véhicule) | DÉBIT (charge associé) | Mohamed prend Tucson | CC-ENT4-VEHICULES |
| 13 | Achat véhicule | DÉBIT (charge) | Range Rover 4M | CC-ENT1-EDEN-VEHICULES |
| 14 | Cession véhicule à GACEB | CRÉDIT (réduction charge) | Range Rover cédé | CC-ENT1-EDEN-CONSTR-GACEB-VEH |
| 15 | Bureau BBZ charge | DÉBIT (charge) | Loyer mensuel 200K | CC-BBZ-LOYER |
| 16 | Avance nature (matériel AMENFORT) | DÉBIT (charge) | 120M matériel | CC-ENT1-EDEN-CONSTR-GACEB-AV120M |

**CHAQUE** flux génère :
1. Une imputation CC (débit ou crédit)
2. Une quote-part par associé (selon le BON %)
3. Un tag RF (RF1/RF2/RF3/RF4)
4. Un rattachement documentaire (pièce justificative ou formulaire si manquante)

---

# 10-19. DÉTAIL DE CHAQUE SOURCE D'ALIMENTATION

## 10. Encaissements → CC

```
ENCAISSEMENT CLIENT LOT EDD :
    │
    ├── Identifier le lot EDD (obligatoire)
    ├── Identifier le projet du lot
    ├── Identifier l'entreprise porteuse du projet
    ├── Déterminer le CC cible :
    │     → Si RF1 : CC-{ENT}-{PROJ}-VENTES-RF1
    │     → Si RF2 : CC-{ENT}-{PROJ}-VENTES-RF2
    ├── Calculer quote-parts associés au % PROJET :
    │     Ex: Lot CHERAGA → Avelis (60/20/20/0)
    │     Ahmed 60% du montant, Mohamed 20%, Lyazid 20%, Yamina 0%
    └── Mettre à jour tous les agrégats (ascendant jusqu'au groupe)
```

## 11. Décaissements directs projet → CC

```
DÉCAISSEMENT FOURNISSEUR/SOUS-TRAITANT PROJET :
    │
    ├── Identifier le projet (par BC, par libellé, par fournisseur habituel)
    ├── Identifier la catégorie (construction, commercial, admin...)
    ├── CC cible : CC-{ENT}-{PROJ}-{CATEGORIE}
    ├── Quote-parts au % PROJET
    └── Impact stock si achat matériel (double imputation : achats puis stock)
```

## 12. Charges partagées → CC

```
MASSE SALARIALE SIÈGE ENT-2 : 3 200 000 DA
    │
    ├── Projets actifs ENT-2 : Opéra, 05H, Avelis Drive, Allo Maison
    ├── Clé répartition : CA (ou budget, ou surface...)
    ├── Ventilation :
    │     Opéra   40% = 1 280 000 → CC-ENT2-OPERA-MASSE-SAL
    │     05H     30% =   960 000 → CC-ENT2-5H-MASSE-SAL
    │     E-Drive 20% =   640 000 → CC-ENT2-EDRIVE-MASSE-SAL
    │     AM      10% =   320 000 → CC-ENT2-ALLOMAISON-MASSE-SAL
    │     Total = 3 200 000 ✓
    │
    ├── Quote-parts PER PROJET (% projet, PAS % entreprise) :
    │     Opéra 1 280 000 → Ahmed ?%, Mohamed ?%, Lyazid ?%, Yamina ?%
    │     (% Jardin Opéra à extraire de la base)
    │     
    │     05H 960 000 → Ahmed 60%=576K, Mohamed 20%=192K, Lyazid 20%=192K, Yamina 0%
    │     (% 05 Hectare = 60/20/20/0 selon nomenclature)
    │
    └── ⚠ ATTENTION : Si on avait utilisé % entreprise (25/25/25/25),
          Yamina aurait payé 25% de la masse salariale ventilée sur 05H.
          C'est FAUX. Yamina est à 0% sur 05 Hectare.
          Le système DOIT utiliser % PROJET pour les charges ventilées sur un projet.
```

## 13. CFF → CC : % ENTREPRISE ÉMETTRICE

**C'est la règle la plus critique du CC.**

```
FACTURE FICTIVE RF3 :
    Émetteur : SARL AMENFORT (hors groupe, dissoute)
    Récepteur : ETS Dendani Khadidja (ENT-1)
    Projet destination : EDEN
    Montant HT : 20 000 000 DA
    
    CFF calculé : TVA 3.8M + IBS 3.8M + TAP 0.4M + Timbre 20K = ~8.02M
    
    IMPUTATION CC :
    → CC-ENT1-EDEN-CFF-AMENFORT : +8 020 000 DA (charge CFF)
    
    QUOTE-PARTS : % de l'entreprise ÉMETTRICE (AMENFORT)
    → Ahmed  ~33% = ~2 673 000 DA
    → Mohamed ~33% = ~2 673 000 DA
    → Lyazid ~33% = ~2 673 000 DA
    → Yamina   0% =          0 DA  ← JAMAIS. Elle n'était PAS dans AMENFORT.
    
    ⚠ PAS les % de ETS DK (25/25/25/25)
    ⚠ PAS les % du projet EDEN (25/25/25/25)
    ⚠ Les % de l'entreprise qui ÉMET la facture fictive = AMENFORT
    
    VÉRIFICATION :
    → Test Ahmed : "Yamina CFF AMENFORT ?" = 0 DA ✓
    → Si le système dit autre chose → REJET TOTAL
```

**Autre exemple — CFF intra-groupe :**

```
FACTURE FICTIVE RF3 :
    Émetteur : SARL Dendani Promotion (ENT-2) — 25/25/25/25
    Récepteur : SARL Avelis Promotion (ENT-5) — 60/20/20/0
    Projet destination : CHERAGA
    Montant HT : 15 000 000 DA
    
    CFF = ~6M (TVA+IBS+TAP+Timbre)
    
    CC cible : CC-ENT5-CHERAGA-CFF-DENDANIPROMO
    
    Quote-parts CFF : % ENTREPRISE ÉMETTRICE = % Dendani Promo = 25/25/25/25
    → Ahmed  25% = 1 500 000 DA
    → Mohamed 25% = 1 500 000 DA
    → Lyazid 25% = 1 500 000 DA
    → Yamina 25% = 1 500 000 DA  ← OUI, Yamina paie du CFF ici car elle est à 25% dans Dendani Promo
    
    ⚠ PAS les % de Avelis (60/20/20/0)
    ⚠ PAS les % du projet CHERAGA (60/20/20/0)
    
    TEST : "Ahmed CFF dans Dendani Promo = ?" → 25% ✓ (pas 60%)
```

## 14. Inter-projets → CC

```
FLUX EDEN → JASMINS : 35 000 000 DA (caisse commune)
    │
    ├── CC-ENT1-EDEN : DÉBIT 35M (sortie d'argent du projet EDEN)
    │   → CC-ENT1-EDEN-INTER-PROJ-SORTIE : +35M (charge ou prêt)
    │
    ├── CC-ENT1-JASMINS : CRÉDIT 35M (entrée d'argent pour JASMINS)
    │   → CC-ENT1-JASMINS-TERRAIN-PART-EDEN : +35M
    │
    ├── CC-ENT1-INTER-EDEN-JASMINS : Trace du flux 35M
    │   Nature : [PRET_REMBOURSABLE | INVESTISSEMENT_DEFINITIF]
    │   → Si non déterminé dans la base → FORMULAIRE
    │
    └── Quote-parts : % EDEN pour le débit (25/25/25/25)
                      % JASMINS pour le crédit (Ahmed 34%, Mohamed 33%, Lyazid 33%, Yamina 0%)
```

## 15. Achats/Stock → CC

```
ACHAT 500 SACS CIMENT → LIVRÉ → STOCKÉ → CONSOMMÉ SUR CHANTIER CHERAGA
    │
    ├── À l'achat : CC-ENT5-CHERAGA-ACHATS += 300 000 DA
    ├── À la consommation : CC-ENT5-CHERAGA-CONSTR-MATERIAUX += 300 000 DA
    │   (Le CC ACHATS peut être débité à l'achat OU à la consommation selon méthode)
    │   Méthode recommandée : imputer au CC du projet à la CONSOMMATION (sortie stock)
    │   Car un stock peut alimenter plusieurs projets
    └── Quote-parts : % projet CHERAGA = 60/20/20/0
```

## 16. Capital associés / Retraits nature → CC

```
AHMED PREND F3 + F2 SUR EDEN (25M DA prélèvement)
    │
    ├── CC-ENT1-EDEN-ASSOC-AHMED : DÉBIT 25M (retrait en nature)
    ├── CCA Ahmed dans ETS DK : DÉBIT 25M
    ├── Quote-part : 100% Ahmed (c'est son retrait personnel)
    │
    PUIS : Ahmed vend les 2 apparts à Bouadjina pour 33M
    ├── Bénéfice = 33M - 25M = 8M → revenus personnels Ahmed
    │   (confirmé par Ahmed : 6M de bénéfice = 33M - 27M si valorisation 27M)
    │   Le système doit prendre la valorisation exacte de la base
    └── CC-ASS-AHMED : bénéfice +6-8M
```

## 17. Véhicules : circuit complet 5 étapes

```
ÉTAPE 1 — ACHAT Range Rover : 4M DA depuis caisse commune
    → CC-ENT1-EDEN-VEHICULES : DÉBIT 4M
    → Immobilisation créée : VEH-RANGE-001
    → Quote-parts : % EDEN (25/25/25/25)

ÉTAPE 2 — IMMATRICULATION au nom d'Ahmed
    → Lien VEH-RANGE-001 → ASS-AHMED
    → Carte grise au nom Ahmed → GED

ÉTAPE 3 — CESSION à GACEB
    → CC-ENT1-EDEN-CONSTR-GACEB-VEH : DÉBIT 4M (cession)
    → Créance GACEB : +4M
    → Immobilisation sortie : VEH-RANGE-001 statut CÉDÉ

ÉTAPE 4 — DÉDUCTION situation GACEB
    → Situation GACEB 30M brut - 4M véhicule = 26M net payé
    → Créance GACEB soldée pour ce véhicule
    → CC-ENT1-EDEN-CONSTR-GACEB-SIT ajusté

ÉTAPE 5 — REVENTE par GACEB (hors CC groupe)
    → Le système note la revente mais c'est le circuit GACEB
```

## 18. Bureau BBZ → CC

```
BUREAU BAB EZZOUAR :
    Aménagement : 60M DA (charge unique)
    Location : 200K/mois × 120 mois = 24M DA
    Avance : 10M DA
    
    Répartition entre associés : Ahmed 60%, Lyazid 20%, Mohamed 20%, Yamina 0%
    
    CC-BBZ-AMENAGEMENT : 60M
    CC-BBZ-LOYER : 200K/mois (charge récurrente)
    CC-BBZ-AVANCE : 10M
    
    VENTILATION sur projets actifs (car le bureau sert TOUS les projets) :
    → Clé : CA projet / CA total groupe (ou nb projets actifs)
    → Chaque mois, le loyer 200K est ventilé sur les projets actifs
    → Quote-parts : par projet selon % projet du projet cible
```

## 19. GACEB 120M matériel AMENFORT → CC EDEN

```
AVANCE EN NATURE 120M :
    │
    ├── CC-ENT1-EDEN-CONSTR-GACEB-AV120M : DÉBIT 120M
    │   (C'est une charge du projet EDEN, mais en NATURE pas en CASH)
    │   (La caisse EDEN n'est PAS touchée)
    │
    ├── Comptabilité : D:409100 (Avance fournisseur GACEB) 120M
    │                  C:211800 (Apport nature matériel) 120M
    │
    ├── Au fur et à mesure des situations GACEB :
    │   Situation 1 : 35M brut - 20M déduction avance = 15M cash payé
    │   → CC-ENT1-EDEN-CONSTR-GACEB-SIT : +35M (coût réel travaux)
    │   → CC-ENT1-EDEN-CONSTR-GACEB-AV120M : -20M (avance amortie)
    │   → Solde avance : 100M
    │
    ├── Quote-parts : % EDEN = 25/25/25/25
    │   Chaque associé supporte 25% de cette charge
    │   ⚠ Yamina supporte 25% car elle est à 25% dans EDEN
    │   ⚠ Même si elle n'était pas dans AMENFORT, l'avance est sur EDEN
    │   ⚠ La distinction CFF vs charge directe est cruciale :
    │     - 120M = charge EDEN → % EDEN (25/25/25/25, Yamina incluse)
    │     - CFF AMENFORT = charge AMENFORT → % AMENFORT (33/33/33/0, Yamina exclue)
    │
    └── Le système doit tracer le solde restant de l'avance 120M à tout moment
```

---

# BLOC D — DOUBLE POURCENTAGE : LES RÈGLES DÉFINITIVES

---

# 20-26. MATRICE DE DÉCISION

## Règle unique et universelle

```
POUR CHAQUE IMPUTATION CC, LE SYSTÈME APPLIQUE :

SI type = CFF :
    % = % de l'entreprise ÉMETTRICE de la facture fictive
    (PAS l'entreprise réceptrice, PAS le projet destination)

SI type = CHARGE_DIRECTE_PROJET (matériaux, ST, commercial, terrain...) :
    % = % du PROJET

SI type = CHARGE_SOCIÉTÉ (siège, admin société, fiscal société) :
    % = % de l'ENTREPRISE

SI type = CHARGE_PARTAGÉE_VENTILÉE_SUR_PROJET :
    Étape 1 : ventiler le montant entre projets (clé CA/surface/etc.)
    Étape 2 : pour chaque part ventilée, appliquer % du PROJET CIBLE

SI type = BÉNÉFICE / DISTRIBUTION :
    % = % du PROJET

SI type = RETRAIT_ASSOCIÉ :
    100% à l'associé concerné

SI type = INTER_PROJET :
    % PROJET SOURCE pour le débit
    % PROJET DESTINATION pour le crédit
```

## Cas Dendani Promotion — Le piège absolu

```
ENT-2 SARL Dendani Promotion :
    % Entreprise : Ahmed 25%, Mohamed 25%, Lyazid 25%, Yamina 25%
    
    % Projet 05 Hectare : Ahmed 60%, Mohamed 20%, Lyazid 20%, Yamina 0%
    % Projet Avelis Drive : Ahmed 60%, Mohamed 20%, Lyazid 20%, Yamina 0%
    % Projet Allo Maison : Ahmed 60%, Mohamed 20%, Lyazid 20%, Yamina 0%
    % Projet Jardin Opéra : À EXTRAIRE (formulaire si absent)

CAS 1 : Achat ciment pour 05 Hectare = 1 000 000 DA
    → CC-ENT2-5H-CONSTR-MATERIAUX : 1M
    → Quote-parts : % projet 05H = Ahmed 600K, Mohamed 200K, Lyazid 200K, Yamina 0
    ✅ CORRECT

CAS 2 : Loyer siège Dendani Promo = 500 000 DA / mois (non ventilé)
    → CC-ENT2-SIEGE-LOCAUX : 500K
    → Quote-parts : % entreprise = Ahmed 125K, Mohamed 125K, Lyazid 125K, Yamina 125K
    ✅ CORRECT

CAS 3 : Loyer siège ventilé sur 4 projets (clé CA)
    → 05H 40% = 200K → CC-ENT2-5H-SIEGE-LOCAUX
      Quote-parts 200K : % projet 05H = Ahmed 120K, Mohamed 40K, Lyazid 40K, Yamina 0
    ✅ CORRECT — Yamina ne paie PAS la part ventilée sur 05H

CAS 4 : CFF — Dendani Promo émet facture RF3 vers Avelis pour CHERAGA
    → CFF = 2M
    → Quote-parts CFF : % entreprise ÉMETTRICE = % Dendani Promo = 25/25/25/25
    → Ahmed 500K, Mohamed 500K, Lyazid 500K, Yamina 500K
    ✅ CORRECT — Yamina PAIE car elle est à 25% dans Dendani Promo (l'émettrice)
    
CAS 5 : CFF — DBPI émet facture RF3 vers Dendani Promo pour 05 Hectare
    → CFF = 3M
    → % entreprise ÉMETTRICE = % DBPI = 60/20/20/0
    → Ahmed 1.8M, Mohamed 600K, Lyazid 600K, Yamina 0
    ✅ CORRECT — Yamina 0% dans DBPI

⚠ SI LE SYSTÈME CONFOND % ENTREPRISE ET % PROJET SUR UN SEUL CAS → REJET TOTAL
```

## Cas Yamina — Les 5 règles absolues

```
RÈGLE Y1 : Yamina est à 25% dans ENT-1 et ENT-2. TOUTES les charges société 
           ENT-1 et ENT-2 lui sont imputées à 25%.

RÈGLE Y2 : Yamina est à 0% dans ENT-3, ENT-4, ENT-5, ENT-6, ENT-7.
           AUCUNE charge de ces sociétés ne lui est imputée. Jamais. 0 DA.

RÈGLE Y3 : Yamina est à 0% sur les projets 05H, Avelis Drive, Allo Maison, 
           Les Lys, Magnolia, Cheraga, El Achour, PFSB.
           AUCUNE charge directe projet ne lui est imputée sur ces projets.

RÈGLE Y4 : Yamina est à 25% sur EDEN et à 0% sur JASMINS (selon nomenclature).
           Les charges EDEN lui sont imputées à 25%.
           Les charges JASMINS ne lui sont JAMAIS imputées.

RÈGLE Y5 : Si l'entreprise ÉMETTRICE d'un CFF est une entreprise où Yamina est à 0%
           (DBPI, Omega, Avelis, Senimar, Bimha, AMENFORT, BAYTI),
           Yamina ne paie JAMAIS le CFF. 0 DA.
           Si l'émettrice est ENT-1 ou ENT-2, Yamina paie 25%.

CES 5 RÈGLES SONT DES TESTS ABSOLUS. 
Si le système viole UNE SEULE de ces règles → BUG CRITIQUE → REJET.
```

---

# BLOC E — RF DANS LE CC

---

# 27-30. TRAITEMENT RF DANS LE CENTRE DE COÛT

## 27. RF2 dans le CC — OUI, TOUJOURS

RF2 = argent RÉEL. Le CC reflète la RÉALITÉ. Donc RF2 est DANS le CC.

```
ENCAISSEMENT CLIENT 2M DA ESPÈCES RF2 LOT EDEN :
    → CC-ENT1-EDEN-VENTES-RF2 : +2M ✅
    → Comptabilité OFFICIELLE : RIEN ❌ (RF2 jamais déclaré)
    → Comptabilité INTERNE : D:530-RF2 2M / C:411-RF2 2M ✅
    → Quote-part associés : calculée sur les 2M (% EDEN = 25/25/25/25)
```

## 29. Double vue CC permanent

Chaque écran CC affiche TOUJOURS 2 colonnes :

```
CC-ENT1-EDEN — Mars 2026
    ╔══════════════════════════╦═══════════════════╦═════════════════════════╗
    ║                          ║ VUE OFFICIELLE    ║ VUE INTERNE (vérité)   ║
    ║                          ║ (RF1 + RF3)       ║ (RF1+RF2+RF3+RF4)      ║
    ╠══════════════════════════╬═══════════════════╬═════════════════════════╣
    ║ Encaissements            ║    95 000 000     ║    163 200 000         ║
    ║   dont RF1               ║    95 000 000     ║     95 000 000         ║
    ║   dont RF2               ║            —      ║     68 200 000         ║
    ╠══════════════════════════╬═══════════════════╬═════════════════════════╣
    ║ Décaissements            ║    72 000 000     ║     85 500 000         ║
    ║   dont charges directes  ║    55 000 000     ║     68 500 000         ║
    ║   dont CFF AMENFORT      ║     8 000 000     ║      8 000 000         ║
    ║   dont charges ventilées ║     9 000 000     ║      9 000 000         ║
    ╠══════════════════════════╬═══════════════════╬═════════════════════════╣
    ║ SOLDE NET                ║   +23 000 000     ║    +77 700 000         ║
    ╠══════════════════════════╬═══════════════════╬═════════════════════════╣
    ║ QP Ahmed (25%)           ║    +5 750 000     ║    +19 425 000         ║
    ║ QP Mohamed (25%)         ║    +5 750 000     ║    +19 425 000         ║
    ║ QP Lyazid (25%)          ║    +5 750 000     ║    +19 425 000         ║
    ║ QP Yamina (25%)          ║    +5 750 000     ║    +19 425 000         ║
    ║                          ║                   ║                         ║
    ║ MAIS : CFF AMENFORT      ║                   ║                         ║
    ║ Ahmed (33%)              ║                   ║     -2 640 000         ║
    ║ Mohamed (33%)            ║                   ║     -2 640 000         ║
    ║ Lyazid (33%)             ║                   ║     -2 640 000         ║
    ║ Yamina (0% AMENFORT)     ║                   ║              0         ║
    ╠══════════════════════════╬═══════════════════╬═════════════════════════╣
    ║ NET APRÈS CFF            ║                   ║                         ║
    ║ Ahmed                    ║                   ║    +16 785 000         ║
    ║ Mohamed                  ║                   ║    +16 785 000         ║
    ║ Lyazid                   ║                   ║    +16 785 000         ║
    ║ Yamina                   ║                   ║    +19 425 000         ║
    ║ (Yamina a PLUS car pas de CFF AMENFORT)      ║                         ║
    ╚══════════════════════════╩═══════════════════╩═════════════════════════╝
```

---

# BLOC F — CONSOLIDATION MULTI-AXES

---

# 31. CONSOLIDATION ASCENDANTE

Chaque imputation au niveau 5 remonte automatiquement :

```
CC-ENT1-EDEN-CONSTR-GACEB-SIT01 : 15 000 000 DA
    ↑ agrège dans
CC-ENT1-EDEN-CONSTR-GACEB : 85 000 000 DA (toutes situations)
    ↑ agrège dans
CC-ENT1-EDEN-CONSTR : 120 000 000 DA (toute construction)
    ↑ agrège dans
CC-ENT1-EDEN : 180 000 000 DA (tout le projet)
    ↑ agrège dans
CC-ENT1 : 250 000 000 DA (toute l'entreprise)
    ↑ agrège dans
CC-GROUPE : 1 200 000 000 DA (tout le groupe)
```

**Vérification :** La somme des CC niveaux inférieurs DOIT = le CC niveau supérieur. Si écart ≠ 0 → **BUG**.

## 32. CONSOLIDATION PAR ASSOCIÉ

Pour chaque associé, le système agrège TOUS ses CC à travers TOUTES les entreprises et projets :

```
AHMED DENDANI — CONSOLIDATION TRANSVERSALE
    │
    ├── ENT-1 ETS DK (25%)
    │   ├── EDEN (25%) : QP nette = X DA (après CFF AMENFORT à 33%)
    │   └── JASMINS (34%) : QP nette = Y DA (après CFF BAYTI)
    │
    ├── ENT-2 Dendani Promo (25% entreprise)
    │   ├── Jardin Opéra (?%) : QP nette = Z DA
    │   ├── 05 Hectare (60%) : QP nette = W DA
    │   ├── Avelis Drive (60%) : QP nette = V DA
    │   └── Allo Maison (60%) : QP nette = U DA
    │   + CFF si ENT-2 émet RF3 : à 25%
    │
    ├── ENT-3 DBPI (60%)
    │   └── Les Lys (60%) : QP nette = T DA
    │
    ├── ENT-4 Omega (60%) : QP nette = S DA
    ├── ENT-5 Avelis (60%) : QP nette = R DA
    ├── ENT-6 Senimar (60%) : QP nette = Q DA
    ├── ENT-7 Bimha (60%) : QP nette = P DA
    │
    ├── Bureau BBZ (60%) : charge = -N DA
    │
    ├── Retraits espèces : -M DA
    ├── Retraits nature : -L DA (apparts EDEN 25M + ventes 33M + dette Khadidja 18M...)
    │
    └── TOTAL NET AHMED = Σ (QP encaissements - QP décaissements - QP CFF - retraits)
```

---

# BLOC G — MOTEUR INTELLIGENT

---

# 36. DÉTECTION AUTOMATIQUE DEPUIS LA BASE 400 Go

```
LE SYSTÈME SCANNE LA BASE ET :
    │
    ├── Détecte les 7 entreprises (NIF/RC croisés dans les journaux)
    ├── Détecte les 4 associés (noms + alias dans comptes 455)
    ├── Résout les alias projets (même terrain/adresse)
    ├── Détecte les flux inter-projets (comptes 580, mêmes dates)
    ├── Détecte les factures fictives RF3 (émetteur ET récepteur du groupe)
    ├── Détecte l'avance 120M (comptes 409 + "AMENFORT" + "matériel")
    ├── Détecte les véhicules cédés (comptes 2182 + cessions)
    ├── Détecte les prélèvements apparts (comptes 455 débit + 701)
    ├── Détecte la dette Khadidja 18M (compte 455 + "KHADIDJA")
    ├── Détecte la commission villa 32M (libellé "villa" ou "Zit Kaci")
    ├── Détecte le bureau BBZ (comptes 2181/613/275 + "BBZ")
    ├── Détecte la répartition 60/20/20 (pattern dans les imputations)
    ├── Détecte le CFF AMENFORT (AMENFORT émet vers ETS DK)
    ├── Détecte le CFF BAYTI (BAYTI émet vers ETS DK)
    └── Extrait les % actionnariat des statuts dans Drive D5 DOC ADMIN
```

---

# BLOC H — VÉRIFICATION MULTI-NIVEAUX

---

# 41. 10 NIVEAUX DE VÉRIFICATION

| Niveau | Quoi | Comment | Fréquence |
|--------|------|---------|-----------|
| **V1** | Somme fils = parent | Σ CC enfants = CC parent | Chaque imputation |
| **V2** | Débit = Crédit | Σ débits comptables = Σ crédits | Chaque écriture |
| **V3** | % associés = 100% | Σ quote-parts = montant total | Chaque calcul QP |
| **V4** | Σ ventilation = source | Charges ventilées = charge initiale | Chaque ventilation |
| **V5** | RF cohérent | RF2 jamais en compta officielle | Chaque écriture |
| **V6** | CFF = % émetteur | Quote-part CFF calculée sur % entreprise émettrice | Chaque CFF |
| **V7** | Yamina 0% respecté | Yamina = 0 DA sur projets/entreprises où 0% | Chaque calcul |
| **V8** | Alias fusionnés | Pas de double CC pour même projet | Quotidien |
| **V9** | Actif = Passif | Bilan équilibré | Mensuel |
| **V10** | CC = Trésorerie | Total CC = Total mouvements trésorerie | Quotidien |

**SI UN SEUL contrôle échoue** → ALERTE CRITIQUE → le système ne continue PAS tant que le problème n'est pas résolu.

## 45. Les 7 tests décisifs d'Ahmed

| # | Question | Réponse correcte | Si faux |
|---|---------|-----------------|---------|
| **1** | Yamina CFF dans DBPI = ? | 0 DA | REJET (confusion actionnariat) |
| **2** | Ahmed CFF dans Dendani Promo = ? | 25% (pas 60%) | REJET (confusion % ent vs projet) |
| **3** | Projet ATLANTIS existe ? | Non trouvé + formulaire | REJET (hallucination) |
| **4** | Les Lys vs 02 Hectare ? | Même projet, 1 total | REJET (alias non résolu) |
| **5** | 120M GACEB sorti de caisse ? | NON (matériel physique) | REJET (erreur compréhension) |
| **6** | Actif = Passif ? | Écart = 0 DA | REJET (erreur fatale) |
| **7** | SPI > 85/100 ? | Oui | REJET si < 70 |

**Le CC doit pouvoir répondre à CHACUN de ces 7 tests correctement.**

---

# BLOC I — RATIOS & REPORTING

---

# 46. RATIOS PAR CC

| Ratio | Formule | Niveau |
|-------|---------|--------|
| Marge brute projet | (Encaissements - Décaissements) / Encaissements × 100% | Projet |
| Coût revient / m² | Total charges / Surface totale | Projet |
| Impact CFF | CFF / CA × 100% | Projet |
| Taux encaissement | Encaissé / CA prévisionnel × 100% | Projet |
| Poids RF2 | RF2 / (RF1+RF2) × 100% | Projet, Société, Groupe |
| Charges partagées / Total | Ventilé / Total charges × 100% | Projet |
| ROI associé | QP net / Capital investi × 100% | Associé × Société |
| Solde GACEB | Marchés × %avancement - 120M - véhicules - apparts - payé | Fournisseur |
| Complétude CC | CC alimentés / CC attendus × 100% | Groupe |
| Écart réel vs budget | (Réel - Budget) / Budget × 100% | CC niveau 3+ |

## 47. DASHBOARD DAF — VUE CC

```
╔══════════════════════════════════════════════════════════════════════╗
║              DASHBOARD DAF — CENTRE DE COÛT — Mars 2026             ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  CONSOLIDATION GROUPE (interne, RF1+RF2+RF3+RF4)                   ║
║  Total encaissements : 1 250 000 000 DA                             ║
║  Total décaissements :   890 000 000 DA                             ║
║  Total CFF           :    52 000 000 DA                             ║
║  Solde net groupe    :   308 000 000 DA                             ║
║                                                                      ║
║  PAR ASSOCIÉ (net après CFF) :                                      ║
║  Ahmed    : 142 500 000 DA                                          ║
║  Mohamed  :  68 200 000 DA                                          ║
║  Lyazid   :  65 800 000 DA                                          ║
║  Yamina   :  31 500 000 DA                                          ║
║                                                                      ║
║  TOP 3 PROJETS (marge) :                                            ║
║  1. EDEN          : marge 42% (RF1: 38%, RF2: 52%)                  ║
║  2. CHERAGA       : marge 35% (en cours)                            ║
║  3. JARDIN OPÉRA  : marge 28%                                      ║
║                                                                      ║
║  ALERTES CC :                                                       ║
║  🔴 Alias non résolu : "SAHEL_2" — quel projet ? → FORMULAIRE     ║
║  🔴 CFF BAYTI : % actionnariat non extrait → FORMULAIRE           ║
║  🟡 GACEB avance 120M : solde = 45M à déduire                     ║
║  🟡 Budget CHERAGA construction : 92% consommé                     ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
```

---

# BLOC J — SCÉNARIOS RÉALISTES

---

# 49. SCÉNARIOS

## Scénario 1 — Masse salariale Dendani Promo ventilée (le piège Yamina)

```
Masse salariale siège ENT-2 Mars 2026 = 2 000 000 DA

ÉTAPE 1 : Identification → CHARGE_PARTAGÉE → clé CA
ÉTAPE 2 : Projets actifs ENT-2 : Opéra (CA 50M), 05H (CA 80M), E-Drive (CA 30M), AM (CA 10M)
          Total CA = 170M
ÉTAPE 3 : Ventilation :
    Opéra   : 2M × 29.4% =   588 235 → CC-ENT2-OPERA-MASSE-SAL
    05H     : 2M × 47.1% =   941 176 → CC-ENT2-5H-MASSE-SAL
    E-Drive : 2M × 17.6% =   352 941 → CC-ENT2-EDRIVE-MASSE-SAL
    AM      : 2M ×  5.9% =   117 647 → CC-ENT2-ALLOMAISON-MASSE-SAL
    Total = 2 000 000 ✓

ÉTAPE 4 : Quote-parts par projet :
    Opéra 588 235 → % Jardin Opéra (à extraire, supposons 60/20/20/0) :
        Ahmed 352 941, Mohamed 117 647, Lyazid 117 647, Yamina 0
    
    05H 941 176 → % 05 Hectare (60/20/20/0) :
        Ahmed 564 706, Mohamed 188 235, Lyazid 188 235, Yamina 0
    
    E-Drive 352 941 → % Avelis Drive (60/20/20/0) :
        Ahmed 211 765, Mohamed 70 588, Lyazid 70 588, Yamina 0
    
    AM 117 647 → % Allo Maison (60/20/20/0) :
        Ahmed 70 588, Mohamed 23 529, Lyazid 23 529, Yamina 0

TOTAL AHMED  : 1 200 000 DA (60% du total)
TOTAL YAMINA :         0 DA ← CORRECT. Yamina est à 0% sur TOUS les projets ENT-2 (sauf Opéra TBD)

⚠ Si le système avait utilisé % entreprise (25%) :
    Yamina aurait payé 500 000 DA → FAUX → REJET
```

## Scénario 2 — CFF AMENFORT sur EDEN

```
AMENFORT émet facture fictive 20M HT à ETS DK pour EDEN

CFF = TVA 3.8M + IBS 3.8M + TAP 0.4M + Timbre 20K = 8 020 000 DA

CC : CC-ENT1-EDEN-CFF-AMENFORT += 8 020 000

Quote-parts CFF : % AMENFORT (~33/33/33/0)
    Ahmed  : 2 673 333 DA
    Mohamed: 2 673 333 DA
    Lyazid : 2 673 333 DA
    Yamina :         0 DA ← CORRECT. Yamina n'était PAS dans AMENFORT.

⚠ Si le système avait utilisé % ETS DK (25/25/25/25) :
    Yamina aurait payé 2 005 000 DA → FAUX → REJET
⚠ Si le système avait utilisé % EDEN (25/25/25/25) :
    Même erreur → REJET
```

## Scénario 3 — Circuit complet véhicule Range Rover

```
① Achat Range Rover 4M caisse commune (affectée à EDEN)
    CC-ENT1-EDEN-VEHICULES += 4 000 000
    QP : Ahmed 25%=1M, Mohamed 25%=1M, Lyazid 25%=1M, Yamina 25%=1M

② Immatriculation au nom Ahmed → lien véhicule-associé

③ Cession à GACEB
    CC-ENT1-EDEN-CONSTR-GACEB-VEH += 4 000 000 (créance GACEB)

④ Déduction situation GACEB
    Situation 30M - 4M véhicule = 26M net payé
    CC-ENT1-EDEN-CONSTR-GACEB-SIT += 30M (coût travaux)
    Créance véhicule soldée

⑤ Impact GACEB : RAP réduit de 4M

VÉRIFICATION : Le 4M n'est imputé qu'UNE FOIS dans le CC EDEN.
La cession et la déduction sont des jeux d'écritures, pas des charges supplémentaires.
Total charge EDEN pour ce véhicule = 4M DA. Point.
```

---

# BLOC K — MODÈLE DE DONNÉES & API

---

# 50. TABLES SQL

```sql
-- Table principale
CREATE TABLE centre_cout (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(100) UNIQUE NOT NULL,
    libelle VARCHAR(500) NOT NULL,
    niveau INTEGER NOT NULL CHECK (niveau BETWEEN 0 AND 5),
    parent_id UUID REFERENCES centre_cout(id),
    chemin_complet VARCHAR(1000) NOT NULL,
    
    entite_juridique_id UUID REFERENCES entite_juridique(id),
    projet_id UUID REFERENCES projet(id),
    associe_id UUID REFERENCES associe(id),
    
    budget_annuel_prevu DECIMAL(15,2) DEFAULT 0,
    
    est_actif BOOLEAN DEFAULT true,
    date_ouverture DATE NOT NULL DEFAULT CURRENT_DATE,
    date_cloture DATE,
    accepte_imputation BOOLEAN DEFAULT true,
    
    cree_par UUID NOT NULL,
    date_creation TIMESTAMP DEFAULT NOW(),
    derniere_maj TIMESTAMP DEFAULT NOW(),
    version INTEGER DEFAULT 1,
    
    CONSTRAINT chk_parent CHECK (
        (niveau = 0 AND parent_id IS NULL) OR
        (niveau > 0 AND parent_id IS NOT NULL)
    )
);

-- Structure de distribution (% par associé par CC)
CREATE TABLE cc_distribution (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    centre_cout_id UUID NOT NULL REFERENCES centre_cout(id),
    associe_id UUID NOT NULL REFERENCES associe(id),
    
    pct_entreprise DECIMAL(5,2) NOT NULL,
    pct_projet DECIMAL(5,2) NOT NULL,
    pct_applicable_charges DECIMAL(5,2) NOT NULL,
    pct_applicable_cff DECIMAL(5,2) NOT NULL,
    pct_applicable_benefice DECIMAL(5,2) NOT NULL,
    
    UNIQUE(centre_cout_id, associe_id)
);

-- Imputation CC (chaque ligne de mouvement)
CREATE TABLE cc_imputation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    centre_cout_id UUID NOT NULL REFERENCES centre_cout(id),
    
    date_imputation DATE NOT NULL,
    periode VARCHAR(7) NOT NULL, -- "2026-03"
    
    -- Source
    mouvement_tresorerie_id UUID REFERENCES mouvement_tresorerie(id),
    mouvement_ventilation_id UUID REFERENCES mouvement_ventilation(id),
    cff_calcul_id UUID REFERENCES cff_calcul(id),
    mouvement_stock_id UUID REFERENCES mouvement_stock(id),
    flux_inter_projet_id UUID REFERENCES flux_inter_projet(id),
    
    -- Nature
    type_imputation VARCHAR(50) NOT NULL, -- "ENCAISSEMENT", "DECAISSEMENT_DIRECT", etc.
    sens VARCHAR(10) NOT NULL CHECK (sens IN ('DEBIT', 'CREDIT')),
    montant DECIMAL(15,2) NOT NULL,
    realite_financiere VARCHAR(3) NOT NULL CHECK (realite_financiere IN ('RF1','RF2','RF3','RF4')),
    
    -- Libellé
    libelle VARCHAR(500) NOT NULL,
    
    -- Quote-parts (calculées au moment de l'imputation)
    quote_parts JSONB NOT NULL, 
    -- Ex: [{"associe":"AHMED","pct":60,"montant":600000,"type_pct":"projet"},...]
    
    -- Documents
    documents JSONB, -- [{doc_id, type}]
    
    -- Audit
    cree_par UUID NOT NULL,
    date_creation TIMESTAMP DEFAULT NOW()
);

-- Vue matérialisée pour agrégats
CREATE MATERIALIZED VIEW cc_agregats AS
SELECT 
    cc.id AS centre_cout_id,
    cc.code,
    cc.niveau,
    cc.parent_id,
    
    SUM(CASE WHEN i.sens = 'CREDIT' THEN i.montant ELSE 0 END) AS total_encaissements,
    SUM(CASE WHEN i.sens = 'CREDIT' AND i.realite_financiere = 'RF1' THEN i.montant ELSE 0 END) AS encaissements_rf1,
    SUM(CASE WHEN i.sens = 'CREDIT' AND i.realite_financiere = 'RF2' THEN i.montant ELSE 0 END) AS encaissements_rf2,
    
    SUM(CASE WHEN i.sens = 'DEBIT' THEN i.montant ELSE 0 END) AS total_decaissements,
    SUM(CASE WHEN i.sens = 'DEBIT' AND i.realite_financiere = 'RF1' THEN i.montant ELSE 0 END) AS decaissements_rf1,
    SUM(CASE WHEN i.sens = 'DEBIT' AND i.realite_financiere = 'RF2' THEN i.montant ELSE 0 END) AS decaissements_rf2,
    
    SUM(CASE WHEN i.type_imputation = 'CFF' THEN i.montant ELSE 0 END) AS total_cff,
    
    SUM(CASE WHEN i.sens = 'CREDIT' THEN i.montant ELSE 0 END) -
    SUM(CASE WHEN i.sens = 'DEBIT' THEN i.montant ELSE 0 END) AS solde_net
    
FROM centre_cout cc
LEFT JOIN cc_imputation i ON i.centre_cout_id = cc.id
GROUP BY cc.id, cc.code, cc.niveau, cc.parent_id;

-- Trigger de vérification après chaque imputation
CREATE OR REPLACE FUNCTION verify_cc_imputation() RETURNS TRIGGER AS $$
DECLARE
    v_sum DECIMAL;
    v_cc RECORD;
BEGIN
    -- V3 : Vérifier que Σ quote-parts = montant
    SELECT SUM((qp->>'montant')::DECIMAL) INTO v_sum
    FROM jsonb_array_elements(NEW.quote_parts) qp;
    
    IF ABS(v_sum - NEW.montant) > 0.01 THEN
        RAISE EXCEPTION 'V3 VIOLATION: Σ quote-parts (%) ≠ montant (%). Écart = %',
            v_sum, NEW.montant, ABS(v_sum - NEW.montant);
    END IF;
    
    -- V7 : Vérifier Yamina 0% respecté
    SELECT * INTO v_cc FROM centre_cout WHERE id = NEW.centre_cout_id;
    IF EXISTS (
        SELECT 1 FROM jsonb_array_elements(NEW.quote_parts) qp
        WHERE (qp->>'associe') = 'YAMINA'
        AND (qp->>'montant')::DECIMAL > 0
        AND (qp->>'pct')::DECIMAL = 0
    ) THEN
        RAISE EXCEPTION 'V7 VIOLATION: Yamina imputée à >0 DA alors que son %% = 0 sur CC %',
            v_cc.code;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_verify_cc_imputation
    BEFORE INSERT ON cc_imputation
    FOR EACH ROW EXECUTE FUNCTION verify_cc_imputation();

-- Table alias
CREATE TABLE alias (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entite_type VARCHAR(30) NOT NULL, -- "PROJET", "ASSOCIE", "ENTREPRISE"
    entite_id UUID NOT NULL,
    alias_texte VARCHAR(200) NOT NULL,
    source VARCHAR(500),
    confiance DECIMAL(5,2),
    valide_par UUID,
    UNIQUE(entite_type, alias_texte)
);

-- Table flux inter-projets
CREATE TABLE flux_inter_projet (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    projet_source_id UUID NOT NULL REFERENCES projet(id),
    projet_destination_id UUID NOT NULL REFERENCES projet(id),
    montant DECIMAL(15,2) NOT NULL,
    date_flux DATE NOT NULL,
    nature VARCHAR(30) NOT NULL CHECK (nature IN ('PRET_REMBOURSABLE', 'INVESTISSEMENT_DEFINITIF', 'A_DETERMINER')),
    est_rembourse BOOLEAN DEFAULT false,
    montant_rembourse DECIMAL(15,2) DEFAULT 0,
    cc_source_id UUID REFERENCES centre_cout(id),
    cc_destination_id UUID REFERENCES centre_cout(id),
    source_detection VARCHAR(200), -- "Compte 580, journal EDEN, 15/03/2022"
    CONSTRAINT chk_not_self CHECK (projet_source_id != projet_destination_id)
);

-- Index
CREATE INDEX idx_cc_parent ON centre_cout(parent_id);
CREATE INDEX idx_cc_entite ON centre_cout(entite_juridique_id);
CREATE INDEX idx_cc_projet ON centre_cout(projet_id);
CREATE INDEX idx_cc_code ON centre_cout(code);
CREATE INDEX idx_cci_cc ON cc_imputation(centre_cout_id);
CREATE INDEX idx_cci_date ON cc_imputation(date_imputation);
CREATE INDEX idx_cci_rf ON cc_imputation(realite_financiere);
CREATE INDEX idx_cci_type ON cc_imputation(type_imputation);
CREATE INDEX idx_cci_mvt ON cc_imputation(mouvement_tresorerie_id);
CREATE INDEX idx_alias_type ON alias(entite_type, alias_texte);
```

---

# 51. API ENDPOINTS

```
// Arbre CC
GET    /api/v1/cc/arbre                              → Arbre complet hiérarchique
GET    /api/v1/cc/arbre?entite={id}                  → Arbre d'une entreprise
GET    /api/v1/cc/arbre?projet={id}                  → Arbre d'un projet

// Détail CC
GET    /api/v1/cc/{id}                               → Détail + agrégats + QP
GET    /api/v1/cc/{id}/imputations                   → Liste imputations
GET    /api/v1/cc/{id}/imputations?rf=RF2             → Filtrer par RF
GET    /api/v1/cc/{id}/imputations?periode=2026-03    → Filtrer par période
GET    /api/v1/cc/{id}/double-vue                    → Vue officielle + interne

// Consolidation
GET    /api/v1/cc/consolidation/groupe               → Consolidation groupe
GET    /api/v1/cc/consolidation/associe/{id}          → Consolidation par associé
GET    /api/v1/cc/consolidation/rf                   → Par RF
GET    /api/v1/cc/consolidation/inter-projets        → Flux inter-projets

// Vérification
GET    /api/v1/cc/verification/10-niveaux            → Résultat 10 vérifications
GET    /api/v1/cc/verification/7-tests-ahmed         → Les 7 tests décisifs
GET    /api/v1/cc/verification/actif-passif          → Test actif = passif
GET    /api/v1/cc/verification/yamina                → Vérification règles Yamina

// Ratios
GET    /api/v1/cc/ratios/{projet_id}                 → Ratios projet
GET    /api/v1/cc/ratios/associe/{id}                → Ratios associé
GET    /api/v1/cc/ratios/gaceb                       → Solde GACEB

// Dashboard
GET    /api/v1/cc/dashboard/daf                      → Dashboard complet

// Alias
GET    /api/v1/cc/alias                              → Tous les alias
POST   /api/v1/cc/alias/valider                      → Valider un alias
GET    /api/v1/cc/alias/non-resolus                  → Alias en attente
```

---

**FIN DU DOCUMENT**

*Ce document est la SEULE référence pour le module Centre de Coût du GFI v7.0. Il couvre chaque combinaison entreprise × projet × associé × RF × type de flux. Il intègre la distinction fatale % entreprise vs % projet, les alias, GACEB, AMENFORT, les véhicules, le bureau BBZ, les prélèvements nature, les flux inter-projets et la caisse commune.*

*Chaque imputation CC est vérifiée à 10 niveaux. Chaque quote-part utilise le BON pourcentage. Yamina ne paie JAMAIS ce qu'elle ne doit pas. Ahmed a ses 7 tests décisifs. Le système détecte, calcule, vérifie, et ne devine JAMAIS.*

*0,000001% d'erreur n'est PAS toléré.*
