"""Rule registry."""

from __future__ import annotations

from .base import Rule
from .destructive import (
    DeleteWithoutWhereRule,
    DropColumnRule,
    DropTableRule,
    IrreversibleOperationRule,
    TruncateRule,
)
from .performance import (
    CreateIndexWithoutConcurrentlyRule,
    LargeTableMutationRule,
    MissingIndexForForeignKeyRule,
    TableRewriteRiskRule,
)
from .safety import (
    DescriptionCommentMissingRule,
    ParseErrorRule,
    RawUpdateDeleteRule,
    RollbackCommentMissingRule,
    TransactionSafetyRule,
)
from .schema_changes import (
    AlterColumnTypeRule,
    EnumOrTypeNarrowingRule,
    NotNullWithoutDefaultRule,
    NullableToNotNullRule,
    RenameDropAddHeuristicRule,
)


def get_default_rules() -> list[Rule]:
    """Return ordered list of default rules."""

    return [
        DropTableRule(),
        DropColumnRule(),
        TruncateRule(),
        DeleteWithoutWhereRule(),
        IrreversibleOperationRule(),
        AlterColumnTypeRule(),
        NullableToNotNullRule(),
        NotNullWithoutDefaultRule(),
        EnumOrTypeNarrowingRule(),
        RenameDropAddHeuristicRule(),
        MissingIndexForForeignKeyRule(),
        LargeTableMutationRule(),
        CreateIndexWithoutConcurrentlyRule(),
        TableRewriteRiskRule(),
        RollbackCommentMissingRule(),
        DescriptionCommentMissingRule(),
        TransactionSafetyRule(),
        RawUpdateDeleteRule(),
        ParseErrorRule(),
    ]


__all__ = ["Rule", "get_default_rules"]
