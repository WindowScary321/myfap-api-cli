"""Exercise release workflow guards without network, credentials or publishing."""
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch
from urllib.error import HTTPError


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / '.github' / 'workflows'
VERSION = '0.2.0'
TAG = 'v0.2.0'
SHA = 'a' * 40
REPOSITORY = 'example/myfap-api-cli'
NOTES = 'Release notes tổng hợp, không chứa dữ liệu tài khoản.\n'


def workflow_text(name):
    return (WORKFLOWS / name).read_text(encoding='utf-8')


def inline_python(name):
    return [textwrap.dedent(match) for match in re.findall(
        r"python -I - <<'PY'\n(.*?)^          PY$",
        workflow_text(name), re.MULTILINE | re.DOTALL)]


def job_blocks(name):
    jobs = workflow_text(name).split('\njobs:\n', 1)[1]
    headers = list(re.finditer(r'^  ([a-z][a-z0-9_-]*):\n', jobs, re.MULTILINE))
    return {match.group(1): jobs[match.end():headers[index + 1].start()
                                if index + 1 < len(headers) else len(jobs)]
            for index, match in enumerate(headers)}


def artifact_fixture(directory):
    dist = directory / 'dist'
    dist.mkdir()
    files = {
        f'myfap-{VERSION}-py3-none-any.whl': b'synthetic wheel bytes',
        f'myfap-{VERSION}.tar.gz': b'synthetic sdist bytes',
    }
    for name, data in files.items():
        (dist / name).write_bytes(data)
    manifest = ''.join(hashlib.sha256(files[name]).hexdigest() + '  ' + name + '\n'
                       for name in sorted(files)).encode('ascii')
    (dist / 'SHA256SUMS').write_bytes(manifest)
    files['SHA256SUMS'] = manifest
    return files, hashlib.sha256(manifest).hexdigest()


@contextmanager
def current_directory(directory):
    previous = Path.cwd()
    os.chdir(directory)
    try:
        yield
    finally:
        os.chdir(previous)


class FakeGitHub:
    """Only the external gh-command boundary is replaced by this fake server."""
    def __init__(self, files, existing=False, draft=False, assets=()):
        self.files = files
        self.release = self.release_payload(draft) if existing else None
        self.assets = {name: files[name] for name in assets}
        self.mutations = []
        self.tag_sha = SHA
        self.annotated = False
        self.corrupt_upload = False
        self.additional_releases = []
        self.release_api_calls = []

    @staticmethod
    def release_payload(draft):
        return {'id': 42, 'tag_name': TAG, 'prerelease': False, 'body': NOTES,
                'draft': draft}

    def run(self, command, **kwargs):
        if command[0] != 'gh':
            raise AssertionError('Unexpected external command')
        args = command[1:]
        if args[0] == 'api':
            path = args[-1]
            prefix = f'repos/{REPOSITORY}/'
            if not path.startswith(prefix):
                raise AssertionError('Unexpected repository')
            path = path[len(prefix):]
            if path == f'git/ref/tags/{TAG}':
                payload = {'object': {'type': 'tag' if self.annotated else 'commit',
                                      'sha': 'b' * 40 if self.annotated else self.tag_sha}}
            elif path == 'git/tags/' + 'b' * 40:
                payload = {'object': {'type': 'commit', 'sha': self.tag_sha}}
            elif path == f'releases/tags/{TAG}':
                self.release_api_calls.append(path)
                # This endpoint excludes drafts even when the caller can push.
                if self.release is None or self.release['draft']:
                    return subprocess.CompletedProcess(command, 1, b'', b'gh: Not Found (HTTP 404)')
                payload = self.release
            elif path == 'releases?per_page=100':
                self.release_api_calls.append(path)
                releases = self.additional_releases + ([self.release] if self.release is not None else [])
                if '--paginate' in args and '--slurp' in args:
                    payload = [releases[index:index + 100] for index in range(0, len(releases), 100)] or [[]]
                else:
                    payload = releases[:100]
            elif path == 'releases/42/assets?per_page=100':
                payload = [{'id': index, 'name': name}
                           for index, name in enumerate(sorted(self.assets), 100)]
            elif path.startswith('releases/assets/'):
                index = int(path.rsplit('/', 1)[1]) - 100
                name = sorted(self.assets)[index]
                return subprocess.CompletedProcess(command, 0, self.assets[name], b'')
            else:
                raise AssertionError('Unexpected API endpoint: ' + path)
            return subprocess.CompletedProcess(command, 0, json.dumps(payload).encode('utf-8'), b'')
        if args[:2] == ['release', 'create']:
            self.mutations.append(tuple(args))
            if self.release is not None or '--draft' not in args or '--verify-tag' not in args:
                raise AssertionError('Must create a draft only once for an existing tag')
            self.release = self.release_payload(True)
            self.release['body'] = Path(args[args.index('--notes-file') + 1]).read_text(encoding='utf-8')
        elif args[:2] == ['release', 'upload']:
            self.mutations.append(tuple(args))
            path = Path(args[3])
            if path.name in self.assets or '--clobber' in args:
                raise AssertionError('Existing assets must not be overwritten')
            self.assets[path.name] = b'corrupt' if self.corrupt_upload else path.read_bytes()
        elif args[:2] == ['release', 'edit']:
            self.mutations.append(tuple(args))
            if args[3:] != ['--draft=false']:
                raise AssertionError('Unexpected release edit')
            self.release['draft'] = False
        else:
            raise AssertionError('Unexpected gh command: ' + repr(args))
        return subprocess.CompletedProcess(command, 0, b'', b'')


