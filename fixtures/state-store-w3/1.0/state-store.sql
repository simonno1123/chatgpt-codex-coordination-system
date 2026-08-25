PRAGMA user_version = 100;

CREATE TABLE IF NOT EXISTS store_metadata (
    metadata_key TEXT PRIMARY KEY,
    metadata_value TEXT NOT NULL
) WITHOUT ROWID;

INSERT OR IGNORE INTO store_metadata(metadata_key, metadata_value)
VALUES
    ('state_store_version', '1.0'),
    ('w3_profile_version', '1.0'),
    ('acos_contract_version', '2.0'),
    ('governance_status', 'UNAUTHENTICATED_SHADOW');

CREATE TABLE IF NOT EXISTS grant_observations (
    observation_id TEXT PRIMARY KEY,
    grant_id TEXT NOT NULL,
    claimed_governance_state TEXT NOT NULL CHECK (
        claimed_governance_state IN (
            'DEFINED', 'ISSUED', 'VALIDATED', 'ACTIVE', 'CONSUMED',
            'DENIED', 'REVOKED', 'EXPIRED', 'SUPERSEDED', 'FAILED'
        )
    ),
    observer_state TEXT NOT NULL CHECK (observer_state = 'OBSERVED'),
    source_reference TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    claim_status TEXT NOT NULL CHECK (claim_status = 'DECLARED_ONLY'),
    governance_status TEXT NOT NULL CHECK (governance_status = 'UNAUTHENTICATED_SHADOW'),
    authority_effect TEXT NOT NULL CHECK (authority_effect = 'NONE'),
    identity_effect TEXT NOT NULL CHECK (identity_effect = 'NONE'),
    execution_effect TEXT NOT NULL CHECK (execution_effect = 'NONE'),
    activation_effect TEXT NOT NULL CHECK (activation_effect = 'NONE'),
    eligible_for_execution INTEGER NOT NULL CHECK (eligible_for_execution = 0)
);

CREATE INDEX IF NOT EXISTS idx_grant_observations_grant_id
ON grant_observations(grant_id, observed_at);

CREATE TABLE IF NOT EXISTS authorization_state (
    authorization_id TEXT PRIMARY KEY,
    claimed_governance_state TEXT NOT NULL CHECK (
        claimed_governance_state IN (
            'DEFINED', 'ISSUED', 'VALIDATED', 'ACTIVE', 'CONSUMED',
            'DENIED', 'REVOKED', 'EXPIRED', 'SUPERSEDED', 'FAILED'
        )
    ),
    current_observer_state TEXT NOT NULL CHECK (
        current_observer_state IN (
            'OBSERVED', 'RESERVED', 'CONSUMED', 'REVOKED',
            'EXPIRED', 'SUPERSEDED', 'CONFLICTED'
        )
    ),
    version INTEGER NOT NULL CHECK (version >= 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    governance_status TEXT NOT NULL CHECK (governance_status = 'UNAUTHENTICATED_SHADOW'),
    authority_effect TEXT NOT NULL CHECK (authority_effect = 'NONE'),
    identity_effect TEXT NOT NULL CHECK (identity_effect = 'NONE'),
    execution_effect TEXT NOT NULL CHECK (execution_effect = 'NONE'),
    activation_effect TEXT NOT NULL CHECK (activation_effect = 'NONE'),
    eligible_for_execution INTEGER NOT NULL CHECK (eligible_for_execution = 0)
);

CREATE TABLE IF NOT EXISTS authorization_events (
    event_id TEXT PRIMARY KEY,
    authorization_id TEXT NOT NULL,
    operation_id TEXT NOT NULL,
    nonce TEXT NOT NULL,
    canonical_request_digest TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN ('RESERVED', 'CONSUMED')),
    previous_observer_state TEXT NOT NULL,
    observer_state TEXT NOT NULL,
    state_version INTEGER NOT NULL CHECK (state_version >= 1),
    observed_at TEXT NOT NULL,
    governance_status TEXT NOT NULL CHECK (governance_status = 'UNAUTHENTICATED_SHADOW'),
    authority_effect TEXT NOT NULL CHECK (authority_effect = 'NONE'),
    identity_effect TEXT NOT NULL CHECK (identity_effect = 'NONE'),
    execution_effect TEXT NOT NULL CHECK (execution_effect = 'NONE'),
    activation_effect TEXT NOT NULL CHECK (activation_effect = 'NONE'),
    eligible_for_execution INTEGER NOT NULL CHECK (eligible_for_execution = 0),
    FOREIGN KEY (authorization_id) REFERENCES authorization_state(authorization_id),
    UNIQUE (authorization_id, operation_id),
    UNIQUE (authorization_id, nonce)
);

