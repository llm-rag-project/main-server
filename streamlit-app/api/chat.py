from api.client import api_post


def send_chat_message(
    chat_id: int,
    message: str,
    article_id: int | None = None,
    conversation_id: str = "",
):
    payload = {
        "message": message,
        "article_id": article_id,
        "conversation_id": conversation_id,
    }

    return api_post(f"/chats/{chat_id}/messages", payload)