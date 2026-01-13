from pathlib import Path
from textwrap import dedent
from typer.testing import CliRunner

from stitcher.cli.app import app
from stitcher.test_utils import WorkspaceFactory


def test_pump_preserves_formatting_and_appends_new_docs(tmp_path: Path):
    """
    Validates the UPDATE intent: `pump` must preserve existing file order,
    comments, and formatting, only appending new entries.
    """
    # ARRANGE
    # 1. Create a workspace with a python module containing one existing
    #    symbol (a_existing_func) and one new symbol with a docstring to be pumped.
    #    (z_new_func).
    ws_factory = WorkspaceFactory(tmp_path).with_source(
        "src/module.py",
        """
        def a_existing_func():
            # This function is already documented in the YAML below.
            pass

        def z_new_func():
            \"\"\"This is the new docstring to be pumped.\"\"\"
            pass
        """,
    )

    # 2. Create the initial .stitcher.yaml with non-alphabetical order,
    #    comments, and extra whitespace to test fidelity.
    initial_yaml_content = dedent("""
        # This is a critical comment that must be preserved.

        b_another_func: |-
          An existing entry.

        a_existing_func: |-
          The original doc for this function.

    """).lstrip()

    ws_factory.with_raw_file("src/module.stitcher.yaml", initial_yaml_content)
    ws_factory.build()

    # ACT
    # Run the pump command
    runner = CliRunner()
    result = runner.invoke(app, ["pump"], catch_exceptions=False)
    assert result.exit_code == 0, result.stdout

    # ASSERT
    # Read the content of the modified file
    final_yaml_path = tmp_path / "src" / "module.stitcher.yaml"
    final_content = final_yaml_path.read_text()

    # 1. The original comment and whitespace must be preserved.
    assert "# This is a critical comment that must be preserved." in final_content

    # 2. The original key order (b before a) must be preserved.
    b_pos = final_content.find("b_another_func:")
    a_pos = final_content.find("a_existing_func:")
    z_pos = final_content.find("z_new_func:")
    assert -1 < b_pos < a_pos < z_pos, "Key order was not preserved"

    # 3. The new key must be appended with the correct format.
    expected_appended_text = dedent("""
        z_new_func: |-
          This is the new docstring to be pumped.
    """).lstrip()
    assert expected_appended_text in final_content

    # 4. The entire expected final state should match.
    expected_final_content = initial_yaml_content.strip() + "\n" + expected_appended_text
    assert final_content.strip() == expected_final_content.strip()


def test_check_command_has_no_formatting_side_effects(tmp_path: Path):
    """
    Validates that `check` is a read-only operation and does not reorder
    or reformat a valid .stitcher.yaml file, even if its keys are not
    alphabetically sorted.
    """
    # ARRANGE
    # 1. Create a python module.
    ws_factory = WorkspaceFactory(tmp_path).with_source(
        "src/module.py",
        """
        def z_func():
            \"\"\"Doc for Z.\"\"\"
            pass
        def a_func():
            \"\"\"Doc for A.\"\"\"
            pass
        """,
    )
    ws_factory.build()

    # 2. Run `init` to create a baseline sorted file.
    runner = CliRunner()
    result = runner.invoke(app, ["init"], catch_exceptions=False)
    assert result.exit_code == 0, result.stdout

    # 3. Manually reorder the YAML file to be non-alphabetical.
    #    This simulates a user's custom ordering.
    yaml_path = tmp_path / "src" / "module.stitcher.yaml"
    sorted_content = yaml_path.read_text()
    unsorted_content = dedent("""
        z_func: |-
          Doc for Z.
        a_func: |-
          Doc for A.
    """).lstrip()
    assert sorted_content != unsorted_content, "Initial state for test is incorrect"
    yaml_path.write_text(unsorted_content)
    # Also update signature file to match new yaml content hash
    # For this test, we can just delete it, `check` will complain about missing signatures
    # but won't fail, and more importantly, it won't trigger reformatting logic.
    # A cleaner way would be to re-run pump, but this is sufficient.
    (tmp_path / ".stitcher/signatures/src/module.json").unlink()


    # ACT
    # Run the check command.
    result = runner.invoke(app, ["check"], catch_exceptions=False)
    # We expect it to pass with warnings about signature drift/missing, which is fine.
    # The key is that it shouldn't fail or reformat.
    assert result.exit_code == 0, result.stdout

    # ASSERT
    # The file must not have been changed.
    final_content = yaml_path.read_text()
    assert final_content == unsorted_content, "Check command reordered the YAML file!"