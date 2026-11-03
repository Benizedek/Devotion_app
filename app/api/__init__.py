"""Request handlers, one module per feature. Every handler has the same shape:

    handler(conn, user, args, body, query) -> JSON-able value

conn is an open database connection (committed if the handler returns, rolled back if it raises),
user is the logged-in user or None, args are the groups captured from the URL pattern, body is the
JSON request body, and query is the URL's ?key=value pairs. Raise validation.ApiError to send an
error to the browser.

    accounts    sign-up, login, preferences, people search
    chats       chats and their members
    messages    messages inside a chat
    sharing     the per-chat devotion / prayer switches and the Permissions page
    devotions   your own devotions (today editable, past read-only)
    prayers     your prayer list and the lists shared with you
    people      someone else's page, limited to what they share with you

    chat_store  helpers shared by chats, messages and sharing
    validation  input checks and ApiError
"""
