"""Checks of the measurement boundary, not tests of a particular solver."""

import json
import os
from pathlib import Path
import tempfile
import unittest

from stereo_survey.mission import generate
from stereo_survey.verify import verify
from tools.stereo_survey_experiments.pilot import (
    check_bundle, evaluate, extract_program, prepare, sandbox,
)


class TemporaryBundle(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.bundle = Path(self.temporary.name) / "bundle"
        self.protocol = prepare(self.bundle)

    def tearDown(self):
        self.temporary.cleanup()


class BundleTests(TemporaryBundle):
    def test_only_public_code_and_examples_enter_prompt(self):
        self.assertEqual(set(self.protocol["bundle_hashes"]), {
            "public/stereo_survey/__init__.py", "public/stereo_survey/geometry.py",
            "public/stereo_survey/verify.py", "public/worker.py", "plain.md", "hinted.md",
            "development-compact.json", "development-expanded.json",
        })
        prompt = (self.bundle / "plain.md").read_text()
        self.assertNotIn("def exact(", prompt)
        self.assertNotIn("class Problem", prompt)
        self.assertNotIn("62000", prompt)
        self.assertEqual(check_bundle(self.bundle), self.protocol)

    def test_changed_validator_is_rejected(self):
        (self.bundle / "public/stereo_survey/verify.py").write_text("fake verifier")
        with self.assertRaisesRegex(ValueError, "frozen bundle changed"):
            check_bundle(self.bundle)

    def test_no_evaluation_before_all_generations_frozen(self):
        with self.assertRaisesRegex(RuntimeError, "all three generations"):
            evaluate(self.bundle, "plain-1")

    def test_extraction_does_not_execute_program_or_repair_response(self):
        program = 'raise AssertionError("must never run on host")\ndef solve(mission):\n    return {}\n'
        self.assertEqual(extract_program(f"```python\n{program}```"), program)
        for response in ("not code", "```python\ndef broken(\n```",
                         "```python\nx=1\n```", "```python\nx=1\n```\n```python\nx=2\n```"):
            with self.assertRaises((SyntaxError, ValueError)):
                extract_program(response)


@unittest.skipUnless(os.environ.get("STEREO_DOCKER_TESTS") == "1", "opt in to local Docker checks")
class DockerBoundaryTests(TemporaryBundle):
    def test_public_helpers_available_private_files_absent(self):
        program = '''import os
from pathlib import Path
from stereo_survey.verify import verify
def solve(mission):
    assert os.getuid() == 65534
    assert not Path('/w/stereo_survey/search.py').exists()
    assert not Path('/w/.env').exists()
    assert 'ANTHROPIC_API_KEY' not in os.environ
    assert verify(mission, {'images': []})['valid']
    try:
        Path('/w/overwrite').write_text('forbidden')
    except OSError:
        pass
    else:
        raise AssertionError('workspace writable')
    mission['cells'].clear()
    print('diagnostic goes to stderr')
    return {'images': []}
'''
        mission = generate(0)
        original = json.dumps(mission, sort_keys=True)
        result = sandbox(self.bundle, program, mission, self.protocol["sandbox"])
        self.assertEqual(result["status"], "ok", result)
        self.assertEqual(result["plan"], {"images": []})
        self.assertIn("diagnostic", result["stderr"])
        self.assertEqual(json.dumps(mission, sort_keys=True), original)
        self.assertEqual(verify(mission, result["plan"])["science"], 0)

    def test_timeout_output_cap_and_import_failure_are_retained(self):
        settings = {**self.protocol["sandbox"], "seconds": 3, "output_bytes": 4096}
        programs = [
            ("timeout", "def solve(mission):\n    while True: pass\n"),
            ("output_limit", "import os\ndef solve(mission):\n    while True: os.write(1, b'x' * 8192)\n"),
            ("runtime_error", "import stereo_survey.search\ndef solve(mission):\n    return {}\n"),
        ]
        for status, program in programs:
            with self.subTest(status=status):
                result = sandbox(self.bundle, program, generate(0), settings)
                self.assertEqual(result["status"], status, result)
                self.assertLessEqual(len(result["stdout"]) + len(result["stderr"]), 4096)


if __name__ == "__main__":
    unittest.main()
