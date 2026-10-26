# Acceptance criteria
| AC | Criterion | Oracle |
|----|-----------|--------|
| AC-01 | A guest pays with an e-mail address and no password | e2e checkout as guest |
| AC-02 | The receipt e-mail links to the order without sign-in | link opens order page |
| AC-03 | At most one form between basket and payment | page count in e2e |
| AC-04 | No account row is created for a guest order | DB assertion |
