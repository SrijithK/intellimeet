# Golden-set evaluation

Run 2026-11-05 16:31 UTC · model `ollama:llama3.1` · embedder `BAAI/bge-small-en-v1.5` · top_k 6

| Metric | Value |
|---|---|
| cases | 29 |
| answerable | 24 |
| unanswerable | 5 |
| retrieval_hit_at_6 | 1.0 |
| retrieval_mrr | 0.958 |
| answer_pass_rate | 1.0 |
| cited_expected_line | 1.0 |
| facts_present | 1.0 |
| false_not_found | 0.0 |
| correct_not_found | 1.0 |
| overall_pass_rate | 1.0 |
| median_latency_ms | 1591 |

| Case | Category | Retrieval rank | Result | Notes |
|---|---|---|---|---|
| launch-new-date | decision | 2 | pass |  |
| launch-why | reasoning | 1 | pass |  |
| launch-original-date | fact | 1 | pass |  |
| team-tier-price | fact | 1 | pass |  |
| beta-pricing | decision | 1 | pass |  |
| pricing-tiers | fact | 1 | pass |  |
| press-release-owner | action_item | 1 | pass |  |
| webhook-fix-owner | action_item | 1 | pass |  |
| onboarding-change | fact | 1 | pass |  |
| onboarding-due | action_item | 1 | pass |  |
| postgres-upgrade-when | decision | 1 | pass |  |
| flaky-ci-cause | reasoning | 1 | pass |  |
| flaky-ci-owner | action_item | 1 | pass |  |
| webhook-incident | fact | 1 | pass |  |
| pager-alert | action_item | 1 | pass |  |
| aisha-action-items | speaker | 1 | pass |  |
| csv-decision | decision | 1 | pass |  |
| churn-main-reason | fact | 1 | pass |  |
| csv-ticket-count | fact | 1 | pass |  |
| csv-customer-note | action_item | 2 | pass |  |
| bank-connection-problems | cross_meeting | 1 | pass |  |
| webhook-fix-approach | cross_meeting | 1 | pass |  |
| mobile-speed-paraphrase | paraphrase | 1 | pass |  |
| standup-decisions-scoped | scoped | 1 | pass |  |
| no-marketing-budget | unanswerable | n/a | pass |  |
| no-ceo | unanswerable | n/a | pass |  |
| no-hiring | unanswerable | n/a | pass |  |
| no-weather | unanswerable | n/a | pass |  |
| no-android | unanswerable | n/a | pass |  |
