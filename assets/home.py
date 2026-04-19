_APP_HOME_OPENED = {
    "type": "home",
    "blocks": [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*Welcome to AccessHub*"},
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "plain_text",
                "text": "My job here is to reduce your headache in the approval process of authentication to multiple frameworks, listed following are the commands avaliable with me currently",
                "emoji": False,
            },
        },
        {"type": "section", "text": {"type": "mrkdwn", "text": "*Commands : *"}},
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": " `/accesshub_tailscale` : Will open up modal window for requesting tailscale access for machines or paramaters of your choice",
            },
        },
    ],
}

_APP_ERROR = {
    "type": "modal",
    "title": {"type": "plain_text", "text": "AccessHub", "emoji": False},
    "close": {"type": "plain_text", "text": "Cancel", "emoji": False},
    "blocks": [
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": "Error Occured: Contact the admin"}
            ],
        }
    ],
}
