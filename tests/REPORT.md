# דוח מקרי בדיקה

נוצר אוטומטית: 2026-11-22 11:05. הקובץ נכתב מחדש בכל ריצה של pytest.

- **סה"כ מקרים:** 142 · **עברו:** 142 · **נכשלו:** 0
- **טעויות שקטות** (כשל במקרה שבודק שדה קריטי): 0 מתוך 60 מקרים קריטיים
- **התראות שווא** (נוצרה הזדמנות במקרה שבו אין לצפות לה): 0 מתוך 4 מקרי ביקורת (0%)

> **מגבלה:** הצלחה במקרי הבדיקה מראה שהמערכת מתנהגת כמצופה במקרים שהוגדרו. אין בה הוכחה לשיעור דיוק בעולם האמיתי.
> מערך הבדיקה אינו מדגם מייצג של חוסכים.

## לפי קטגוריה

| קטגוריה | מקרים | עברו |
|---|---|---|
| 01 חישובי דמי ניהול | 25 | 25 |
| 02 תחזית שלושה תרחישים | 15 | 15 |
| 03 רגישות לשינויי קלט | 10 | 10 |
| 04 נתונים חסרים | 10 | 10 |
| 05 נתונים לא עקביים | 8 | 8 |
| 06 כשלים באיסוף נתונים | 8 | 8 |
| 07 מקרי קצה וקלט לא תקין | 13 | 13 |
| 08 מקורות לא מעודכנים | 7 | 7 |
| 09 זכאות לא ניתנת לאימות | 5 | 5 |
| 10 אין השוואה אמינה | 5 | 5 |
| 11 ראיון ובניית פרופיל | 24 | 24 |
| 13 תצוגה ברורה ללא ידע פנסיוני | 12 | 12 |

## פירוט

### 01 חישובי דמי ניהול

