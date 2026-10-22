"""Visual snapshot tests for the TUI screens, using the example gallery.

Each test renders an example screen (populated with fake data, no git/LLM) to
an SVG and compares it against a committed baseline. Regenerate baselines with
``uv run pytest --snapshot-update`` and review the resulting SVG diff before
committing.
"""

from diffweave import preview

TERMINAL_SIZE = (120, 40)


def test_tree_screen_snapshot(snap_compare):
    assert snap_compare(preview.build_tree_app(), terminal_size=TERMINAL_SIZE)


def test_review_screen_snapshot(snap_compare):
    async def run_before(pilot):
        # Let the (fake, instant) generation worker populate the message.
        await pilot.pause()
        await pilot.pause()

    assert snap_compare(
        preview.build_review_app(),
        terminal_size=TERMINAL_SIZE,
        run_before=run_before,
    )
