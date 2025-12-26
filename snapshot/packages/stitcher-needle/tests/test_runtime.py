import json
from pathlib import Path
from stitcher.needle import Needle, L

def test_needle_loading_and_fallback(tmp_path: Path):
    # 1. Setup the FINAL SST structure inside the mock project root
    project_root = tmp_path
    needle_dir = project_root / ".stitcher" / "needle"
    
    # English (Default)
    en_dir = needle_dir / "en"
    (en_dir / "cli").mkdir(parents=True)
    (en_dir / "auth").mkdir()

    (en_dir / "cli" / "main.json").write_text(json.dumps({
        "cli.hello": "Hello World",
        "cli.only_en": "I am English"
    }))
    
    (en_dir / "auth" / "login.json").write_text(json.dumps({
        "auth.login.fail": "Login Failed"
    }))

    # Chinese (Target)
    zh_dir = needle_dir / "zh"
    (zh_dir / "cli").mkdir(parents=True)
    
    (zh_dir / "cli" / "main.json").write_text(json.dumps({
        "cli.hello": "你好世界"
    }))

    # 2. Initialize Runtime
    # The runtime should now automatically find the `stitcher` dir within the root_path
    rt = Needle(root_path=project_root, default_lang="en")

    # 3. Test: Target Language Hit
    # L.cli.hello should be found in zh's cli/main.json
    assert rt.get(L.cli.hello, lang="zh") == "你好世界"

    # 4. Test: Fallback to Default Language
    # L.cli.only_en is missing in zh, should fallback to en
    assert rt.get(L.cli.only_en, lang="zh") == "I am English"

    # 5. Test: FQN loading from subdirectories
    # L.auth.login.fail should be found in en's auth/login.json
    assert rt.get(L.auth.login.fail) == "Login Failed"

    # 6. Test: Ultimate Identity Fallback
    # L.unknown.key is not in any file
    assert rt.get(L.unknown.key) == "unknown.key"