| מקרה | תיאור (קלט ← תוצאה צפויה) | תוצאה בפועל |
|---|---|---|
| `test_no_return_no_fees_is_sum_of_deposits` 🔒 | תשואה 0, ללא דמי ניהול ← צבירה = צבירה התחלתית + סכום ההפקדות | ✅ עבר |
| `test_deposit_fee_only_zero_return` 🔒 | 1,000 ₪ × 12, דמי הפקדה 2% ← דמי ניהול 240 ₪, צבירה 11,760 ₪ | ✅ עבר |
| `test_deposit_fee_at_legal_max` 🔒 | דמי הפקדה 6% (תקרה), 1,000 ₪ × 12 ← צבירה 11,280 ₪ | ✅ עבר |
| `test_accumulation_fee_only_no_deposits` 🔒 | 100,000 ₪, דמי צבירה 0.30%, שנה ← 100,000 × (1−0.003/12)^12 | ✅ עבר |
| `test_accumulation_fee_at_legal_max` 🔒 | דמי צבירה 0.5% (תקרה), 200,000 ₪, שנה ← 200,000 × (1−0.005/12)^12 | ✅ עבר |
| `test_monthly_rate_compounds_to_annual` | תשואה חודשית שקולה ל-3.5% שנתי ← (1+r_m)^12 = 1.035 | ✅ עבר |
| `test_return_no_fees_matches_annuity_formula` 🔒 | 50,000 ₪ + 2,000 ₪ לחודש, 10 שנים, 4% ← נוסחת אנונה סגורה | ✅ עבר |
| `test_full_engine_matches_closed_form[420000-3330-348-0.02-2.0-0.3]` 🔒 | מנוע מלא (הפקדה + צבירה + תשואה) ← תואם נוסחה סגורה בדיוק 1e-12 | ✅ עבר |
| `test_full_engine_matches_closed_form[420000-3330-348-0.035-2.0-0.3]` 🔒 | מנוע מלא (הפקדה + צבירה + תשואה) ← תואם נוסחה סגורה בדיוק 1e-12 | ✅ עבר |
| `test_full_engine_matches_closed_form[420000-3330-348-0.05-2.0-0.3]` 🔒 | מנוע מלא (הפקדה + צבירה + תשואה) ← תואם נוסחה סגורה בדיוק 1e-12 | ✅ עבר |
| `test_full_engine_matches_closed_form[420000-3330-348-0.035-1.39-0.1]` 🔒 | מנוע מלא (הפקדה + צבירה + תשואה) ← תואם נוסחה סגורה בדיוק 1e-12 | ✅ עבר |
| `test_full_engine_matches_closed_form[0-5000-240-0.03-6.0-0.5]` 🔒 | מנוע מלא (הפקדה + צבירה + תשואה) ← תואם נוסחה סגורה בדיוק 1e-12 | ✅ עבר |
| `test_full_engine_matches_closed_form[1000000-0-60-0.04-0-0.25]` 🔒 | מנוע מלא (הפקדה + צבירה + תשואה) ← תואם נוסחה סגורה בדיוק 1e-12 | ✅ עבר |
| `test_full_engine_matches_closed_form[10000-1-12--0.05-1.0-0.1]` 🔒 | מנוע מלא (הפקדה + צבירה + תשואה) ← תואם נוסחה סגורה בדיוק 1e-12 | ✅ עבר |
| `test_one_month_by_hand` | חודש אחד: 1,000 + 100×0.99, תשואה 12% שנתי, צבירה 0.12% ← חישוב ידני | ✅ עבר |
| `test_zero_months_keeps_balance` | 0 חודשים ← הצבירה לא משתנה ואין דמי ניהול | ✅ עבר |
| `test_fees_reconcile_with_balance_when_zero_return` | תשואה 0 ← צבירה סופית + סך דמי ניהול = צבירה התחלתית + סך הפקדות | ✅ עבר |
| `test_total_fees_is_sum_of_components` | סך דמי ניהול = רכיב הפקדות + רכיב צבירה | ✅ עבר |
| `test_salary_growth_raises_deposit_yearly` | הפקדה 1,000 ₪, צמיחת שכר 10% ← שנה ב׳ מפקידה 1,100 ₪ לחודש | ✅ עבר |
| `test_yearly_balances_length` | 348 חודשים ← 29 ערכי צבירה שנתיים, האחרון = הצבירה הסופית | ✅ עבר |
| `test_yearly_balance_matches_closed_form_at_year_10` | צבירה בסוף שנה 10 ← נוסחה סגורה עם n=120 | ✅ עבר |
| `test_ido_monthly_deposit_and_horizon` 🔒 | שכר 18,000 ₪ × 18.5% ← הפקדה 3,330 ₪; גיל 38→67 ← 348 חודשים | ✅ עבר |
| `test_ido_first_year_deposit_fee_saving_vs_alternative` 🔒 | 2.00%→1.39% מההפקדות ← חיסכון 3,330×12×0.61% = 243.756 ₪; רכיב הצבירה שלילי קטן | ✅ עבר |
| `test_first_year_deposit_saving_one_point` 🔒 | 2.00%→1.00% מההפקדות ← חיסכון בשנה הראשונה 399.6 ₪ ברכיב ההפקדות | ✅ עבר |
| `test_accumulation_saving_without_deposits` 🔒 | 420,000 ₪ ללא הפקדות, 0.30%→0.15%, תשואה 0 ← הפרש לפי נוסחה סגורה | ✅ עבר |

### 02 תחזית שלושה תרחישים

