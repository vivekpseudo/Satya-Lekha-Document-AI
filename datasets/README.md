# Classification datasets

Keep real financial documents outside the public repository unless redistribution rights are confirmed.

Expected JSONL schema:

```json
{"id":"doc-001","label":"balance_sheet","text":"...","source":"..."}
```

Recommended labels:

- balance_sheet
- profit_and_loss
- cash_flow
- statement_of_changes_in_equity
- notes_to_accounts
- accounting_policies
- auditor_report
- other

Use document-level and page-level splits where possible. Keep train/validation/test sources separated to avoid leakage between pages from the same annual report.
