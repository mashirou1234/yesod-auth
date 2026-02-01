# Requirements Document

## Introduction

This document defines the requirements for adding webhook functionality to the yesod-auth OAuth authentication system. Webhooks enable external services to receive real-time notifications when user-related events occur in the system, supporting OSS use cases where integrators need to synchronize user data or trigger downstream workflows.

## Glossary

- **Webhook**: An HTTP callback that delivers event notifications to external URLs when specific events occur in the system
- **Webhook_Endpoint**: A registered URL that receives webhook event payloads
- **Webhook_Event**: A notification payload sent to registered endpoints when a triggering action occurs
- **Webhook_Signature**: An HMAC-SHA256 signature used to verify the authenticity of webhook payloads
- **Webhook_Secret**: A shared secret key used to generate and verify webhook signatures
- **Event_Type**: A category of user action that triggers webhook notifications (e.g., user.created, user.deleted)
- **Delivery_Attempt**: A single attempt to send a webhook payload to an endpoint
- **Retry_Policy**: The strategy for re-attempting failed webhook deliveries

## Requirements

### Requirement 1: Webhook Event Types

**User Story:** As an integrator, I want to receive notifications for user lifecycle events, so that I can keep my external systems synchronized with user data.

#### Acceptance Criteria

1. WHEN a new user is created THEN THE Webhook_System SHALL emit a `user.created` event
2. WHEN a user profile is updated THEN THE Webhook_System SHALL emit a `user.updated` event
3. WHEN a user account is soft-deleted THEN THE Webhook_System SHALL emit a `user.deleted` event
4. WHEN a user links a new OAuth provider THEN THE Webhook_System SHALL emit a `user.oauth_linked` event
5. WHEN a user unlinks an OAuth provider THEN THE Webhook_System SHALL emit a `user.oauth_unlinked` event
6. WHEN a user successfully logs in THEN THE Webhook_System SHALL emit a `user.login` event

### Requirement 2: Webhook Endpoint Registration

**User Story:** As a system administrator, I want to register webhook endpoints, so that external services can receive event notifications.

#### Acceptance Criteria

1. THE Webhook_System SHALL load endpoint configurations exclusively from `config/webhooks.yaml`
2. WHEN registering an endpoint THEN THE Webhook_System SHALL require a URL, secret key, and list of subscribed event types
3. THE Webhook_System SHALL validate that endpoint URLs use HTTPS protocol
4. WHEN an endpoint is registered THEN THE Webhook_System SHALL generate a unique endpoint ID
5. THE Webhook_System SHALL support multiple endpoints subscribing to the same event type
6. THE Webhook_System SHALL support an endpoint subscribing to multiple event types
7. IF `config/webhooks.yaml` does not exist THEN THE Webhook_System SHALL disable webhook functionality and log a notice

### Requirement 3: Webhook Payload Format

**User Story:** As an integrator, I want webhook payloads to follow a consistent format, so that I can reliably parse and process event data.

#### Acceptance Criteria

1. THE Webhook_System SHALL send payloads as JSON with Content-Type `application/json`
2. THE Webhook_Payload SHALL include: event_id (UUID), event_type, timestamp (ISO 8601), and data object
3. THE Webhook_Payload data object SHALL include user_id for all user-related events
4. THE Webhook_Payload SHALL include a `webhook_id` field identifying the endpoint configuration
5. WHEN serializing a Webhook_Payload THEN THE Webhook_System SHALL produce valid JSON
6. FOR ALL valid Webhook_Payload objects, serializing then deserializing SHALL produce an equivalent object

### Requirement 4: Webhook Security

**User Story:** As an integrator, I want webhook payloads to be signed, so that I can verify they originated from the authentication system.

#### Acceptance Criteria

1. THE Webhook_System SHALL sign all payloads using HMAC-SHA256 with the endpoint's secret key
2. THE Webhook_System SHALL include the signature in the `X-Webhook-Signature` HTTP header
3. THE Webhook_System SHALL include a timestamp in the `X-Webhook-Timestamp` header
4. THE Webhook_Signature SHALL be computed over the concatenation of timestamp and payload body
5. THE Webhook_System SHALL provide documentation for signature verification
6. IF a secret key is not configured for an endpoint THEN THE Webhook_System SHALL reject the endpoint registration

### Requirement 4.1: Secret Key Security Guidance

**User Story:** As a system administrator, I want to be warned about insecure secret storage, so that I follow security best practices.

#### Acceptance Criteria

1. WHEN the system starts THEN THE Webhook_System SHALL check if secrets are loaded from Docker Secrets
2. IF secrets are loaded from environment variables or .env files THEN THE Webhook_System SHALL log a WARNING recommending Docker Secrets
3. THE Warning message SHALL include instructions for migrating to Docker Secrets
4. THE Webhook_System SHALL support reading secrets from Docker Secrets path (`/run/secrets/`)
5. THE Webhook_System SHALL prefer Docker Secrets over environment variables when both are available

### Requirement 5: Webhook Delivery and Retries

**User Story:** As an integrator, I want failed webhook deliveries to be retried, so that temporary network issues don't cause missed events.

#### Acceptance Criteria

1. WHEN a webhook delivery fails THEN THE Webhook_System SHALL retry with exponential backoff
2. THE Webhook_System SHALL attempt a maximum of 5 delivery retries
3. THE Webhook_System SHALL consider HTTP status codes 2xx as successful delivery
4. IF all retry attempts fail THEN THE Webhook_System SHALL log the failure with event details
5. THE Webhook_System SHALL set a delivery timeout of 30 seconds per attempt
6. WHILE retrying delivery THEN THE Webhook_System SHALL preserve the original event order per endpoint

### Requirement 6: Webhook Delivery Logging

**User Story:** As a system administrator, I want to view webhook delivery history, so that I can troubleshoot integration issues.

#### Acceptance Criteria

1. THE Webhook_System SHALL log all delivery attempts with timestamp, endpoint, event type, and status
2. THE Webhook_System SHALL log HTTP response status codes for each delivery attempt
3. THE Webhook_System SHALL log delivery latency for successful deliveries
4. IF a delivery fails THEN THE Webhook_System SHALL log the error message or response body (truncated)
5. THE Webhook_System SHALL retain delivery logs for a configurable period (default 30 days)

### Requirement 7: Webhook Configuration Management

**User Story:** As a system administrator, I want to manage webhook configurations without restarting the service, so that I can add or modify endpoints dynamically.

#### Acceptance Criteria

1. THE Webhook_System SHALL load endpoint configurations from `config/webhooks.yaml` at startup
2. THE Webhook_System SHALL support reloading configurations via an admin API endpoint
3. WHEN configuration is reloaded THEN THE Webhook_System SHALL validate all endpoint configurations
4. IF configuration validation fails THEN THE Webhook_System SHALL reject the reload and keep existing configuration
5. THE Webhook_System SHALL support enabling/disabling individual endpoints without removing them
6. IF webhooks.yaml is placed in a non-standard location THEN THE Webhook_System SHALL ignore it and log a warning

### Requirement 8: Async Webhook Processing

**User Story:** As a system architect, I want webhook delivery to be asynchronous, so that it doesn't block the main request processing.

#### Acceptance Criteria

1. THE Webhook_System SHALL queue events for asynchronous delivery
2. THE Webhook_System SHALL not block the triggering API request while delivering webhooks
3. WHEN the system restarts THEN THE Webhook_System SHALL resume processing queued events
4. THE Webhook_System SHALL use Valkey (Redis) as the queue backend for consistency with existing infrastructure