| מקרה | תיאור (קלט ← תוצאה צפויה) | תוצאה בפועל |
|---|---|---|
| `test_identical_terms_give_zero_gap` 🔕 | תנאים זהים ← פער 0 בכל שלושת התרחישים | ✅ עבר |
| `test_cheaper_terms_gap_positive_and_grows_with_return` 🔒 | תנאים זולים יותר ← פער חיובי, שמרני < מרכזי < אופטימי | ✅ עבר |
| `test_gap_matches_closed_form_difference[conservative-0.02]` 🔒 | פער בגיל 67 בכל תרחיש ← הפרש בין שתי נוסחאות סגורות | ✅ עבר |
| `test_gap_matches_closed_form_difference[central-0.035]` 🔒 | פער בגיל 67 בכל תרחיש ← הפרש בין שתי נוסחאות סגורות | ✅ עבר |
| `test_gap_matches_closed_form_difference[optimistic-0.05]` 🔒 | פער בגיל 67 בכל תרחיש ← הפרש בין שתי נוסחאות סגורות | ✅ עבר |
| `test_more_expensive_alternative_gives_negative_gap` | חלופה יקרה יותר ← פער שלילי | ✅ עבר |
| `test_first_year_saving_uses_central_scenario_only` | שינוי התשואה השמרנית ← אינו משנה את החיסכון בשנה הראשונה | ✅ עבר |
| `test_empty_scenarios_rejected` | אין תרחישים ← שגיאה מפורשת | ✅ עבר |
| `test_pipeline_returns_three_scenarios_in_order` | ניתוח עידו ← שלושה תרחישים: שמרני, מרכזי, אופטימי | ✅ עבר |
| `test_pipeline_yearly_series_length` | גיל 38→67 ← 29 נקודות שנתיות לכל סדרה | ✅ עבר |
| `test_pipeline_gap_equals_difference` 🔒 | בכל תרחיש ← פער = צבירה חלופית − צבירה נוכחית (בעיגול לשקל) | ✅ עבר |
| `test_pipeline_compared_fund_is_top_alternative` | הקרן בגרף ← הקרן של ממצא המעבר הראשון (הפער הגדול ביותר) | ✅ עבר |
| `test_pipeline_retirement_60_shortens_series` | גיל פרישה 60 ← 22 נקודות שנתיות | ✅ עבר |
| `test_pipeline_balance_increases_with_return` | צבירה בתנאים נוכחיים ← שמרני < מרכזי < אופטימי | ✅ עבר |
| `test_pipeline_central_return_from_assumptions` | שינוי התשואה המרכזית בקובץ ההנחות ← שינוי בפער המרכזי | ✅ עבר |

### 03 רגישות לשינויי קלט

| מקרה | תיאור (קלט ← תוצאה צפויה) | תוצאה בפועל |
|---|---|---|
| `test_higher_salary_bigger_gap` | שכר גבוה יותר ← פער גדול יותר | ✅ עבר |
| `test_higher_balance_bigger_gap` | צבירה גבוהה יותר ← פער גדול יותר | ✅ עבר |
| `test_later_retirement_bigger_gap` | פרישה מאוחרת יותר ← פער גדול יותר | ✅ עבר |
| `test_older_age_smaller_gap` | גיל מבוגר יותר (אותה צבירה) ← פער קטן יותר | ✅ עבר |
| `test_higher_contribution_bigger_deposit_saving` | שיעור הפקדה 20.5% ← חיסכון גדול יותר ברכיב ההפקדות | ✅ עבר |
| `test_salary_growth_bigger_gap` | צמיחת שכר ריאלית 1% ← פער גדול יותר | ✅ עבר |
| `test_equal_deposit_fee_only_accumulation_component` 🔒 | דמי הפקדה זהים ← החיסכון ברכיב ההפקדות כמעט 0 (רק השפעה עקיפה של הצבירה) | ✅ עבר |
| `test_smaller_accumulation_diff_smaller_gap` | פער קטן יותר בדמי הצבירה ← פער מצטבר קטן יותר | ✅ עבר |
| `test_double_deposit_diff_doubles_deposit_saving` 🔒 | הכפלת ההפרש בדמי ההפקדה ← הכפלת החיסכון ברכיב ההפקדות | ✅ עבר |
| `test_gap_monotonic_in_return` | תשואות 0%..6% ← פער עולה באופן מונוטוני | ✅ עבר |

### 04 נתונים חסרים

