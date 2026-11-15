"""Private archive adapter: cache-only Volume reads; original live call binding.

Run prepare only after the final call has settled. Download the two documented
Volume prefixes with the existing Modal CLI, then run verify. No job is launched.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import time
from types import SimpleNamespace

SOURCE_ROOT = Path('/tmp/junction-hybrid-recovery2-frozen')
PINNED_SOURCES = {'docs/learning-final-results/policy-freeze.json': '78db73d1afb6ce2dd2c51a9597c14abcaeddd01e7331bf95ca297664fddd1fb7', 'docs/learning-final.md': '71d042804cb9a834274f9f12cec6d60333c9269554338f6d332226c79ce78004', 'docs/learning-hybrid.md': 'f1861c681f7d5951a41127d03ded1009a7cb887fad8f4ff1deb9fd281148c2ff', 'lightlag/__init__.py': 'c8ec30fc8723d8f6d7ffa8fbd9d4ef7cf0ef480a777829722ce82f98f9201d06', 'lightlag/__main__.py': '3969a425d2ea0ba912c5cb825e81ad596ed6b081a229ffbc7ea216feca72ce36', 'lightlag/controllers/__init__.py': 'b9c20ca7d13f1e6357d2304094061040135b416d2370758edf5697135f5f22c0', 'lightlag/controllers/api.py': 'f8737cf928f965ef24f786b2ce0e660207ca239745c06497cc5d12b19fb13aec', 'lightlag/controllers/baselines.py': '25b588b76ee050c780e544b723ed64e78652729884753be9d52e039ded875f0b', 'lightlag/controllers/geometry.py': 'e83b7bcda9b5b7285e991b570738396f22dc1bea6cff73647e868c55beea593e', 'lightlag/controllers/predictor.py': '1c46181899ca320f9d326247c0045c97acfd87f80ab8bb719604c01430f52643', 'lightlag/controllers/reference.py': '0c34d751759440b46a72e81b0e6200a241ead27c82f86dda572ecd60c8a13d62', 'lightlag/environment.py': 'a6f4d56ea7d218276bdcc700fe94e061c929fb9267f8b735bbfb0cec36689a01', 'lightlag/evaluation.py': '7b543ce8d1e92bb7ab8d14dbf091b3e946426f138da0ba518b287ec7921fb9f4', 'lightlag/model.py': 'd7800c912a48a056a224baaee58f263831128d0916527938e4e0463a9c976c1a', 'lightlag_hybrid/__init__.py': '98d6553e139d70fb818a042e26023358fe37a3cb20af679975f5f0eb003a623e', 'lightlag_hybrid/policy.py': '7fc61a9e372383d8cf6239e0a87943150e82729d117f8193af67f29d1641f561', 'lightlag_hybrid/worker.py': '744c68444dc9b6d186f70d62992040cc28e64ecd3bffea7c95c6410f59dc4aa2', 'lightlag_learning/__init__.py': '77f483e957fb0ad8bd3a32eb9383a05d58dfb128519cada3d25a066ecb3620af', 'lightlag_learning/environment.py': '9e8bc1fd7cc5606964ef5f313b7809ae78425e00960be9e120c2cde2498bbe95', 'lightlag_learning/learners.py': 'bcf07d7676280dc98c04ee2cf72a32872e33aaaed62bc093115c4e157d44a429', 'lightlag_learning/models.py': 'd4b03e694cf0441dd0793d919eb5474685e81868e6b8171fb695bd88d70ad781', 'lightlag_learning/train.py': 'a2ac312422f7dc7ad63381594c8fe5dc50bb4b3c94e5cd1457185f3f6ce4cf1d', 'lightlag_learning_final/__init__.py': '854a1772da8e9de4279a0b8fc71d12838508a70de34a4d8141fbf9a3d6bdf3cc', 'lightlag_learning_final/train.py': '3719263b652a41d67c53e6f5b3e1a301264165b9372d656a8b5a7dbd5e914916', 'lightlag_mcp/__init__.py': 'ae202374e48ff6d3d9b490d0b636d57cfe4d3e7da45f16cc5bf74af65cbe8158', 'lightlag_mcp/__main__.py': 'd362cd394c3a3e9752115d859b5cd8526fdbec939a556dd6fa28f7d32bf78db8', 'lightlag_mcp/client.py': '66bdeb5c9a0337138beb2e6a6e397e4aef5f0cffbe069ee95624d75fdd8e4278', 'lightlag_mcp/finish.py': '97e3e75fa4a8cb3475d66ae175380c1d06a6b7313eccf08086af046292b7ed87', 'lightlag_mcp/server.py': 'a15c05da870cca1ae8a9f8f3bae718a076b8c301757d249bf48abe22cf5e7e59', 'lightlag_mcp/service.py': '46d00c28cab43dc0267c600a957c555d6977e6a451ee0290c504d3760c4d2b98', 'lightlag_rl/__init__.py': '74e93161cf9db3c59f4edee185f103536acee10a9f39ee2bcb6ab1e4907b8501', 'lightlag_rl/adapter.py': '4113253c465f8bc8ca0d9745e563c37198cc7f7e0937e024e664240df4475279', 'lightlag_rl/model.py': 'd263c69be352ea8d536c65871ed47e9df24f0b3c6e4c18d12f1b3470b3706b93', 'lightlag_rl/train.py': '0034df7df59ba6971d3f6f5a2cd2aa4eff2dfb3b71a42f116efcd0aad88c80b9', 'lightlag_rl_feasible/__init__.py': '65f239288dc32162ce63f2365c722021a3ea8a21d77da5cf81a34bd0e8b079a1', 'lightlag_rl_feasible/adapter.py': '6335ef34c97fb31bccb6145581c092d51ff4c12b2038fa388160c95b55f88b28', 'lightlag_traverse/__init__.py': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'lightlag_traverse/campaign.py': '838d167a38d39d3a79270fa66ef12c64eaefca94bd1c1186956bef0c7560ba0b', 'lightlag_traverse/environment.py': 'ece97a96967f78b7f845c51eb36de90ca4aadb948c18dc8f573d3b63dc4031e9', 'lightlag_traverse/make_task.py': '8bb87e2ed8a416f55dd9b1fefc2df92733e9866015518473217df4950a8da7fe', 'lightlag_traverse/oneshot.py': '56280efc6480367607f9e05aa6888252195fd0fa745ecc82fda7f364690e610e', 'lightlag_traverse/pilot.py': '4b2e2b238a8b336b9ece86ec7a173aa8509785360b2d69c73cec4b291202a074', 'lightlag_traverse/planning.py': '629c06325e891b5d49d49b294297f282b332fc1a4dfb13281e0efd2cc49248c5', 'lightlag_traverse/play.py': '7d4e766e1757ff133a0cd9424ccb5d1e4a3160b6d4df39723e55a646f6d93fa7', 'lightlag_traverse/sandbox.py': '861ab363cb61907a30cd02d5bd4d73a428011bb91acfd93576bcd1a239cec1a6', 'lightlag_traverse/sandbox_worker.py': 'd72fc9cbbff9c312006d742d49a01d5c09cd9a09b994b7cc08a5f85c94d977cb', 'lightlag_traverse/server.py': '9d2bb5997f026e8e166145dba2b443d72d92f87c55cd8bee2058cad4f0a95444', 'lightlag_traverse/surface.py': 'ad58635a093fcde8a971812b54d456d6ab7026bbc5ac2d7001a4a53490087233', 'lightlag_traverse/terrain.py': '8bbc6d73ee3fc95c745fc156c05f895acce368c252dd33292e8469a75793db19', 'tools/learning_final/__init__.py': '31d106634dde8946bf6cc4534b5cea8cbe3cdcf9328bfb2559eb0097fbe1ce3c', 'tools/learning_final/evaluate.py': '62f2c57ff7a32c7c374c83d98fff35009427e095099d410d06b5ff5eec91b07e', 'tools/learning_hybrid/__init__.py': '98d6553e139d70fb818a042e26023358fe37a3cb20af679975f5f0eb003a623e', 'tools/learning_hybrid/cloud.py': '16e4b61c1260393195f83cb102dddc18fc77630c8ec10eff3d1e3172ccbde567', 'tools/learning_hybrid/experiment.py': 'dcdb7be8d391a409ec8b19c184ac0bc01a9916be667a42a20433fdf027b71a02', 'tools/learning_hybrid/manage.py': '3bec887dd3a3f6571058944f5a9a55c1bd932f07a821bb826585dd1ef53ffe69', 'tools/learning_hybrid_ops/recovery.py': 'd79172fec3f9a351542d3c470d3cba8f68dbcff5a08769f121d916370048655b', 'tools/learning_hybrid_ops/recovery2.py': '4c76455af19c19d1dd1d5468b74e4dff0ba4e32a401ef8ddd561ed230051353b', 'tools/learning_hybrid_ops/stages2.py': '8692fa082729f02258eb3d184f863d4bb9e3b9a2fda50e0b63538fb54b016306'}
VOLUME = 'junction-learning-hybrid'
MASTER_SHA256 = 'ff04b33503f212b2e855d5d0a5843457be01cb22396bd42d27cafc72bad8dab7'
MARKER = '.cache-identity.json'
RECEIPT_SHA256 = 'f0773dcc0bc488a2260421840efb3a9d654d79fb02147cd36cc992b3f6d0470f'
FINAL_CALL = 'fc-01M7EHYJ7272Q4Z5432990CT78'
FINAL_OPS_SHA256 = 'f79ce4f9b42549aed0ccdfd53c6ce17da03e259a5c400323ab816ddc3892864d'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def identity(receipt_path):
    receipt = json.loads(Path(receipt_path).read_text())
    require(receipt.get('schema') == 'learning-hybrid-receipt-v1'
            and receipt.get('stage') == 'final' and receipt.get('status') == 'submitted'
            and receipt.get('volume') == VOLUME and receipt.get('freeze_sha256') == MASTER_SHA256
            and receipt.get('coordinator_call_id') == FINAL_CALL
            and receipt.get('ops_freeze_sha256') == FINAL_OPS_SHA256
            and sha(receipt_path) == RECEIPT_SHA256,
            'require the original submitted final receipt')
    return {'schema': 'hybrid-final-cache-v1', 'receipt_sha256': sha(receipt_path),
            'helper_sha256': sha(__file__), 'source_sha256': PINNED_SOURCES,
            'volume': VOLUME, 'prefixes': ['final', 'final-ops2/artifacts/final/jobs']}


def check_sources():
    for name, expected in PINNED_SOURCES.items():
        path = SOURCE_ROOT / name
        require(not path.is_symlink() and sha(path) == expected, 'frozen source changed: ' + name)


class StopGuard:
    def __init__(self, paths, control=None):
        require(paths, 'provide existing operator pause/stop marker paths with --stop-file')
        self.paths = tuple(Path(p) for p in paths)
        self.control = control
        self.next_remote_check = 0.

    def check(self, force=False):
        require(not any(p.exists() for p in self.paths), 'local pause/stop marker present')
        if self.control is not None and (force or time.monotonic() >= self.next_remote_check):
            require(not self.control.get('stop'), 'remote campaign stop marker present')
            self.next_remote_check = time.monotonic() + 30


def prepare(cache, receipt_path, stop_files):
    cache = Path(cache)
    guard = StopGuard(stop_files)
    guard.check()
    check_sources()
    require(not cache.resolve().is_relative_to(SOURCE_ROOT.resolve()), 'cache cannot be inside the frozen source')
    value = identity(receipt_path)
    cache.mkdir(parents=True, exist_ok=False)
    (cache / 'final-ops2/artifacts/final').mkdir(parents=True)
    (cache / MARKER).write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')
    return value


class CacheOnlyVolume:
    def __init__(self, cache, guard):
        self.cache = Path(cache).resolve()
        self.guard = guard

    def read_file(self, relative):
        self.guard.check()
        require(isinstance(relative, str) and PurePosixPath(relative).as_posix() == relative
                and not PurePosixPath(relative).is_absolute() and '..' not in PurePosixPath(relative).parts,
                'unsafe cache path')
        allowed = (relative in ('final/state.json', 'final/plan.json', 'final/ops-freeze.json')
                   or re.fullmatch(r'final/receipts/[A-Za-z0-9_-]{1,100}\.json', relative)
                   or re.fullmatch(r'final-ops2/artifacts/final/jobs/[A-Za-z0-9_-]{1,100}/(?:case\.json\.gz|row\.json)', relative))
        require(allowed, 'cache path is outside the exact final artifact allowlist')
        path = self.cache / relative
        require(path.resolve().is_relative_to(self.cache)
                and not any(p.is_symlink() for p in (path, *path.parents) if p != self.cache.parent),
                'cache path uses a symlink or leaves the cache')
        with path.open('rb') as stream:  # Missing files fail; never fetch from the network.
            while chunk := stream.read(1024 * 1024):
                self.guard.check()
                yield chunk


def cached_sdk(real_sdk, cache, guard):
    volume = CacheOnlyVolume(cache, guard)
    def from_name(name, **kwargs):
        require(name == VOLUME and not kwargs.get('create_if_missing'), 'unexpected Volume request')
        return volume
    # Dict and FunctionCall deliberately remain the real SDK classes.
    return SimpleNamespace(Dict=real_sdk.Dict, FunctionCall=real_sdk.FunctionCall,
                           Volume=SimpleNamespace(from_name=from_name))


def verify(cache, receipt_path, output, stop_files):
    cache, output = Path(cache), Path(output)
    check_sources()
    guard = StopGuard(stop_files)
    guard.check()
    require(cache.is_dir() and not cache.is_symlink()
            and json.loads((cache / MARKER).read_text()) == identity(receipt_path), 'cache identity differs')
    require(not output.exists() and not output.resolve().is_relative_to(cache.resolve())
            and not cache.resolve().is_relative_to(output.resolve())
            and not output.resolve().is_relative_to(SOURCE_ROOT.resolve()), 'output must be new and separate')
    sys.path.insert(0, str(SOURCE_ROOT))
    from tools.learning_hybrid_ops import stages2
    stages2.source_context(SOURCE_ROOT)
    real_sdk = stages2.m.sdk_module()
    control = real_sdk.Dict.from_name(stages2.c.CONTROL_NAME)
    guard.control = control
    guard.check(force=True)
    receipt = json.loads(Path(receipt_path).read_text())
    terminal = real_sdk.FunctionCall.from_id(receipt['coordinator_call_id']).get(timeout=0)
    require(terminal.get('status') == 'complete' and terminal.get('stage') == 'final'
            and terminal.get('jobs_total') == terminal.get('jobs_complete') == 2560
            and terminal.get('coordinator_call_id') == receipt['coordinator_call_id'],
            'original final call is not terminal and complete for all2560 cases')
    result = stages2.download(receipt_path, output, artifacts=True, sdk=cached_sdk(real_sdk, cache, guard))
    guard.check(force=True)
    require(result['status'] == 'complete', 'final archive is incomplete')
    record = {**identity(receipt_path), 'schema': 'hybrid-final-cache-verification-v1',
              'download_manifest_sha256': sha(output / 'download.json'),
              'terminal_state_sha256': stages2.c.state_hash(terminal),
              'source_root': str(SOURCE_ROOT), 'verified_output': str(output),
              'volume_reads_from_cache_only': True, 'live_dict_and_functioncall_binding': True,
              'cases': 2560, 'physics_and_controller_audits': 'Existing frozen downloader verifies retained remote audit metadata; no mission is repeated locally.'}
    (output / 'cache-verification.json').write_text(json.dumps(record, sort_keys=True, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'verify'))
    parser.add_argument('--cache', required=True, type=Path)
    parser.add_argument('--receipt', required=True, type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--stop-file', required=True, action='append', type=Path)
    args = parser.parse_args()
    if args.action == 'prepare':
        result = prepare(args.cache, args.receipt, args.stop_file)
    else:
        require(args.output is not None, '--output required')
        result = verify(args.cache, args.receipt, args.output, args.stop_file)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
