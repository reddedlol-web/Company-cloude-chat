from src.bot.commands_menu import ADMIN_COMMANDS, ADMIN_ONLY_COMMANDS, USER_COMMANDS


def test_user_commands_are_public_only() -> None:
    names = {c.command for c in USER_COMMANDS}
    assert names == {"start", "help", "limit"}


def test_admin_commands_include_user_and_admin() -> None:
    names = {c.command for c in ADMIN_COMMANDS}
    assert {"start", "help", "limit"}.issubset(names)
    assert {c.command for c in ADMIN_ONLY_COMMANDS}.issubset(names)
    assert "invite" in names
    assert "reindex" in names