| מקרה | תיאור (קלט ← תוצאה צפויה) | תוצאה בפועל |
|---|---|---|
| `test_missing_profile_field_blocks_analysis[age]` 🔒 | שדה פרופיל חסר ← invalid_input, אין ממצאים, השדה מזוהה ומוזכר בעברית בשגיאה | ✅ עבר |
| `test_missing_profile_field_blocks_analysis[deposit_fee_pct]` 🔒 | שדה פרופיל חסר ← invalid_input, אין ממצאים, השדה מזוהה ומוזכר בעברית בשגיאה | ✅ עבר |
| `test_missing_profile_field_blocks_analysis[accumulation_fee_pct]` 🔒 | שדה פרופיל חסר ← invalid_input, אין ממצאים, השדה מזוהה ומוזכר בעברית בשגיאה | ✅ עבר |
| `test_missing_profile_field_blocks_analysis[gross_monthly_salary]` 🔒 | שדה פרופיל חסר ← invalid_input, אין ממצאים, השדה מזוהה ומוזכר בעברית בשגיאה | ✅ עבר |
| `test_missing_profile_field_blocks_analysis[accumulated_balance]` 🔒 | שדה פרופיל חסר ← invalid_input, אין ממצאים, השדה מזוהה ומוזכר בעברית בשגיאה | ✅ עבר |
| `test_no_snapshot_is_insufficient` 🔒 | אין נתוני שוק ← insufficient, ממצא יחיד ברמת ודאות 3, אין תרחישים | ✅ עבר |
| `test_empty_funds_is_insufficient` | snapshot ללא קרנות ← insufficient | ✅ עבר |
| `test_snapshot_without_period_is_insufficient` | snapshot בלי תקופת דיווח ← insufficient | ✅ עבר |
| `test_parse_rejects_missing_fees` | רשומה ללא דמי ניהול ← נפסלת עם סיבה, לא נכללת | ✅ עבר |
| `test_parse_rejects_missing_fund_id` | רשומה ללא FUND_ID ← נפסלת | ✅ עבר |

### 05 נתונים לא עקביים

| מקרה | תיאור (קלט ← תוצאה צפויה) | תוצאה בפועל |
|---|---|---|
| `test_retirement_not_after_age` | גיל 67, פרישה 67 ← invalid_input | ✅ עבר |
| `test_deposit_fee_above_cap` 🔒 | דמי הפקדה 7% (מעל התקרה) ← invalid_input, לא ממצא | ✅ עבר |
| `test_accumulation_fee_above_cap` 🔒 | דמי צבירה 0.6% (מעל התקרה) ← invalid_input | ✅ עבר |
| `test_negative_salary` | שכר שלילי ← invalid_input | ✅ עבר |
| `test_parse_tracks_with_different_fees_not_comparable` | שני מסלולים של אותה קרן עם דמי ניהול שונים ← הקרן לא ברת-השוואה | ✅ עבר |
| `test_parse_duplicate_row_rejected` | אותו מסלול ואותה תקופה פעמיים ← הכפילות נפסלת | ✅ עבר |
| `test_parse_invalid_period_rejected` | תקופת דיווח 202613 ← נפסלת | ✅ עבר |
| `test_future_period_not_usable` | תקופת דיווח עתידית ← הנתונים לא בשימוש, insufficient | ✅ עבר |

### 06 כשלים באיסוף נתונים

| מקרה | תיאור (קלט ← תוצאה צפויה) | תוצאה בפועל |
|---|---|---|
| `test_success_writes_snapshot` 🔒 | תשובה תקינה ← נוצרים snapshot ו-manifest, נכללות 2 קרנות מקיפות בלבד | ✅ עבר |
| `test_http_500_keeps_previous_snapshot` 🔒 | רענון מוצלח ואחריו HTTP 500 ← ה-snapshot הקודם נשאר, הניסיון מסומן failed | ✅ עבר |
| `test_timeout_fails` | Timeout ברשת ← failed, אין snapshot | ✅ עבר |
| `test_api_success_false_fails` | ה-API מחזיר success=false ← failed | ✅ עבר |
| `test_schema_change_fails` | עמודת דמי ניהול נעלמה מהמקור ← failed עם הודעה על שינוי מבנה | ✅ עבר |
| `test_partial_download_fails` | התקבלו פחות רשומות מה-total ← failed (לא נשמר מידע חלקי) | ✅ עבר |
| `test_no_in_scope_funds_fails` | רק קרנות כלליות במקור ← failed | ✅ עבר |
| `test_ui_warned_after_failed_refresh` 🔒 | רענון נכשל אחרי הצלחה ← הניתוח רץ על הנתונים הקודמים ומסמן last_refresh_failed | ✅ עבר |

### 07 מקרי קצה וקלט לא תקין