class ReleaseWorkflowTests(unittest.TestCase):
    def test_production_starts_from_a_tag_and_reuses_ci_without_rebuilding(self):
        workflow = workflow_text('publish.yml')
        self.assertIn('tags: ["v*.*.*"]', workflow)
        self.assertNotIn('types: [published]', workflow)
        self.assertIn('uses: ./.github/workflows/ci.yml', workflow)
        self.assertIn('ref: ${{ needs.validate.outputs.sha }}', workflow)
        self.assertNotIn('uv build', workflow)
        self.assertIn('cancel-in-progress: false', workflow)

    def test_publish_and_release_are_the_only_privileged_jobs(self):
        for name, environment in [('publish.yml', 'pypi'), ('testpypi.yml', 'testpypi')]:
            with self.subTest(workflow=name):
                jobs = job_blocks(name)
                self.assertEqual([job for job, body in jobs.items() if 'id-token: write' in body], ['publish'])
                self.assertIn('environment: ' + environment, jobs['publish'])
                for job in ('publish', 'release'):
                    if job not in jobs:
                        continue
                    body = jobs[job]
                    self.assertNotIn('actions/checkout@', body)
                    self.assertNotRegex(body, r'(?:uv|pip) (?:build|sync|install)')
                    self.assertNotRegex(body, r'python[^\n]* scripts/')
                writers = [job for job, body in jobs.items() if 'contents: write' in body]
                self.assertEqual(writers, ['release'] if name == 'publish.yml' else [])
                self.assertIn('MANIFEST_SHA256:', jobs['publish'])
                self.assertNotIn('skip-existing:', jobs['publish'])
        self.assertIn('needs: [validate, ci, verify]', job_blocks('publish.yml')['release'])
        self.assertIn("needs.verify.result == 'success'", job_blocks('publish.yml')['release'])

    def test_actions_are_pinned_and_testpypi_is_manual_and_separate(self):
        for name in ('publish.yml', 'testpypi.yml', 'ci.yml'):
            for action, ref in re.findall(r'uses:\s+([^\s@]+)@([^\s#]+)', workflow_text(name)):
                with self.subTest(workflow=name, action=action):
                    self.assertRegex(ref, r'^[a-f0-9]{40}$')
        rehearsal = workflow_text('testpypi.yml')
        self.assertIn('workflow_dispatch:', rehearsal)
        self.assertNotIn('\n  push:', rehearsal)
        self.assertIn('https://test.pypi.org/legacy/', rehearsal)
        self.assertIn('--test-pypi', rehearsal)
        self.assertNotIn('--extra-index-url', rehearsal)
        self.assertNotIn('\n  release:', rehearsal)

    def test_source_ci_checks_out_workflows_that_its_tests_exercise(self):
        source = job_blocks('ci.yml')['source']
        self.assertIn('/.github/workflows/', source)
        self.assertIn('/scripts/', source)
        self.assertIn('/tests/', source)
        self.assertNotIn('/docs/', source)
        self.assertNotIn('/tasks/', source)


