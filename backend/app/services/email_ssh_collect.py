from sqlalchemy.orm import Session

from app.models.email_queue_snapshot import EmailQueueSnapshot
from app.models.email_ssh_snapshot import EmailSshSnapshot
from app.models.server import Server
from app.monitoring.email_ssh_collectors import collect_email_ssh_insights, should_collect_email_ssh_insights


def collect_and_store_email_ssh(db: Session, server: Server) -> EmailSshSnapshot | None:
    if not should_collect_email_ssh_insights(server.ip_address, server.project):
        return None
    snap = collect_email_ssh_insights(
        host=server.ip_address,
        port=server.ssh_port,
        username=server.ssh_username,
        credential_ref=server.credential_ref,
        ssh_password=server.ssh_password,
        ssh_auth_mode=server.ssh_auth_mode or "auto",
    )
    db.add(
        EmailQueueSnapshot(
            server_id=server.id,
            collected_at=snap.collected_at,
            queue_messages=snap.queue_messages,
            queue_size_kb=snap.queue_size_kb,
            postfix_active=snap.postfix_active,
            collect_error=snap.error,
        )
    )
    row = EmailSshSnapshot(
        server_id=server.id,
        collected_at=snap.collected_at,
        queue_messages=snap.queue_messages,
        queue_size_kb=snap.queue_size_kb,
        postfix_active=snap.postfix_active,
        dovecot_active=snap.dovecot_active,
        opendkim_active=snap.opendkim_active,
        mail_received=snap.mail_received,
        mail_delivered=snap.mail_delivered,
        mail_bounced=snap.mail_bounced,
        mail_rejected=snap.mail_rejected,
        mail_deferred=snap.mail_deferred,
        stats_source=snap.stats_source,
        recent_log_sample=snap.recent_log_sample,
        collect_error=snap.error,
    )
    db.add(row)
    return row
