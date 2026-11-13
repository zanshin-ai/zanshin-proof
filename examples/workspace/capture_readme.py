"""Capture the actual workspace using the synthetic demo in an isolated browser.

Requires optional playwright and Pillow packages, kept outside the runtime dependencies.
Run from the repository root. The output contains synthetic evidence only.
"""

from __future__ import annotations

import argparse
import base64
import functools
import http.server
import io
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="/tmp/proof-readme-assets")
    parser.add_argument("--emit-base64", action="store_true", help="emit assets for retrieval")
    args = parser.parse_args()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="proof-capture-") as temporary:
        folder = Path(temporary)
        html = folder / "index.html"
        subprocess.run(
            [sys.executable, str(ROOT / "examples/workspace/make_demo.py"),
             "--store", str(folder / "demo.db"), "--output", str(html)], check=True,
        )
        # Label all captures while retaining the real generated workspace and interactions.
        html.write_text(html.read_text().replace("LOCAL SNAPSHOT", "SYNTHETIC DEMO"))
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(folder))
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 1440, "height": 1000},
                                        device_scale_factor=1, reduced_motion="reduce")
                errors: list[str] = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{server.server_port}")
                page.get_by_role("heading", name="Make every run count.").wait_for()
                assert page.locator("#run-rows tr").count() == 3
                frames = [page.screenshot()]

                page.get_by_role("link", name="Compare runs", exact=True).click()
                baseline = page.locator("#baseline option").all()
                ids = {option.inner_text().split(" · ")[0]: option.get_attribute("value")
                       for option in baseline}
                page.locator("#baseline").select_option(ids["synthetic-baseline"])
                page.locator("#candidate").select_option(ids["synthetic-regression"])
                assert page.locator("#comparison").get_by_text("BLOCKED", exact=True).count() == 1
                frames.append(page.screenshot())

                page.get_by_role("link", name="Evaluation runs", exact=True).click()
                page.locator("#run-rows tr").filter(has_text="synthetic-regression").get_by_role(
                    "button"
                ).click()
                detail = page.locator("#detail").inner_text()
                assert "candidate 0.7; minimum allowed 0.807" in detail
                page.wait_for_function(
                    "Math.abs(scrollY - Math.min(document.querySelector('#evidence')"
                    ".getBoundingClientRect().top + scrollY - 20, "
                    "document.documentElement.scrollHeight - innerHeight)) < 2"
                )
                frames.append(page.screenshot())
                assert not errors, errors

                # Also verify the real layout at a phone width.
                page.set_viewport_size({"width": 390, "height": 844})
                page.get_by_role("link", name="Overview", exact=True).click()
                assert page.get_by_role("heading", name="Make every run count.").is_visible()
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                browser.close()
        finally:
            server.shutdown()
            server.server_close()

    images = [Image.open(io.BytesIO(frame)).convert("RGB") for frame in frames]
    images[0].save(output / "proof-workspace.webp", "WEBP", quality=88, method=6)
    labels = ["1 / Track evaluations and see which runs pass",
              "2 / Compare a candidate with the baseline",
              "3 / Inspect the required check that blocked release"]
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    font = (ImageFont.truetype(font_path, 18) if Path(font_path).exists()
            else ImageFont.load_default())
    animation = []
    for image, label in zip(images, labels, strict=True):
        image = image.resize((1008, 700), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (1008, 754), "#0c1111")
        canvas.paste(image, (0, 54))
        draw = ImageDraw.Draw(canvas)
        draw.text((18, 17), label, fill="#d6f49b", font=font)
        draw.text((810, 17), "Synthetic demo", fill="#9caeac", font=font)
        animation.append(canvas.quantize(colors=96))
    animation[0].save(output / "proof-workflow.gif", save_all=True, append_images=animation[1:],
                      duration=[3000, 4000, 5000], loop=0, optimize=True, disposal=2)
    for path in sorted(output.iterdir()):
        print(f"Asset: {path.name} ({path.stat().st_size} bytes)")
        if args.emit_base64:
            print(f"PROOF_ASSET_BEGIN:{path.name}")
            print(base64.b64encode(path.read_bytes()).decode("ascii"))
            print(f"PROOF_ASSET_END:{path.name}")


if __name__ == "__main__":
    main()