class InlineArtifactVerifierTests(unittest.TestCase):
    def run_guard(self, name, directory, manifest, selected=None, version=VERSION):
        environment = os.environ.copy()
        environment.pop('UPLOAD_FILES', None)
        environment.update(VERSION=version, MANIFEST_SHA256=manifest)
        if selected is not None:
            environment['UPLOAD_FILES'] = json.dumps(selected)
        return subprocess.run([sys.executable, '-I', '-c', inline_python(name)[0]],
                              cwd=directory, env=environment, capture_output=True, timeout=15)

    def test_both_publish_guards_copy_only_the_verified_missing_file(self):
        for name in ('publish.yml', 'testpypi.yml'):
            with self.subTest(workflow=name), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                files, digest = artifact_fixture(directory)
                wheel = f'myfap-{VERSION}-py3-none-any.whl'
                result = self.run_guard(name, directory, digest, [wheel])
                self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', errors='replace'))
                self.assertEqual([p.name for p in (directory / 'upload').iterdir()], [wheel])
                self.assertEqual((directory / 'upload' / wheel).read_bytes(), files[wheel])

    def test_both_guards_reject_wrong_digest_tampering_and_unexpected_inventory(self):
        for name in ('publish.yml', 'testpypi.yml'):
            for damage in ('manifest', 'bytes', 'extra', 'directory', 'version'):
                with self.subTest(workflow=name, damage=damage), tempfile.TemporaryDirectory() as temporary:
                    directory = Path(temporary)
                    _, digest = artifact_fixture(directory)
                    if damage == 'manifest':
                        digest = '0' * 64
                    elif damage == 'bytes':
                        (directory / 'dist' / f'myfap-{VERSION}.tar.gz').write_bytes(b'tampered')
                    elif damage == 'extra':
                        (directory / 'dist' / 'credential.txt').write_bytes(b'synthetic')
                    elif damage == 'directory':
                        (directory / 'dist' / 'nested').mkdir()
                    result = self.run_guard(name, directory, digest,
                                            [f'myfap-{VERSION}.tar.gz'],
                                            version='00.2.0' if damage == 'version' else VERSION)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse((directory / 'upload').exists())

    def test_both_guards_reject_empty_duplicate_or_unsafe_upload_subsets(self):
        wheel = f'myfap-{VERSION}-py3-none-any.whl'
        for name in ('publish.yml', 'testpypi.yml'):
            for selected in ([], [wheel, wheel], ['../escape.whl'], ['SHA256SUMS'], {'file': wheel}, [False]):
                with self.subTest(workflow=name, selected=selected), tempfile.TemporaryDirectory() as temporary:
                    directory = Path(temporary)
                    _, digest = artifact_fixture(directory)
                    result = self.run_guard(name, directory, digest, selected)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse((directory / 'upload').exists())

    def test_release_can_verify_without_preparing_an_upload(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            _, digest = artifact_fixture(directory)
            result = self.run_guard('publish.yml', directory, digest)
            self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', errors='replace'))
            self.assertFalse((directory / 'upload').exists())


class InlineReconcileTests(unittest.TestCase):
    def fixture(self, directory):
        files, digest = artifact_fixture(directory)
        (directory / 'upload').mkdir()
        for name, data in files.items():
            if name != 'SHA256SUMS':
                (directory / 'upload' / name).write_bytes(data)
        return files, digest

    def execute(self, name, directory, digest, remote):
        scripts = [script for script in inline_python(name) if 'urlopen' in script]
        self.assertEqual(len(scripts), 1, 'Publish must reconcile fresh index state before upload')
        environment = {
            'VERSION': VERSION, 'MANIFEST_SHA256': digest,
            'INDEX_URL': 'https://test.pypi.org/pypi' if name == 'testpypi.yml' else 'https://pypi.org/pypi',
            'GITHUB_OUTPUT': str(directory / 'github-output.txt'),
        }
        if isinstance(remote, BaseException):
            response = patch('urllib.request.urlopen', side_effect=remote)
        else:
            body = io.BytesIO(json.dumps(remote).encode('utf-8'))
            body.status = 200
            body.getcode = lambda: 200
            response = patch('urllib.request.urlopen', return_value=body)
        with current_directory(directory), patch.dict(os.environ, environment), response:
            exec(compile(scripts[0], '<publish reconcile>', 'exec'), {'__name__': '__main__'})
        return (directory / 'github-output.txt').read_text(encoding='utf-8')

    @staticmethod
    def remote_payload(files, names):
        return {'info': {'name': 'myfap', 'version': VERSION}, 'urls': [
            {'filename': name, 'digests': {'sha256': hashlib.sha256(files[name]).hexdigest()}, 'yanked': False}
            for name in names]}

    def test_retry_after_partial_server_acceptance_uploads_only_still_missing_file(self):
        wheel = f'myfap-{VERSION}-py3-none-any.whl'
        sdist = f'myfap-{VERSION}.tar.gz'
        for name in ('publish.yml', 'testpypi.yml'):
            with self.subTest(workflow=name), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                files, digest = self.fixture(directory)
                output = self.execute(name, directory, digest, self.remote_payload(files, [wheel]))
                self.assertEqual([p.name for p in (directory / 'upload').iterdir()], [sdist])
                self.assertIn('publish_required=true', output)

    def test_retry_after_complete_server_acceptance_skips_the_publish_action(self):
        for name in ('publish.yml', 'testpypi.yml'):
            with self.subTest(workflow=name), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                files, digest = self.fixture(directory)
                output = self.execute(name, directory, digest, self.remote_payload(
                    files, [entry for entry in files if entry != 'SHA256SUMS']))
                self.assertEqual(list((directory / 'upload').iterdir()), [])
                self.assertIn('publish_required=false', output)
                self.assertRegex(job_blocks(name)['publish'],
                                 r"if:.*steps\.reconcile\.outputs\.publish_required == 'true'")

    def test_missing_version_keeps_both_files_for_upload(self):
        for name in ('publish.yml', 'testpypi.yml'):
            with self.subTest(workflow=name), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                files, digest = self.fixture(directory)
                missing = HTTPError('https://example.invalid/index', 404, 'Not Found', {}, None)
                output = self.execute(name, directory, digest, missing)
                self.assertEqual({p.name for p in (directory / 'upload').iterdir()}, set(files) - {'SHA256SUMS'})
                self.assertIn('publish_required=true', output)

    def test_remote_lost_file_not_in_original_upload_subset_requires_new_preflight(self):
        for name in ('publish.yml', 'testpypi.yml'):
            with self.subTest(workflow=name), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                files, digest = self.fixture(directory)
                wheel = f'myfap-{VERSION}-py3-none-any.whl'
                (directory / 'upload' / wheel).unlink()
                with self.assertRaises(SystemExit):
                    self.execute(name, directory, digest, self.remote_payload(files, []))
                self.assertEqual([p.name for p in (directory / 'upload').iterdir()], [f'myfap-{VERSION}.tar.gz'])

    def test_network_failure_does_not_become_permission_to_upload(self):
        for name in ('publish.yml', 'testpypi.yml'):
            with self.subTest(workflow=name), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                files, digest = self.fixture(directory)
                unavailable = HTTPError('https://example.invalid/index', 503, 'Unavailable', {}, None)
                with self.assertRaises(SystemExit):
                    self.execute(name, directory, digest, unavailable)
                self.assertEqual({p.name for p in (directory / 'upload').iterdir()}, set(files) - {'SHA256SUMS'})

    def test_reconcile_rejects_changed_local_bytes_before_contacting_index(self):
        for name in ('publish.yml', 'testpypi.yml'):
            for target in ('dist', 'upload'):
                with self.subTest(workflow=name, target=target), tempfile.TemporaryDirectory() as temporary:
                    directory = Path(temporary)
                    _, digest = self.fixture(directory)
                    (directory / target / f'myfap-{VERSION}.tar.gz').write_bytes(b'tampered')
                    with self.assertRaises(SystemExit):
                        self.execute(name, directory, digest, AssertionError('Index must not be contacted'))

    def test_remote_conflict_stops_before_removing_prepared_files(self):
        wheel = f'myfap-{VERSION}-py3-none-any.whl'
        for name in ('publish.yml', 'testpypi.yml'):
            for damage in ('hash', 'unexpected', 'duplicate', 'yanked'):
                with self.subTest(workflow=name, damage=damage), tempfile.TemporaryDirectory() as temporary:
                    directory = Path(temporary)
                    files, digest = self.fixture(directory)
                    payload = self.remote_payload(files, [wheel])
                    if damage == 'hash':
                        payload['urls'][0]['digests']['sha256'] = '0' * 64
                    elif damage == 'unexpected':
                        payload['urls'][0]['filename'] = 'foreign.whl'
                    elif damage == 'duplicate':
                        payload['urls'].append(payload['urls'][0].copy())
                    else:
                        payload['urls'][0]['yanked'] = True
                    with self.assertRaises(SystemExit):
                        self.execute(name, directory, digest, payload)
                    self.assertEqual({p.name for p in (directory / 'upload').iterdir()}, set(files) - {'SHA256SUMS'})


class InlineReleaseTests(unittest.TestCase):
    def fixture(self, directory, **kwargs):
        files, _ = artifact_fixture(directory)
        (directory / 'notes').mkdir()
        with (directory / 'notes' / 'release-notes.md').open('w', encoding='utf-8', newline='') as notes:
            notes.write(NOTES)
        return FakeGitHub(files, **kwargs)

    def execute(self, directory, github, notes_digest=None):
        environment = {
            'GH_REPO': REPOSITORY, 'TAG': TAG, 'SHA': SHA,
            'NOTES_SHA256': notes_digest or hashlib.sha256(NOTES.encode('utf-8')).hexdigest(),
            'GITHUB_STEP_SUMMARY': str(directory / 'summary.md'),
        }
        script = inline_python('publish.yml')[-1]
        with current_directory(directory), patch.dict(os.environ, environment), patch(
                'subprocess.run', side_effect=github.run):
            exec(compile(script, '<release workflow>', 'exec'), {'__name__': '__main__'})

    def test_missing_release_is_drafted_uploaded_verified_then_published(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            github = self.fixture(directory)
            self.execute(directory, github)
            commands = [args[1] for args in github.mutations]
            self.assertEqual(commands, ['create', 'upload', 'upload', 'upload', 'edit'])
            self.assertEqual(github.assets, github.files)
            self.assertFalse(github.release['draft'])
            self.assertIn(TAG, (directory / 'summary.md').read_text(encoding='utf-8'))

    def test_matching_published_release_is_a_read_only_rerun(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            github = self.fixture(directory, existing=True)
            github.assets = github.files.copy()
            github.annotated = True
            self.execute(directory, github)
            self.assertEqual(github.mutations, [])

    def test_partial_draft_uploads_only_missing_assets_then_publishes(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            wheel = f'myfap-{VERSION}-py3-none-any.whl'
            github = self.fixture(directory, existing=True, draft=True, assets=[wheel])
            self.execute(directory, github)
            uploads = [Path(args[3]).name for args in github.mutations if args[1] == 'upload']
            self.assertEqual(set(uploads), {'SHA256SUMS', f'myfap-{VERSION}.tar.gz'})
            self.assertEqual(github.assets[wheel], github.files[wheel])
            self.assertFalse(github.release['draft'])

    def test_draft_hidden_from_tag_lookup_is_resumed_from_authorized_release_list(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            github = self.fixture(directory, existing=True, draft=True, assets=['SHA256SUMS'])
            self.execute(directory, github)
            self.assertNotIn('create', [args[1] for args in github.mutations])
            self.assertIn('releases?per_page=100', github.release_api_calls)
            self.assertNotIn(f'releases/tags/{TAG}', github.release_api_calls)
            self.assertFalse(github.release['draft'])
            self.assertEqual(github.assets, github.files)

    def test_existing_release_on_a_later_page_is_not_recreated(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            github = self.fixture(directory, existing=True, draft=True, assets=['SHA256SUMS'])
            github.additional_releases = [dict(github.release, id=1000 + index, tag_name=f'v1.0.{index}')
                                          for index in range(100)]
            self.execute(directory, github)
            self.assertNotIn('create', [args[1] for args in github.mutations])
            self.assertEqual(github.assets, github.files)
            self.assertFalse(github.release['draft'])

    def test_duplicate_matching_release_tags_are_rejected_before_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            github = self.fixture(directory, existing=True, draft=True)
            other = github.release.copy()
            other['id'] = 43
            github.additional_releases = [other]
            with self.assertRaises(SystemExit):
                self.execute(directory, github)
            self.assertEqual(github.mutations, [])

    def test_conflicting_tag_notes_or_existing_asset_prevents_every_mutation(self):
        for damage in ('tag', 'notes-file', 'notes-body', 'asset', 'unexpected', 'prerelease'):
            with self.subTest(damage=damage), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                github = self.fixture(directory, existing=True, draft=True)
                if damage == 'tag':
                    github.tag_sha = 'c' * 40
                elif damage == 'notes-file':
                    (directory / 'notes' / 'release-notes.md').write_bytes(b'tampered')
                elif damage == 'notes-body':
                    github.release['body'] = 'Different notes'
                elif damage == 'asset':
                    github.assets['SHA256SUMS'] = b'not the trusted manifest'
                elif damage == 'unexpected':
                    github.assets['unrelated.txt'] = b'extra'
                elif damage == 'prerelease':
                    github.release['prerelease'] = True
                with self.assertRaises(SystemExit):
                    self.execute(directory, github)
                self.assertEqual(github.mutations, [])

    def test_corrupt_upload_is_never_published(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            github = self.fixture(directory)
            github.corrupt_upload = True
            with self.assertRaises(SystemExit):
                self.execute(directory, github)
            self.assertTrue(github.release['draft'])
            self.assertNotIn('edit', [args[1] for args in github.mutations])


if __name__ == '__main__':
    unittest.main()
