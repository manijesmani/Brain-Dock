import type { Plan } from "@/types/domain";

/** The account kinds by their Persian names, as the admin shows them too. */
export const PLAN_LABELS: Record<Plan, string> = {
  guest: "مهمان",
  free: "عادی",
  premium: "ویژه",
  owner: "مالک",
};
