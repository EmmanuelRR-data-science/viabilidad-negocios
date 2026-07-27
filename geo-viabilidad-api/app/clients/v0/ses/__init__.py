"""Cliente SES — raw (boto3) + processed (envío tipado)."""

from app.clients.v0.ses.ses_client_processed import enviar_email_html  # noqa: F401
from app.clients.v0.ses.ses_client_raw import enviar_email_ses_raw, guardar_email_local  # noqa: F401
