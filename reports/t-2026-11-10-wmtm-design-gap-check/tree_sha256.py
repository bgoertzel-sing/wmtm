"""Same tree hash as tests/test_design_s12_engine.py::tree_sha256, for checking a vendored tree against a
fresh extract of the upstream codeload tarball.

  python tree_sha256.py DIR [DIR ...]
  python tree_sha256.py --tgz FILE.tgz      # extracts to a temp dir, hashes the single top-level directory
"""
import hashlib, os, sys, tarfile, tempfile

_SKIP_DIRS = {"__pycache__", ".pytest_cache", ".git"}


def tree_sha256(root):
    h = hashlib.sha256()
    for d, dirs, files in os.walk(root):
        dirs[:] = sorted(x for x in dirs if x not in _SKIP_DIRS)
        for fn in sorted(files):
            if fn.endswith(".pyc"):
                continue
            p = os.path.join(d, fn)
            if os.path.islink(p):
                data = ("link:" + os.readlink(p)).encode()
            else:
                with open(p, "rb") as f:
                    data = f.read()
            h.update(("%s\0%s\n" % (os.path.relpath(p, root), hashlib.sha256(data).hexdigest())).encode())
    return h.hexdigest()


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["--tgz"]:
        for t in args[1:]:
            with tempfile.TemporaryDirectory() as td:
                with tarfile.open(t) as tf:
                    tf.extractall(td)
                (top,) = os.listdir(td)
                print(tree_sha256(os.path.join(td, top)), t, top)
    else:
        for a in args:
            print(tree_sha256(a), a)
