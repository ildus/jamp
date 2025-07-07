import subprocess as sp
import os
import tempfile
import shutil
import atexit

from contextlib import contextmanager
from jamp.build import main_cli


@contextmanager
def rel(path):
    curdir = os.getcwd()
    os.chdir(path)
    try:
        yield curdir
    finally:
        os.chdir(curdir)


def test_simple():
    d = "tests/test_simple"
    with rel(d):
        main_cli(skip_args=True)
        sp.run(["ninja", "-t", "clean"])
        output = sp.check_output("ninja")
        print(output)
        assert b"Two test.c" in output
        assert os.path.exists("test.c")
        output = sp.check_output("ninja")
        assert b"ninja: no work to do." in output
        output = sp.check_output(["ninja", "-t", "clean"])
        assert b"Cleaning... 1 files." in output


def test_subgen():
    d = "tests/test_subgen"
    with rel(d):
        os.environ["TOP"] = "."
        main_cli(skip_args=True)
        sp.run(["ninja", "-t", "clean"])
        output = sp.check_output("ninja")
        assert os.path.exists("app")
        output = sp.check_output("ninja")
        assert b"ninja: no work to do." in output


def test_dirs():
    d = "tests/test_dirs"
    with rel(d):
        main_cli(skip_args=True)
        sp.run(["ninja", "-t", "clean"])
        sp.check_output("ninja")
        assert os.path.exists("sub1/two.c")
        assert os.path.exists("sub2/three.c")
        sp.run(["ninja", "-t", "clean"])
        assert not os.path.exists("sub1/two.c")
        assert not os.path.exists("sub2/three.c")
        assert os.path.exists("sub1")


def test_copy_files():
    d = "tests/test_copy_files"
    with rel(d):
        main_cli(skip_args=True)
        sp.run(["ninja", "-t", "clean"])
        sp.check_output("ninja")
        assert os.path.exists("foo.so")
        sp.run(["ninja", "-t", "clean"])
        assert not os.path.exists("foo.so")


def test_multiline():
    d = "tests/test_multiline"
    with rel(d):
        main_cli(skip_args=True)
        sp.run(["ninja", "-t", "clean"])
        sp.check_output("ninja")
        assert os.path.exists("out.txt")
        sp.run(["ninja", "-t", "clean"])
        assert not os.path.exists("out.txt")


def test_simple_app():
    d = "tests/test_simple_app"
    with rel(d):
        main_cli(skip_args=True)
        sp.run(["ninja", "-t", "clean"])
        sp.check_output("ninja")
        assert os.path.exists("app")
        assert os.path.exists("libprint.a")
        assert os.path.exists("libsay.a")
        sp.run(["ninja", "-t", "clean"])
        assert not os.path.exists("app")


def test_math_example():
    d = "tests/test_math_example"
    with rel(d):
        main_cli(skip_args=True)
        sp.run(["ninja", "-t", "clean"])
        sp.check_output("ninja")
        assert os.path.exists("app")
        assert os.path.exists("libprint.a")
        sp.run(["ninja", "-t", "clean"])
        assert not os.path.exists("app")
        assert not os.path.exists("libprint.a")


def test_circular_inc():
    d = "tests/test_circular_inc"
    with rel(d):
        main_cli(skip_args=True)
        sp.run(["ninja", "-t", "clean"])
        sp.check_output("ninja")
        assert os.path.exists("app")
        sp.run(["ninja", "-t", "clean"])
        assert not os.path.exists("app")


def test_jam_compat():
    try:
        sp.check_output(["jam", "-v"])
    except:
        return

    files = ("tests/data/jam1.jam",)
    outputs = (
        b"""[1/1] One1 a.txt
a.txt b.txt
a.txt b.txt
a.txt b.txt
b.txt a.txt
""",
    )

    for i, f in enumerate(files):
        tdir = tempfile.mkdtemp(prefix="jamp")
        atexit.register(lambda: shutil.rmtree(tdir, ignore_errors=True))

        with rel(tdir) as old:
            out = os.path.join(tdir, "Jamfile")
            with open(os.path.join(old, f)) as fin:
                content = fin.read()
                with open(out, "w") as fout:
                    fout.write(content)

            main_cli(skip_args=True)
            ninja_output = sp.check_output("ninja")
            assert ninja_output == outputs[i]

            failed = False
            try:
                out = sp.check_output(["jam"])
            except:
                failed = True

            assert not failed, out
