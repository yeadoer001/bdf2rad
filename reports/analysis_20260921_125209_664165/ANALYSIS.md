# Full-model analysis

Status: ANALYZED_NOT_CONVERTED
SOL: 402

No runnable RAD published. Implicit controls are not explicit controls.

| Card | Count | Status | First line |
|---|---:|---|---:|
| NLCNTLG | 1 | REQUIRES_VALIDATION | 100 |
| NLCNTL2 | 1 | REQUIRES_VALIDATION | 102 |
| BCTADD | 1 | UNSUPPORTED | 104 |
| BCTSET | 1 | UNSUPPORTED | 106 |
| DESC | 1 | UNSUPPORTED | 107 |
| BGADD | 1 | UNSUPPORTED | 108 |
| BGSET | 313 | UNSUPPORTED | 149 |
| TSTEP1 | 1 | REQUIRES_VALIDATION | 774 |
| PARAM | 8 | UNSUPPORTED | 779 |
| GRID | 551461 | REQUIRES_VALIDATION | 790 |
| CHEXA | 9139 | UNSUPPORTED | 1103717 |
| CPENTA | 139 | UNSUPPORTED | 1114361 |
| CTETRA | 248363 | UNSUPPORTED | 1119128 |
| CONM2 | 14 | UNSUPPORTED | 1577275 |
| RBE3 | 14 | UNSUPPORTED | 1577331 |
| RBE2 | 51 | UNSUPPORTED | 1625191 |
| PSOLID | 12 | UNSUPPORTED | 1628029 |
| MAT1 | 12 | UNSUPPORTED | 1628056 |
| MATS1 | 5 | UNSUPPORTED | 1628059 |
| GRAV | 1 | UNSUPPORTED | 1628088 |
| BSURFS | 420 | UNSUPPORTED | 1628090 |
| BCRPARA | 420 | UNSUPPORTED | 1628332 |
| TEMPD | 1 | UNSUPPORTED | 1653792 |
| SPC | 1401 | UNSUPPORTED | 1653794 |
| TIC | 548571 | UNSUPPORTED | 1655196 |

## Effective subcase selections

Subcase 1: SPC=317, LOAD=1, IC=401, BCSET=400, BGSET=400, TSTEP=401, NLCNTL=400, TEMP(INIT)=2

## Required implementation order

1. Verified high-order topology and solid formulation; retain all midside nodes.
2. Joint MAT1/MATS1 mapping, thermal semantics, PSOLID and Part assignment.
3. BSURFS face topology and distinct glue/contact mapping with selected sets.
4. RBE weighting/DOFs, CONM2 inertia, selected SPC/TIC/GRAV and units.
5. Explicit timing decision, Starter/Engine execution and independent physical checks.

These mappings remain unimplemented. This report does not convert or validate them.
