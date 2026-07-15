"""
One-off script: populate Term.order for rows created before this column
existed.

Run this AFTER adding the `order` column (nullable, no unique constraint
yet) and BEFORE adding the uq_term_order_per_session unique constraint or
making the column NOT NULL — see migration notes. If your MySQL server
already silently filled existing rows with 0 (non-strict sql_mode default
for a NOT NULL integer column with no explicit default), this script
treats 0 the same as unset and overwrites it too.

Usage:
    python -m scripts.backfill_term_order

Maps common name patterns to 1/2/3. Anything it can't confidently map, or
any session left with two terms sharing the same order, is printed out —
resolve those manually (edit the term name to match a pattern, or set
Term.order directly) before applying the unique constraint.
"""

import re

from app import create_app
from app.models import db, Term

NAME_PATTERNS = {
    1: re.compile(r"\b(1st|first)\b", re.IGNORECASE),
    2: re.compile(r"\b(2nd|second)\b", re.IGNORECASE),
    3: re.compile(r"\b(3rd|third)\b", re.IGNORECASE),
}


def guess_order(name):
    for order, pattern in NAME_PATTERNS.items():
        if pattern.search(name):
            return order
    return None


def main():
    app = create_app()
    with app.app_context():
        unmapped = []
        for term in Term.query.all():
            # MySQL silently defaults a new NOT-NULL-with-no-default INTEGER
            # column to 0 for pre-existing rows on non-strict sql_mode —
            # treat both "never set" (None) and "MySQL's silent 0" as unset.
            if term.order not in (None, 0):
                continue
            guessed = guess_order(term.name)
            if guessed:
                term.order = guessed
                print(f"Term {term.id} ({term.name!r}) -> order {guessed}")
            else:
                unmapped.append(term)

        db.session.commit()

        if unmapped:
            print("\nCould not confidently map these — set order manually before enforcing NOT NULL / the unique constraint:")
            for term in unmapped:
                print(f"  Term {term.id}: {term.name!r} (session_id={term.session_id})")
        else:
            print("\nAll terms mapped.")

        # Sanity check: any session with two terms sharing the same order
        # will still blow up the unique constraint — surface that now
        # rather than after the next failed ALTER TABLE.
        from collections import defaultdict
        seen = defaultdict(list)
        for term in Term.query.all():
            seen[(term.session_id, term.order)].append(term.id)
        dupes = {k: v for k, v in seen.items() if len(v) > 1}
        if dupes:
            print("\nDuplicate (session_id, order) pairs remain — fix these before adding the unique constraint:")
            for (session_id, order), ids in dupes.items():
                print(f"  session_id={session_id}, order={order}: term ids {ids}")


if __name__ == "__main__":
    main()
