import logging
from .db import DatabaseManager

log = logging.getLogger(__name__)


class Linker:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def link(self) -> None:
        """
        Resolves symbolic references and aliases by linking them to their definitions
        using Canonical FQNs (Fully Qualified Names).
        """
        with self.db.get_connection() as conn:
            # 1. Link References
            # Strategy: Match references.target_fqn -> symbols.canonical_fqn
            # We only attempt to link references that remain unresolved (target_id IS NULL).
            log.debug("Linking references...")
            cursor = conn.execute(
                """
                UPDATE "references"
                SET target_id = (
                    SELECT id 
                    FROM symbols 
                    WHERE symbols.canonical_fqn = "references".target_fqn 
                    LIMIT 1
                )
                WHERE target_id IS NULL
                """
            )
            if cursor.rowcount > 0:
                log.debug(f"Linked {cursor.rowcount} references.")

            # 2. Link Aliases
            # Strategy: Match symbols.alias_target_fqn -> symbols.canonical_fqn
            # Only for symbols that are aliases (kind='alias') and unresolved.
            log.debug("Linking aliases...")
            cursor = conn.execute(
                """
                UPDATE symbols
                SET alias_target_id = (
                    SELECT id 
                    FROM symbols AS s2 
                    WHERE s2.canonical_fqn = symbols.alias_target_fqn 
                    LIMIT 1
                )
                WHERE kind = 'alias' 
                  AND alias_target_id IS NULL 
                  AND alias_target_fqn IS NOT NULL
                """
            )
            if cursor.rowcount > 0:
                log.debug(f"Linked {cursor.rowcount} aliases.")