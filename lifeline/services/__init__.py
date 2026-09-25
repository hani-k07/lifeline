"""Business rules. Pages call these; these call repositories and the pure engine.

Every function that changes data runs in ONE transaction, validates before writing, writes an audit row (actor,
action, entity, before/after, PKT time) on the same connection, and raises DomainError (nothing written) if a rule
is broken."""