| מקרה | תיאור (קלט ← תוצאה צפויה) | תוצאה בפועל |
|---|---|---|
| `test_invalid_fees_rejected[-1-0.3]` | דמי ניהול שליליים / 100% / NaN / חסרים ← שגיאה | ✅ עבר |
| `test_invalid_fees_rejected[2.0--0.1]` | דמי ניהול שליליים / 100% / NaN / חסרים ← שגיאה | ✅ עבר |
| `test_invalid_fees_rejected[100-0.3]` | דמי ניהול שליליים / 100% / NaN / חסרים ← שגיאה | ✅ עבר |
| `test_invalid_fees_rejected[nan-0.3]` | דמי ניהול שליליים / 100% / NaN / חסרים ← שגיאה | ✅ עבר |
| `test_invalid_fees_rejected[None-0.3]` | דמי ניהול שליליים / 100% / NaN / חסרים ← שגיאה | ✅ עבר |
| `test_invalid_sim_input_rejected[kwargs0]` | צבירה/הפקדה/חודשים שליליים או תשואה −100% ← שגיאה | ✅ עבר |
| `test_invalid_sim_input_rejected[kwargs1]` | צבירה/הפקדה/חודשים שליליים או תשואה −100% ← שגיאה | ✅ עבר |
| `test_invalid_sim_input_rejected[kwargs2]` | צבירה/הפקדה/חודשים שליליים או תשואה −100% ← שגיאה | ✅ עבר |
| `test_invalid_sim_input_rejected[kwargs3]` | צבירה/הפקדה/חודשים שליליים או תשואה −100% ← שגיאה | ✅ עבר |
| `test_retirement_age_not_after_age_rejected` | גיל פרישה = גיל נוכחי ← שגיאה | ✅ עבר |
| `test_contribution_rate_out_of_range_rejected` | שיעור הפקדה 18.5 (אחוז במקום שבר) ← שגיאה | ✅ עבר |
| `test_guard_blocks_dropped_finding` | הסוכן משמיט ממצא ← הניתוח נכשל, לא מוצגות תוצאות | ✅ עבר |
| `test_guard_blocks_empty_field` | הסוכן מחזיר הסבר ריק ← הניתוח נכשל | ✅ עבר |

### 08 מקורות לא מעודכנים

| מקרה | תיאור (קלט ← תוצאה צפויה) | תוצאה בפועל |
|---|---|---|
| `test_two_month_lag_is_fresh` | תקופה 09/2026, היום 11/2026 ← פיגור 2, ניתוח מלא | ✅ עבר |
| `test_lag_equal_threshold_is_fresh` | פיגור של 4 חודשים (בדיוק הסף) ← עדיין עדכני | ✅ עבר |
| `test_lag_above_threshold_is_stale` 🔒 | פיגור 5 חודשים ← insufficient, ודאות 3 | ✅ עבר |
| `test_stale_shows_no_money` 🔒 | נתונים ישנים ← אין תרחישים ואין סכומים בתוכנית הפעולה | ✅ עבר |
| `test_lag_across_year_boundary` | תקופה 11/2026, היום 01/2027 ← פיגור 2 | ✅ עבר |
| `test_parse_rejects_track_missing_latest_period` | מסלול שלא דווח בתקופה האחרונה ← נפסל ולא נכלל | ✅ עבר |
| `test_stale_message_names_period` | נתונים ישנים ← ההודעה מציינת את תקופת הדיווח | ✅ עבר |

### 09 זכאות לא ניתנת לאימות

| מקרה | תיאור (קלט ← תוצאה צפויה) | תוצאה בפועל |
|---|---|---|
| `test_never_certainty_one` 🔒 | נתוני שוק = ממוצעים ← אף ממצא אינו ברמת ודאות 1 | ✅ עבר |
| `test_switch_limitations_say_not_an_offer` | ממצא מעבר ← המגבלות מציינות שזה ממוצע ולא הצעה | ✅ עבר |
| `test_switch_text_says_not_an_offer` | ממצא מעבר ← ההסבר עצמו אומר 'לא הצעה עבורך' | ✅ עבר |
| `test_risk_levels` 🔒 | פנייה לקרן הנוכחית ← סיכון נמוך; מעבר קרן ← סיכון גבוה | ✅ עבר |
| `test_low_risk_ranked_first_even_if_less_money` 🔒 | פעולה בסיכון נמוך עם סכום קטן ← מדורגת לפני פעולה בסיכון גבוה עם סכום גדול | ✅ עבר |

