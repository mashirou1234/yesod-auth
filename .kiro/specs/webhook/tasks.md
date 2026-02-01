# Implementation Plan: Webhook Feature

## Overview

This implementation plan breaks down the webhook feature into incremental coding tasks. Each task builds on previous work, ensuring no orphaned code. The implementation follows existing project patterns (FastAPI routers, SQLAlchemy models, Valkey integration).

## Tasks

- [x] 1. Set up webhook module structure and core data models
  - [x] 1.1 Create `api/app/webhooks/` directory structure with `__init__.py`
    - Create module files: `__init__.py`, `models.py`, `schemas.py`, `config.py`, `emitter.py`, `worker.py`, `signer.py`, `router.py`
    - _Requirements: 2.1_
  
  - [x] 1.2 Implement WebhookEvent dataclass and serialization
    - Create `WebhookEvent` dataclass with event_id, event_type, timestamp, data fields
    - Implement `to_payload()` and `from_payload()` methods for JSON serialization
    - _Requirements: 3.1, 3.2, 3.5_
  
  - [x] 1.3 Write property test for WebhookEvent serialization round-trip
    - **Property 2: Payload Serialization Round-Trip**
    - **Validates: Requirements 3.5, 3.6**

- [x] 2. Implement webhook configuration loader
  - [x] 2.1 Create WebhookEndpoint dataclass and WebhookConfigLoader
    - Define `WebhookEndpoint` with id, url, secret, events, enabled, description
    - Implement YAML loading from fixed path `config/webhooks.yaml`
    - Implement validation (HTTPS required, secret required, events required)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.7_
  
  - [x] 2.2 Implement secret resolution with Docker Secrets support
    - Check `/run/secrets/<secret_name>` first (Docker Secrets)
    - Fall back to environment variables if Docker Secret not found
    - Log WARNING when using environment variables instead of Docker Secrets
    - Include migration instructions in warning message
    - _Requirements: 4.1.1, 4.1.2, 4.1.3, 4.1.4, 4.1.5_
  
  - [x] 2.3 Create sample `config/webhooks.yaml.example` configuration file
    - Add to `config/` directory with example endpoints (disabled by default)
    - Document Docker Secrets format and environment variable fallback
    - _Requirements: 2.1, 7.1_
  
  - [x] 2.4 Write property test for configuration validation
    - **Property 8: Configuration Validation**
    - **Validates: Requirements 2.2, 2.3, 4.6, 7.3, 7.4**

- [x] 3. Checkpoint - Ensure configuration loading works
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement webhook signature generation
  - [x] 4.1 Create WebhookSigner class with HMAC-SHA256 signing
    - Implement `sign(payload, secret, timestamp)` method
    - Implement `verify(payload, secret, timestamp, signature)` method for testing
    - Use `hmac` and `hashlib` standard library modules
    - _Requirements: 4.1, 4.4_
  
  - [x] 4.2 Write property test for signature computation
    - **Property 4: Signature Computation Correctness**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4**

- [x] 5. Implement webhook delivery logging model
  - [x] 5.1 Create WebhookDelivery SQLAlchemy model
    - Define model with id, event_id, event_type, endpoint_id, endpoint_url, status, http_status, error_message, attempt_count, latency_ms, created_at, completed_at
    - Add to `api/app/webhooks/models.py`
    - _Requirements: 6.1, 6.2, 6.3, 6.4_
  
  - [x] 5.2 Create Alembic migration for webhook_deliveries table
    - Generate migration file in `api/alembic/versions/`
    - Handle PostgreSQL-specific features with `_is_testing()` pattern
    - _Requirements: 6.1_

- [x] 6. Implement webhook emitter service
  - [x] 6.1 Create WebhookEmitter class with Valkey queue integration
    - Implement `emit(event_type, data)` method to queue events
    - Implement `emit_user_event(event_type, user_id, extra_data)` convenience method
    - Use existing Valkey client pattern from `api/app/valkey.py`
    - _Requirements: 8.1, 8.2_
  
  - [x] 6.2 Write property test for non-blocking async delivery
    - **Property 10: Non-Blocking Async Delivery**
    - **Validates: Requirements 8.1, 8.2**

