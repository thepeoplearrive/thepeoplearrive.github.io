"""Preview must never delete or overwrite an existing directory."""
import pathlib
import tempfile
import unittest
import make_preview


class PreviewSafety(unittest.TestCase):
    def test_checkout_and_ancestors_are_rejected_without_change(self):
        root = pathlib.Path(make_preview.ROOT)
        before = (root / 'index.html').read_bytes()
        for target in [root, root.parent, root / '_tests' / '..']:
            with self.subTest(target=target), self.assertRaises(ValueError):
                make_preview.main(str(target))
        self.assertEqual((root / 'index.html').read_bytes(), before)

    def test_existing_directory_and_symlink_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            existing = pathlib.Path(tmp) / 'valuable'
            existing.mkdir()
            marker = existing / 'keep.txt'
            marker.write_text('keep me')
            with self.assertRaises(ValueError):
                make_preview.main(str(existing))
            self.assertEqual(marker.read_text(), 'keep me')
            alias = pathlib.Path(tmp) / 'alias'
            try:
                alias.symlink_to(existing, target_is_directory=True)
            except OSError:
                return  # Windows may deny symlink creation; existing-directory check still ran.
            with self.assertRaises(ValueError):
                make_preview.main(str(alias))
            self.assertEqual(marker.read_text(), 'keep me')

    def test_new_directory_builds_all_pages_with_review_banner(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = pathlib.Path(tmp) / 'new-preview'
            make_preview.main(str(target))
            for rel in make_preview.PAGES:
                self.assertIn('Not the live site.', (target / rel).read_text(encoding='utf-8'))
            self.assertTrue((target / 'css/site.css').is_file())


if __name__ == '__main__':
    unittest.main(verbosity=2)
