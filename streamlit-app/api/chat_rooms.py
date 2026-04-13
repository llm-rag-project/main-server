from api.client import api_get, api_post


def create_chat(title: str):
    payload = {
        "title": title,
    }
    return api_post("/chats", payload)


def get_chat_list(page: int = 1, size: int = 20, q: str | None = None):
    params = {
        "page": page,
        "size": size,
    }
    if q:
        params["q"] = q

    query_string = "&".join(f"{key}={value}" for key, value in params.items())
    return api_get(f"/chats?{query_string}")


def get_chat_detail(chat_id: int):
    return api_get(f"/chats/{chat_id}")