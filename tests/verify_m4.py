"""MVP: 管理后台上传真实 PDF -> 知识库列表 -> 查看内容."""
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from senza_knowledge_mcp.admin_app import create_app


def main(pdf: str, raw_root: str) -> None:
    app = create_app(Path(raw_root))
    c = TestClient(app)

    with open(pdf, "rb") as f:
        content = f.read()
    r = c.post(
        "/api/upload",
        files={"file": (Path(pdf).name, content, "application/pdf")},
    )
    assert r.status_code == 200, r.text
    info = r.json()
    print(f"[1] 上传成功: {info['source_id']} ({info['origin']})")

    r2 = c.get("/api/sources")
    items = r2.json()
    assert any(s["source_id"] == info["source_id"] for s in items), "列表应含新上传"
    print(f"[2] 知识库 {len(items)} 个 source")

    r3 = c.get(f"/api/sources/{info['source_id']}")
    assert r3.status_code == 200
    doc = r3.json()["document"]
    print(f"[3] source 内容 {len(doc)} chars")

    r4 = c.get("/sources")
    assert "text/html" in r4.headers["content-type"]
    print("[4] 页面可访问")
    print("VERIFY: M4 MVP OK")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else ".data/raw")
