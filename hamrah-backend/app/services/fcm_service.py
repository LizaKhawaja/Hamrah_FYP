def send_notification(tokens, title, body, data: dict = None):
    if not tokens:
        return None

    if isinstance(tokens, str):
        tokens = [tokens]

    str_data = {k: str(v) for k, v in (data or {}).items()}

    try:
        from firebase_admin import messaging

        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            data=str_data if str_data else None,
            tokens=tokens,
        )
        response = messaging.send_each_for_multicast(message)
        print("SUCCESS:", response.success_count)
        print("FAIL:", response.failure_count)
        for i, resp in enumerate(response.responses):
            if not resp.success:
                print(f"Token {i} error: {resp.exception}")
        return response
    except Exception as e:
        print(f"[FCM] Notification skipped: {e}")
        return None
