from datetime import datetime

from pydantic import BaseModel


class EmailQueueSnapshotRead(BaseModel):
    id: int
    server_id: int
    collected_at: datetime
    queue_messages: int | None
    queue_size_kb: int | None
    postfix_active: bool | None
    collect_error: str | None

    model_config = {"from_attributes": True}


class EmailLogEventRead(BaseModel):
    id: int
    server_id: int | None
    occurred_at: datetime
    event_type: str | None
    direction: str | None
    from_addr: str | None
    to_addr: str | None
    subject: str | None
    status: str | None
    dsn: str | None
    queue_id: str | None

    model_config = {"from_attributes": True}


class EmailOverviewRead(BaseModel):
    period_hours: int
    total: int
    inbound: int
    outbound: int
    delivered: int
    bounced: int
    failed: int
    deferred: int = 0
    blocked: int = 0
    timed_out: int = 0
    wrong_hits: int = 0
    sync_configured: bool
    scheduled_sync_enabled: bool = False
    read_only: bool = True
    last_source_id: int | None
    last_synced_at: datetime | None
    last_sync_error: str | None


class EmailSshSnapshotRead(BaseModel):
    id: int
    server_id: int
    collected_at: datetime
    queue_messages: int | None
    queue_size_kb: int | None
    queue_active: int | None = None
    queue_deferred: int | None = None
    queue_hold: int | None = None
    postfix_active: bool | None
    dovecot_active: bool | None
    opendkim_active: bool | None
    amavis_active: bool | None = None
    clamav_active: bool | None = None
    mail_received: int | None
    mail_delivered: int | None
    mail_bounced: int | None
    mail_rejected: int | None
    mail_deferred: int | None
    log_reject_lines: int | None = None
    log_bounce_lines: int | None = None
    log_amavis_lines: int | None = None
    log_spam_lines: int | None = None
    fail2ban_banned: int | None = None
    stats_source: str | None
    recent_log_sample: str | None
    collect_error: str | None

    model_config = {"from_attributes": True}


class EmailSshServerOverview(BaseModel):
    server_id: int
    server_name: str
    ip_address: str
    snapshot: EmailSshSnapshotRead | None


class EmailSshOverviewRead(BaseModel):
    read_only: bool = True
    source: str = "ssh"
    servers: list[EmailSshServerOverview]
    total_delivered: int | None
    total_bounced: int | None
    total_rejected: int | None
    total_deferred: int | None
    total_received: int | None
    note: str


class EmailSyncResultRead(BaseModel):
    ok: bool
    inserted: int | None = None
    skipped: bool | None = None
    reason: str | None = None
    error: str | None = None
    last_source_id: int | None = None


class EmailExtraSenderRead(BaseModel):
    sender: str
    count: int = 0


class EmailExtraTotalsRead(BaseModel):
    sent: int = 0
    bounce: int = 0
    deferred: int = 0
    host_not_reachable: int = 0
    delivered: int = 0
    inbound: int = 0
    outbound: int = 0
    failed: int = 0
    blocked: int = 0
    spam: int = 0
    quarantine: int = 0
    campaign_queued: int = 0
    log_total: int = 0


class EmailExtraQueueRead(BaseModel):
    queue_count: int = 0
    deferred_count: int = 0
    active_count: int = 0
    incoming_count: int = 0
    snapshot_at: datetime | str | None = None


class EmailExtraServerRead(BaseModel):
    server: str | None = None
    server_name: str | None = None
    inventory_name: str | None = None
    queue_count: int = 0
    deferred_count: int = 0
    active_count: int = 0
    incoming_count: int = 0
    snapshot_at: datetime | str | None = None
    top_senders: list[EmailExtraSenderRead] = []


class EmailExtraEventRead(BaseModel):
    id: int
    occurred_at: datetime | str | None = None
    event_type: str | None = None
    direction: str | None = None
    from_addr: str | None = None
    to_addr: str | None = None
    subject: str | None = None
    status: str | None = None
    dsn: str | None = None
    reason: str | None = None
    queue_id: str | None = None
    message_id: str | None = None
    spam_score: float | None = None
    dkim_result: str | None = None
    spf_result: str | None = None
    classification: str | None = None
    server: str | None = None
    server_name: str | None = None
    inventory_name: str | None = None


class EmailExtrasRead(BaseModel):
    ok: bool
    database: str | None = None
    reason: str | None = None
    period_hours: int = 24
    totals: EmailExtraTotalsRead
    queue: EmailExtraQueueRead
    servers: list[EmailExtraServerRead]
    events: list[EmailExtraEventRead]
