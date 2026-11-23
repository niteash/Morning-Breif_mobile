"""Firebase adapter. Return only safe outcome codes; never log tokens/responses."""
import logging
import os
import threading

import firebase_admin
from firebase_admin import credentials, messaging

logger = logging.getLogger(__name__)
_initialization_lock = threading.Lock()


def initialize_firebase() -> bool:
    with _initialization_lock:
        if firebase_admin._apps:
            return True
        path = os.getenv('FIREBASE_SERVICE_ACCOUNT_PATH')
        if not path or not os.path.isfile(path):
            return False
        try:
            firebase_admin.initialize_app(credentials.Certificate(path), options={'httpTimeout': 15})
            return True
        except Exception as error:
            logger.warning('Firebase initialization failed: error_type=%s', type(error).__name__)
            return False


def send_briefing_notification(token: str, briefing_id: str, briefing_date: str,
                               notification_id: str, ttl_seconds: int) -> str:
    if not initialize_firebase():
        return 'retry'
    message = messaging.Message(
        notification=messaging.Notification(
            title='နေ့သစ် · သင့်သတင်းအနှစ်ချုပ် အသင့်ဖြစ်ပါပြီ',
            body='သင်ရွေးချယ်ထားသော သတင်းများကို မိနစ်အနည်းငယ်ဖြင့် နားဆင်နိုင်ပါပြီ။',
        ),
        data={
            'type': 'briefing_ready',
            'briefing_id': briefing_id,
            'briefing_date': briefing_date,
            'notification_id': notification_id,
        },
        android=messaging.AndroidConfig(
            priority='high', collapse_key=notification_id, ttl=ttl_seconds,
            notification=messaging.AndroidNotification(
                channel_id='morning-brief', sound='default', tag=notification_id,
            ),
        ),
        token=token,
    )
    try:
        messaging.send(message)
        return 'sent'
    except messaging.UnregisteredError:
        return 'invalid'
    except Exception as error:
        # Invalid payload/credentials/sender configuration must not deactivate a device.
        logger.warning('FCM delivery failed: error_type=%s', type(error).__name__)
        return 'retry'


def send_breaking_news_notification(token: str, news_id: str, headline: str,
                                    publisher: str, notification_id: str,
                                    ttl_seconds: int) -> str:
    if not initialize_firebase():
        return 'retry'
    message = messaging.Message(
        notification=messaging.Notification(
            title=f'လတ်တလော · {publisher[:60]}',
            body=headline[:180],
        ),
        data={'type': 'breaking_news', 'article_id': news_id,
              'notification_id': notification_id},
        android=messaging.AndroidConfig(
            priority='high', collapse_key=f'breaking-{news_id}', ttl=ttl_seconds,
            notification=messaging.AndroidNotification(
                channel_id='morning-brief', sound='default', tag=notification_id,
            ),
        ), token=token,
    )
    try:
        messaging.send(message)
        return 'sent'
    except messaging.UnregisteredError:
        return 'invalid'
    except Exception as error:
        logger.warning('Breaking-news FCM delivery failed: error_type=%s', type(error).__name__)
        return 'retry'