- [x] 7. Checkpoint - Ensure emitter and queue work
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement webhook worker with retry logic
  - [x] 8.1 Create WebhookWorker class for background processing
    - Implement `start()` and `stop()` methods for lifecycle management
    - Implement `_process_event()` to consume from Valkey queue
    - Implement `deliver(event, endpoint)` with httpx for HTTP delivery
    - _Requirements: 5.3, 5.5_
  
  - [x] 8.2 Implement exponential backoff retry logic
    - Add retry loop with configurable max_retries (default 5)
    - Calculate delay as `base_delay * 2^attempt` seconds
    - Log each retry attempt
    - _Requirements: 5.1, 5.2_
  
  - [x] 8.3 Implement delivery logging
    - Create WebhookDelivery records for each attempt
    - Log success with latency_ms, failure with error_message
    - _Requirements: 6.1, 6.2, 6.3, 6.4_
  
  - [x] 8.4 Write property test for HTTP 2xx success criteria
    - **Property 5: HTTP 2xx Success Criteria**
    - **Validates: Requirements 5.3**
  
  - [x] 8.5 Write property test for retry exponential backoff
    - **Property 6: Retry Exponential Backoff**
    - **Validates: Requirements 5.1, 5.2**
  
  - [x] 8.6 Write property test for event ordering preservation
    - **Property 7: Event Ordering Preservation**
    - **Validates: Requirements 5.6**

- [x] 9. Integrate webhook emitter into existing routers
  - [x] 9.1 Add webhook emission to auth router (login events)
    - Import WebhookEmitter in `api/app/auth/router.py`
    - Emit `user.login` event after successful OAuth callback
    - Emit `user.created` event when new user is created during OAuth
    - Emit `user.oauth_linked` and `user.oauth_unlinked` events
    - _Requirements: 1.1, 1.4, 1.5, 1.6_
  
  - [x] 9.2 Add webhook emission to users router (profile events)
    - Import WebhookEmitter in `api/app/users/router.py`
    - Emit `user.updated` event after profile update
    - Emit `user.deleted` event after account deletion
    - _Requirements: 1.2, 1.3_
  
  - [x] 9.3 Write property test for user lifecycle event emission
    - **Property 1: User Lifecycle Events Trigger Webhooks**
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6**

- [x] 10. Checkpoint - Ensure event emission works end-to-end
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Implement admin API endpoints
  - [x] 11.1 Create webhook admin router
    - Create `api/app/webhooks/router.py` with admin endpoints
    - Implement `POST /api/v1/admin/webhooks/reload` for config reload
    - Implement `GET /api/v1/admin/webhooks/endpoints` to list endpoints
    - Implement `GET /api/v1/admin/webhooks/deliveries` to list delivery history
    - Add router to main app
    - _Requirements: 7.2, 7.3, 7.4_
  
  - [x] 11.2 Create Pydantic schemas for admin API responses
    - Create `WebhookEndpointResponse` schema
    - Create `WebhookDeliveryResponse` schema
    - Create `WebhookReloadResponse` schema
    - _Requirements: 7.2_

- [x] 12. Integrate webhook worker into application lifecycle
  - [x] 12.1 Start webhook worker in FastAPI lifespan
    - Modify `api/app/main.py` lifespan to start WebhookWorker
    - Add graceful shutdown for worker
    - Load webhook config at startup
    - _Requirements: 7.1, 8.3_
  
  - [x] 12.2 Write property test for payload structure completeness
    - **Property 3: Payload Structure Completeness**
    - **Validates: Requirements 3.2, 3.3, 3.4**
  
  - [x] 12.3 Write property test for delivery logging completeness
    - **Property 9: Delivery Logging Completeness**
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4**

- [-] 13. Final checkpoint - Full integration testing
  - Ensure all tests pass, ask the user if questions arise.
  - Verify webhook emission, delivery, retry, and logging work together

## Notes

- All tasks are required (including property-based tests)
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties using `hypothesis`
- Unit tests validate specific examples and edge cases
- Follow project conventions: use `TESTING=1` to skip PostgreSQL-specific features in tests
- Mock Valkey operations in tests per `conftest.py` patterns
- Use `httpx` with `respx` for mocking HTTP delivery in tests
- Configuration file MUST be at `config/webhooks.yaml` (fixed location)
- Docker Secrets are preferred over environment variables for webhook secrets
