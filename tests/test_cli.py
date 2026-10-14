import unittest
from importlib import metadata

from typer.testing import CliRunner

from myfap.cli import app


class VersionCommandTests(unittest.TestCase):
    def test_version_displays_installed_package_version(self):
        result = CliRunner().invoke(app, ["version"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(
            result.output.strip(),
            f"MyFap API CLI version: {metadata.version('myfap')}",
        )


if __name__ == "__main__":
    unittest.main()
