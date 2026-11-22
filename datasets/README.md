# Classification datasets

The classifier ([app/classifier.py](../app/classifier.py)) is a transparent, rule-based baseline. Its tests use
short synthetic snippets plus checks written against one company's documents. **There is no labelled corpus of
real annual reports in this repository**, so its accuracy on other documents is unmeasured. Build one before
relying on the classification.

Keep real financial documents outside the public repository unless you have the right to redistribute them.

## Labels

The classifier returns one of:

- `balance_sheet`
- `profit_and_loss`
- `cash_flow`
- `notes_to_accounts`
- `directors_report`
- `auditors_report`
- `agm_notice`
- `invoice`
- `other`

A schedule that holds a balance sheet, a statement of profit and loss and the notes is labelled by its first
statement, `balance_sheet`. That is the label the balance-sheet and profit-and-loss rules run on. If you want a
separate `financial_statements` label, the rules need to follow.

## Format

One JSON object per line:

```json
{"id": "doc-001", "label": "directors_report", "text": "...", "source": "..."}
```

Score a set with `app.evaluation.evaluate_texts`, which reports accuracy and per-class recall.

## Building a useful set

- Label whole documents, and pages where one file holds several statements.
- Include scanned and text PDFs, abbreviated and spaced-out text (some fonts put stray spaces inside words), and
  more than one company and auditor.
- Keep train, validation and test sets from different filings, so pages of one annual report never appear on
  both sides of a split.
- Report per-class precision and recall and a confusion matrix, not only accuracy, and track how often the
  classifier answers `other`.
