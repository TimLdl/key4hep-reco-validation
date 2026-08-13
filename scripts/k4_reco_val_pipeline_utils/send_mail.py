import argparse
import os
import sys
from email.message import EmailMessage
from pathlib import Path
import smtplib

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from k4_reco_val_pipeline_utils.logger import setup_logger

logger = setup_logger("send_mail")


def send_mail(sender: str, recipient: str, subject: str, body: str, server: str):
    """Constructs and dispatches an email via the specified SMTP server."""
    logger.info(f"Preparing to send email to '{recipient}' via server '{server}'...")
    logger.debug(f"Subject: {subject}")

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
        logger.error(
            f"Failed to send email to '{recipient}' via server '{server}': {e}"
        )
        sys.exit(1)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Helper script to send status emails for Key4hep Reco validation."
    )
    parser.add_argument(
        "-b",
        "--body",
        type=str,
        default=None,
        help="Body of the email (has precedence over --input-file)",
    )
    parser.add_argument(
        "-f",
        "--input-file",
        type=str,
        default=None,
        help="File containing the body of the email",
    )
    parser.add_argument(
        "-s",
        "--subject",
        type=str,
        default="Key4hep Reco Validation Status",
        help="Subject of the email",
    )
    parser.add_argument(
        "--from",
        dest="sender",
        type=str,
        default="key4hep-reco-validation-noreply@cern.ch",
        help="Email address of the sender",
    )
    parser.add_argument(
        "--to",
        dest="recipient",
        required=True,
        type=str,
        help="Email address(es) of the receiver(s)",
    )
    parser.add_argument(
        "--server",
        type=str,
        default="cernmx.cern.ch",
        help="Email SMTP server to use",
    )
    return parser.parse_args()


def main():
    args = parse_arguments()

    logger.info("Starting email notification script execution.")
    logger.info(f"Recipient: {args.recipient}")
    logger.info(f"Subject:   {args.subject}")
    logger.info(f"Server:    {args.server}")

    body = args.body
    if body is None and args.input_file is not None:
        try:
            with open(args.input_file, "r", encoding="utf-8") as infile:
                body = infile.read()
            logger.debug(f"Successfully read email body from file: {args.input_file}")
        except Exception as e:
            logger.error(
                f"Failed to read email body input file '{args.input_file}': {e}"
            )
            sys.exit(1)

    if not body:
        logger.error("Please provide email text using either --body or --input-file.")
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
