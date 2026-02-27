"""Generate human-readable explanations of strategies."""

from veupath_chatbot.domain.strategy.ops import CombineOp


def explain_operation(op: CombineOp) -> str:
    """Explain what a combine operation does.

    :param op: Combine operator.
    :returns: Human-readable explanation of the operation.
    """
    explanations = {
        CombineOp.INTERSECT: (
            "Returns records that appear in **both** input sets. "
            "Use this to find records that match multiple criteria."
        ),
        CombineOp.UNION: (
            "Returns records that appear in **either** input set. "
            "Use this to combine results from different searches."
        ),
        CombineOp.MINUS: (
            "Returns records from the **left** set that are **not** in the right set. "
            "Use this to exclude certain records from your results."
        ),
        CombineOp.RMINUS: (
            "Returns records from the **right** set that are **not** in the left set. "
            "The opposite of left minus."
        ),
        CombineOp.COLOCATE: (
            "Returns records from the left set that are **genomically near** "
            "records in the right set. Use this to find genes near other features."
        ),
    }
    return explanations.get(op, f"Combine operation: {op.value}")