### 10 אין השוואה אמינה

| מקרה | תיאור (קלט ← תוצאה צפויה) | תוצאה בפועל |
|---|---|---|
| `test_all_funds_not_comparable` | כל הקרנות לא ברות-השוואה ← insufficient | ✅ עבר |
| `test_cheaper_than_market_no_opportunity` 🔕 | עידו משלם 0.5%/0.05% (זול מכולם) ← 'לא נמצא פער', בלי המלצת מעבר | ✅ עבר |
| `test_identical_to_market_no_opportunity` 🔕 | שוק עם קרן אחת בתנאים זהים לעידו ← 'לא נמצא פער' | ✅ עבר |
| `test_guard_blocks_invented_number` 🔒 | הסוכן מוסיף סכום שלא חושב (999,999 ₪) ← הניתוח נכשל, אין תוצאות | ✅ עבר |
| `test_agent_exception_fails_cleanly` | ספק הניסוח זורק שגיאה ← הניתוח נכשל, לא מוצגת תוצאה חלקית | ✅ עבר |

### 11 ראיון ובניית פרופיל

| מקרה | תיאור (קלט ← תוצאה צפויה) | תוצאה בפועל |
|---|---|---|
| `test_parse_number_formats[18,000-18000]` 🔒 | פורמטים שונים של סכום ← ערך מספרי נכון | ✅ עבר |
| `test_parse_number_formats[18000 \u20aa-18000]` 🔒 | פורמטים שונים של סכום ← ערך מספרי נכון | ✅ עבר |
| `test_parse_number_formats[18 \u05d0\u05dc\u05e3-18000]` 🔒 | פורמטים שונים של סכום ← ערך מספרי נכון | ✅ עבר |
| `test_parse_number_formats[18k-18000]` 🔒 | פורמטים שונים של סכום ← ערך מספרי נכון | ✅ עבר |
| `test_parse_number_formats[\u05db-420 \u05d0\u05dc\u05e3-420000]` 🔒 | פורמטים שונים של סכום ← ערך מספרי נכון | ✅ עבר |
| `test_parse_number_formats[1.2 \u05de\u05d9\u05dc\u05d9\u05d5\u05df-1200000]` 🔒 | פורמטים שונים של סכום ← ערך מספרי נכון | ✅ עבר |
| `test_parse_number_formats[0,3-0.3]` 🔒 | פורמטים שונים של סכום ← ערך מספרי נכון | ✅ עבר |
| `test_parse_number_formats[\u20aa 3,330 \u05e9"\u05d7-3330]` 🔒 | פורמטים שונים של סכום ← ערך מספרי נכון | ✅ עבר |
| `test_parse_number_rejects_ambiguous[\u05d1\u05e2\u05e8\u05da \u05d4\u05e8\u05d1\u05d4]` | תשובה בלי מספר או עם שני מספרים ← נדחית, לא מנחשים | ✅ עבר |
| `test_parse_number_rejects_ambiguous[18-20 \u05d0\u05dc\u05e3]` | תשובה בלי מספר או עם שני מספרים ← נדחית, לא מנחשים | ✅ עבר |
| `test_parse_number_rejects_ambiguous[]` | תשובה בלי מספר או עם שני מספרים ← נדחית, לא מנחשים | ✅ עבר |
| `test_fee_above_legal_cap_rejected` 🔒 | דמי צבירה 3% (מעל התקרה 0.5%) ← נדחה עם הסבר | ✅ עבר |
| `test_percent_field_ignores_thousand_word` | שדה אחוזים ← מילת 'אלף' לא מכפילה את הערך | ✅ עבר |
| `test_retirement_must_follow_age` | גיל 45, פרישה 40 ← נדחה | ✅ עבר |
| `test_full_chat_builds_profile_matching_answers` 🔒 | שיחה מלאה עם ערכי עידו ← פרופיל עם אותם ערכים בדיוק | ✅ עבר |
| `test_chat_profile_gives_same_analysis_as_demo` 🔒 | פרופיל מהשיחה עם ערכי עידו ← אותם ממצאים וסכומים כמו פרופיל ההדגמה | ✅ עבר |
| `test_chat_profile_changes_results` 🔒 | שכר וצבירה שונים בשיחה ← פער שונה בתוצאות (הפרופיל משפיע על הניתוח) | ✅ עבר |
| `test_single_skips_spouse_question` | מצב משפחתי רווק/ה ← לא נשאלת שאלה על בן/בת זוג | ✅ עבר |
| `test_invalid_answer_reasks_same_question` | תשובה לא תקינה לגיל ← אותה שאלה שוב, הערך לא נשמר | ✅ עבר |
| `test_unknown_fee_offers_help_then_continue_without` | 'לא יודע' לדמי ניהול ← הסבר איפה למצוא + אפשרות להמשיך בלי הנתון | ✅ עבר |
| `test_missing_fee_blocks_analysis` 🔒 | המשך בלי דמי הפקדה ← הפרופיל נוצר אבל הניתוח נחסם ומציין את השדה | ✅ עבר |
| `test_edit_field_from_summary` | תיקון שכר מהסיכום ← חוזר לשאלה, מעדכן וחוזר לסיכום | ✅ עבר |
| `test_restart_clears_answers` | 'התחל מחדש' ← כל התשובות נמחקות | ✅ עבר |
| `test_first_message_warns_against_real_data` | הודעת הפתיחה ← אזהרה לא להזין נתונים אמיתיים | ✅ עבר |

