# Late-2023 source structure and extraction feasibility

Assessment date: 2026-08-29  
Scope: October-December 2023 sources only; no extraction and no canonical-data changes.

## Decision

**Recommended next action: `EXTRACT_OCT_NOV_ONLY_DEC_UNAVAILABLE`.**

October and November are defensible full monthly coded sources. The supplied December Flash Report is only a 20-page executive summary with selected Tables A-F and has no full-population project table. The quarterly report is a full coded quarter-end source, but it should not be substituted for the December monthly source: it reports 1,897 projects versus the December Flash Report's 1,820 and organizes the population across status-specific annexures with non-uniform fields. It can be retained as a separately dated quarterly source for a future, explicitly authorized extraction.

## Source comparison

| Source | Classification | Reference date | Population and rows | Row-level source code | Project-level fields | Jan-2024 continuity |
|---|---|---|---|---|---|---|
| October 2023 Flash Report | `FULL_MONTHLY_CODED` | October 2023; month-end presentation is also labelled `as on 31.10.2023` / cost analysis `01.11.2023` | Full ongoing Rs 150 crore+ population. The detail table runs on physical PDF pages 92-215 and contains exactly **1,788 rows and 1,788 distinct codes**, matching the executive summary. | Yes: legacy `N########` and nine-digit codes are printed in each project cell. | Approval; original/revised/anticipated completion; original/revised/anticipated cost; cumulative expenditure; milestones achieved/total. Agency and state are printed with the code; sector is a source heading. No physical-progress percentage. | Defensible exact-code matching. Oct-Nov overlap is 1,773. |
| November 2023 Flash Report | `FULL_MONTHLY_CODED` | November 2023; month-end presentation is also labelled `as on 30.11.2023` / cost analysis `01.12.2023` | Full ongoing Rs 150 crore+ population. The detail table runs on physical PDF pages 417-541 and contains exactly **1,831 rows and 1,831 distinct codes**, matching the executive summary. | Yes, in the same row-level legacy form. | Same full monthly field structure as October: approval, cost/date triplets, expenditure, and milestone counts; agency/state in the project cell and sector headings. No physical-progress percentage. | Defensible exact-code matching. November-January overlap is 1,786, although December monthly data are absent. |
| December 2023 Flash Report (20 pages) | `SUMMARY_ONLY` | December 2023; aggregate tables are `as on 01.01.2024` | Reports **1,820** monitored projects only in aggregate. Pages 6-20 contain selected maximum-five/earliest-project Tables A-F, not a full population. | No row-level codes anywhere in the file. | Selected tables contain subsets of cost/date/expenditure attributes, but not a project-month population. | No project-level longitudinal matching is possible. |
| QPISR October-December 2023 | `FULL_QUARTERLY_CODED` | Explicit quarter ending **31.12.2023**; cover says October-December 2023 (QTR-3) | Reports **1,897** projects. The project annexures partition the full population into 902 delayed, 56 ahead, 632 on-schedule, 274 without a reported date of commissioning, and 33 without an original date: total 1,897. Exactly **1,897 distinct source codes** are printed across these lists. | Yes: row-level legacy codes. Agency/state accompany the code and sector is a source heading. | Original/revised cost, anticipated cost, completion dates and expenditure exist across the project annexures, but availability is layout/category dependent. Milestone/delay information appears in some annexures; there is no uniform physical-progress percentage. | Strong code continuity: 1,799 of 1,897 quarterly codes occur in January 2024. This supports it as a separate quarter-end source, not as proof that it is the missing December monthly table. |
| January 2024 accepted monthly source | `FULL_MONTHLY_CODED` | January 2024 | 1,821 coded rows in the accepted `legacy-detail-ongoing-nine-column-milestones-v1` layout. | Yes. | Same general full-monthly detail semantics as October/November. | Boundary comparator only; no data changed in this assessment. |

## Quarterly Part-I and project annexures

- The supplied quarterly PDF contains a labelled **Part-I overview** (starting at physical page 10). It is aggregate/analytical and is not itself a row-level canonical table.
- The **project annexures** begin after the annexure divider at physical page 82. They collectively cover the 1,897-project population in separate status-based tables and provide defensible source codes.
- No separately labelled **Part-II** document is present under `data/raw/2023/`. The annexure portion should not be represented as a separately supplied Part-II file.
- The quarterly population reconciles internally, but it does **not** reconcile to the December Flash Report's 1,820 monitored projects. Its 1,897-code population overlaps November by 1,829 codes (2 November-only; 68 quarterly-only) and January by 1,799 codes (98 quarterly-only; 22 January-only). This population/semantics difference is why it is not recommended as an automatic December monthly substitute.

## Feasibility conclusion

October and November appear compatible with the accepted legacy detail/milestones family, but any later extraction must still pass the existing semantic selector and fail closed against the actual headers. December monthly project-level extraction is unavailable from the supplied 20-page source. The quarterly source is feasible only as a separately labelled quarter-end dataset with several narrowly scoped status-table adapters; it must not be inserted as `report_month = 2023-12` without a later explicit decision about quarterly semantics.

Repository health during assessment: **91/91 tests passed**. `data/processed/projects_monthly.csv` remained at SHA-256 `FE115E5FE71CC70552669FC4E0ACC2699B14CFE7545A319EEAEAF577E4DB95C3`.
