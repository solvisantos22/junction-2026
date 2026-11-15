"""Independent audits may finish and update the same inventory concurrently."""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import unittest

from tools.planner_lab.common import write


class ArchiveTests(unittest.TestCase):
    def test_concurrent_atomic_reports(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'inventory.json'
            payloads = [{'writer':i, 'values':[i]*200} for i in range(64)]
            with ThreadPoolExecutor(max_workers=16) as pool:
                list(pool.map(lambda value:write(path,value), payloads))
            self.assertIn(json.loads(path.read_text()),payloads)
            self.assertEqual(list(Path(folder).glob('*.tmp')),[])


if __name__=='__main__': unittest.main()
