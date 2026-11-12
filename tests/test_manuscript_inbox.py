import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from orchestrator.manuscript_inbox import complete_book


class ManuscriptInboxTest(unittest.TestCase):
    def test_resume_and_package_without_redrafting_or_changing_source(self):
        seed = (
            "# Smoke Test\n\n<!-- target-chapters: 3 -->\n\n"
            "## Chapter 1: The arrival\n\nMara arrived at the station.\n"
        )
        paragraph = ("Mara waited on the platform — she could hear the tide. " * 40).strip()
        chapter_two = "## Chapter 2: The wait\n\n" + "\n\n".join([paragraph] * 45)
        chapter_three = "## Chapter 3: The return\n\nThe train returned at dusk."

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "seed.md"
            source.write_text(seed, encoding="utf-8")
            output = root / "output"

            with patch("orchestrator.manuscript_inbox.call_llm", side_effect=[chapter_two, None]):
                with self.assertRaisesRegex(RuntimeError, "Chapter 3"):
                    complete_book(source, seed, output, "Test Author")
            job, = output.iterdir()
            self.assertFalse((job / "complete.json").exists())

            with patch("orchestrator.manuscript_inbox.call_llm", return_value=chapter_three) as model:
                complete_book(source, seed, output, "Test Author")
                complete_book(source, seed, output, "Test Author")
            model.assert_called_once()
            self.assertEqual(model.call_args.kwargs["provider"], "local")
            self.assertIn("Write Chapter 3", model.call_args.args[0]["messages"][1]["content"])
            self.assertEqual(source.read_text(encoding="utf-8"), seed)
            finished = (job / "finished.md").read_text(encoding="utf-8")
            self.assertTrue(finished.startswith(seed))
            self.assertEqual(finished.count("## Chapter 2"), 1)
            self.assertIn(chapter_three, finished)
            self.assertTrue((job / "complete.json").exists())
            workspace = job / "manuscript_workspace"
            self.assertEqual(len(list(workspace.glob("build/*_interior.pdf"))), 1)
            package, = (workspace / "kdp_packages").iterdir()
            for filename in ("cover_wrap_print.pdf", "cover_ebook_front.jpg", "kdp_answers.json"):
                self.assertGreater((package / filename).stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
