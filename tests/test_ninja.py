import subprocess as sp
import os
from contextlib import contextmanager
from jamp.build import main_cli


@contextmanager
def rel(path):
    curdir = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(curdir)


def test_simple():
    d = "tests/test_simple"
    with rel(d):
        main_cli()
        sp.run(["ninja", "-t", "clean"])
        output = sp.check_output("ninja")
        assert b"cp test.h test.c" in output
        assert os.path.exists("test.c")
        output = sp.check_output("ninja")
        assert b"ninja: no work to do." in output
        output = sp.check_output(["ninja", "-t", "clean"])
        assert b"Cleaning... 1 files." in output


def test_subdir():
    d = "tests/test_subgen"
    with rel(d):
        os.environ["TOP"] = "."
        main_cli()
        sp.run(["ninja", "-t", "clean"])
        output = sp.check_output("ninja")
        assert os.path.exists("app")
        output = sp.check_output("ninja")
        assert b"ninja: no work to do." in output


def test_dirs():
    d = "tests/test_dirs"
    with rel(d):
        main_cli()
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
        main_cli()
        sp.run(["ninja", "-t", "clean"])
        sp.check_output("ninja")
        assert os.path.exists("foo.so")
        sp.run(["ninja", "-t", "clean"])
        assert not os.path.exists("foo.so")


def test_multiline():
    d = "tests/test_multiline"
    with rel(d):
        main_cli()
        sp.run(["ninja", "-t", "clean"])
        sp.check_output("ninja")
        assert os.path.exists("out.txt")
        sp.run(["ninja", "-t", "clean"])
        assert not os.path.exists("out.txt")
