# Financial Validation Rules

All arithmetic checks run in deterministic Python code after extraction. The OCR or optional language-model layer supplies source values only; it never decides whether a financial equation passes.

## Status semantics

- `PASS`: the calculated and reported values agree within tolerance.
- `FAIL`: all required source values are present and the variance exceeds tolerance.
- `NOT_APPLICABLE`: one or more source values are absent, or OCR/table alignment is not reliable enough to support a decision. No value is invented.

The tolerance is the larger of the configured absolute tolerance and the configured relative tolerance multiplied by the reported value.

## Invoice

- Line amount: `quantity × unit_price = reported line amount`
- Subtotal reconciliation: `sum(line amounts) = subtotal`, when the extracted line-item set appears complete
- Total: `subtotal + tax + shipping - discount = total`
- Tax-inclusive total: `subtotal + shipping - discount = total`
- Change: `cash paid - total = change`

## Balance sheet

For every extracted comparative period:

`total capital and liabilities = total assets`

## Profit and loss

For every extracted comparative period:

- `interest earned + other income = total income`
- `interest expended + operating expenses + provisions = total expenditure`
- `total income - total expenditure = profit before minority interest`
- Attributable profit is reconciled from profit, minority interest, and associates using the statement's available formulation.

## Cash flow

For every extracted comparative period:

- `operating + investing + financing + FX adjustment = net change in cash`
- `opening cash + net change + acquired-cash adjustment = closing cash`

Every check records its formula, operands, calculated value, reported value, variance, period, status, and a diagnostic message when relevant.
