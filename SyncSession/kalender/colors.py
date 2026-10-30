EVENT_COLORS = [
    "#1f77b4",  # blau
    "#ff7f0e",  # orange
    "#1b4a38",  # dunkelgrün, klar dunkler als das Annahme-Grün
    "#9467bd",  # violett
    "#8c564b",  # braun
    "#e377c2",  # pink
    "#17becf",  # cyan
    "#bcbd22",  # oliv
]

CARD_COLOR = "#fffdf8"

TINT_RATIO = 0.88

CONSENSUS_COLOR = "#347864"

CONSENSUS_BACKGROUND = "#e8f5f0"

DECLINED_COLOR = "#9f1d1d"

DECLINED_BACKGROUND = "#f8e8e8"


def color_for_user(user_id):
    return EVENT_COLORS[(user_id - 1) % len(EVENT_COLORS)]


def _mix(hex_color, hex_target, ratio):
    """ratio 0 = hex_color, ratio 1 = hex_target."""
    color = hex_color.lstrip("#")
    target = hex_target.lstrip("#")
    channels = [
        round(
            int(color[index : index + 2], 16) * (1 - ratio)
            + int(target[index : index + 2], 16) * ratio
        )
        for index in (0, 2, 4)
    ]
    return "#{:02x}{:02x}{:02x}".format(*channels)


def background_for_user(user_id):
    return _mix(color_for_user(user_id), CARD_COLOR, TINT_RATIO)
