import { formatDA } from './format';

export interface ValidationResult {
  valid: boolean;
  errors: string[];
}

export interface PaymentForm {
  type_rf: 'RF1' | 'RF2';
  mode_reglement: 'CHEQUE' | 'VIREMENT' | 'ESPECES' | 'CHEQUE_NOTAIRE';
  montant: number;
}

export interface DossierADV {
  prix_vente_rf1: number;
  prix_vente_rf2: number;
  prix_vente_reel: number;
  total_rf1_paid: number;
  total_rf2_paid: number;
  total_paid: number;
  statut_rf2: string;
  montant_rf2_securise: number;
  type_paiement: string;
  fond_garantie_disponible: number;
  montant_credit: number;
}

// PAY-C01 through PAY-C06
export function validatePayment(payment: PaymentForm, dossier: DossierADV): ValidationResult {
  const errors: string[] = [];

  if (payment.type_rf === 'RF1' && payment.mode_reglement === 'ESPECES') {
    errors.push('Paiement RF1 en espèces interdit. Mode autorisé : chèque ou virement.');
  }
  if (payment.type_rf === 'RF2' && payment.mode_reglement !== 'ESPECES') {
    errors.push('Paiement RF2 : seules les espèces sont autorisées.');
  }

  const totalRF1 = dossier.total_rf1_paid + (payment.type_rf === 'RF1' ? payment.montant : 0);
  if (totalRF1 > dossier.prix_vente_rf1) {
    errors.push(`Dépassement RF1 : total ${formatDA(totalRF1)} > prix RF1 ${formatDA(dossier.prix_vente_rf1)}.`);
  }

  const totalRF2 = dossier.total_rf2_paid + (payment.type_rf === 'RF2' ? payment.montant : 0);
  if (totalRF2 > dossier.prix_vente_rf2) {
    errors.push(`Dépassement RF2 : total ${formatDA(totalRF2)} > prix RF2 ${formatDA(dossier.prix_vente_rf2)}.`);
  }

  const totalAll = dossier.total_paid + payment.montant;
  if (totalAll > dossier.prix_vente_reel) {
    errors.push(`Dépassement total : ${formatDA(totalAll)} > prix réel ${formatDA(dossier.prix_vente_reel)}.`);
  }

  return { valid: errors.length === 0, errors };
}

// R-003 CCA withdrawal
export function validateCCAWithdrawal(amount: number, individualBalance: number, globalBalance: number): ValidationResult {
  const errors: string[] = [];
  const max50 = individualBalance * 0.5;
  if (amount > max50) {
    errors.push(`Montant maximum autorisé : ${formatDA(max50)} (50% du solde individuel de ${formatDA(individualBalance)}).`);
  }
  if (globalBalance <= 0) {
    errors.push('Solde global CCA négatif — retrait interdit.');
  }
  return { valid: errors.length === 0, errors };
}

// ADV engagement preconditions
export function canEngage(dossier: DossierADV): { allowed: boolean; blockers: string[] } {
  const blockers: string[] = [];
  if (dossier.statut_rf2 !== 'SÉCURISÉ') {
    blockers.push(`RF2 non sécurisé. Sécurisé : ${formatDA(dossier.montant_rf2_securise)} / Requis : ${formatDA(dossier.prix_vente_rf2)}.`);
  }
  if (dossier.type_paiement === 'FONDS_PROPRES' && dossier.total_paid < dossier.prix_vente_reel * 0.3) {
    blockers.push(`30% non atteint : versé ${formatDA(dossier.total_paid)} < requis ${formatDA(dossier.prix_vente_reel * 0.3)}.`);
  }
  if (dossier.type_paiement === 'CRÉDIT_BANCAIRE' && dossier.fond_garantie_disponible < dossier.montant_credit) {
    blockers.push(`Fond de garantie insuffisant : ${formatDA(dossier.fond_garantie_disponible)} < ${formatDA(dossier.montant_credit)}.`);
  }
  return { allowed: blockers.length === 0, blockers };
}

// Notary état détaillé sum check
export function validateEtatDetaille(montant_global: number, lignes: { montant: number }[]): ValidationResult {
  const sum = lignes.reduce((s, l) => s + l.montant, 0);
  if (Math.abs(sum - montant_global) > 0.01) {
    return { valid: false, errors: [`Écart état détaillé : somme lignes ${formatDA(sum)} ≠ montant chèque ${formatDA(montant_global)}.`] };
  }
  return { valid: true, errors: [] };
}

// RF mode constraints for dropdowns
export function getAllowedModes(rf: 'RF1' | 'RF2'): string[] {
  return rf === 'RF1' ? ['CHEQUE', 'VIREMENT', 'CHEQUE_NOTAIRE'] : ['ESPECES'];
}

// Salary minimum check
export function validateSalary(base: number): ValidationResult {
  if (base < 20000) {
    return { valid: false, errors: ['Le salaire de base doit être ≥ 20 000 DA (SNMG).'] };
  }
  return { valid: true, errors: [] };
}

// NIN format check (18 digits)
export function validateNIN(nin: string): boolean {
  return /^\d{18}$/.test(nin);
}

// RIB format check (20 digits)
export function validateRIB(rib: string): boolean {
  return /^\d{20}$/.test(rib);
}

// Age constraint (16-70)
export function validateAge(birthDate: string): ValidationResult {
  const age = Math.floor((Date.now() - new Date(birthDate).getTime()) / (365.25 * 24 * 3600 * 1000));
  if (age < 16 || age > 70) return { valid: false, errors: [`Âge ${age} ans hors limites (16-70).`] };
  return { valid: true, errors: [] };
}
