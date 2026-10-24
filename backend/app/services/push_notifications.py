import logging
import os

import firebase_admin

from firebase_admin import credentials, messaging

logger = logging.getLogger(__name__)


def initialize_firebase() -> None:
    """Initialize Firebase Admin SDK once."""

    if firebase_admin._apps:
        return

    credentials_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")

    if not credentials_path:
        logger.warning(
            "Firebase credentials are not configured. "
            "Push notifications are disabled."
        )
        return

    if not os.path.isfile(credentials_path):
        logger.error(
            "Firebase service-account file was not found."
        )
        return

    try:
        credential = credentials.Certificate(credentials_path)
        firebase_admin.initialize_app(credential)

        logger.info("Firebase Admin SDK initialized.")

    except Exception:
        logger.exception(
            "Could not initialize Firebase Admin SDK."
        )


def send_briefing_notification(
    token: str,
    briefing_date: str,
) -> bool:
    """Send a push notification when a briefing is ready."""

    initialize_firebase()

    if not firebase_admin._apps:
        logger.warning(
            "Skipping push notification: Firebase is unavailable."
        )
        return False

    message = messaging.Message(
        notification=messaging.Notification(
            title="Your Morning Brief is ready! 🎧",
            body="Your personalized Burmese news briefing is ready to listen.",
        ),
        data={
            "type": "briefing_ready",
            "briefing_date": briefing_date,
        },
        android=messaging.AndroidConfig(
            priority="high",
            notification=messaging.AndroidNotification(
                channel_id="morning-brief",
                sound="default",
            ),
        ),
        token=token,
    )

    try:
        messaging.send(message)

        logger.info(
            "Briefing notification sent for %s.",
            briefing_date,
        )

        return True

    except Exception:
        logger.exception(
            "Failed to send briefing notification."
        )
        return False