"""The ghosts. Each one browses the way a real person does, and notices different things."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Ghost:
    id: str
    name: str
    epitaph: str
    story: str
    voice: str
    viewport: dict
    device_scale_factor: float = 1
    is_mobile: bool = False
    has_touch: bool = False
    keyboard_only: bool = False
    network: dict | None = None
    lens: tuple[str, ...] = field(default_factory=tuple)


GHOSTS: dict[str, Ghost] = {
    "marisol": Ghost(
        id="marisol",
        name="Marisol",
        epitaph="Ordered everything on the bus, one bar of signal at a time.",
        story=("You browse on a small phone over a weak mobile connection, standing on a bus with one hand free. "
               "You give a page about three seconds before you lose patience. Sideways scrolling and buttons too "
               "small for your thumb make you leave."),
        voice="Warm, quick and a little impatient. Short sentences. Says what she was trying to do.",
        viewport={"width": 375, "height": 667},
        device_scale_factor=2,
        is_mobile=True,
        has_touch=True,
        network={"latency_ms": 300, "download_kbps": 750, "upload_kbps": 250},
        lens=("slow_load", "horizontal_scroll", "small_tap_target"),
    ),
    "tomas": Ghost(
        id="tomas",
        name="Tomás",
        epitaph="Read the whole web by ear, and never once saw a button.",
        story=("You are blind and use a screen reader with a keyboard: Tab and Shift+Tab move between controls, "
               "Enter activates, and you type into whatever has focus. You only know a field by the name your "
               "screen reader announces. If something can't be reached with Tab, it doesn't exist for you."),
        voice="Calm, precise and dryly funny. Describes what his screen reader announced.",
        viewport={"width": 1280, "height": 800},
        keyboard_only=True,
        lens=("unnamed_control", "not_keyboard_reachable"),
    ),
    "rosa": Ghost(
        id="rosa",
        name="Abuela Rosa",
        epitaph="Set the ofrenda every November, reading glasses on, browser zoomed to 200%.",
        story=("You are 78 with low vision and you browse on a laptop zoomed to 200%. Small or faint grey text is "
               "hard for you to read, and you get tired quickly. You came to order bread for your family's ofrenda."),
        voice="Gentle, patient and a little old-fashioned. Mentions her glasses, her grandchildren, the ofrenda.",
        viewport={"width": 640, "height": 450},
        device_scale_factor=2,
        lens=("small_text", "low_contrast"),
    ),
}


def pick(ids: list[str] | None) -> list[Ghost]:
    if not ids:
        return list(GHOSTS.values())
    unknown = [i for i in ids if i not in GHOSTS]
    if unknown:
        raise ValueError(f"unknown ghost(s): {', '.join(unknown)}. Choose from: {', '.join(GHOSTS)}")
    return [GHOSTS[i] for i in ids]
