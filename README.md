Jam build system on Python
--------------------------

This is a Python reimplementation of the Jam build system
([link](https://swarm.workshop.perforce.com/projects/perforce_software-jam)).

Supported platforms: Linux (Unix), OpenVMS, Windows (WIP), MacOS (WIP)

What is Jam
------------

Jam is a build system (similar to meson, cmake, etc.). The key difference is that its core is
essentially an interpreter for its internal language, with all building functionality
written in this language.

The raw Jam language doesn't know how to build anything by itself, but it allows you to define rules
and dependencies which construct the actual command sequence to build
projects using a dependency tree.

Jam includes `Jambase`, which is a collection of generic rules to build C, C++ and
Fortran projects. It can be easily extended (or modified)
to support other types of projects.

Differences from the original Jam
-----------------------------

* Uses `ninja`, `samurai` or other `ninja`-compatible builders for
    the actual building of executables.
* `mkdir` is a built-in command that collects all created directories to the `dirs` target.
* Built-in rules are case-insensitive (`Echo` and `ECHO` are the same).
* Regular expressions are Python-based.
* `Clean` actions are ignored in favor of `ninja -t clean`.

Quick Start
-----------

Install:

    # Install jamp with the system pip
    pip3 install jam-build

    # Or from the latest main branch.
    pip3 install git+https://github.com/ildus/jamp

    # Using pypy3 provides approximately twice the performance
    # pypy3 -m pip install jam-build

    # Install ninja using your package manager
    dnf install ninja
    # or pacman -Syu ninja
    # etc.

Example project structure with a library and a main executable that uses math functions:

    src
        main.c
    lib
        print.c
    include
        common.h

    Jamfile

Corresponding Jamfile:

    HDRS = include ;                    # common includes, affects all sources
    Library libprint : lib/print.c ;    # on Unix this will create libprint.a
    Main app : src/main.c ;             # executable
    LinkLibraries app : libprint ;      # linking the executable with our library
    LINKLIBS on app = -lm ;             # system libraries

To build the executable, simply run:

    jamp && ninja

For more complex examples, look at the `tests` directory. When dealing with subdirectories,
it's recommended to use the `SubDir` rule. Note that this example should work on Windows
and Linux (because of explicit paths), but will not work on VMS.

Contributing
-----------

    git clone git@github.com:ildus/jamp.git

    # To run without installing
    export PYTHONPATH=$PYTHONPATH:<current_dir>/jamp/src
    python3 -m jamp

    # Testing changes
    pip install pytest
    cd <jamp root folder>
    pytest

Documentation
-------------

See the `docs` directory.

OpenVMS Notes
---------------

Use my `github.com/ildus/samurai` fork for compilation. It supports the additional '$^' escape
sequence for newlines, allowing you to add full scripts to `build.ninja`.
