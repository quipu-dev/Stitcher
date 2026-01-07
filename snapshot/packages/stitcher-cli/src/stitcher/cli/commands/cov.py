from stitcher.cli.factories import make_app


def cov_command():
    app_instance = make_app()
    app_instance.run_cov()
