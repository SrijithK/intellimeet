# Golden-set evaluation

Run 2026-11-09 14:44 UTC · model `ollama:llama3.1` · embedder `BAAI/bge-small-en-v1.5` · top_k 6

| Metric | Value |
|---|---|
| cases | 39 |
| answerable | 31 |
| unanswerable | 8 |
| retrieval_hit_at_6 | 1.0 |
| retrieval_mrr | 0.898 |
| answer_pass_rate | 1.0 |
| cited_expected_line | 1.0 |
| facts_present | 1.0 |
| false_not_found | 0.0 |
| correct_not_found | 0.75 |
| overall_pass_rate | 0.949 |
| tuned_set_pass_rate | 1.0 |
| held_out_pass_rate | 0.8 |
| median_latency_ms | 3353 |

| Case | Category | Held out | Retrieval rank | Result | Notes |
|---|---|---|---|---|---|
| launch-new-date | decision |  | 3 | pass |  |
| launch-why | reasoning |  | 1 | pass |  |
| launch-original-date | fact |  | 1 | pass |  |
| team-tier-price | fact |  | 1 | pass |  |
| beta-pricing | decision |  | 1 | pass |  |
| pricing-tiers | fact |  | 1 | pass |  |
| press-release-owner | action_item |  | 1 | pass |  |
| webhook-fix-owner | action_item |  | 1 | pass |  |
| onboarding-change | fact |  | 1 | pass |  |
| onboarding-due | action_item |  | 1 | pass |  |
| postgres-upgrade-when | decision |  | 1 | pass |  |
| flaky-ci-cause | reasoning |  | 1 | pass |  |
| flaky-ci-owner | action_item |  | 1 | pass |  |
| webhook-incident | fact |  | 1 | pass |  |
| pager-alert | action_item |  | 1 | pass |  |
| aisha-action-items | speaker |  | 1 | pass |  |
| csv-decision | decision |  | 1 | pass |  |
| churn-main-reason | fact |  | 1 | pass |  |
| csv-ticket-count | fact |  | 1 | pass |  |
| csv-customer-note | action_item |  | 2 | pass |  |
| bank-connection-problems | cross_meeting |  | 1 | pass |  |
| webhook-fix-approach | cross_meeting |  | 1 | pass |  |
| mobile-speed-paraphrase | paraphrase |  | 1 | pass |  |
| standup-decisions-scoped | scoped |  | 1 | pass |  |
| no-marketing-budget | unanswerable |  | n/a | pass |  |
| no-ceo | unanswerable |  | n/a | pass |  |
| no-hiring | unanswerable |  | n/a | pass |  |
| no-weather | unanswerable |  | n/a | pass |  |
| no-android | unanswerable |  | n/a | pass |  |
| nw-seat-count | messy_fact | yes | 1 | pass |  |
| nw-pilot-length | reversed_decision | yes | 1 | pass |  |
| nw-sso-gap | messy_fact | yes | 1 | pass |  |
| nw-decision-deadline | buried_in_monologue | yes | 2 | pass |  |
| nw-priya-commitment | speaker_label_variant | yes | 2 | pass |  |
| nw-marcus-sso-action | action_item | yes | 2 | pass |  |
| nw-injection-summary | prompt_injection | yes | 2 | pass |  |
| near-starter-beta-price | near_miss_unanswerable | yes | n/a | FAIL | answered an unanswerable question |
| near-ledger-3-launch | near_miss_unanswerable | yes | n/a | pass |  |
| near-mobile-ticket-count | near_miss_unanswerable | yes | n/a | FAIL | answered an unanswerable question |

## Failures

**near-starter-beta-price**: What is the Starter tier price for beta customers?

> The Starter tier price for beta customers is 12 dollars per seat, but they will keep the Team tier at 20 dollars for the first year. [product-launch-planning, 00:03:14, Dana][product-launch-planning, 00:03:40, Priya]

**near-mobile-ticket-count**: How many support tickets complained about the slow mobile app?

> A few complaints about the mobile app being slow to load the dashboard, but much smaller volume. [customer-feedback-review, 00:02:41, Sofia]

