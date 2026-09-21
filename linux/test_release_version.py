import unittest
from release_version import next_version


class ReleaseVersionTest(unittest.TestCase):
    def release(self, tag, draft=False, prerelease=False):
        return dict(tag_name=tag, draft=draft, prerelease=prerelease)

    def test_initial_version_ignores_android_and_drafts(self):
        self.assertEqual(next_version([]), '0.1.0')
        self.assertEqual(next_version([
            self.release('v1.16'),
            self.release('linux-v0.1.0', draft=True),
            self.release('linux-v0.2.0', prerelease=True),
            self.release('linux-v20260921'),
        ]), '0.1.0')

    def test_published_versions_sort_numerically(self):
        self.assertEqual(next_version([
            self.release('linux-v0.1.9'),
            self.release('linux-v0.1.10'),
            self.release('linux-v0.1.11', draft=True),
        ]), '0.1.11')
        self.assertEqual(next_version([self.release('linux-v1.2.3')]), '1.2.4')


if __name__ == '__main__':
    unittest.main()
