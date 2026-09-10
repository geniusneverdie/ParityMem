"""Packaging integrity and write-boundary tests; no scientific experiment."""
from pathlib import Path
import hashlib,importlib.util,json,tempfile,unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('artifact',ROOT/'tools/artifact.py')
artifact=importlib.util.module_from_spec(spec);spec.loader.exec_module(artifact)

class ManifestBoundaryTests(unittest.TestCase):
    def test_manifest_accepts_original_and_detects_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'record.json';p.write_text('{"frozen":true}\n')
            (root/'MANIFEST.sha256').write_text(hashlib.sha256(p.read_bytes()).hexdigest()+'  record.json\n')
            self.assertEqual(artifact.verify_manifest(root),1)
            p.write_text('{"frozen":false}\n')
            with self.assertRaisesRegex(ValueError,'Hash mismatch'):artifact.verify_manifest(root)
    def test_manifest_rejects_parent_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'MANIFEST.sha256').write_text('0'*64+'  ../outside\n')
            with self.assertRaisesRegex(ValueError,'Invalid manifest path'):artifact.verify_manifest(root)
    def test_demo_refuses_existing_output_without_importing_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'existing';out.mkdir();(out/'keep.txt').write_text('keep')
            with self.assertRaisesRegex(ValueError,'already exists'):artifact.run_demo(ROOT,out)
            self.assertEqual((out/'keep.txt').read_text(),'keep')

if __name__=='__main__':unittest.main()
