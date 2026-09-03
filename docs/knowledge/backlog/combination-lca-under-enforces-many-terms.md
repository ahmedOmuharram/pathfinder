---
type: Backlog
---

# The combination check under-enforces three or more terms

**What I did.** Checked the constraint "A OR B OR C" against the tree
`UNION(A, INTERSECT(B, C))` with `first_combination_violation`
(domain/strategy/combination_check.py).

**What I got.** No breach: the lowest common ancestor of all three leaves is
the UNION, so the check passes, although the tree computes A OR (B AND C),
not A OR B OR C.

**Why that's wrong.** A user who states a three-way OR can still get a tree
that silently ANDs two of the branches. Two-term constraints (the shipped
incident) are checked exactly; the gap opens only at three or more terms,
which the intent-gate docstring invites.

**Why it happens.** `meeting_operator` checks only the operator of the node
where all wanted criteria meet; it does not require every internal combine
on the paths between those leaves and the meeting node to carry the same
operator.

**Fix.** For an n-term constraint, verify the meeting node's operator AND
that every combine on the path from each matched leaf to the meeting node
whose subtree holds two or more of the matched criteria carries the required
operator. Never a false refusal: combines mixing matched with unmatched
criteria stay unconstrained.

**What you'd get.** "A OR B OR C" refuses `UNION(A, INTERSECT(B, C))` and
accepts `UNION(A, UNION(B, C))`, at any nesting depth.
