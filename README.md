Jam build system on Python
--------------------------

This is reimplementation of Jam build system
([link](https://swarm.workshop.perforce.com/projects/perforce_software-jam))
on Python.

Supported platforms: Linux (Unix), OpenVMS, Windows (WIP)

What is Jam
------------

Jam is a build system (like meson, cmake etc). The difference is that its core is
basically only an interpreter for its internal language and all the building part
written on this language.

The raw Jam language doesn't know how to build anything, but it allows to define rules
and dependencies which will allow construct the actual command sequence to build
something with a help of the dependency tree.

Jam includes `Jambase` which is a collection of generic rules to build C, C++ and
Fortran projects. But it can be easily extended (or modified)
to building other types of projects.

Differences from original Jam
-----------------------------

* Uses `ninja`, `samurai` or other `ninja` compatible builder for
    the actual executables building.
* `mkdir` is a builtin command, collects all created dirs to `dirs` target.
* Builtin rules are case-insensitive (Echo and ECHO are same).
* Regular expressions are Python based.
* `Clean` actions are ignored in favour of `ninja -t clean`.

Quick start
-----------

Install:

    # install jamp
    pip3 install git+https://github.com/ildus/jamp

    # install ninja using your package manager
    dnf install ninja
    # or pacman -Syu ninja
    # etc

For example we have this directory structure with a library and a main executable, and the
main executable uses math functions:

    src
        main.c
    lib
        print.c
    include
        common.h

    Jamfile

Corresponding Jamfile:

    HDRS = include ;
    Library libprint : lib/print.c ;
    Main app : src/main.c ;
    LinkLibraries app : libprint ;
    LINKLIBS on app = -lm ;

So to get the executable we only need to run this commands:

    jamp && ninja

Look at the tests dir to see more complex usage examples.

Contribution
-----------

    git clone git@github.com:ildus/jamp.git

    # to run it without installing
    export PYTHONPATH=$PYTHONPATH:<current_dir>/jamp/src
    python3 -m jamp

    # testing the changes
    pip install pytest
    cd <jamp root folder>
    pytest

Documentation
-------------

See the `docs` directory.

OpenVMS notes
---------------

Use my `github.com/ildus/samurai` fork for compilation. It supports additional '$^' escape
sequence for newlines to allow adding full scripts to `build.ninja`.
