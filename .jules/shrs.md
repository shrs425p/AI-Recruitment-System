## 2024-10-21 - [Audit fix] ARS-001 Canonical Skill Matching
**The Problem:** Incorrect skill matches caused by substring logic in candidate ranking engine. `Go` could match `Django`.
**The Execution:** Replaced fuzzy substring matches with exact canonical skill and certification matching. Introduced an explicit reviewable alias map. Added regression tests.
**The Impact:** Improved accuracy of scoring and candidate evaluation by preventing false positives in skill matching.
