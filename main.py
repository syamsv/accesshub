import assets
import config


def init():
    config.init(
        env_file=".env",
        required=[
            "ACCESS_DURATION_INTERVAL_IN_MINS",
            "TAILNET",
            "TAILSCALE_API_KEY",
        ],
    )


if __name__ == "__main__":
    init()
    print(assets.calculateAccessDurationIntervals())
