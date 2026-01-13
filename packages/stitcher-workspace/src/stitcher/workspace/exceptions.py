class WorkspaceError(Exception):
    pass


class WorkspaceNotFoundError(WorkspaceError):
    def __init__(self, start_path: str):
        self.start_path = start_path
        super().__init__(
            f"无法从路径 '{start_path}' 向上定位到 Stitcher 工作区。 "
            "请确保该目录或其父目录中包含 .git 或配置了 [tool.uv.workspace] 的 pyproject.toml。"
        )
