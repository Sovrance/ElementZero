# Agent Math and Notation Readability Standard

This document exists because previous rendered equations were not reliably readable by downstream agents.

## Rule 1: ASCII is normative

Every equation that affects implementation MUST appear in a fenced `text` block using plain ASCII characters.

Good:

```text
A = Z + N
I = (N - Z) / A
RMSE = sqrt(mean((prediction - truth)^2))
```

Do not make an agent depend on rendered subscripts, Greek glyphs, equation images, Word equation objects, or Unicode-only operators.

## Rule 2: define every symbol immediately

Example:

```text
Z = proton number
N = neutron number
A = mass number = Z + N
B = total nuclear binding energy in MeV
```

## Rule 3: state units in field names when practical

Prefer:

```text
mass_excess_keV
binding_energy_MeV
charge_radius_fm
```

over fields whose unit must be guessed.

## Rule 4: use machine-readable equivalents

If an equation defines production behavior, include either code or JSON schema alongside it.

## Rule 5: no typographic minus ambiguity

Use ASCII `-`, not Unicode minus.

## Rule 6: no hidden multiplication

Prefer:

```text
a_c * Z * (Z - 1) / A^(1/3)
```

rather than juxtaposed mathematical typography.

## Rule 7: fractions

Exact rational values in evidence/certificates use strings:

```text
"7/1250"
```

when exactness is part of the claim.

## Rule 8: LaTeX is optional commentary

LaTeX may follow the ASCII block for humans, but never replaces it.

## Automated check

`scripts/validate_bundle.py` verifies that all normative engineering documents contain balanced code fences and that the bundle's declared math examples are ASCII encodable.
