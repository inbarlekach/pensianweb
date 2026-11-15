"""Template-based stand-in for an LLM. Output is marked generated_by="template" and the
UI labels it as NOT produced by an AI model."""
from __future__ import annotations

from .base import AgentOutput, AnalysisInput, FeeAnalystAgent, WordedFinding
from .fmt import ils, pct


class TemplateAgent(FeeAnalystAgent):
    def analyze(self, inp: AnalysisInput) -> AgentOutput:
        c = {k: v.value for k, v in inp.calcs.items()}
        out = []
        for d in inp.drafts:
            f = d.facts
            if d.kind == "insufficient":
                out.append(WordedFinding(
                    finding_id=d.finding_id,
                    title="אין מספיק מידע להשוואה אמינה",
                    finding="לא ניתן היה להשוות את דמי הניהול שלך לנתוני שוק עדכניים.",
                    explanation="הסיבות: " + " ".join(f.get("reasons", [])),
                    next_step="אפשר לבדוק את דמי הניהול שלך מול המחשבון הרשמי של רשות שוק ההון, או לנסות שוב לאחר רענון הנתונים."))
            elif d.kind == "no_material_gap":
                out.append(WordedFinding(
                    finding_id=d.finding_id,
                    title="לא נמצא פער משמעותי בדמי הניהול",
                    finding=f"דמי הניהול שלך ({pct(c['cur_dep'])} מההפקדות, {pct(c['cur_acc'])} מהצבירה) קרובים לממוצעים בשוק.",
                    explanation=f"החיסכון המשוער מול הקרן הזולה ביותר בנתונים הוא {ils(c['alt1_y1'])} בשנה – מתחת לסף המשמעותיות שהוגדר.",
                    next_step="אין צורך בפעולה דחופה בנושא דמי הניהול. כדאי לבדוק שוב מדי שנה."))
            elif d.kind == "fee_gap_negotiate":
                lead = ("דמי הניהול שלך גבוהים מהממוצע שנגבה בפועל בכל אחת מהקרנות המקיפות שנבדקו."
                        if f.get("costlier_than_all") else
                        "דמי הניהול שלך גבוהים מהממוצע שנגבה בפועל ברוב הקרנות המקיפות שנבדקו.")
                out.append(WordedFinding(
                    finding_id=d.finding_id,
                    title="כדאי לבקש מהקרן הנוכחית הפחתה בדמי הניהול",
                    finding=f"{lead} אתה משלם {pct(c['cur_dep'])} מההפקדות ו-{pct(c['cur_acc'])} מהצבירה.",
                    explanation=(f"בקרן שנמצאת באמצע הדירוג ({f['median_fund']}) הממוצע הוא {pct(c['median_dep'])} מההפקדות ו-{pct(c['median_acc'])} מהצבירה. "
                                 f"אילו קיבלת תנאים כאלה, היית חוסך כ-{ils(c['median_y1'])} בשנה הראשונה, "
                                 f"והצבירה בפרישה הייתה גבוהה בכ-{ils(c['median_gap_central'])} בתרחיש המרכזי "
                                 f"(בין {ils(c['median_gap_conservative'])} ל-{ils(c['median_gap_optimistic'])} בתרחישים האחרים)."),
                    next_step="לפנות לקרן הפנסיה (או למחלקת משאבי אנוש) ולבקש הצעה מעודכנת לדמי ניהול. זו פעולה ללא סיכון: אין בה מעבר קרן ואין בה שינוי בכיסוי הביטוחי."))
            elif d.kind == "verify_fees":
                out.append(WordedFinding(
                    finding_id=d.finding_id,
                    title="לוודא מהם דמי הניהול שאתה משלם בפועל",
                    finding=f"הניתוח מבוסס על דמי ניהול של {pct(c['cur_dep'])} מההפקדות ו-{pct(c['cur_acc'])} מהצבירה.",
                    explanation="דמי הניהול מופיעים בדוח השנתי או הרבעוני של הקרן. לפעמים הנחה ניתנת לתקופה מוגבלת ומסתיימת בלי הודעה.",
                    next_step="לבדוק בדוח האחרון של הקרן או באזור האישי באתר הקרן מהם דמי הניהול בפועל ומתי מסתיימת הנחה, אם יש."))
            elif d.kind == "fee_gap_switch":
                i = d.finding_id.rsplit("-", 1)[-1]
                out.append(WordedFinding(
                    finding_id=d.finding_id,
                    title=f"לבחון מעבר ל{f['fund']}",
                    finding=f"הממוצע שנגבה בפועל ב{f['fund']} הוא {pct(c[f'alt{i}_dep'])} מההפקדות ו-{pct(c[f'alt{i}_acc'])} מהצבירה.",
                    explanation=(f"אילו קיבלת תנאים בגובה הממוצע הזה, החיסכון המשוער בשנה הראשונה הוא כ-{ils(c[f'alt{i}_y1'])}, "
                                 f"והפער בצבירה בפרישה הוא כ-{ils(c[f'alt{i}_gap_central'])} בתרחיש המרכזי "
                                 f"(בין {ils(c[f'alt{i}_gap_conservative'])} ל-{ils(c[f'alt{i}_gap_optimistic'])}). "
                                 "זה ממוצע שנגבה מכלל העמיתים, לא הצעה עבורך."),
                    next_step=f"לבקש מ{f['fund']} הצעה אישית בכתב, ולבדוק לפני מעבר את ההשלכות על הכיסוי הביטוחי. מומלץ להתייעץ עם יועץ פנסיוני מורשה."))
        return AgentOutput(generated_by="template", provider="template-v1", findings=out)
