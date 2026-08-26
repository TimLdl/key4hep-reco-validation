"""SMTP email notification helper for pipeline status alerts."""

import argparse
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIR) not in sys.path:
    import sys as _sys
    _sys.path.insert(0, str(_SCRIPTS_DIR))

from k4_reco_val_pipeline_utils.logger import setup_logger

logger = setup_logger("send_mail")


def send_mail(sender: str, recipient: str, subject: str, body: str, server: str):
    """Constructs and dispatches an email via the specified SMTP server."""
    logger.info(f"Sending email to '{recipient}' via '{server}'")
    logger.info(f"Subject: {subject}")

    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient

    try:
        with smtplib.SMTP(server) as smtp:
            smtp.send_message(msg)
        logger.info(f"Email successfully sent to '{recipient}'.")
    except Exception as e:
        logger.error(f"Failed to send email to '{recipient}' via '{server}': {e}")
        sys.exit(1)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Send status notification emails for the key4hep reconstruction validation pipeline."
    )
    parser.add_argument("-b", "--body", default=None, help="Email body text")
    parser.add_argument(
        "-f", "--input-file", default=None, help="File containing the email body"
    )
    parser.add_argument(
        "-s",
        "--subject",
        default="Key4hep Reco Validation Status",
        help="Email subject line",
    )
    parser.add_argument(
        "--from",
        dest="sender",
        default="key4hep-reco-validation-noreply@cern.ch",
        help="Sender email address",
    )
    parser.add_argument(
        "--to", dest="recipient", required=True, help="Recipient email address(es)"
    )
    parser.add_argument(
        "--server", default="cernmx.cern.ch", help="SMTP server hostname"
    )
    return parser.parse_args()


def main():
    args = parse_arguments()

    body = args.body
    if body is None and args.input_file is not None:
        try:
            body = Path(args.input_file).read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to read email body from '{args.input_file}': {e}")
            sys.exit(1)

    if not body:
        logger.error("No email body provided. Use --body or --input-file.")
        sys.exit(1)

    send_mail(
        sender=args.sender,
        recipient=args.recipient,
        subject=args.subject,
        body=body,
        server=args.server,
    )


if __name__ == "__main__":
    main()
