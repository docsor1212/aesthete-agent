# -*- coding: utf-8 -*-
"""test_v00500 — 0.5.0 回归(report 一键验收/prompt 导出/渐变禁令 P0/场景回归)。"""
import json, os, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
ENGINE = os.path.join(ROOT, "scripts", "palette_forge.py")
LINT = os.path.join(ROOT, "scripts", "lint_page.py")
PAL = "264653,2A9D8F,E9C46A,F4A261,E76F51"
TMP = tempfile.mkdtemp(prefix="t050_")


def run(args, **kw):
    return subprocess.run([sys.executable] + args, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", **kw)


class TestReport(unittest.TestCase):
    def test_report_shape_and_exit(self):
        r = run([ENGINE, "report", "--palette", PAL])
        self.assertIn(r.returncode, (0, 1))
        d = json.loads(r.stdout)
        self.assertIn(d["verdict"], ("PASS", "FAIL"))
        for gate in ("contrast", "color_blind", "ai_slop", "score"):
            self.assertIn(gate, d["gates"])
            self.assertIsInstance(d["gates"][gate]["pass"], bool)

    def test_report_fail_is_fail(self):
        r = run([ENGINE, "report", "--palette", "8B5CF6,A855F7,7C3AED,6D28D9"])
        self.assertEqual(r.returncode, 1)
        self.assertEqual(json.loads(r.stdout)["verdict"], "FAIL")


class TestPromptExport(unittest.TestCase):
    def test_prompt_block(self):
        r = run([ENGINE, "export", "--palette", PAL, "--format", "prompt"])
        self.assertEqual(r.returncode, 0)
        self.assertIn("PALETTE", r.stdout)
        self.assertIn("60-30-10", r.stdout)
        self.assertIn("AVOID", r.stdout)
        self.assertTrue("gradients of any kind" in r.stdout)


class TestGradientBan(unittest.TestCase):
    def test_lint_single_gradient_is_p0(self):
        fd, bad = tempfile.mkstemp(suffix=".html")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write('<html><style>.y{background:linear-gradient(90deg,#E07066,#FAF3DD)}'
                        '</style><p>t</p></html>')
            r = run([LINT, bad, "--palette", PAL])
            self.assertEqual(r.returncode, 1)
            self.assertIn("P0", r.stdout)
            self.assertIn("禁渐变", r.stdout)
        finally:
            os.unlink(bad)

    def test_visualizer_no_gradient_scene(self):
        out = os.path.join(TMP, "viz.html")
        r = run([ENGINE, "visualize", "--palette", PAL, "--out", out])
        self.assertEqual(r.returncode, 0)
        html = open(out, encoding="utf-8").read()
        self.assertNotIn("Gradient Hero", html)
        self.assertNotIn("linear-gradient", html)
        os.unlink(out)

    def test_card_output_gradient_free(self):
        out = os.path.join(TMP, "card.html")
        r = run([ENGINE, "card", "--palette", PAL, "--name", "T", "--out", out])
        self.assertEqual(r.returncode, 0)
        html = open(out, encoding="utf-8").read()
        self.assertNotIn("-gradient(", html)
        os.unlink(out)


if __name__ == "__main__":
    unittest.main()