CREATE INDEX IF NOT EXISTS idx_authorization_events_authorization
ON authorization_events(authorization_id, state_version);

CREATE TABLE IF NOT EXISTS workflow_state_events (
    workflow_event_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    observed_from_state TEXT NOT NULL,
    observed_to_state TEXT NOT NULL,
    observer_state TEXT NOT NULL CHECK (observer_state = 'OBSERVED'),
    source_reference TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    governance_status TEXT NOT NULL CHECK (governance_status = 'UNAUTHENTICATED_SHADOW'),
    authority_effect TEXT NOT NULL CHECK (authority_effect = 'NONE'),
    identity_effect TEXT NOT NULL CHECK (identity_effect = 'NONE'),
    execution_effect TEXT NOT NULL CHECK (execution_effect = 'NONE'),
    activation_effect TEXT NOT NULL CHECK (activation_effect = 'NONE'),
    eligible_for_execution INTEGER NOT NULL CHECK (eligible_for_execution = 0)
);

CREATE INDEX IF NOT EXISTS idx_workflow_state_events_task
ON workflow_state_events(task_id, observed_at);

CREATE TABLE IF NOT EXISTS audit_events (
    sequence INTEGER PRIMARY KEY,
    audit_event_id TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    aggregate_type TEXT NOT NULL CHECK (
        aggregate_type IN (
            'GRANT_OBSERVATION', 'AUTHORIZATION_OBSERVATION',
            'WORKFLOW_OBSERVATION', 'W2_SHADOW_OBSERVATION'
        )
    ),
    aggregate_id TEXT NOT NULL,
    payload_digest TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL UNIQUE,
    observed_at TEXT NOT NULL,
    governance_status TEXT NOT NULL CHECK (governance_status = 'UNAUTHENTICATED_SHADOW'),
    authority_effect TEXT NOT NULL CHECK (authority_effect = 'NONE'),
    identity_effect TEXT NOT NULL CHECK (identity_effect = 'NONE'),
    execution_effect TEXT NOT NULL CHECK (execution_effect = 'NONE'),
    activation_effect TEXT NOT NULL CHECK (activation_effect = 'NONE'),
    eligible_for_execution INTEGER NOT NULL CHECK (eligible_for_execution = 0)
);

CREATE INDEX IF NOT EXISTS idx_audit_events_aggregate
ON audit_events(aggregate_type, aggregate_id, sequence);

CREATE TRIGGER IF NOT EXISTS authorization_events_no_update
BEFORE UPDATE ON authorization_events BEGIN
    SELECT RAISE(ABORT, 'authorization_events are append-only');
END;

CREATE TRIGGER IF NOT EXISTS authorization_events_no_delete
BEFORE DELETE ON authorization_events BEGIN
    SELECT RAISE(ABORT, 'authorization_events are append-only');
END;

CREATE TRIGGER IF NOT EXISTS workflow_state_events_no_update
BEFORE UPDATE ON workflow_state_events BEGIN
    SELECT RAISE(ABORT, 'workflow_state_events are append-only');
END;

CREATE TRIGGER IF NOT EXISTS workflow_state_events_no_delete
BEFORE DELETE ON workflow_state_events BEGIN
    SELECT RAISE(ABORT, 'workflow_state_events are append-only');
END;

CREATE TRIGGER IF NOT EXISTS audit_events_no_update
BEFORE UPDATE ON audit_events BEGIN
    SELECT RAISE(ABORT, 'audit_events are append-only');
END;

CREATE TRIGGER IF NOT EXISTS audit_events_no_delete
BEFORE DELETE ON audit_events BEGIN
    SELECT RAISE(ABORT, 'audit_events are append-only');
END;
