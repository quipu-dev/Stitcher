#### Acts 1: 更新测试数据

~~~~~act
patch_file
tests/integration/test_stub_package.py
~~~~~
~~~~~python.old
        .with_source(
            "src/my_app/main.py",
            """
            def run():
                \"\"\"Main entry point.\"\"\"
                pass
            """,
        )
~~~~~
~~~~~python.new
        .with_source(
            "src/my_app/main.py",
            """
            def run() -> None:
                \"\"\"Main entry point.\"\"\"
                pass
            """,
        )
~~~~~