### 13 תצוגה ברורה ללא ידע פנסיוני

| מקרה | תיאור (קלט ← תוצאה צפויה) | תוצאה בפועל |
|---|---|---|
| `test_first_year_deposit_fees_by_hand` 🔒 | הפקדה 3,330 ₪ × 12 חודשים × 2.00% ← 799.2 ₪ דמי ניהול מההפקדות (מעוגל 799) | ✅ עבר |
| `test_first_year_accumulation_fees_within_hand_bounds` 🔒 | צבירה 420,000 ₪ ו-0.30% ← בין 0.30% מהצבירה ההתחלתית (1,260) לבין 0.30% מהצבירה המקסימלית האפשרית (≈1,426) | ✅ עבר |
| `test_total_is_sum_of_parts` 🔒 | סך דמי הניהול בשנה = בדיוק רכיב ההפקדות + רכיב הצבירה כפי שמוצגים (בלי הפרש עיגול גלוי) | ✅ עבר |
| `test_per_1000_and_per_100k_examples` 🔒 | 2.00% מההפקדות ← 20 ₪ מכל 1,000; 0.30% מהצבירה ← 300 ₪ בשנה מכל 100,000 | ✅ עבר |
| `test_examples_are_marked_as_facts_and_totals_as_estimates` | הדוגמאות לפי אחוזים ← עובדה; הסכום השנתי ← הערכה | ✅ עבר |
| `test_verdict_higher_than_all` 🔒 | עידו מול 5 קרנות זולות יותר ← 'גבוה מכולן' | ✅ עבר |
| `test_verdict_lower_when_cheapest` 🔒 🔕 | דמי ניהול זולים מכולם ← 'lower', בלי הזדמנות | ✅ עבר |
| `test_verdict_mixed_and_most` | קרן אחת זולה מתוך חמש ← 'mixed'; שלוש מתוך חמש ← 'higher_than_most' | ✅ עבר |
| `test_no_new_numbers_break_the_guard` | המספרים החדשים לא מופיעים בטקסט הסוכן ← הניתוח עדיין עובר את בדיקת המספרים | ✅ עבר |
| `test_insufficient_data_has_no_fee_amounts` | אין נתוני שוק ← אין סכומי דמי ניהול מוצגים (לא ממציאים) | ✅ עבר |
| `test_html_has_detail_window_and_term_buttons` | ה-HTML ← יש חלון פירוט (dialog), ומונחי הפרופיל הם כפתורים ולא רמזי עכבר בלבד | ✅ עבר |
| `test_every_inline_term_has_a_glossary_entry` | כל מונח שמסומן ב-data-term או ב-term() בקוד ← קיים במילון | ✅ עבר |

🔒 = שדה קריטי · 🔕 = מקרה ביקורת להתראות שווא
