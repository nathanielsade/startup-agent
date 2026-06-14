from startup_agent.adapters.delivery.file_channel import FileChannel


def test_file_channel_deliver_writes_file(tmp_path):
    channel = FileChannel(directory=str(tmp_path))
    channel.deliver("2026-06-14", "# Digest\n")
    expected = tmp_path / "2026-06-14.md"
    assert expected.exists()
    assert expected.read_text() == "# Digest\n"


def test_file_channel_path_for_returns_correct_path(tmp_path):
    channel = FileChannel(directory=str(tmp_path))
    path = channel.path_for("2026-06-14")
    assert path == tmp_path / "2026-06-14.md"


def test_file_channel_creates_directory_if_missing(tmp_path):
    nested = tmp_path / "a" / "b"
    channel = FileChannel(directory=str(nested))
    channel.deliver("test", "body")
    assert (nested / "test.md").exists()


def test_file_channel_safe_title_replaces_slashes_and_spaces(tmp_path):
    channel = FileChannel(directory=str(tmp_path))
    path = channel.path_for("my title/with spaces")
    assert path.name == "my_title-with_spaces.md"
