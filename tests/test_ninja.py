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
