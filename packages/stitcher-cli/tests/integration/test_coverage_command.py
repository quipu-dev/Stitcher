from typer.testing import CliRunner

from stitcher.cli.main import app
from stitcher.test_utils import WorkspaceFactory

runner = CliRunner()


def test_coverage_command_output_and_alignment(tmp_path, monkeypatch):
    """
    Tests the `stitcher cov` command for:
    1. Correct coverage calculation for various scenarios.
    2. Correct aggregation in the TOTAL line.
    3. Proper column alignment regardless of path length.
    4. Exclusion of non-documentable modules from the report.
    """
    # 1. Setup a workspace with diverse documentation coverage
    ws_root = (
        WorkspaceFactory(tmp_path)
        .with_config({"scan_paths": ["src"]})
        .with_source(
            "src/fully_documented.py",
            """
            \"\"\"Module docstring.\"\"\"
            def func_one():
                pass
            class MyClass:
                def method_one(self):
                    pass
            """,
        )
        .with_docs(
            "src/fully_documented.stitcher.yaml",
            {
                "__doc__": "Module docstring.",
                "func_one": "Doc for func_one.",
                "MyClass": "Doc for MyClass.",
                "MyClass.method_one": "Doc for method_one.",
            },
        )
        .with_source(
            "src/partially/documented_long_path.py",
            """
            \"\"\"Module docstring.\"\"\"
            def func_documented():
                pass
            def func_undocumented():
                pass
            """,
        )
        .with_docs(
            "src/partially/documented_long_path.stitcher.yaml",
            {
                "__doc__": "Module docstring.",
                "func_documented": "Doc for func_documented.",
            },
        )
        .with_source(
            "src/undocumented.py",
            """
            def func_a():
                pass
            def func_b():
                pass
            """,
        )
        .with_source(
            "src/not_documentable.py",
            """
            # This file contains no public, documentable symbols.
            def _private_func():
                pass
            _private_var = 1
            """,
        )
        .build()
    )
    monkeypatch.chdir(ws_root)

    # 2. Run the command
    result = runner.invoke(app, ["cov"], catch_exceptions=False)

    # 3. Assertions
    assert result.exit_code == 0, f"CLI command failed: {result.stdout}"
    output = result.stdout

    # Helper to parse a report line into a dict
    def parse_line(line_str: str) -> dict:
        parts = line_str.split()
        return {
            "name": parts[0],
            "stmts": int(parts[1]),
            "miss": int(parts[2]),
            "cover": parts[3],
        }

    lines = output.strip().split("\n")
    report_lines = [line for line in lines if line.strip().startswith("src/")]
    report_data = {parse_line(line)["name"]: parse_line(line) for line in report_lines}

    # -- Assert Data Correctness --
    assert "src/fully_documented.py" in report_data
    fd_data = report_data["src/fully_documented.py"]
    assert fd_data["stmts"] == 4
    assert fd_data["miss"] == 0
    assert fd_data["cover"] == "100.0%"

    assert "src/partially/documented_long_path.py" in report_data
    pd_data = report_data["src/partially/documented_long_path.py"]
    assert pd_data["stmts"] == 3
    assert pd_data["miss"] == 1
    assert pd_data["cover"] == "66.7%"

    assert "src/undocumented.py" in report_data
    ud_data = report_data["src/undocumented.py"]
    assert ud_data["stmts"] == 3
    assert ud_data["miss"] == 3
    assert ud_data["cover"] == "0.0%"

    assert "src/not_documentable.py" not in report_data, (
        "Non-documentable files should be excluded"
    )

    # -- Assert TOTAL line --
    total_line = next((line for line in lines if line.startswith("TOTAL")), None)
    assert total_line is not None, "TOTAL line is missing from output"
    total_data = parse_line(total_line)
    assert total_data["name"] == "TOTAL"
    assert total_data["stmts"] == 10  # 4 + 3 + 3
    assert total_data["miss"] == 4  # 0 + 1 + 3
    assert total_data["cover"] == "60.0%"  # (10-4)/10

    # -- Assert Alignment --
    header_line = next(line for line in lines if line.strip().startswith("Name"))
    long_path_line = next(line for line in lines if "documented_long_path.py" in line)
    short_path_line = next(line for line in lines if "undocumented.py" in line)

    # Find start index of each column in the header, which defines our search boundaries
    stmts_start = header_line.find("Stmts")
    miss_start = header_line.find("Miss")
    cover_start = header_line.find("Cover")

    # Check that TOTAL line columns align with header
    # By providing a start index to find(), we ensure we search in the correct column region.
    assert total_line.find(str(total_data["stmts"]), stmts_start) != -1
    assert total_line.find(str(total_data["miss"]), miss_start) != -1
    assert total_line.find(total_data["cover"], cover_start) != -1

    # Check a data line with a long path for alignment
    assert long_path_line.find(str(pd_data["stmts"]), stmts_start) != -1
    assert long_path_line.find(str(pd_data["miss"]), miss_start) != -1
    assert long_path_line.find(pd_data["cover"], cover_start) != -1

    # Check a data line with a short path for alignment (this was the failing one)
    assert short_path_line.find(str(ud_data["stmts"]), stmts_start) != -1
    assert short_path_line.find(str(ud_data["miss"]), miss_start) != -1
    assert short_path_line.find(ud_data["cover"], cover_start) != -1
